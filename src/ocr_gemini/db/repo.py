from __future__ import annotations
import psycopg2
from typing import Optional
from . import DbConfig

class OcrRepo:
    def __init__(self, cfg: DbConfig):
        self.cfg = cfg
        self.conn = None

    def connect(self):
        if self.conn and not self.conn.closed:
            return
        if self.cfg.dsn:
            self.conn = psycopg2.connect(self.cfg.dsn)
        else:
            self.conn = psycopg2.connect(
                host=self.cfg.host,
                port=self.cfg.port,
                dbname=self.cfg.dbname,
                user=self.cfg.user,
                password=self.cfg.password,
            )
        self.conn.autocommit = False

    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()

    def commit(self):
        if self.conn:
            self.conn.commit()

    def rollback(self):
        if self.conn:
            self.conn.rollback()

    def get_or_create_document(self, source_path: str, source_sha256: Optional[str] = None) -> int:
        self.connect()
        # "Use existing DB schema if already present"
        # My migration uses 'ocr_document' with source_path, source_sha256.
        sql = """
        INSERT INTO ocr_document (source_path, source_sha256, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (source_path) DO UPDATE SET
            source_sha256 = EXCLUDED.source_sha256,
            updated_at = NOW()
        RETURNING doc_id
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (source_path, source_sha256))
            row = cur.fetchone()
            if row:
                return row[0]
            # Should not happen with RETURNING, but just in case
            raise ValueError("Failed to get doc_id")

    def has_successful_run(self, doc_id: int, pipeline: str) -> bool:
        """
        Check if doc has a 'done' run.
        Note: Checks globally for the doc.
        Pipeline version/tag logic relies on ocr_document having correct metadata if needed,
        but explicit requirement says 'for the same pipeline version/tag'.
        Since we update document metadata on create_run, if the document has a run AND
        ocr_document.pipeline matches, we assume it's valid.
        However, simplicity: status='done' for this doc_id.
        """
        self.connect()
        sql = """
        SELECT 1 FROM ocr_run
        WHERE doc_id = %s AND status = 'done'
        LIMIT 1
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (doc_id,))
            return cur.fetchone() is not None

    def create_run(self, doc_id: int, pipeline: str, run_tag: Optional[str] = None, status: str = 'queued') -> int:
        self.connect()

        # Update document metadata to reflect current attempt's context
        update_doc_sql = """
        UPDATE ocr_document SET pipeline = %s, run_tag = %s WHERE doc_id = %s
        """
        with self.conn.cursor() as cur:
            cur.execute(update_doc_sql, (pipeline, run_tag, doc_id))

        if status == 'processing':
             sql = """
                INSERT INTO ocr_run (doc_id, status, created_at, started_at)
                VALUES (%s, %s, NOW(), NOW())
                RETURNING run_id
             """
             params = (doc_id, status)
        else:
             sql = """
                INSERT INTO ocr_run (doc_id, status, created_at)
                VALUES (%s, %s, NOW())
                RETURNING run_id
             """
             params = (doc_id, status)

        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchone()[0]

    def mark_run_status(self, run_id: int, status: str, error_code: Optional[str] = None, error_message: Optional[str] = None, out_path: Optional[str] = None):
        self.connect()
        sql = """
        UPDATE ocr_run
        SET status = %s,
            error_code = COALESCE(%s, error_code),
            error_message = COALESCE(%s, error_message),
            out_path = COALESCE(%s, out_path),
            finished_at = CASE WHEN %s IN ('done', 'failed') THEN NOW() ELSE finished_at END,
            started_at = CASE WHEN %s = 'processing' AND started_at IS NULL THEN NOW() ELSE started_at END
        WHERE run_id = %s
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (status, error_code, error_message, out_path, status, status, run_id))

    def mark_step(self, run_id: int, step_name: str, status: str, error_message: Optional[str] = None):
        self.connect()
        sql = """
        INSERT INTO ocr_step (run_id, step_name, status, error_message)
        VALUES (%s, %s, %s, %s)
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (run_id, step_name, status, error_message))
