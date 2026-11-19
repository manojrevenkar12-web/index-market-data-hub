"""The designs: how one day's vendor quotes and announcements become golden prices and corporate actions.

Each design is a strategy with the same two calls: `propose(day)` returns a decision without changing anything,
`commit(decision)` makes it the design's memory for the next day. Proposing twice (at the close, and again the next
morning with late files) is therefore safe.
"""
from __future__ import annotations

import datetime as dt
import math
import statistics
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from imdh import corporate_actions as ca
from imdh.corporate_actions import CorporateAction
from imdh.domain import (
    Announcement,
    Candidate,
    Desk,
    DeskUnavailable,
    PriceDecision,
    Quote,
    RefInstrument,
    ReviewItem,
)
from imdh.symbology import NaiveMap, SecurityMaster

SPLIT_FACTORS = (2.0, 3.0, 4.0, 5.0, 10.0, 0.5, 1 / 3, 0.25, 0.2, 0.1)


def major(value: float, unit: str) -> float:
    """Vendor labels are trusted here; checking them is a hub step."""
    return value / 100.0 if unit == "GBX" else value


@dataclass
class Day:
    day: dt.date
    quotes: list[Quote]  # for this business date, delivered by the knowledge time
    announcements: list[Announcement]  # every announcement delivered by the knowledge time
    weights: dict[str, float]  # largest index weight per instrument, from yesterday's close
    desk: Desk | None = None
    keep: Decision | None = None  # restating: keep these desk answers and actions


@dataclass
class Decision:
    day: dt.date
    prices: dict[str, PriceDecision]
    actions: list[CorporateAction]
    reviews: list[ReviewItem] = field(default_factory=list)
    renames: list[tuple[str, Announcement]] = field(default_factory=list)

    @property
    def lookups(self) -> int:
        return sum(1 for r in self.reviews if r.looked_up)


class Design(ABC):
    name: str = "design"
    dated_symbology = True

    def __init__(self, reference: list[RefInstrument], start: dt.date, settings: dict):
        self.reference = {r.id: r for r in reference}
        self.s = settings
        self.master = SecurityMaster(reference, start) if self.dated_symbology else NaiveMap(reference, start)
        self.prev: dict[str, float] = {}
        self.vendor_last: dict[tuple[str, str], float] = {}
        self.applied: list[CorporateAction] = []
        self.seen_renames: set[tuple] = set()

    # -- shared helpers ------------------------------------------------------------------------------------
    def trusted_vendors(self) -> set[str] | None:
        return None  # None means every vendor

    def _renames(self, d: Day) -> list[tuple[str, Announcement]]:
        out = []
        trusted = self.trusted_vendors()
        for a in d.announcements:
            if a.kind != "rename" or (trusted is not None and a.vendor not in trusted):
                continue
            k = (a.vendor, a.identifier, a.new_identifier, a.ex_date)
            if k in self.seen_renames:
                continue
            self.seen_renames.add(k)
            inst = self.master.rename(a)
            if inst:
                out.append((inst, a))
        return out

    def candidates(self, d: Day, vendors: set[str] | None = None) -> dict[str, list[tuple[Quote, float]]]:
        out: dict[str, list[tuple[Quote, float]]] = {}
        for q in d.quotes:
            if vendors is not None and q.vendor not in vendors:
                continue
            inst = self.master.resolve_quote(q)
            if inst is None or inst not in self.reference:
                continue
            out.setdefault(inst, []).append((q, major(q.value, q.unit)))
        return out

    def restated_prev(self, inst: str, actions: list[CorporateAction]) -> float | None:
        p = self.prev.get(inst)
        if p is None:
            return None
        for a in actions:
            if a.instrument == inst:
                p = a.restate_previous(p)
        return p

    def already_applied(self, action: CorporateAction) -> bool:
        w = self.s["actions"]["duplicate_window_days"]
        return any(action.same_event(a, w) for a in self.applied)

    def announcement_value(self, a: Announcement) -> float:
        return a.factor if a.kind == "split" else major(a.amount, a.unit)

    def carried(self, inst: str, actions: list[CorporateAction], why: str) -> PriceDecision:
        p = self.restated_prev(inst, actions)
        return PriceDecision(inst, p if p is not None else float("nan"), "carried", (), (why,))

    # -- the strategy ----------------------------------------------------------------------------------------
    @abstractmethod
    def propose(self, d: Day) -> Decision: ...

    def commit(self, decision: Decision) -> None:
        for inst, p in decision.prices.items():
            if not math.isnan(p.price):
                self.prev[inst] = p.price
            for c in p.candidates:
                self.vendor_last[(c.vendor, inst)] = c.value
        self.applied.extend(decision.actions)


class SingleVendor(Design):
    """Northwind only: its prices, its announcements, its renames."""

    name = "single_vendor"
    dated_symbology = False
    vendor = "northwind"

    def trusted_vendors(self):
        return {self.vendor}

    def own_actions(self, d: Day, vendors: set[str]) -> list[CorporateAction]:
        out = []
        for a in d.announcements:
            if a.vendor in vendors and a.kind != "rename" and a.ex_date == d.day:
                inst = self.master.resolve_announcement(a)
                if inst in self.reference:
                    act = ca.make(a.kind, inst, d.day, self.announcement_value(a), a.vendor)
                    if not self.already_applied(act) and not any(act.same_event(x, 0) for x in out):
                        out.append(act)
        return out

    def propose(self, d: Day) -> Decision:
        renames = self._renames(d)
        actions = self.own_actions(d, {self.vendor})
        cands = self.candidates(d, {self.vendor})
        prices = {}
        for inst in self.reference:
            got = cands.get(inst)
            if got:
                q, v = got[-1]
                prices[inst] = PriceDecision(inst, v, "primary", (q.vendor,), (), (Candidate(q.vendor, v),))
            else:
                prices[inst] = self.carried(inst, actions, "no quote")
        return Decision(d.day, prices, actions, renames=renames)


class PrimaryBackup(SingleVendor):
    """Northwind first; Meridian's price when Northwind has none for the instrument."""

    name = "primary_backup"
    backup = "meridian"

    def trusted_vendors(self):
        return {self.vendor, self.backup}

    def propose(self, d: Day) -> Decision:
        renames = self._renames(d)
        actions = self.own_actions(d, {self.vendor})
        cands = self.candidates(d, {self.vendor, self.backup})
        prices = {}
        for inst in self.reference:
            got = {q.vendor: (q, v) for q, v in cands.get(inst, [])}
            for vendor, method in ((self.vendor, "primary"), (self.backup, "backup")):
                if vendor in got:
                    _, v = got[vendor]
                    prices[inst] = PriceDecision(inst, v, method, (vendor,), (), (Candidate(vendor, v),))
                    break
            else:
                prices[inst] = self.carried(inst, actions, "no quote")
        return Decision(d.day, prices, actions, renames=renames)


class MedianConsensus(Design):
    """Median of every vendor's quote; an action is applied when two vendors announce it for the day."""

    name = "median_consensus"
    dated_symbology = False

    def propose(self, d: Day) -> Decision:
        renames = self._renames(d)
        groups: dict[tuple, list[Announcement]] = {}
        for a in d.announcements:
            if a.kind == "rename" or a.ex_date != d.day:
                continue
            inst = self.master.resolve_announcement(a)
            if inst in self.reference:
                groups.setdefault((inst, a.kind), []).append(a)
        actions = []
        for (inst, kind), anns in groups.items():
            if len({a.vendor for a in anns}) >= 2:
                act = ca.make(kind, inst, d.day, statistics.median(self.announcement_value(a) for a in anns))
                if not self.already_applied(act):
                    actions.append(act)
        cands = self.candidates(d)
        prices = {}
        for inst in self.reference:
            got = cands.get(inst)
            if got:
                vals = [v for _, v in got]
                prices[inst] = PriceDecision(inst, statistics.median(vals), "median", tuple(q.vendor for q, _ in got),
                                             (), tuple(Candidate(q.vendor, v) for q, v in got))
            else:
                prices[inst] = self.carried(inst, actions, "no quote")
        return Decision(d.day, prices, actions, renames=renames)


class Hub(Design):
    """Dated symbology, unit repair, stale detection, vendor agreement, price-confirmed corporate actions and a
    desk that looks up the riskiest open questions first."""

    name = "hub"
    unit_check = True
    stale_check = True
    action_check = True
    review = "ranked"  # ranked | unranked | none

    # -- corporate actions ----------------------------------------------------------------------------------
    def _claims(self, d: Day) -> dict[tuple[str, str], dict[str, Announcement]]:
        w = self.s["actions"]["duplicate_window_days"]
        claims: dict[tuple[str, str], dict[str, Announcement]] = {}
        for a in sorted(d.announcements, key=lambda a: a.announced_on or a.ex_date):
            if a.kind == "rename" or abs((a.ex_date - d.day).days) > w:
                continue
            inst = self.master.resolve_announcement(a)
            if inst in self.reference:
                claims.setdefault((inst, a.kind), {})[a.vendor] = a  # a vendor's latest word counts
        return claims

    def _agreeing(self, values: list[float]) -> list[list[float]]:
        tol = self.s["actions"]["value_tolerance"]
        groups: list[list[float]] = []
        for v in sorted(values):
            if groups and abs(v / groups[-1][0] - 1) <= tol:
                groups[-1].append(v)
            else:
                groups.append([v])
        return sorted(groups, key=len, reverse=True)

    def _actions(self, d: Day, raw: dict[str, float], reviews: list[ReviewItem]) -> list[CorporateAction]:
        sa = self.s["actions"]
        out: list[CorporateAction] = []
        for (inst, kind), by_vendor in self._claims(d).items():
            on_day = [a for a in by_vendor.values() if a.ex_date == d.day]
            if not on_day:
                continue
            other_dates = [a for a in by_vendor.values() if a.ex_date != d.day]
            weight = d.weights.get(inst, 0.0)
            if len(other_dates) > len(on_day):
                continue  # most vendors say another day
            values = [self.announcement_value(a) for a in on_day]
            agreed = self._agreeing(values)[0]
            act: CorporateAction | None = None
            if not self.action_check:
                act = ca.make(kind, inst, d.day, statistics.median(agreed), "announced")
            elif len(agreed) >= 2:
                act = ca.make(kind, inst, d.day, statistics.median(agreed), "agreed")
            elif kind == "split":
                prev, now = self.prev.get(inst), raw.get(inst)
                if prev and now:
                    ratio = now / prev
                    fits = [f for f in values if abs(ratio * f - 1) <= sa["split_confirm_tolerance"]]
                    if fits:
                        act = ca.make(kind, inst, d.day, fits[0], "price-confirmed")
                    elif abs(ratio - 1) <= sa["split_confirm_tolerance"] and other_dates:
                        continue  # no move today and another vendor says another day: wait
                if act is None:
                    reviews.append(ReviewItem(inst, d.day, "action", f"unconfirmed {kind} {values}", weight * 1.0,
                                              details={"kind": kind, "values": values}))
                    continue
            else:
                prev = self.prev.get(inst) or 1.0
                single = len(on_day) == 1 and len(values) == 1
                if single and not other_dates and values[0] / prev < sa["dividend_review_yield"]:
                    act = ca.make(kind, inst, d.day, values[0], "single-source")
                else:
                    reviews.append(ReviewItem(inst, d.day, "action", f"disputed {kind} {values}",
                                              weight * max(values) / prev, details={"kind": kind, "values": values}))
                    continue
            if act is not None and not self.already_applied(act):
                out.append(act)
        return out

    # -- prices ---------------------------------------------------------------------------------------------
    def _cluster(self, vals: list[tuple[str, float]]) -> list[list[tuple[str, float]]]:
        tol = self.s["prices"]["agree_tolerance"]
        groups: list[list[tuple[str, float]]] = []
        for vendor, v in sorted(vals, key=lambda x: x[1]):
            if groups and abs(v / groups[-1][0][1] - 1) <= tol:
                groups[-1].append((vendor, v))
            else:
                groups.append([(vendor, v)])
        return sorted(groups, key=len, reverse=True)

    def _raw_consensus(self, cands: dict[str, list[tuple[Quote, float]]]) -> dict[str, float]:
        out = {}
        for inst, got in cands.items():
            best = self._cluster([(q.vendor, v) for q, v in got])[0]
            if len(best) >= 2:
                out[inst] = statistics.median(v for _, v in best)
        return out

    def _price(self, inst: str, got: list[tuple[Quote, float]], expected: float | None, d: Day,
               actions: list[CorporateAction], reviews: list[ReviewItem]) -> PriceDecision:
        sp = self.s["prices"]
        weight = d.weights.get(inst, 0.0)
        cands: list[Candidate] = []
        reasons: list[str] = []
        for q, v in got:
            # yesterday's golden price moved by the peers is the reference; the other vendors only when there is no
            # yesterday, because with two vendors one mislabelled quote would make the good one look mislabelled
            others = [x for qq, x in got if qq is not q]
            ref = expected or (statistics.median(others) if others else None)
            repaired = None
            if self.unit_check and ref:
                lo, hi = sp["unit_ratio"]
                r = v / ref
                if lo <= r <= hi:
                    v, repaired = v / 100.0, "pence labelled as pounds"
                elif 1 / hi <= r <= 1 / lo:
                    v, repaired = v * 100.0, "pounds labelled as pence"
            if repaired:
                reasons.append(f"{q.vendor}: {repaired}")
            cands.append(Candidate(q.vendor, v, repaired))

        live = list(cands)
        if self.stale_check:
            moved_peers = expected is not None and self.prev.get(inst) and abs(
                expected / self.restated_prev(inst, actions) - 1) >= sp["stale_min_move"]
            keep = []
            for c in live:
                last = self.vendor_last.get((c.vendor, inst))
                others_differ = any(abs(o.value / c.value - 1) > sp["agree_tolerance"] for o in live if o is not c)
                if last is not None and c.value == last and (others_differ or moved_peers):
                    reasons.append(f"{c.vendor}: repeated yesterday's price")
                    continue
                keep.append(c)
            if not keep and live and expected:
                # every quote repeats yesterday while the market moved: ask the desk, keep the repeat meanwhile
                move = abs(expected / self.restated_prev(inst, actions) - 1)
                reviews.append(ReviewItem(inst, d.day, "price", f"only repeated prices, peers moved {move:.1%}",
                                          weight * move, live[0].value))
            live = keep or live

        if not live:
            reviews.append(ReviewItem(inst, d.day, "price", "no usable quote", weight * 1.0))
            dec = self.carried(inst, actions, "no usable quote")
            dec.candidates = tuple(cands)
            return dec

        best = self._cluster([(c.vendor, c.value) for c in live])
        if len(best[0]) >= 2:
            price = statistics.median(v for _, v in best[0])
            outvoted = [c.vendor for c in live if c.vendor not in {v for v, _ in best[0]}]
            if outvoted:
                reasons.append("outvoted: " + ", ".join(outvoted))
            if self.review == "unranked" and (outvoted or len(live) < len(cands)):
                reviews.append(ReviewItem(inst, d.day, "price", "vendors disagree", 0.0, price))
            return PriceDecision(inst, price, "consensus", tuple(v for v, _ in best[0]), tuple(reasons), tuple(cands))

        if len(live) == 1:
            c = live[0]
            dev = abs(c.value / expected - 1) if expected else 0.0
            if dev > sp["single_source_max_move"]:
                # an unverified big move from one vendor: hold the last valid price until the desk confirms it
                reviews.append(ReviewItem(inst, d.day, "price", f"one source, {dev:.1%} from expected",
                                          weight * dev, c.value))
                held = self.carried(inst, actions, f"held: {c.vendor} alone moved {dev:.1%}")
                held.candidates, held.reasons = tuple(cands), tuple(reasons) + held.reasons
                return held
            if self.review == "unranked":
                reviews.append(ReviewItem(inst, d.day, "price", "one source", 0.0, c.value))
            return PriceDecision(inst, c.value, "single", (c.vendor,), tuple(reasons), tuple(cands))

        pick = min(live, key=lambda c: abs(c.value / expected - 1)) if expected else live[0]
        spread = max(c.value for c in live) / min(c.value for c in live) - 1
        if spread > sp["disagreement_review"] or self.review == "unranked":
            reviews.append(ReviewItem(inst, d.day, "price", f"vendors {spread:.1%} apart", weight * spread, pick.value))
        reasons.append("closest to the peer-expected price")
        return PriceDecision(inst, pick.value, "closest", (pick.vendor,), tuple(reasons), tuple(cands))

    def _silent_splits(self, d: Day, prices: dict[str, PriceDecision], actions: list[CorporateAction],
                       reviews: list[ReviewItem]) -> None:
        sa = self.s["actions"]
        split_today = {a.instrument for a in actions if a.kind == "split"}
        for inst, p in prices.items():
            prev = self.prev.get(inst)
            if inst in split_today or not prev or p.method != "consensus" or d.weights.get(inst, 0.0) == 0:
                continue
            r = p.price / prev
            if abs(math.log(r)) < sa["unannounced_split_min_move"]:
                continue
            if any(abs(r * f - 1) <= sa["unannounced_split_tolerance"] for f in SPLIT_FACTORS):
                reviews.append(ReviewItem(inst, d.day, "action", f"price moved x{r:.3f}, no split announced",
                                          d.weights[inst], details={"kind": "split", "values": []}))

    def _desk(self, d: Day, prices: dict[str, PriceDecision], actions: list[CorporateAction],
              reviews: list[ReviewItem]) -> list[CorporateAction]:
        if self.review == "none" or d.desk is None:
            return actions
        cap = self.s["review"]["capacity_per_day"]
        relevant = [r for r in reviews if d.weights.get(r.instrument, 0.0) > 0]
        order = (sorted(relevant, key=lambda r: r.priority, reverse=True) if self.review == "ranked"
                 else sorted(relevant, key=lambda r: r.instrument))
        seen: set[tuple[str, str]] = set()
        for r in order:
            if len(seen) >= cap:
                break
            if (r.instrument, r.topic) in seen:
                continue
            seen.add((r.instrument, r.topic))
            try:
                answer = (d.desk.price(r.instrument, d.day) if r.topic == "price"
                          else d.desk.actions(r.instrument, d.day))
            except DeskUnavailable:
                continue
            r.looked_up = True
            if r.topic == "price":
                r.answer = answer
                old = prices[r.instrument]
                prices[r.instrument] = PriceDecision(r.instrument, r.answer, "desk", ("desk",),
                                                     (*old.reasons, f"desk: {r.reason}"), old.candidates)
            else:
                told = answer
                actions = [a for a in actions if not (a.instrument == r.instrument and a.kind == r.details["kind"])]
                for t in told:
                    if t["kind"] == r.details["kind"] or r.details["kind"] == "split":
                        act = ca.make(t["kind"], r.instrument, d.day, t["value"], "desk")
                        if not self.already_applied(act) and not any(act.same_event(x, 0) for x in actions):
                            actions.append(act)
        return actions

    def propose(self, d: Day) -> Decision:
        renames = self._renames(d)
        cands = self.candidates(d)
        raw = self._raw_consensus(cands)
        reviews: list[ReviewItem] = []
        actions = list(d.keep.actions) if d.keep is not None else self._actions(d, raw, reviews)

        # peer-expected move per region from instruments where two vendors agree
        moves: dict[str, list[float]] = {}
        for inst, v in raw.items():
            p = self.restated_prev(inst, actions)
            if p:
                moves.setdefault(self.reference[inst].region, []).append(v / p - 1)
        peer = {k: statistics.median(v) for k, v in moves.items()}

        prices: dict[str, PriceDecision] = {}
        for inst in self.reference:
            if d.keep is not None and d.keep.prices[inst].method == "desk":
                prices[inst] = d.keep.prices[inst]
                continue
            p0 = self.restated_prev(inst, actions)
            expected = p0 * (1 + peer.get(self.reference[inst].region, 0.0)) if p0 else None
            got = cands.get(inst, [])
            if not got:
                reviews.append(ReviewItem(inst, d.day, "price", "no quote", d.weights.get(inst, 0.0) * 1.0))
                prices[inst] = self.carried(inst, actions, "no quote")
                continue
            prices[inst] = self._price(inst, got, expected, d, actions, reviews)

        if d.keep is None:
            if self.action_check:
                self._silent_splits(d, prices, actions, reviews)
            actions = self._desk(d, prices, actions, reviews)
        return Decision(d.day, prices, actions, reviews, renames)


class HubNoDesk(Hub):
    name = "hub_no_desk"
    review = "none"


class HubUnranked(Hub):
    name = "hub_unranked_desk"
    review = "unranked"


class HubNoActionCheck(Hub):
    name = "hub_no_action_check"
    action_check = False


class HubNoStaleCheck(Hub):
    name = "hub_no_stale_or_unit_check"
    stale_check = False
    unit_check = False


class HubUndatedSymbology(Hub):
    name = "hub_undated_symbology"
    dated_symbology = False


DESIGNS: dict[str, type[Design]] = {
    c.name: c for c in (SingleVendor, PrimaryBackup, MedianConsensus, HubNoDesk, HubUnranked, HubNoActionCheck,
                        HubNoStaleCheck, HubUndatedSymbology, Hub)
}
