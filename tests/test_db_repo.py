import pytest
from unittest.mock import patch

from ocr_gemini.db.repo import OcrRepo
from ocr_gemini.db import DbConfig


@pytest.fixture
def mock_db_config():
    return DbConfig(host="localhost", port=5432, dbname="test", user="user", dsn="postgres://...")


@pytest.fixture
def mock_connect():
    # ✅ patch where it's USED (module under test), not global psycopg2
    with patch("ocr_gemini.db.repo.psycopg2.connect") as m:
        yield m


def test_repo_init(mock_db_config):
    repo = OcrRepo(mock_db_config)
    assert repo.cfg == mock_db_config


def test_get_or_create_document(mock_db_config, mock_connect):
    repo = OcrRepo(mock_db_config)

    mock_conn = mock_connect.return_value
    mock_cursor = mock_conn.cursor.return_value
    mock_cursor.__enter__.return_value = mock_cursor
    mock_cursor.fetchone.return_value = [123]

    doc_id = repo.get_or_create_document("/tmp/foo.jpg", "abc")

    assert doc_id == 123
    mock_cursor.execute.assert_called_once()
    assert "INSERT INTO ocr_document" in mock_cursor.execute.call_args[0][0]


def test_has_successful_run(mock_db_config, mock_connect):
    repo = OcrRepo(mock_db_config)
    mock_cursor = mock_connect.return_value.cursor.return_value.__enter__.return_value

    mock_cursor.fetchone.return_value = [1]
    assert repo.has_successful_run(1, "pipe") is True

    mock_cursor.fetchone.return_value = None
    assert repo.has_successful_run(1, "pipe") is False


def test_create_run(mock_db_config, mock_connect):
    repo = OcrRepo(mock_db_config)
    mock_cursor = mock_connect.return_value.cursor.return_value.__enter__.return_value
    mock_cursor.fetchone.return_value = [999]

    run_id = repo.create_run(1, "pipe", status="queued")
    assert run_id == 999

    # check calls: update doc, insert run
    assert mock_cursor.execute.call_count == 2
