from __future__ import annotations
import psycopg2
from typing import Optional, Dict, Any, Tuple
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
            raise ValueError("Failed to get doc_id")

    def has_successful_run(self, doc_id: int, pipeline: str) -> bool:
        self.connect()
        # Check if done, and ensure it belongs to the same pipeline if needed?
        # Actually, if a doc is done by ANY pipeline, usually we treat it as done?
        # But for strict consistency, maybe we should check pipeline.
        # But 'has_successful_run' is mostly for 'skip if done'.
        # If I processed it with v1, and now running v2, maybe I want to re-process?
        # The prompt says "attempt_no ... per document+pipeline".
        # This implies runs are scoped to pipeline.
        # So if I have a done run for pipeline A, and I run pipeline B, it's not done for B.

        # Check if ocr_document.pipeline matches AND we have a done run?
        # No, ocr_document.pipeline is just the LAST pipeline.
        # We need to know if there is a done run for THIS pipeline.
        # Since ocr_run doesn't store pipeline, we can only infer it from ocr_document
        # if ocr_document.pipeline == pipeline.

        # So: if ocr_document.pipeline == pipeline AND exists(ocr_run where status='done')

        sql = """
        SELECT 1
        FROM ocr_run r
        JOIN ocr_document d ON r.doc_id = d.doc_id
        WHERE d.doc_id = %s AND r.status = 'done' AND d.pipeline = %s
        LIMIT 1
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (doc_id, pipeline))
            return cur.fetchone() is not None

    def get_latest_run(self, doc_id: int, pipeline: str) -> Optional[Dict[str, Any]]:
        self.connect()

        # Ensure we are looking at the history of the requested pipeline.
        # Since ocr_run doesn't have pipeline_id, we check ocr_document.pipeline.
        # If the document's last associated pipeline is different, we consider this a fresh start for the new pipeline.
        check_sql = "SELECT pipeline FROM ocr_document WHERE doc_id = %s"
        with self.conn.cursor() as cur:
            cur.execute(check_sql, (doc_id,))
            row = cur.fetchone()
            if row and row[0] != pipeline:
                 return None

        # Fetch the most recent run for this document
        sql = """
        SELECT run_id, status, attempt_no, error_kind
        FROM ocr_run
        WHERE doc_id = %s
        ORDER BY run_id DESC
        LIMIT 1
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (doc_id,))
            row = cur.fetchone()
            if row:
                return {
                    "run_id": row[0],
                    "status": row[1],
                    "attempt_no": row[2] or 1,
                    "error_kind": row[3]
                }
            return None

    def create_run(self, doc_id: int, pipeline: str, run_tag: Optional[str] = None, status: str = 'queued',
                   attempt_no: int = 1, parent_run_id: Optional[int] = None) -> int:
        self.connect()

        update_doc_sql = """
        UPDATE ocr_document SET pipeline = %s, run_tag = %s WHERE doc_id = %s
        """
        with self.conn.cursor() as cur:
            cur.execute(update_doc_sql, (pipeline, run_tag, doc_id))

        if status == 'processing':
             sql = """
                INSERT INTO ocr_run (doc_id, status, attempt_no, parent_run_id, created_at, started_at)
                VALUES (%s, %s, %s, %s, NOW(), NOW())
                RETURNING run_id
             """
        else:
             sql = """
                INSERT INTO ocr_run (doc_id, status, attempt_no, parent_run_id, created_at)
                VALUES (%s, %s, %s, %s, NOW())
                RETURNING run_id
             """

        with self.conn.cursor() as cur:
            cur.execute(sql, (doc_id, status, attempt_no, parent_run_id))
            return cur.fetchone()[0]

    def mark_run_status(self, run_id: int, status: str, error_code: Optional[str] = None,
                        error_message: Optional[str] = None, out_path: Optional[str] = None,
                        error_kind: Optional[str] = None, retry_after_seconds: Optional[int] = None):
        self.connect()
        sql = """
        UPDATE ocr_run
        SET status = %s,
            error_code = COALESCE(%s, error_code),
            error_message = COALESCE(%s, error_message),
            out_path = COALESCE(%s, out_path),
            error_kind = COALESCE(%s, error_kind),
            retry_after_seconds = COALESCE(%s, retry_after_seconds),
            finished_at = CASE WHEN %s IN ('done', 'failed') THEN NOW() ELSE finished_at END,
            started_at = CASE WHEN %s = 'processing' AND started_at IS NULL THEN NOW() ELSE started_at END
        WHERE run_id = %s
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (status, error_code, error_message, out_path, error_kind, retry_after_seconds, status, status, run_id))

    def mark_step(self, run_id: int, step_name: str, status: str, error_message: Optional[str] = None):
        self.connect()
        sql = """
        INSERT INTO ocr_step (run_id, step_name, status, error_message)
        VALUES (%s, %s, %s, %s)
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, (run_id, step_name, status, error_message))
