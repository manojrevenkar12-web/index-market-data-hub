import datetime as dt

from imdh.eval.export import export
from imdh.service.drops import FolderDrops
from imdh.service.eod import run_eod
from imdh.service.publisher import MemoryPublisher
from imdh.store.repo import Store


def test_the_eod_job_publishes_from_drops_once(tmp_path, cfg, world, settings):
    export(cfg, tmp_path / "drops")
    store = Store(f"sqlite:///{tmp_path}/eod.db")
    pub = MemoryPublisher()
    mid = dt.datetime.combine(world.market.days[5], dt.time(19, 0))
    first = run_eod(FolderDrops(tmp_path / "drops"), store, settings, pub, mid)
    assert first["recorded"] == 6 and first["relayed"] >= 6 * len(world.guidelines)
    again = run_eod(FolderDrops(tmp_path / "drops"), store, settings, pub, mid)
    assert again["recorded"] == 0 and again["landed"] == 0 and again["relayed"] == 0
    end = dt.datetime.combine(world.market.days[-1], dt.time(19, 0))
    last = run_eod(FolderDrops(tmp_path / "drops"), store, settings, pub, end)
    assert last["recorded"] == len(world.market.days) - 6
    assert len(store.days()) == len(world.market.days)
    seqs = [e["seq"] for e in pub.sent]
    assert seqs == sorted(seqs) and len(seqs) == len(set(seqs))
