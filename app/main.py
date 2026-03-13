from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .database import Base, engine, get_db
from .models import Cluster, CommandLog, Ticket
from .schemas import (
    ClusterCreate,
    ClusterHealthOut,
    ClusterOut,
    ESQueryIn,
    ESSlowlogConfigUpdate,
    ExecuteCommandIn,
    ExecuteCommandOut,
    RedisSlowlogConfigUpdate,
    TicketCreate,
    TicketOut,
    TicketReview,
    UserContext,
)
from .services import (
    cluster_health,
    get_es_slowlog_settings,
    get_redis_slowlog,
    get_redis_slowlog_config,
    run_es_command,
    run_es_query,
    run_redis_command,
    set_es_slowlog_settings,
    set_redis_slowlog_config,
)

app = FastAPI(title="ES / Redis 管理控制台", version="1.1.0")
Base.metadata.create_all(bind=engine)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


def get_user_context(
    x_user: str = Header(default="guest"),
    x_role: str = Header(default="viewer"),
) -> UserContext:
    if x_role not in {"viewer", "operator", "admin"}:
        raise HTTPException(status_code=400, detail="Invalid role")
    return UserContext(username=x_user, role=x_role)


def require_roles(user: UserContext, allowed: set[str]):
    if user.role not in allowed:
        raise HTTPException(status_code=403, detail="Permission denied")


def must_get_cluster(db: Session, cluster_id: int, expected_kind: str | None = None) -> Cluster:
    cluster = db.get(Cluster, cluster_id)
    if not cluster:
        raise HTTPException(status_code=404, detail="Cluster not found")
    if expected_kind and cluster.kind != expected_kind:
        raise HTTPException(status_code=400, detail=f"Cluster {cluster_id} is not {expected_kind}")
    return cluster


@app.get("/")
def index():
    return FileResponse("app/static/index.html")


@app.post("/api/clusters", response_model=ClusterOut)
def create_cluster(
    payload: ClusterCreate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_user_context),
):
    require_roles(user, {"admin"})
    entity = Cluster(**payload.model_dump())
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@app.get("/api/clusters", response_model=list[ClusterOut])
def list_clusters(
    kind: str | None = None,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_user_context),
):
    require_roles(user, {"viewer", "operator", "admin"})
    query = db.query(Cluster).order_by(Cluster.id.desc())
    if kind:
        query = query.filter(Cluster.kind == kind)
    return query.all()


@app.get("/api/clusters/{cluster_id}/health", response_model=ClusterHealthOut)
def get_cluster_health(
    cluster_id: int,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_user_context),
):
    require_roles(user, {"viewer", "operator", "admin"})
    cluster = must_get_cluster(db, cluster_id)
    return ClusterHealthOut(cluster_id=cluster_id, summary=cluster_health(cluster))


@app.get("/api/clusters/{cluster_id}/redis/slowlog")
def redis_slowlog(
    cluster_id: int,
    count: int = 20,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_user_context),
):
    require_roles(user, {"viewer", "operator", "admin"})
    cluster = must_get_cluster(db, cluster_id, expected_kind="redis")
    return {"cluster_id": cluster_id, "rows": get_redis_slowlog(cluster, count=min(max(count, 1), 128))}


@app.get("/api/clusters/{cluster_id}/redis/slowlog/config")
def redis_slowlog_config(
    cluster_id: int,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_user_context),
):
    require_roles(user, {"viewer", "operator", "admin"})
    cluster = must_get_cluster(db, cluster_id, expected_kind="redis")
    return {"cluster_id": cluster_id, "config": get_redis_slowlog_config(cluster)}


@app.put("/api/clusters/{cluster_id}/redis/slowlog/config")
def update_redis_slowlog_config(
    cluster_id: int,
    payload: RedisSlowlogConfigUpdate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_user_context),
):
    require_roles(user, {"admin"})
    cluster = must_get_cluster(db, cluster_id, expected_kind="redis")
    return {
        "cluster_id": cluster_id,
        "config": set_redis_slowlog_config(cluster, payload.slower_than_us, payload.max_len),
    }


@app.post("/api/clusters/{cluster_id}/es/query")
def es_query(
    cluster_id: int,
    payload: ESQueryIn,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_user_context),
):
    require_roles(user, {"viewer", "operator", "admin"})
    cluster = must_get_cluster(db, cluster_id, expected_kind="es")
    return run_es_query(cluster, index=payload.index, query=payload.query, size=payload.size)


@app.get("/api/clusters/{cluster_id}/es/slowlog/settings")
def es_slowlog_settings(
    cluster_id: int,
    index_pattern: str = "*",
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_user_context),
):
    require_roles(user, {"viewer", "operator", "admin"})
    cluster = must_get_cluster(db, cluster_id, expected_kind="es")
    return {"cluster_id": cluster_id, "index_pattern": index_pattern, "settings": get_es_slowlog_settings(cluster, index_pattern)}


@app.put("/api/clusters/{cluster_id}/es/slowlog/settings")
def update_es_slowlog_settings(
    cluster_id: int,
    payload: ESSlowlogConfigUpdate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_user_context),
):
    require_roles(user, {"admin"})
    cluster = must_get_cluster(db, cluster_id, expected_kind="es")
    settings = set_es_slowlog_settings(
        cluster,
        index_pattern=payload.index_pattern,
        search_warn_threshold=payload.search_warn_threshold,
        indexing_warn_threshold=payload.indexing_warn_threshold,
    )
    return {"cluster_id": cluster_id, "index_pattern": payload.index_pattern, "settings": settings}


@app.post("/api/tickets", response_model=TicketOut)
def create_ticket(
    payload: TicketCreate,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_user_context),
):
    require_roles(user, {"operator", "admin"})
    must_get_cluster(db, payload.cluster_id)
    ticket = Ticket(**payload.model_dump(), requester=user.username)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@app.get("/api/tickets", response_model=list[TicketOut])
def list_tickets(
    status: str | None = None,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_user_context),
):
    require_roles(user, {"viewer", "operator", "admin"})
    query = db.query(Ticket).order_by(Ticket.id.desc())
    if user.role == "operator":
        query = query.filter(or_(Ticket.requester == user.username, Ticket.status == "approved"))
    if status:
        query = query.filter(Ticket.status == status)
    return query.all()


@app.post("/api/tickets/{ticket_id}/review", response_model=TicketOut)
def review_ticket(
    ticket_id: int,
    payload: TicketReview,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_user_context),
):
    require_roles(user, {"admin"})
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket.status not in {"pending", "approved"}:
        raise HTTPException(status_code=400, detail="Ticket can no longer be reviewed")
    ticket.status = "approved" if payload.action == "approve" else "rejected"
    ticket.approver = user.username
    ticket.approval_note = payload.note
    db.commit()
    db.refresh(ticket)
    return ticket


@app.post("/api/commands/execute", response_model=ExecuteCommandOut)
def execute_command(
    payload: ExecuteCommandIn,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_user_context),
):
    require_roles(user, {"operator", "admin"})
    cluster = must_get_cluster(db, payload.cluster_id)

    if user.role != "admin":
        if not payload.ticket_id:
            raise HTTPException(status_code=400, detail="Non-admin must provide approved ticket")
        ticket = db.get(Ticket, payload.ticket_id)
        if not ticket or ticket.status != "approved":
            raise HTTPException(status_code=403, detail="Ticket is not approved")
        if ticket.cluster_id != payload.cluster_id or ticket.command.strip() != payload.command.strip():
            raise HTTPException(status_code=403, detail="Command mismatch with approved ticket")
    else:
        ticket = db.get(Ticket, payload.ticket_id) if payload.ticket_id else None

    try:
        result = run_redis_command(cluster, payload.command) if cluster.kind == "redis" else run_es_command(cluster, payload.command)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Command failed: {exc}") from exc

    log = CommandLog(cluster_id=cluster.id, executed_by=user.username, command=payload.command, result=result)
    db.add(log)

    if ticket:
        ticket.status = "executed"
        ticket.execution_result = result[:4000]

    db.commit()
    return ExecuteCommandOut(ok=True, result=result)


@app.get("/api/logs")
def logs(
    limit: int = 50,
    cluster_id: int | None = None,
    executed_by: str | None = None,
    keyword: str | None = None,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_user_context),
):
    require_roles(user, {"viewer", "operator", "admin"})
    query = db.query(CommandLog).order_by(CommandLog.id.desc())
    if cluster_id:
        query = query.filter(CommandLog.cluster_id == cluster_id)
    if executed_by:
        query = query.filter(CommandLog.executed_by == executed_by)
    if keyword:
        query = query.filter(or_(CommandLog.command.contains(keyword), CommandLog.result.contains(keyword)))

    rows = query.limit(min(limit, 300)).all()
    return [
        {
            "id": r.id,
            "cluster_id": r.cluster_id,
            "executed_by": r.executed_by,
            "command": r.command,
            "result": r.result,
            "created_at": r.created_at,
        }
        for r in rows
    ]
