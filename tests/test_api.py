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


def test_dashboard_template_precheck_and_export():
    cluster_id = create_cluster(kind="redis", name="redis-main")

    d = client.get("/api/dashboard", headers=headers("viewer", "viewer"))
    assert d.status_code == 200
    assert "clusters_total" in d.json()

    t = client.post(
        "/api/templates",
        headers=headers(),
        json={"name": "ping", "kind": "redis", "command": "PING", "description": "health"},
    )
    assert t.status_code == 200

    p = client.post(
        "/api/commands/precheck",
        headers=headers("op", "operator"),
        json={"cluster_id": cluster_id, "command": "PING"},
    )
    assert p.status_code == 200
    assert p.json()["ok"] is True

    ex = client.get("/api/logs/export", headers=headers())
    assert ex.status_code == 200
    assert ex.headers["content-type"].startswith("text/csv")
