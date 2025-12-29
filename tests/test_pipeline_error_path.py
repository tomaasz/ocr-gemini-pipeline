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
        return len(self.documents)

    def upsert_entry(self, **kwargs):
        self.entries.append(kwargs)
        return len(self.entries)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def fake_iter_files(root: Path, recursive: bool, limit: int):
    return [
        SimpleNamespace(
            path=root / "a.jpg",
            rel_path=Path("a.jpg"),
            file_name="a.jpg",
        )
    ]


def fake_with_sha256(items):
    for it in items:
        it.sha256 = "deadbeef" * 8
        yield it


def test_pipeline_error_path_rolls_back_and_writes_error_meta(monkeypatch, tmp_path: Path):
    # --- monkeypatch: files ---
    monkeypatch.setattr("ocr_gemini.pipeline.iter_files", fake_iter_files)
    monkeypatch.setattr("ocr_gemini.pipeline.with_sha256", fake_with_sha256)

    # --- fake DB ---
    fake_db = FakeDbWriter()

    # --- write_outputs: 1. call -> wyjątek, 2. call (error meta) -> OK ---
    calls = []

    def flaky_write_outputs(**kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            raise RuntimeError("disk full (simulated)")
        base_dir = kwargs["out_root"] / kwargs["rel_path"]
        return SimpleNamespace(
            base_dir=base_dir,
            txt_path=base_dir / "result.txt",
            json_path=base_dir / "result.json",
            meta_path=base_dir / "meta.json",
        )

    monkeypatch.setattr("ocr_gemini.pipeline.write_outputs", flaky_write_outputs)

    cfg = PipelineConfig(
        ocr_root=tmp_path / "in",
        out_root=tmp_path / "out",
        prompt_id="test-prompt",
        recursive=False,
        limit=0,
        run_tag="err-test",
        pipeline_name="stage1-no-ui",
        processing_by="pytest",
    )

    p = Pipeline(cfg, db_writer=fake_db)

    # Pipeline w tej implementacji propaguje wyjątek dalej – to akceptujemy w teście.
    with pytest.raises(RuntimeError, match="disk full \\(simulated\\)"):
        p.run()

    # commit nie powinien się wydarzyć
    assert fake_db.commits == 0

    # rollback powinien zostać zawołany
    assert fake_db.rollbacks == 1

    # entry nie powinno powstać (bo do upsert_entry dochodzimy dopiero po write_outputs)
    assert len(fake_db.entries) == 0

    # write_outputs powinno być wywołane 2 razy:
    # 1) normalny zapis (wyjątek)
    # 2) zapis meta_err (best-effort)
    assert len(calls) == 2

    first = calls[0]
    second = calls[1]

    assert first["text"] is not None
    assert first["data_json"] is not None

    assert second["text"] is None
    assert second["data_json"] is None
    assert "meta" in second
    assert second["meta"].get("error") == "disk full (simulated)"
