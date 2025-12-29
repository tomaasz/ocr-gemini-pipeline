# db_writer.py
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import psycopg2
from psycopg2.extras import Json


@dataclass
class DbConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: Optional[str] = None
    schema: str = "genealogy"


def db_config_from_env() -> DbConfig:
    return DbConfig(
        host=os.environ.get("PGHOST", "127.0.0.1"),
        port=int(os.environ.get("PGPORT", "5432")),
        dbname=os.environ.get("PGDATABASE", "genealogy"),
        user=os.environ.get("PGUSER", "tomaasz"),
        password=os.environ.get("PGPASSWORD") or None,
        schema=os.environ.get("PGSCHEMA", "genealogy"),
    )


class MinimalDbWriter:
    """
    Minimalny zapis end-to-end:
      - genealogy.ocr_document: UPSERT po source_path -> doc_id
      - genealogy.ocr_entry: UPSERT po (doc_id, entry_no) -> entry_id
    """

    def __init__(self, cfg: DbConfig):
        self.cfg = cfg
        self.conn = None

    def connect(self):
        if self.conn and self.conn.closed == 0:
            return
        self.conn = psycopg2.connect(
            host=self.cfg.host,
            port=self.cfg.port,
            dbname=self.cfg.dbname,
            user=self.cfg.user,
            password=self.cfg.password,
        )
        self.conn.autocommit = False

    def close(self):
        if self.conn and self.conn.closed == 0:
            self.conn.close()

    def commit(self):
        if self.conn:
            self.conn.commit()

    def rollback(self):
        if self.conn:
            self.conn.rollback()

    def upsert_document(
        self,
        *,
        source_path: str,
        file_name: str,
        source_sha256: Optional[str] = None,
        doc_type: str = "unknown",
        confidence: Optional[float] = None,
        issues: Optional[str] = None,
        pipeline: str = "two-step",
        run_tag: Optional[str] = None,
        status: Optional[str] = None,
        processing_by: Optional[str] = None,
        processing_started_at=None,
        processing_finished_at=None,
    ) -> int:
        self.connect()
        s = self.cfg.schema

        sql = f"""
        INSERT INTO {s}.ocr_document
          (source_path, file_name, source_sha256, doc_type, confidence, issues, pipeline, run_tag,
           status, processing_by, processing_started_at, processing_finished_at, updated_at)
        VALUES
          (%s, %s, %s, %s, %s, %s, %s, %s,
           %s, %s, %s, %s, now())
        ON CONFLICT (source_path)
        DO UPDATE SET
          file_name              = EXCLUDED.file_name,
          source_sha256          = EXCLUDED.source_sha256,
          doc_type               = EXCLUDED.doc_type,
          confidence             = EXCLUDED.confidence,
          issues                 = EXCLUDED.issues,
          pipeline               = EXCLUDED.pipeline,
          run_tag                = EXCLUDED.run_tag,
          status                 = EXCLUDED.status,
          processing_by          = EXCLUDED.processing_by,
          processing_started_at  = EXCLUDED.processing_started_at,
          processing_finished_at = EXCLUDED.processing_finished_at,
          updated_at             = now()
        RETURNING doc_id
        """
        with self.conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    source_path,
                    file_name,
                    source_sha256,
                    doc_type,
                    confidence,
                    issues,
                    pipeline,
                    run_tag,
                    status,
                    processing_by,
                    processing_started_at,
                    processing_finished_at,
                ),
            )
            return int(cur.fetchone()[0])

    def upsert_entry(
        self,
        *,
        doc_id: int,
        entry_no: int,
        entry_text: Optional[str],
        entry_json: Dict[str, Any],
        entry_type: Optional[str] = None,
        entry_date=None,
        location: Optional[str] = None,
    ) -> int:
        self.connect()
        s = self.cfg.schema

        sql = f"""
        INSERT INTO {s}.ocr_entry
          (doc_id, entry_no, entry_type, entry_date, location, entry_text, entry_json)
        VALUES
          (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (doc_id, entry_no)
        DO UPDATE SET
          entry_type = EXCLUDED.entry_type,
          entry_date = EXCLUDED.entry_date,
          location   = EXCLUDED.location,
          entry_text = EXCLUDED.entry_text,
          entry_json = EXCLUDED.entry_json
        RETURNING entry_id
        """
        with self.conn.cursor() as cur:
            cur.execute(
                sql,
                (doc_id, entry_no, entry_type, entry_date, location, entry_text, Json(entry_json)),
            )
            return int(cur.fetchone()[0])
