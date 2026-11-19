import pytest

from imdh.eval.run import load_yaml, quick
from imdh.pipeline import Inbox
from imdh.world import build_world


@pytest.fixture(scope="session")
def settings():
    return load_yaml("hub.yaml")


@pytest.fixture(scope="session")
def gate():
    return load_yaml("gate.yaml")


@pytest.fixture(scope="session")
def cfg():
    return quick(load_yaml("world.yaml"))


@pytest.fixture(scope="session")
def world(cfg):
    return build_world(cfg)


@pytest.fixture(scope="session")
def inbox(world):
    return Inbox.read(world.feeds.files)
