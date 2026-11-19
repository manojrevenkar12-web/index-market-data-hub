"""Write a simulated quarter as vendor drops: python -m imdh.eval.export --out drops [--quick]

Each file gets its delivery time as modification time, the way an SFTP receiver would leave it, plus the reference,
guideline and FX files. `python -m imdh.service.eod` then runs on the folder exactly as it runs on the bucket."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from imdh.eval.run import load_yaml, quick
from imdh.world import build_world


def export(cfg: dict, out: Path) -> int:
    w = build_world(cfg)
    for f in w.feeds.files:
        p = out / f.name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f.content)
        os.utime(p, (f.delivered_at.timestamp(), f.delivered_at.timestamp()))
    (out / "reference.json").write_text(json.dumps(w.feeds.reference))
    (out / "guidelines.json").write_text(json.dumps(w.guidelines))
    (out / "fx.json").write_text(json.dumps({d.isoformat(): v for d, v in w.feeds.fx.items()}))
    return len(w.feeds.files)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="drops")
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    cfg = load_yaml("world.yaml")
    n = export(quick(cfg) if a.quick else cfg, Path(a.out))
    print(f"wrote {n} vendor files to {a.out}")


if __name__ == "__main__":
    main()
