from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # redis | es
    host: Mapped[str] = mapped_column(String(128), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    password: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id"), nullable=False)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    requester: Mapped[str] = mapped_column(String(64), nullable=False)
    approver: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approval_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    cluster: Mapped[Cluster] = relationship()


class CommandLog(Base):
    __tablename__ = "command_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id"), nullable=False)
    executed_by: Mapped[str] = mapped_column(String(64), nullable=False)
    command: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    cluster: Mapped[Cluster] = relationship()


class CommandTemplate(Base):
    __tablename__ = "command_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # redis | es
    command: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
