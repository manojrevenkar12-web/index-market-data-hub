import hashlib

import numpy as np

from imdh.eval.run import calculators_agree
from imdh.world import build_world
from imdh.world.market import isin_check_digit


def test_isins_carry_valid_check_digits(world):
    for inst in world.feeds.reference["instruments"]:
        assert inst["isin"][-1] == isin_check_digit(inst["isin"][:-1])
    assert isin_check_digit("US037833100") == "5"  # a real ISIN: US0378331005


def test_same_seed_same_files(cfg, world):
    again = build_world(cfg)
    digest = lambda w: hashlib.sha256("".join(f.name + f.content for f in w.feeds.files).encode()).hexdigest()  # noqa: E731
    assert digest(again) == digest(world)


def test_prices_positive_and_listed(world):
    for inst, p in world.market.prices.items():
        listed = p[~np.isnan(p)]
        assert (listed > 0).all(), inst


def test_faults_are_logged_by_kind(world):
    kinds = {f.kind.split(":")[0] for f in world.feeds.faults}
    assert {"stale", "missing", "spike"} <= kinds


def test_the_two_index_engines_agree_on_the_true_market(world):
    assert calculators_agree(world) < 1e-9


def test_every_vendor_sends_a_price_and_an_action_file_per_day(world):
    days = len(world.market.days)
    for vendor in ("northwind", "meridian", "kestrel"):
        assert sum(1 for f in world.feeds.files if f.vendor == vendor and f.kind == "prices") == days
        assert sum(1 for f in world.feeds.files if f.vendor == vendor and f.kind == "actions") == days
