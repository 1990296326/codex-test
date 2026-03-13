from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class UserContext(BaseModel):
    username: str
    role: str = Field(pattern="^(viewer|operator|admin)$")


class ClusterCreate(BaseModel):
    name: str
    kind: str = Field(pattern="^(redis|es)$")
    host: str
    port: int
    username: str | None = None
    password: str | None = None


class ClusterOut(ClusterCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class TicketCreate(BaseModel):
    title: str
    description: str
    cluster_id: int
    command: str


class TicketReview(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    note: str | None = None


class TicketOut(BaseModel):
    id: int
    title: str
    description: str
    cluster_id: int
    command: str
    status: str
    requester: str
    approver: str | None
    approval_note: str | None
    execution_result: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExecuteCommandIn(BaseModel):
    cluster_id: int
    command: str
    ticket_id: int | None = None


class ExecuteCommandOut(BaseModel):
    ok: bool
    result: str


class ClusterHealthOut(BaseModel):
    cluster_id: int
    summary: dict[str, Any]


class RedisSlowlogConfigUpdate(BaseModel):
    slower_than_us: int | None = Field(default=None, ge=0)
    max_len: int | None = Field(default=None, ge=1)


class ESQueryIn(BaseModel):
    index: str
    query: dict[str, Any]
    size: int = Field(default=20, ge=1, le=200)


class ESSlowlogConfigUpdate(BaseModel):
    index_pattern: str = "*"
    search_warn_threshold: str | None = None
    indexing_warn_threshold: str | None = None


class CommandTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    kind: str = Field(pattern="^(redis|es)$")
    command: str = Field(min_length=1)
    description: str | None = None


class CommandTemplateOut(CommandTemplateCreate):
    id: int
    created_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class CommandPrecheckIn(BaseModel):
    cluster_id: int
    command: str
