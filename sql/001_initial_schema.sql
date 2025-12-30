CREATE TABLE IF NOT EXISTS ocr_document (
    doc_id SERIAL PRIMARY KEY,
    source_path TEXT UNIQUE NOT NULL,
    source_sha256 TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    doc_type TEXT DEFAULT 'unknown',
    pipeline TEXT,
    run_tag TEXT
);

CREATE TABLE IF NOT EXISTS ocr_run (
    run_id SERIAL PRIMARY KEY,
    doc_id INTEGER REFERENCES ocr_document(doc_id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status TEXT NOT NULL CHECK (status IN ('queued', 'processing', 'done', 'failed', 'skipped')),
    started_at TIMESTAMP WITH TIME ZONE,
    finished_at TIMESTAMP WITH TIME ZONE,
    error_code TEXT,
    error_message TEXT,
    out_path TEXT
);

CREATE TABLE IF NOT EXISTS ocr_step (
    step_id SERIAL PRIMARY KEY,
    run_id INTEGER REFERENCES ocr_run(run_id) ON DELETE CASCADE,
    step_name TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('started', 'done', 'failed')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    error_message TEXT
);
