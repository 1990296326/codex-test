import json
from typing import Any

from elasticsearch import Elasticsearch
from redis import Redis

from .models import Cluster

ALLOWED_REDIS_PREFIX = {"GET", "SET", "DEL", "HGET", "HSET", "EXPIRE", "TTL", "PING", "INFO", "DBSIZE"}
ALLOWED_ES_METHOD = {"GET", "POST", "PUT", "DELETE"}


def get_redis_client(cluster: Cluster) -> Redis:
    return Redis(
        host=cluster.host,
        port=cluster.port,
        username=cluster.username,
        password=cluster.password,
        decode_responses=True,
        socket_timeout=5,
    )


def get_es_client(cluster: Cluster) -> Elasticsearch:
    return Elasticsearch(
        hosts=[{"host": cluster.host, "port": cluster.port, "scheme": "http"}],
        basic_auth=(cluster.username, cluster.password) if cluster.username else None,
        request_timeout=8,
    )


def run_redis_command(cluster: Cluster, command: str) -> str:
    parts = command.strip().split()
    if not parts:
        raise ValueError("Empty command")
    op = parts[0].upper()
    if op not in ALLOWED_REDIS_PREFIX:
        raise ValueError(f"Unsupported redis operation: {op}")

    result = get_redis_client(cluster).execute_command(*parts)
    return json.dumps(result, ensure_ascii=False)


def run_es_command(cluster: Cluster, command: str) -> str:
    chunks = command.split(" ", 2)
    if len(chunks) < 2:
        raise ValueError("ES command format must be: METHOD /path [json]")
    method, path = chunks[0].upper(), chunks[1]
    body: Any = None
    if method not in ALLOWED_ES_METHOD:
        raise ValueError(f"Unsupported es method: {method}")
    if len(chunks) == 3 and chunks[2].strip():
        body = json.loads(chunks[2])

    result = get_es_client(cluster).transport.perform_request(method, path, body=body)
    return json.dumps(result.body if hasattr(result, "body") else result, ensure_ascii=False)


def cluster_health(cluster: Cluster) -> dict:
    if cluster.kind == "redis":
        info = get_redis_client(cluster).info()
        return {
            "type": "redis",
            "version": info.get("redis_version"),
            "connected_clients": info.get("connected_clients"),
            "used_memory_human": info.get("used_memory_human"),
            "used_cpu_sys": info.get("used_cpu_sys"),
            "uptime_in_days": info.get("uptime_in_days"),
            "db0_keys": info.get("db0", {}).get("keys") if isinstance(info.get("db0"), dict) else None,
        }

    health = get_es_client(cluster).cluster.health()
    return {
        "type": "es",
        "cluster_name": health.get("cluster_name"),
        "status": health.get("status"),
        "number_of_nodes": health.get("number_of_nodes"),
        "active_shards": health.get("active_shards"),
        "unassigned_shards": health.get("unassigned_shards"),
    }


def cluster_connectivity(cluster: Cluster) -> dict[str, Any]:
    if cluster.kind == "redis":
        pong = get_redis_client(cluster).ping()
        return {"type": "redis", "ok": bool(pong), "message": "PONG" if pong else "NO_PONG"}

    info = get_es_client(cluster).info()
    return {
        "type": "es",
        "ok": True,
        "cluster_name": info.get("cluster_name"),
        "version": info.get("version", {}).get("number"),
        "tagline": info.get("tagline"),
    }


def get_redis_slowlog(cluster: Cluster, count: int = 20) -> list[dict[str, Any]]:
    entries = get_redis_client(cluster).slowlog_get(max(count, 1))
    rows: list[dict[str, Any]] = []
    for e in entries:
        rows.append(
            {
                "id": e.get("id"),
                "start_time": e.get("start_time"),
                "duration_us": e.get("duration"),
                "command": " ".join(e.get("command", [])) if isinstance(e.get("command"), list) else e.get("command"),
                "client_address": e.get("client_address"),
                "client_name": e.get("client_name"),
            }
        )
    return rows


def get_redis_slowlog_config(cluster: Cluster) -> dict[str, Any]:
    client = get_redis_client(cluster)
    return {
        "slowlog_log_slower_than": int(client.config_get("slowlog-log-slower-than").get("slowlog-log-slower-than", 0)),
        "slowlog_max_len": int(client.config_get("slowlog-max-len").get("slowlog-max-len", 0)),
    }


def set_redis_slowlog_config(cluster: Cluster, slower_than_us: int | None, max_len: int | None) -> dict[str, Any]:
    client = get_redis_client(cluster)
    if slower_than_us is not None:
        client.config_set("slowlog-log-slower-than", slower_than_us)
    if max_len is not None:
        client.config_set("slowlog-max-len", max_len)
    return get_redis_slowlog_config(cluster)


def run_es_query(cluster: Cluster, index: str, query: dict[str, Any], size: int = 20) -> dict[str, Any]:
    return get_es_client(cluster).search(index=index, query=query, size=min(max(size, 1), 200))


def get_es_slowlog_settings(cluster: Cluster, index_pattern: str = "*") -> dict[str, Any]:
    body = get_es_client(cluster).indices.get_settings(index=index_pattern)
    result: dict[str, Any] = {}
    for index_name, meta in body.items():
        idx = meta.get("settings", {}).get("index", {})
        result[index_name] = {
            "search_warn": idx.get("search", {}).get("slowlog", {}).get("threshold", {}).get("query", {}).get("warn"),
            "index_warn": idx.get("indexing", {}).get("slowlog", {}).get("threshold", {}).get("index", {}).get("warn"),
        }
    return result


def set_es_slowlog_settings(
    cluster: Cluster,
    index_pattern: str,
    search_warn_threshold: str | None,
    indexing_warn_threshold: str | None,
) -> dict[str, Any]:
    settings: dict[str, Any] = {}
    if search_warn_threshold:
        settings["index.search.slowlog.threshold.query.warn"] = search_warn_threshold
    if indexing_warn_threshold:
        settings["index.indexing.slowlog.threshold.index.warn"] = indexing_warn_threshold
    if settings:
        get_es_client(cluster).indices.put_settings(index=index_pattern, settings=settings)
    return get_es_slowlog_settings(cluster, index_pattern=index_pattern)
