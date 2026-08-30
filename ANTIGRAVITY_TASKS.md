# Handing work to Antigravity (Gemini)

You said Gemini has not been useful on this project. That matches what I would
expect, and the reason is structural rather than about the model: you were
asking it to hold a 1,770-line single-cell program in its head and reason about
Drive FUSE semantics, SQLite locking, HTTP auth and sixty source APIs at once.
Nothing does that well.

This repository is arranged so that the work Gemini *is* reliably good at —
bounded, verifiable, schema-constrained edits — is separated from the work it
is not. Give it registry tasks, not engine tasks.

**The rule: Antigravity edits `registry/*.yaml` and writes adapters. It does not
touch `gmsdl/fetch.py`, `gmsdl/runner.py`, `gmsdl/transport.py` or
`gmsdl/manifest.py`.** Those are load-bearing and already tested.

Every task below ends in a command that either passes or fails, so you never
have to review the work by reading it.

---

## Task 1 — Repair whatever the health report flags

> **Prompt to paste into Antigravity:**
>
> The repository `gms-data-lake` ingests public datasets into a data lake. The
> file `registry_health.md` is the output of `python -m gmsdl.cli doctor` and
> lists registry entries whose URLs are failing, with a diagnosis for each.
>
> For every failing entry, find the source's *current* download URL or API
> endpoint and fix its entry in the matching `registry/*.yaml` file. Rules:
>
> - Only edit files under `registry/`. Do not modify anything in `gmsdl/`.
> - Never point an entry at an HTML page. Every `url:` must return a file.
>   If the host only offers a JavaScript interface, find its underlying API —
>   open the site's network tab and look at the XHR requests it makes.
> - If a source genuinely has no machine-readable endpoint, set
>   `enabled: false` and write a `notes:` line explaining why. Do not invent
>   a URL.
> - Preserve the schema exactly: `id`, `name`, `subdomain`, `kind`, `cadence`,
>   `tier`, `homepage`, `license`, and either `datasets:` (for `kind: static`)
>   or `adapter:` + `params:` (for `kind: adapter`).
>
> Verify your work with:
> ```
> python -m gmsdl.cli plan
> python -m gmsdl.cli doctor --source <THE_SOURCE_ID>
> ```
> Both must succeed and the doctor line for that source must read `ok`.
> Report which entries you fixed, which you disabled, and why.

---

## Task 2 — Add a domain that is not yet covered

The architecture defines 21 domains; the registry currently seeds 13. Missing:
`07_SUPPLY_CHAIN` (beyond GSCPI), `10_ENTREPRENEURSHIP`, `12_PROCUREMENT`
(beyond USAspending), `14_ENERGY_COMMODITIES` (beyond EIA), `16_COMPETITION`,
`17_DIGITAL_ECONOMY` (beyond OWID), `18_SCIENCE`, `19_HEALTH`, `20_GEOGRAPHY`.

> **Prompt:**
>
> Create `registry/<NN>_<domain>.yaml` for the domain `<DOMAIN NAME>`, following
> the exact schema used by the existing files in `registry/`. Requirements:
>
> - 4 to 8 sources, each a **legally accessible public** dataset with a stated
>   `license:`. No paywalled, scraped, or terms-violating sources.
> - Every `url:` must be a direct file or a documented API endpoint that you
>   have actually confirmed responds — not a landing page you assume works.
> - Set `tier: bulk` for anything over about 2 GB so routine runs skip it.
> - Set `rate_limit_per_sec` for any host that publishes a rate limit.
> - If a source needs a key, set `requires_secret: <ENVVAR_NAME>` and mention
>   in `notes:` where the key comes from.
>
> Verify:
> ```
> python -m gmsdl.cli plan --domain <DOMAIN>
> python -m gmsdl.cli doctor --domain <DOMAIN> --max-failure-rate 0.2
> python tests/test_engine.py
> ```
> All three must pass. Report the sources you added and the licence of each.

---

## Task 3 — Write an adapter for an API-only source

Use this when a source has no stable file URL — it paginates, or requires a
POST, or enumerates datasets through a catalogue.

> **Prompt:**
>
> Add an adapter for `<SOURCE>` in `gmsdl/adapters/catalogues.py`. Follow the
> existing adapters in that file exactly:
>
> ```python
> @register("my_adapter_name")
> def my_adapter(source, session, settings) -> list[Dataset]:
>     ...
>     return [Dataset(id=..., url=..., filename=..., tier=source.tier)]
> ```
>
> Constraints:
> - Read every tunable from `source.params`, never hard-code it.
> - Return an empty list rather than raising when the catalogue is empty.
> - Cap the number of datasets returned with a `max_datasets` param.
> - Do not parse HTML. If the only route is HTML, say so and stop.
> - Do not import anything outside `requests`, the standard library and the
>   existing `gmsdl` modules.
>
> Then add the registry entry that uses it, and verify:
> ```
> python tests/test_engine.py     # must stay at 0 failures
> python -m gmsdl.cli plan --source <SOURCE_ID>
> python -m gmsdl.cli doctor --source <SOURCE_ID>
> ```

---

## Task 4 — Build the cross-domain research layer

This is the part you actually care about, and it should only start once the raw
lake has been refreshing cleanly for a few weeks.

> **Prompt:**
>
> Write `gmsdl/harmonise.py`, which reads raw files from the lake and emits
> tidy Parquet into `22_RESEARCH_READY_CROSS_DOMAIN/`. Build these master
> tables first, because every cross-domain join depends on them:
>
> - `COMPANY_MASTER` — CIK, ticker, LEI, name, SIC, NAICS, country.
>   Sources: SEC `company_tickers.json`, `company_tickers_exchange.json`,
>   GLEIF `lei2-golden-copy`, Nasdaq symbol directory.
> - `COUNTRY_MASTER` — ISO2, ISO3, M49, World Bank code, region, income group.
>   Sources: GeoNames `countryInfo.txt`, World Bank country API.
> - `INDUSTRY_MASTER` — NAICS 2022 and SIC with a crosswalk between them.
> - `TIME_MASTER` — a calendar spine with day, week, month, quarter, year and
>   fiscal-year variants.
>
> Every output table must carry `source_file`, `source_url` and `ingested_at`
> columns so any figure in a paper can be traced to the exact file it came
> from. Use DuckDB over the Parquet files; do not load anything fully into
> pandas. Write one function per table, each independently runnable and
> independently testable, and add a test for each to `tests/`.

---

## What to keep away from Antigravity

Hand these back to me, or reason about them yourself:

- Anything in `gmsdl/fetch.py`, `runner.py`, `transport.py`, `manifest.py`.
- The GitHub Actions workflows.
- The OAuth and secrets setup.
- Deciding what a paper's identification strategy needs.

The distinction is not about difficulty. It is that registry edits are checkable
by a command, and engine edits are checkable only by understanding the whole
system.
