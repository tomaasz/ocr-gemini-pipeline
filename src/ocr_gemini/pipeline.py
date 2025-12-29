from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .db import MinimalDbWriter, db_config_from_env
from .files import DiscoveredFile, iter_files, with_sha256
from .metrics import DocumentMetrics
from .output import write_outputs
from .ui.engine import OcrEngine
from .ui.fake_engine import FakeEngine


@dataclass
class PipelineConfig:
    """
    Konfiguracja pipeline'u (bez UI).
    Źródło prawdy: env z /etc/default/gemini-ocr
    """

    ocr_root: Path
    out_root: Path
    prompt_id: str
    recursive: bool = False
    limit: int = 0
    run_tag: Optional[str] = None
    pipeline_name: str = "stage1-no-ui"
    processing_by: str = "ocr-gemini-pipeline"


def config_from_env() -> PipelineConfig:
    # Required
    root = Path(os.environ["OCR_ROOT"])
    out_root = Path(os.environ["OCR_OUT_ROOT"])
    prompt_id = os.environ["OCR_PROMPT_ID"]

    # Optional
    recursive = os.environ.get("OCR_RECURSIVE", "0") == "1"
    limit = int(os.environ.get("OCR_LIMIT", "0") or "0")
    run_tag = os.environ.get("OCR_RUN_TAG") or None

    host = socket.gethostname()
    processing_by = f"{os.environ.get('USER','user')}@{host}"

    return PipelineConfig(
        ocr_root=root,
        out_root=out_root,
        prompt_id=prompt_id,
        recursive=recursive,
        limit=limit,
        run_tag=run_tag,
        pipeline_name=os.environ.get("OCR_PIPELINE", "stage1-no-ui"),
        processing_by=processing_by,
    )


class Pipeline:
    """
    Stage 1.3+: Orkiestracja bez prawdziwego UI (UI/Playwright później).
    Zamiast placeholdera mamy silnik OCR (domyślnie FakeEngine).
    """

    def __init__(
        self,
        cfg: PipelineConfig,
        *,
        db_writer: Optional[MinimalDbWriter] = None,
        engine: Optional[OcrEngine] = None,
    ):
        self.cfg = cfg
        self.db = db_writer or MinimalDbWriter(db_config_from_env())
        self.engine = engine or FakeEngine()

    def run(self) -> int:
        items = with_sha256(
            iter_files(self.cfg.ocr_root, recursive=self.cfg.recursive, limit=self.cfg.limit)
        )

        processed = 0
        for item in items:
            processed += 1
            self._process_one(item, entry_no=1)

        return processed

    def _process_one(self, item: DiscoveredFile, *, entry_no: int) -> None:
        m = DocumentMetrics(file_name=item.file_name, start_ts=time.time())
        m.attempts = 1

        started_at = None
        finished_at = None

        try:
            # DB: document start
            doc_id = self.db.upsert_document(
                source_path=str(item.path),
                file_name=item.file_name,
                source_sha256=item.sha256,
                doc_type="unknown",
                confidence=None,
                issues=None,
                pipeline=self.cfg.pipeline_name,
                run_tag=self.cfg.run_tag,
                status="processing",
                processing_by=self.cfg.processing_by,
                processing_started_at=started_at,
                processing_finished_at=finished_at,
            )

            # OCR (engine; Stage 2/3: Playwright)
            res = self.engine.ocr(item.path, self.cfg.prompt_id)
            ocr_text = res.text
            ocr_json: Dict[str, Any] = dict(res.data)

            # Safety: block placeholder junk unless explicitly allowed
            if (
                os.environ.get("OCR_ALLOW_PLACEHOLDER", "0") != "1"
                and isinstance(ocr_text, str)
                and ocr_text.startswith("PLACEHOLDER")
            ):
                raise RuntimeError(
                    "Placeholder OCR blocked. Set OCR_ALLOW_PLACEHOLDER=1 if you really want placeholder outputs."
                )

            # Output meta
            meta: Dict[str, Any] = {
                "source_path": str(item.path),
                "rel_path": str(item.rel_path),
                "file_name": item.file_name,
                "sha256": item.sha256,
                "prompt_id": self.cfg.prompt_id,
                "run_tag": self.cfg.run_tag,
                "pipeline": self.cfg.pipeline_name,
                "processing_by": self.cfg.processing_by,
                "doc_id": doc_id,
                "entry_no": entry_no,
                "metrics": asdict(m),
            }

            # Write artifacts
            paths = write_outputs(
                out_root=self.cfg.out_root,
                rel_path=item.rel_path,
                file_name=item.file_name,
                text=ocr_text,
                data_json=ocr_json,
                meta=meta,
            )

            # DB: entry upsert
            entry_id = self.db.upsert_entry(
                doc_id=doc_id,
                entry_no=entry_no,
                entry_text=ocr_text,
                entry_json={
                    "ocr": ocr_json,
                    "outputs": {
                        "base_dir": str(paths.base_dir),
                        "txt_path": str(paths.txt_path),
                        "json_path": str(paths.json_path),
                        "meta_path": str(paths.meta_path),
                    },
                    "meta": meta,
                },
                entry_type=None,
                entry_date=None,
                location=None,
            )

            # DB: document done
            m.finish("success")
            doc_id2 = self.db.upsert_document(
                source_path=str(item.path),
                file_name=item.file_name,
                source_sha256=item.sha256,
                doc_type="unknown",
                confidence=None,
                issues=None,
                pipeline=self.cfg.pipeline_name,
                run_tag=self.cfg.run_tag,
                status="done",
                processing_by=self.cfg.processing_by,
                processing_started_at=started_at,
                processing_finished_at=finished_at,
            )

            self.db.commit()
            print(f"OK: {item.file_name} -> doc_id={doc_id2} entry_id={entry_id} out={paths.base_dir}")

        except Exception as e:
            try:
                self.db.rollback()
            except Exception:
                pass

            m.finish("error", error_reason=str(e))

            # best-effort error meta
            try:
                meta_err = {
                    "source_path": str(item.path),
                    "rel_path": str(item.rel_path),
                    "file_name": item.file_name,
                    "sha256": item.sha256,
                    "prompt_id": self.cfg.prompt_id,
                    "run_tag": self.cfg.run_tag,
                    "pipeline": self.cfg.pipeline_name,
                    "processing_by": self.cfg.processing_by,
                    "error": str(e),
                    "metrics": asdict(m),
                }
                write_outputs(
                    out_root=self.cfg.out_root,
                    rel_path=item.rel_path,
                    file_name=item.file_name,
                    text=None,
                    data_json=None,
                    meta=meta_err,
                )
            except Exception:
                pass

            raise


def run_from_env() -> int:
    cfg = config_from_env()
    p = Pipeline(cfg)
    return p.run()


if __name__ == "__main__":
    count = run_from_env()
    print(json.dumps({"processed": count}, ensure_ascii=False))
