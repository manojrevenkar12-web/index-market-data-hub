# Working in index-market-data-hub

Fast feedback first: `python -m pytest` builds a 22-day market with 90 instruments, runs every design through it,
checks the adapters, the symbology, the calculator, the store, the API, the end-of-day job and the invariants in
about five seconds. `ruff check .` for lint. After any change to the world, the hub or the settings run

```bash
python -m imdh.eval.cli evaluate && python -m imdh.eval.cli gate && python -m imdh.eval.cli readme
```

and commit the regenerated `reports/dev.json`, `reports/charts/` and `README.md`. CI fails when they disagree.
The dashboard has its own loop: `cd web && pnpm build && pnpm e2e` (Playwright with axe, against a loaded store).

## Layout

| path | what it is | may read |
|---|---|---|
| `imdh/world` | the simulated market: instruments, true closes, FX, corporate actions, renames and reused tickers; three vendors' files with their faults; the index guidelines; the true levels; the desk | `config/world.yaml` or `config/heldout.yaml`, `imdh/keyed.py` |
| `imdh/vendors` | one adapter per vendor format, all behind `VendorAdapter` | vendor file text |
| `imdh/symbology.py` | which instrument an identifier means on a date | announcements |
| `imdh/corporate_actions.py` | splits and dividends as objects the calculator asks, never inspects | |
| `imdh/decide.py` | the designs, each a strategy with `propose` and `commit` | quotes, announcements, `config/hub.yaml` |
| `imdh/indexcalc.py` | divisor-method calculation, capped and equal weights, price and total return | golden prices, actions, FX |
| `imdh/pipeline.py` | one design through the window: knowledge cut at the close, restatement next morning | deliveries |
| `imdh/store` | the bitemporal golden source and the publication outbox (SQLAlchemy; SQLite or PostgreSQL) | |
| `imdh/service` | FastAPI read API and stream, drops from a folder or GCS, Pub/Sub publisher, end-of-day job | the store, drops |
| `imdh/eval` | builds the world, runs every design on the same files, scores against the truth, gates, reports | everything |
| `web/` | the dashboard: `src/features/*` per view, `src/theme/tokens.ts` for every colour, size and duration | the API |
| `infra/terraform` | GCP: Cloud Run service and job, Cloud SQL, GCS drops, Pub/Sub, Scheduler, Secret Manager | |

## Invariants (checked in `tests/test_invariants.py` and the unit tests)

1. **The truth stays in the world.** Nothing outside `imdh/world` and `imdh/eval` imports `imdh.world`. The hub
   sees vendor files, the reference file, the guidelines, FX fixings and desk answers, nothing else.
2. **The world does not read the hub's settings.** `imdh/world` reads its world file only, never `hub.yaml`,
   `gate.yaml` or product code.
3. **Same luck for every design.** Every draw is keyed by what it is about (`imdh/keyed.py`); all designs read the
   same parsed inbox.
4. **Identifiers decide, on the date they are valid.** A quote maps to an instrument only through an identifier
   valid on the trade date. Names and expired identifiers never map.
5. **A published close is never edited.** A restatement adds a version and closes the old one; `as_of` reproduces
   what was published at any moment.
6. **Every vendor adapter meets one contract.** New formats subclass `VendorAdapter` and pass `tests/test_adapters.py`
   unchanged.
7. **Settings in config.** World rates in `config/world.yaml`, hub thresholds in `config/hub.yaml`, the gate in
   `config/gate.yaml`, the dashboard's look in `web/src/theme/tokens.ts`.
8. **Generated reports.** Every number in the README comes from `reports/`.

## The held-out rule

`config/heldout.yaml` (a stormier quarter with 1.6 times the vendor faults, more splits and renames, and a second
vendor that mislabels pence) is run once with `python -m imdh.eval.cli heldout`, with the code and settings
development ended on. It writes `config/heldout.lock` and `reports/heldout.json`; findings go into
`docs/heldout.md`. Fixes are made and measured on the development market. The held-out market is not run again and
`config/gate.yaml` is not moved.
