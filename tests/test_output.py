import json
from pathlib import Path

from ocr_gemini.output import write_outputs


def _as_path(x) -> Path:
    if isinstance(x, Path):
        return x
    return Path(str(x))


def test_write_outputs_creates_expected_files(tmp_path: Path):
    out_root = tmp_path / "out"

    rel_path = Path("run1/doc1")
    file_name = "test.jpg"

    text = "OCR RESULT"
    data_json = {"text": "OCR RESULT", "engine": "placeholder"}
    meta = {"source_path": "/some/source.jpg", "doc_id": 1, "entry_id": 1}

    out_paths = write_outputs(
        out_root=out_root,
        rel_path=rel_path,
        file_name=file_name,
        text=text,
        data_json=data_json,
        meta=meta,
    )

    # OutputPaths jest kontraktem: z niego bierzemy realne ścieżki
    # (zakładamy, że ma pola wskazujące na pliki)
    candidates = {}
    for name in ("out_dir", "dir", "output_dir"):
        if hasattr(out_paths, name):
            candidates["out_dir"] = _as_path(getattr(out_paths, name))
            break

    for name in ("result_txt", "txt_path", "text_path"):
        if hasattr(out_paths, name):
            candidates["result_txt"] = _as_path(getattr(out_paths, name))
            break

    for name in ("result_json", "json_path", "data_json_path"):
        if hasattr(out_paths, name):
            candidates["result_json"] = _as_path(getattr(out_paths, name))
            break

    for name in ("meta_json", "meta_path", "meta_json_path"):
        if hasattr(out_paths, name):
            candidates["meta_json"] = _as_path(getattr(out_paths, name))
            break

    # Minimalne wymaganie: musimy dostać ścieżki do 3 plików
    assert "result_txt" in candidates, f"OutputPaths bez ścieżki do result.txt: {out_paths!r}"
    assert "result_json" in candidates, f"OutputPaths bez ścieżki do result.json: {out_paths!r}"
    assert "meta_json" in candidates, f"OutputPaths bez ścieżki do meta.json: {out_paths!r}"

    result_txt = candidates["result_txt"]
    result_json = candidates["result_json"]
    meta_json = candidates["meta_json"]

    # Pliki mają istnieć
    assert result_txt.exists(), f"Brak pliku: {result_txt}"
    assert result_json.exists(), f"Brak pliku: {result_json}"
    assert meta_json.exists(), f"Brak pliku: {meta_json}"

    # I mają mieć właściwą treść
    assert result_txt.read_text(encoding="utf-8") == text
    assert json.loads(result_json.read_text(encoding="utf-8")) == data_json
    assert json.loads(meta_json.read_text(encoding="utf-8")) == meta
