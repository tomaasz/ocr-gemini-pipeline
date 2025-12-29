# Documentation Changelog

## 2025-05-?? - Docs Audit & Restructure
- **Added** root `README.md` as the main entry point.
- **Moved** `MANIFEST.md` to `docs/MANIFEST.md` to declutter root.
- **Organized** `docs/` folder:
  - Created `docs/snapshots/` for historical snapshots.
  - Created `docs/reference/` for specific environment details.
- **Updated** `docs/MANIFEST.md`:
  - Corrected Environment Variable list (added `OCR_ALLOW_PLACEHOLDER`).
  - Corrected Database configuration (removed `DATABASE_URL`, confirmed `PG*` vars).
  - Clarified Stage 1.3 scope (FakeEngine).
- **Updated** `docs/reference/ENVIRONMENT_UBUNTUOVH.md`:
  - Clarified legacy vs new pipeline execution.
