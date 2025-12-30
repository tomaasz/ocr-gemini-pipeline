-- Migration to add retry tracking fields to ocr_run

ALTER TABLE ocr_run
ADD COLUMN attempt_no INTEGER DEFAULT 1,
ADD COLUMN parent_run_id INTEGER REFERENCES ocr_run(run_id) ON DELETE SET NULL,
ADD COLUMN error_kind TEXT,
ADD COLUMN retry_after_seconds INTEGER;
