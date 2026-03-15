import datetime as dt
from typing import Optional
from sqlalchemy import String, Integer, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def now():
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Department(Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Surgery(Base):
    __tablename__ = "surgeries"
    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"))
    name: Mapped[str] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    department: Mapped["Department"] = relationship()


class Item(Base):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    category: Mapped[str] = mapped_column(String(50), default="일반", index=True)
    storage: Mapped[str] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(50), index=True, default="멸균완료/보관")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    set_instances: Mapped[list["SetInstance"]] = relationship(back_populates="set_item")


class SetInstance(Base):
    __tablename__ = "set_instances"
    id: Mapped[int] = mapped_column(primary_key=True)
    set_item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    serial_no: Mapped[int] = mapped_column(Integer, index=True)
    memo: Mapped[Optional[str]] = mapped_column(String(200), default="", nullable=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    set_item: Mapped["Item"] = relationship(back_populates="set_instances")


class ProcedureDefault(Base):
    __tablename__ = "procedure_defaults"
    id: Mapped[int] = mapped_column(primary_key=True)
    surgery_id: Mapped[int] = mapped_column(ForeignKey("surgeries.id"))
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    surgery: Mapped["Surgery"] = relationship()
    item: Mapped["Item"] = relationship()


class UsageRecord(Base):
    __tablename__ = "usage_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    case_date: Mapped[dt.date] = mapped_column(Date, index=True)
    room_no: Mapped[int] = mapped_column(Integer, index=True)
    surgery_order: Mapped[int] = mapped_column(Integer, index=True)
    department: Mapped[str] = mapped_column(String(50), index=True)
    surgery_name: Mapped[str] = mapped_column(String(100), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    set_instance_id: Mapped[Optional[int]] = mapped_column(ForeignKey("set_instances.id"), nullable=True, index=True)
    is_contaminated: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_urgent: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(30), index=True, default="사용중")
    used_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=now)
    returned_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    washed_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sterilized_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_date: Mapped[Optional[dt.date]] = mapped_column(Date, nullable=True, index=True)
    csr_received_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    process_started_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    process_due_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    machine_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    machine_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    process_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    release_requested_at: Mapped[Optional[dt.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    item: Mapped["Item"] = relationship()
    set_instance: Mapped[Optional["SetInstance"]] = relationship()


class MachineConfig(Base):
    __tablename__ = "machine_configs"
    id: Mapped[int] = mapped_column(primary_key=True)
    machine_key: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    machine_name: Mapped[str] = mapped_column(String(100))
    process_type: Mapped[str] = mapped_column(String(20), index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
