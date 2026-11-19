# Repeatable tasks

## Add a vendor
1. Subclass `VendorAdapter` in `imdh/vendors/<name>.py` with `name`, `id_type`, `read_price`, `read_action` (and
   `header_like` if the file has a header). Import it in `imdh/vendors/__init__.py`.
2. Add a malformed line for it to `BAD` in `tests/test_adapters.py`; the contract tests then run against it.
3. Add the vendor to the world (`config/world.yaml` and the format branch in `imdh/world/feeds.py`) so the designs
   meet it, run `evaluate`, and commit the reports.

## Add a corporate-action type
Subclass `CorporateAction` and answer `quantity_factor`, `restate_previous` and `cash` for it; register it in `KINDS`.
Add the event to the world and to `imdh/world/indices.py` (the second engine) and keep `test_the_two_index_engines_agree`
green.

## Tune a hub setting
Change `config/hub.yaml`, run `python -m imdh.eval.cli evaluate`, read the designs table and the causes, and keep the
change only if the hub improves on the development market without more desk lookups than the gate allows.
Never look at the held-out market while tuning.

## Investigate a wrong close
`python -m imdh.eval.load` fills `imdh.db`; `python -m imdh.service` serves it. Open the index and date in the
dashboard: the provenance marks show which vendors were used, outvoted, repaired or absent, and the Desk tab shows
what was looked up. `/api/indices/<id>/versions/<date>` lists every published version.

## Replay drops like production
`python -m imdh.eval.export --out drops` writes a quarter as vendor drops with their arrival times;
`IMDH_DROPS=drops IMDH_NOW=2026-09-25T19:00 python -m imdh.service.eod` lands them, publishes and relays.

## Deploy to GCP
Build and push the image (`docker build -t <region>-docker.pkg.dev/<project>/imdh/hub:<sha> .`), then
`terraform -chdir=infra/terraform apply -var project=<project> -var image=<image>`. See `docs/gcp.md`.

## Run the held-out market
Only when development is finished and `python -m imdh.eval.cli gate` passes:
`python -m imdh.eval.cli heldout`, then write what it got wrong in `docs/heldout.md` and regenerate the README.
