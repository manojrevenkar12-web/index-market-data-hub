import datetime as dt

import pytest

from imdh.corporate_actions import Dividend, SpecialDividend, Split, make
from imdh.indexcalc import Guideline, IndexCalculator, capped

D = dt.date
FX = {"EUR": 1.0, "USD": 1.1, "GBP": 0.85}


def calc(return_type="price", weighting="equal"):
    g = Guideline("T", "Test", "EUR", return_type, weighting, None, 1000.0, D(2026, 7, 1), (), ("A", "B"))
    return IndexCalculator(g, {"A": "EUR", "B": "USD"}, {"A": 10.0, "B": 20.0})


def test_a_split_leaves_the_level_alone():
    c = calc()
    c.start({"A": 100.0, "B": 50.0}, FX)
    level = c.step(D(2026, 7, 2), {"A": 50.0, "B": 50.0}, FX, [Split("A", D(2026, 7, 2), factor=2.0)])
    assert level == pytest.approx(1000.0)


def test_a_missed_split_drops_the_index():
    c = calc()
    c.start({"A": 100.0, "B": 50.0}, FX)
    assert c.step(D(2026, 7, 2), {"A": 50.0, "B": 50.0}, FX, []) == pytest.approx(750.0)


def test_special_dividend_is_neutral_in_price_return_ordinary_is_not():
    c = calc("price")
    c.start({"A": 100.0, "B": 50.0}, FX)
    assert c.step(D(2026, 7, 2), {"A": 90.0, "B": 50.0}, FX,
                  [SpecialDividend("A", D(2026, 7, 2), amount=10.0)]) == pytest.approx(1000.0)
    c = calc("price")
    c.start({"A": 100.0, "B": 50.0}, FX)
    assert c.step(D(2026, 7, 2), {"A": 98.0, "B": 50.0}, FX,
                  [Dividend("A", D(2026, 7, 2), amount=2.0)]) == pytest.approx(990.0)


def test_total_return_reinvests_an_ordinary_dividend():
    c = calc("total")
    c.start({"A": 100.0, "B": 50.0}, FX)
    assert c.step(D(2026, 7, 2), {"A": 98.0, "B": 50.0}, FX,
                  [Dividend("A", D(2026, 7, 2), amount=2.0)]) == pytest.approx(1000.0)


def test_capped_weights_respect_the_cap_and_sum_to_one():
    w = capped({"a": 70.0, "b": 20.0, "c": 5.0, "d": 5.0, "e": 5.0}, 0.3)
    assert max(w.values()) <= 0.3 + 1e-12 and sum(w.values()) == pytest.approx(1.0)
    assert capped({"a": 9.0, "b": 1.0}, 0.2) == pytest.approx({"a": 0.5, "b": 0.5})  # infeasible cap -> 1/n


def test_actions_answer_for_themselves():
    assert make("split", "A", D(2026, 7, 2), 4.0).restate_previous(100.0) == 25.0
    assert make("dividend", "A", D(2026, 7, 2), 1.0).cash("price") == 0.0
    assert make("special", "A", D(2026, 7, 2), 1.0).cash("price") == 1.0
    assert make("split", "A", D(2026, 7, 2), 2.0).same_event(make("split", "A", D(2026, 7, 3), 2.0), 3)
