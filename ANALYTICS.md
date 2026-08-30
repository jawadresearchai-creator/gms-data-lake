# Research/query layer

The raw lake remains immutable in Google Drive. Analytics runs on ephemeral
GitHub-hosted compute and writes only research-ready derivatives back to Drive.
Large raw datasets are not copied to the laptop.

## OpenAlex phase 1: scalar master tables

`.github/workflows/openalex-curate.yml` starts automatically only after a
successful `OpenAlex Full Snapshot` workflow (or can be resumed manually from a
batch number). It uses the same 15 deterministic OpenAlex key ranges as the raw
backfill.

For each Parquet object the worker:

1. enumerates OpenAlex S3 metadata without downloading the dataset from S3;
2. downloads the already-ingested raw object from Drive to the ephemeral runner;
3. uses DuckDB to discover the file schema and select scalar top-level columns;
4. writes a Zstandard-compressed Parquet shard to `02_CURATED/openalex/v1`;
5. uploads a per-batch SQLite checkpoint/report under
   `00_CONTROL/analytics/openalex`;
6. deletes both raw and curated temporary files before moving to the next object.

Current master-table families include `WORK_MASTER`, `AUTHOR_MASTER`,
`INSTITUTION_MASTER`, `SOURCE_MASTER`, `TOPIC_MASTER`, `FUNDER_MASTER`, and the
other OpenAlex entity masters that are present in the live Parquet snapshot.

Nested graph structures such as authorships, topics-on-works, locations, and
references remain in `01_RAW_IMMUTABLE`. They are intentionally deferred to the
edge-table phase so the first curation pass is schema-tolerant and resumable.

Analytics-only Python dependencies are kept in `requirements-analytics.txt` so
routine ingestion jobs stay lightweight.
