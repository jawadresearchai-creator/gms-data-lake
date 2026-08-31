# Patent data strategy

The patent domain no longer depends on USPTO Open Data Portal identity verification.

## Source roles

- `GOOGLE_PATENTS_PUBLIC` — primary bulk analytical source. The live public table is
  `patents-public-data.patents.publications`, a worldwide bibliographic dataset with
  US full text. It is accessed through a dedicated BigQuery workflow, not the generic
  URL downloader.
- `EPO_OPS` — independent authoritative validation/enrichment source. It is not a bulk
  mirror because the free OPS allowance is limited and requires EPO registration.
- `USPTO_ODP` / `PATENTSVIEW` — optional authoritative/legacy sources. They remain in
  the registry for provenance and future cross-checking but are disabled so account
  verification cannot block the lake.

## Cost and safety controls

Every Google Patents job runs a BigQuery dry-run first. Execution is refused if the
estimated bytes processed exceed the configured hard cap. Queries use explicit columns
and a jurisdiction/year predicate. Google Cloud credentials are stored only as encrypted
GitHub secrets; no values belong in the repository.

The initial proof of concept is US publications. Once live dry-run measurements are
known, the backfill strategy will be chosen to minimize repeated scans of the public
source table. Query outputs are stored as immutable, provenance-preserving Parquet
extracts in Drive and accompanied by a control report containing source table, query
parameters, bytes processed/billed, row count, output hash, and destination path.

## Dedicated workflow

`.github/workflows/google-patents.yml`

Required encrypted GitHub secrets:

- `GCP_BIGQUERY_PROJECT_ID`
- `GCP_BIGQUERY_CREDENTIALS`

The existing Drive secrets are reused only for the final upload to the lake.
