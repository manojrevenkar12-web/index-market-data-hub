import pytest
from fastapi.testclient import TestClient

from imdh.eval.load import load
from imdh.service.api import create_app
from imdh.store.repo import Store


@pytest.fixture(scope="module")
def client(tmp_path_factory, cfg, settings):
    store = Store(f"sqlite:///{tmp_path_factory.mktemp('api')}/api.db")
    load(store, cfg, settings)
    return TestClient(create_app(store))


def test_board_lists_every_index_on_the_last_close(client, world):
    b = client.get("/api/board").json()
    assert b["date"] == world.market.days[-1].isoformat()
    assert {i["id"] for i in b["indices"]} == {g["id"] for g in world.guidelines}
    assert all(i["level"] > 0 and len(i["spark"]) >= 2 for i in b["indices"])


def test_constituents_carry_provenance_and_weights(client, world):
    g = world.guidelines[0]
    r = client.get(f"/api/indices/{g['id']}/constituents").json()
    assert {x["instrument"] for x in r["rows"]} == set(g["constituents"])
    assert sum(x["weight"] for x in r["rows"]) == pytest.approx(1.0)
    assert all(x["candidates"] or x["method"] == "carried" for x in r["rows"])


def test_desk_actions_and_results(client):
    assert "items" in client.get("/api/desk").json()
    assert isinstance(client.get("/api/actions").json(), list)
    assert "dev" in client.get("/api/results").json()


def test_stream_replays_publications_in_order(client):
    body = client.get("/api/stream").text
    ids = [int(line[4:]) for line in body.splitlines() if line.startswith("id: ")]
    assert ids and ids == sorted(ids)
    assert "event: index.published" in body
    tail = client.get(f"/api/stream?after={ids[-2]}").text
    assert tail.count("id: ") == 1


def test_bad_requests_are_answered_plainly(client):
    assert client.get("/api/indices/NOPE").status_code == 404
    assert client.get("/api/board?date=1999-01-01").status_code == 404
    assert client.get("/api/desk?date=yesterday").status_code == 422
    assert client.get("/api/health").json()["ok"] is True
