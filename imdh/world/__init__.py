"""The simulated market and everything it sends. Product code never imports this package."""
from __future__ import annotations

from dataclasses import dataclass

from imdh.world.desk import WorldDesk
from imdh.world.feeds import Feeds, build_feeds
from imdh.world.indices import guidelines, true_levels
from imdh.world.market import Market, build_market


@dataclass
class World:
    cfg: dict
    market: Market
    feeds: Feeds
    guidelines: list[dict]

    def desk(self) -> WorldDesk:
        return WorldDesk(self.market, self.cfg["desk"]["minutes_per_lookup"])

    def truth(self) -> dict[str, list[float]]:
        return {g["id"]: [float(x) for x in true_levels(g, self.market)] for g in self.guidelines}


def build_world(cfg: dict) -> World:
    market = build_market(cfg)
    return World(cfg, market, build_feeds(cfg, market), guidelines(cfg, market))
