from pathlib import Path
from types import SimpleNamespace

import pytest

from ocr_gemini.pipeline import Pipeline, PipelineConfig


class FakeDbWriter:
    def __init__(self):
        self.documents = []
        self.entries = []
        self.commits = 0
        self.rollbacks = 0

    def upsert_document(self, **kwargs):
        self.documents.append(kwargs)
        # udajemy doc_id
        return len(self.documents)

    def upsert_entry(self, **kwargs):
        self.entries.append(kwargs)
        # udajemy entry_id
        return len(self.entries)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def fake_iter_files(root: Path, recursive: bool, limit: int):
    # Zwracamy 2 „odkryte” pliki
    items = [
        SimpleNamespace(
            path=root / "a.jpg",
            rel_path=Path("a.jpg"),
            file_name="a.jpg",
        ),
        SimpleNamespace(
            path=root / "b.jpg",
            rel_path=Path("b.jpg"),
            file_name="b.jpg",
        ),
    ]
    return items[: limit or None]


def fake_with_sha256(items):
    # Doklejamy sha256
    for it in items:
        it.sha256 = "deadbeef" * 8
        yield it


def fake_write_outputs(**kwargs):
    # Zwracamy atrapy ścieżek
    base_dir = kwargs["out_root"] / kwargs["rel_path"]
    return SimpleNamespace(
        base_dir=base_dir,
        txt_path=base_dir / "result.txt",
        json_path=base_dir / "result.json",
        meta_path=base_dir / "meta.json",
    )


def test_pipeline_smoke(monkeypatch, tmp_path: Path):
    # --- monkeypatch: files ---
    monkeypatch.setattr("ocr_gemini.pipeline.iter_files", fake_iter_files)
    monkeypatch.setattr("ocr_gemini.pipeline.with_sha256", fake_with_sha256)

    # --- monkeypatch: output ---
    monkeypatch.setattr("ocr_gemini.pipeline.write_outputs", fake_write_outputs)

    # --- fake DB ---
    fake_db = FakeDbWriter()

    cfg = PipelineConfig(
        ocr_root=tmp_path / "in",
        out_root=tmp_path / "out",
        prompt_id="test-prompt",
        recursive=False,
        limit=0,
        run_tag="smoke-test",
        pipeline_name="stage1-no-ui",
        processing_by="pytest",
    )

    p = Pipeline(cfg, db_writer=fake_db)

    processed = p.run()

    # --- asercje ---
    assert processed == 2

    # dla każdego pliku:
    # - 2x upsert_document (processing + done)
    assert len(fake_db.documents) == 4

    # - 1x entry
    assert len(fake_db.entries) == 2

    # - commit po każdym pliku
    assert fake_db.commits == 2

    # - brak rollbacków
    assert fake_db.rollbacks == 0

    # sanity-check danych wpisu
    entry = fake_db.entries[0]
    assert entry["entry_text"].startswith("PLACEHOLDER")
    assert "outputs" in entry["entry_json"]
    assert entry["entry_json"]["ocr"]["stage"] == "1.3"
