from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def headers(user="root", role="admin"):
    return {"X-User": user, "X-Role": role}


def create_cluster(kind="redis", name="redis-local"):
    c = client.post(
        "/api/clusters",
        headers=headers(),
        json={"name": name, "kind": kind, "host": "localhost", "port": 6379 if kind == "redis" else 9200},
    )
    assert c.status_code == 200
    return c.json()["id"]


def test_cluster_and_ticket_flow():
    cluster_id = create_cluster(kind="redis", name="redis-flow")

    t = client.post(
        "/api/tickets",
        headers=headers("op", "operator"),
        json={"title": "test", "description": "desc", "cluster_id": cluster_id, "command": "PING"},
    )
    assert t.status_code == 200
    ticket_id = t.json()["id"]

    rv = client.post(
        f"/api/tickets/{ticket_id}/review",
        headers=headers(),
        json={"action": "approve", "note": "ok"},
    )
    assert rv.status_code == 200
    assert rv.json()["status"] == "approved"


def test_redis_slowlog_endpoints(monkeypatch):
    cluster_id = create_cluster(kind="redis", name="redis-slowlog")

    monkeypatch.setattr("app.main.get_redis_slowlog", lambda cluster, count: [{"id": 1, "duration_us": 1200, "command": "GET a"}])
    monkeypatch.setattr("app.main.get_redis_slowlog_config", lambda cluster: {"slowlog_log_slower_than": 20000, "slowlog_max_len": 128})
    monkeypatch.setattr("app.main.set_redis_slowlog_config", lambda cluster, slower_than_us, max_len: {"slowlog_log_slower_than": slower_than_us or 1, "slowlog_max_len": max_len or 1})

    g1 = client.get(f"/api/clusters/{cluster_id}/redis/slowlog?count=10", headers=headers("viewer", "viewer"))
    assert g1.status_code == 200
    assert g1.json()["rows"][0]["id"] == 1

    g2 = client.get(f"/api/clusters/{cluster_id}/redis/slowlog/config", headers=headers("viewer", "viewer"))
    assert g2.status_code == 200

    p = client.put(
        f"/api/clusters/{cluster_id}/redis/slowlog/config",
        headers=headers(),
        json={"slower_than_us": 30000, "max_len": 256},
    )
    assert p.status_code == 200
    assert p.json()["config"]["slowlog_max_len"] == 256
