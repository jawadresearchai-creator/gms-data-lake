# Global Multidisciplinary Management Science Data Lake — ingestion engine

Acquires legally accessible public datasets across the management sciences and
ships them to Google Drive, on a schedule, with no local disk footprint and no
human in the loop.

```bash
pip install -r requirements.txt

python -m gmsdl.cli plan                    # what would run
python -m gmsdl.cli doctor                  # probe every URL, write a health report
python -m gmsdl.cli run --tier core         # acquire and ship
python -m gmsdl.cli status                  # what the lake holds
```

Setup is in **[SETUP.md](SETUP.md)**. Extending it is in
**[ANTIGRAVITY_TASKS.md](ANTIGRAVITY_TASKS.md)**.

## Shape of it

```
registry/*.yaml      the sources — data, not code. Edit these to add sources.
gmsdl/registry.py    parse + validate + tier/domain selection
gmsdl/adapters/      enumerate datasets from official catalogues and APIs
gmsdl/fetch.py       streaming HTTP: conditional GET, size ceiling, HTML sniffing
gmsdl/runner.py      per-source isolation; one failure never stops a run
gmsdl/transport.py   rclone → Google Drive
gmsdl/manifest.py    SQLite state, on local disk, shipped to Drive as a file
gmsdl/doctor.py      registry health check
.github/workflows/   the scheduler
```

## Four properties that matter

**Nothing accumulates locally.** Fetch one file, ship it, delete it, next. Peak
disk is the largest single file, enforced by a configurable ceiling that is
checked before the transfer starts rather than discovered when the disk fills.

**A failure is one line in a report, not a dead run.** Every source and every
dataset is isolated. Failures are recorded with a diagnosis that says what to do
about it, and the run continues.

**Re-runs are nearly free.** ETag and Last-Modified are stored per file, so a
weekly refresh transfers only what actually changed.

**The registry is verifiable on a schedule.** Public download URLs rot — hosts
retire, paths gain a year segment, agencies move to APIs, clients get blocked.
`gmsdl doctor` probes everything weekly and reports what broke, so the rot is
visible instead of silent.

## Tiers

Size discipline is declarative. Every source carries a tier and routine runs
only take `core`.

| Tier | Meaning | In a scheduled run? |
|---|---|---|
| `core` | small, high-value, fast | yes |
| `extended` | larger or slower | on request |
| `bulk` | hundreds of MB to a few GB | explicit backfill |
| `massive` | tens of GB and up | explicit, narrowed backfill |

That is why the OpenAlex snapshot can sit in the registry without a scheduled
run ever attempting its 660 GB.

## Testing

```bash
python tests/test_engine.py
```

Thirty checks against a local mock server that reproduces each real failure mode
— 403 bot-blocking, 404 stale paths, HTML served as data, oversized files,
flaky 5xx, empty bodies. No network, no credentials, no Drive.
