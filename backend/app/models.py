from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Date,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class PlanPrice(Base):
    __tablename__ = "plan_prices"
    id: Mapped[int] = mapped_column(primary_key=True)
    plan_name: Mapped[str] = mapped_column(String(80), unique=True)
    price_inr: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    yearly_price_inr: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("5999"), server_default="5999")
    gst_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("18"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class GeneratedReport(Base):
    __tablename__ = "generated_reports"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    period: Mapped[str] = mapped_column(String(12))
    period_end: Mapped[date] = mapped_column(Date)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (UniqueConstraint("restaurant_id", "period", "period_end", name="uq_report_outlet_period_end"),)


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    number: Mapped[str] = mapped_column(String(24), unique=True)
    plan_name: Mapped[str] = mapped_column(String(80))
    outlets: Mapped[int] = mapped_column(Integer, default=1)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    gst: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(12), default="pending")
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TenantProfile(Base):
    __tablename__ = "tenant_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), unique=True, index=True)
    owner_name: Mapped[str] = mapped_column(String(120))
    mobile: Mapped[str] = mapped_column(String(16))
    address_line: Mapped[str] = mapped_column(String(300))
    city: Mapped[str] = mapped_column(String(80))
    state_code: Mapped[str] = mapped_column(String(4))
    pincode: Mapped[str] = mapped_column(String(10))
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="manager")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Restaurant(Base):
    __tablename__ = "outlets"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    state_code: Mapped[str | None] = mapped_column(String(4), nullable=True)
    tax_config: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)


class DiningTable(Base):
    __tablename__ = "dining_tables"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    floor_id: Mapped[int | None] = mapped_column(ForeignKey("floors.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(48))
    seats: Mapped[int] = mapped_column(Integer, default=2)
    x: Mapped[float] = mapped_column(default=0)
    y: Mapped[float] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(24), default="FREE")
    __table_args__ = (UniqueConstraint("restaurant_id", "name"),)


class MenuCategory(Base):
    __tablename__ = "menu_categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(default=0)


class MenuItem(Base):
    __tablename__ = "menu_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("menu_categories.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(160))
    sku: Mapped[str] = mapped_column(String(64))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=Decimal("0"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("restaurant_id", "sku"),)


class MenuOption(Base):
    """A size/variant (replaces the item price) or an add-on (added to the item price)."""
    __tablename__ = "menu_options"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), index=True)
    kind: Mapped[str] = mapped_column(String(8))
    name: Mapped[str] = mapped_column(String(80))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    loyalty_points: Mapped[int] = mapped_column(default=0)
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
    anniversary: Mapped[date | None] = mapped_column(Date, nullable=True)
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    address: Mapped[str | None] = mapped_column(String(400), nullable=True)


class RestaurantOrder(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    table_id: Mapped[int | None] = mapped_column(ForeignKey("dining_tables.id"), nullable=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    order_number: Mapped[str] = mapped_column(String(48))
    idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    order_type: Mapped[str] = mapped_column(String(24), default="dine_in")
    contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(String(400), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open")
    source: Mapped[str] = mapped_column(String(32), default="built_in")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    tax_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    discount_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    discount_type: Mapped[str | None] = mapped_column(String(8), nullable=True)
    discount_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), server_default="0")
    discount_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    service_charge: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), server_default="0")
    service_charge_waived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    round_off: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0"), server_default="0")
    tip: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), server_default="0")
    covers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remark: Mapped[str | None] = mapped_column(String(300), nullable=True)
    staff_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    complimentary_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    items: Mapped[list["OrderItem"]] = relationship(cascade="all, delete-orphan")

    @property
    def active_items(self) -> list["OrderItem"]:
        return [i for i in self.items if i.status == "active"]

    __table_args__ = (
        UniqueConstraint("tenant_id", "order_number"),
        UniqueConstraint("tenant_id", "idempotency_key"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"))
    item_name: Mapped[str] = mapped_column(String(160))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(6, 3))
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    notes: Mapped[str | None] = mapped_column(String(300), nullable=True)
    kot_no: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    complimentary: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    status: Mapped[str] = mapped_column(String(16), default="active", server_default="active")
    cancel_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    variant_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    addons: Mapped[list | None] = mapped_column(JSON, nullable=True)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    method: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), default="recorded")
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (
        UniqueConstraint("tenant_id", "order_id", "idempotency_key", name="uq_payments_tenant_order_idempotency"),
    )


class OperationalEvent(Base):
    __tablename__ = "operational_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    table_id: Mapped[int | None] = mapped_column(ForeignKey("dining_tables.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(48))
    source: Mapped[str] = mapped_column(String(32), default="native_pos")
    idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    evidence_source: Mapped[str] = mapped_column(String(32), default="staff")
    evidence_status: Mapped[str] = mapped_column(String(24), default="confirmed")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    processing_status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    processing_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (UniqueConstraint("tenant_id", "source", "idempotency_key"),)


class Camera(Base):
    __tablename__ = "cameras"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    source_type: Mapped[str] = mapped_column(String(16), default="rtsp")
    stream_url_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    recording_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference_image_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    floor_id: Mapped[int | None] = mapped_column(ForeignKey("floors.id"), nullable=True, index=True)
    regions: Mapped[list] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Observation(Base):
    __tablename__ = "observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("cameras.id"), index=True)
    table_id: Mapped[int | None] = mapped_column(ForeignKey("dining_tables.id"), nullable=True)
    observation_type: Mapped[str] = mapped_column(String(48))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)
    validation_status: Mapped[str] = mapped_column(String(24), default="unvalidated")
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class InventoryItem(Base):
    __tablename__ = "inventory_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    sku: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(160))
    unit: Mapped[str] = mapped_column(String(24), default="unit")
    quantity_on_hand: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal("0"))
    reorder_level: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=Decimal("0"))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    __table_args__ = (UniqueConstraint("restaurant_id", "sku"),)


class StockMovement(Base):
    __tablename__ = "stock_movements"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    inventory_item_id: Mapped[int] = mapped_column(ForeignKey("inventory_items.id"))
    quantity_delta: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    movement_type: Mapped[str] = mapped_column(String(32))
    reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class LoyaltyEntry(Base):
    __tablename__ = "loyalty_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    points_delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Employee(Base):
    __tablename__ = "employees"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    display_name: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    monthly_salary: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Shift(Base):
    __tablename__ = "shifts"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="scheduled")


class TimeEntry(Base):
    __tablename__ = "time_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    clock_in: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    clock_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)


class PayrollRun(Base):
    __tablename__ = "payroll_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="draft")
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class PayrollLine(Base):
    __tablename__ = "payroll_lines"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    payroll_run_id: Mapped[int] = mapped_column(ForeignKey("payroll_runs.id"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"))
    earnings: Mapped[dict] = mapped_column(JSON, default=dict)
    deductions: Mapped[dict] = mapped_column(JSON, default=dict)
    employer_contributions: Mapped[dict] = mapped_column(JSON, default=dict)
    gross_pay: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    net_pay: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    accountant_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Floor(Base):
    __tablename__ = "floors"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))


class OutletMembership(Base):
    __tablename__ = "outlet_memberships"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(32))
    __table_args__ = (UniqueConstraint("outlet_id", "user_id"),)


class StaffTask(Base):
    __tablename__ = "staff_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    table_id: Mapped[int | None] = mapped_column(ForeignKey("dining_tables.id"), nullable=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    task_type: Mapped[str] = mapped_column(String(48))
    target_role: Mapped[str] = mapped_column(String(32), index=True)
    assigned_employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    title: Mapped[str] = mapped_column(String(180))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    entitlements: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("subscription_plans.id"))
    status: Mapped[str] = mapped_column(String(24), default="trial")
    billing_cycle: Mapped[str] = mapped_column(String(8), default="monthly", server_default="monthly")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FestivalCalendar(Base):
    __tablename__ = "festival_calendar"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int | None] = mapped_column(ForeignKey("outlets.id"), nullable=True, index=True)
    state_code: Mapped[str | None] = mapped_column(String(4), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String(300), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Refund(Base):
    __tablename__ = "refunds"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    payment_id: Mapped[int | None] = mapped_column(ForeignKey("payments.id"), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reason: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(24), default="recorded")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (
        UniqueConstraint("tenant_id", "order_id", "idempotency_key", name="uq_refunds_tenant_order_idempotency"),
    )


class PaymentOrder(Base):
    """One Razorpay order raised to pay a subscription invoice."""
    __tablename__ = "payment_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    invoice_id: Mapped[int] = mapped_column(ForeignKey("invoices.id"), index=True)
    razorpay_order_id: Mapped[str] = mapped_column(String(40), unique=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    amount_paise: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12), default="created")  # created | paid | duplicate
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AutoRenewal(Base):
    """A Razorpay Subscription that charges the owner's mandate every period."""
    __tablename__ = "autorenewals"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    razorpay_subscription_id: Mapped[str] = mapped_column(String(40), unique=True)
    billing_cycle: Mapped[str] = mapped_column(String(8))
    amount_paise: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="created")  # created | authenticated | active | halted | cancelled | completed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class RazorpayPlan(Base):
    """Razorpay plans are fixed-amount, so one is created per (cycle, amount) and reused."""
    __tablename__ = "razorpay_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    billing_cycle: Mapped[str] = mapped_column(String(8))
    amount_paise: Mapped[int] = mapped_column(Integer)
    razorpay_plan_id: Mapped[str] = mapped_column(String(40))


class PasswordResetToken(Base):
    """Single-use reset link; only the hash of the token is stored. Not tenant-scoped: used before sign-in."""
    __tablename__ = "password_reset_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class ReminderLog(Base):
    """Every renewal reminder we email to a restaurant owner. Read only by platform admin, so not tenant-scoped."""
    __tablename__ = "reminder_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(10))  # auto | manual
    days_left: Mapped[int | None] = mapped_column(Integer, nullable=True)
    to_email: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20))  # sent | failed | not_configured
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class PettyCashEntry(Base):
    __tablename__ = "petty_cash_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    business_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(4))  # in | out
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reason: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    pay_method: Mapped[str] = mapped_column(String(16), default="cash", server_default="cash")
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class CustomerLedgerEntry(Base):
    """Customer account: a debit is a bill put on account, a credit is money the customer paid back."""
    __tablename__ = "customer_ledger"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    kind: Mapped[str] = mapped_column(String(6))  # debit | credit
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    method: Mapped[str | None] = mapped_column(String(16), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(200), nullable=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class DayClose(Base):
    __tablename__ = "day_closes"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    business_date: Mapped[date] = mapped_column(Date)
    opening_cash: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    cash_sales: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    petty_in: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    petty_out: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    expected_cash: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    counted_cash: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    difference: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    closed_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (UniqueConstraint("restaurant_id", "business_date", name="uq_day_close_outlet_date"),)


class DeliveryChannel(Base):
    """One inbound webhook per outlet and provider. Looked up by token hash before any tenant is known, so no RLS."""
    __tablename__ = "delivery_channels"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    provider: Mapped[str] = mapped_column(String(24))
    label: Mapped[str | None] = mapped_column(String(80), nullable=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    secret_ciphertext: Mapped[str] = mapped_column(String(300))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class DeliveryOrder(Base):
    __tablename__ = "delivery_orders"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("delivery_channels.id"), index=True)
    provider: Mapped[str] = mapped_column(String(24))
    external_id: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16))
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True)
    aggregator_total: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    commission: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"), server_default="0")
    total_mismatch: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    unmatched: Mapped[list | None] = mapped_column(JSON, nullable=True)
    raw: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    __table_args__ = (UniqueConstraint("channel_id", "external_id"),)


class IntegrationConnection(Base):
    """A restaurant's connection to one trusted provider adapter. Resolved by webhook token hash before any
    tenant is known, so this table has no RLS; every query must filter by tenant_id."""
    __tablename__ = "integration_connections"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    restaurant_id: Mapped[int | None] = mapped_column(ForeignKey("outlets.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending|connected|error|disabled
    credentials_ciphertext: Mapped[str] = mapped_column(Text, default="")
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    webhook_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    circuit_open_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, onupdate=now_utc)
    __table_args__ = (UniqueConstraint("tenant_id", "restaurant_id", "provider", name="uq_integration_scope_provider"),)


class IntegrationEvent(Base):
    __tablename__ = "integration_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    connection_id: Mapped[int] = mapped_column(ForeignKey("integration_connections.id"), index=True)
    provider: Mapped[str] = mapped_column(String(40))
    event_type: Mapped[str] = mapped_column(String(80))
    external_event_id: Mapped[str] = mapped_column(String(120))
    payload: Mapped[dict] = mapped_column(JSON)
    processing_status: Mapped[str] = mapped_column(String(16), default="received")  # received|processed|failed|ignored
    retry_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("connection_id", "external_event_id", name="uq_integration_event_once"),)


class IntegrationSyncJob(Base):
    """Outbox: jobs are written in the same transaction as the business change and executed by a worker."""
    __tablename__ = "integration_sync_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    connection_id: Mapped[int] = mapped_column(ForeignKey("integration_connections.id"), index=True)
    operation: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)  # pending|running|succeeded|dead
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    error_message: Mapped[str | None] = mapped_column(String(300), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    __table_args__ = (UniqueConstraint("connection_id", "idempotency_key", name="uq_integration_job_idem"),)


class IntegrationExternalId(Base):
    __tablename__ = "integration_external_ids"
    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), index=True)
    connection_id: Mapped[int] = mapped_column(ForeignKey("integration_connections.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(24))  # menu_item, category, order, customer, ...
    local_id: Mapped[int] = mapped_column(Integer)
    external_id: Mapped[str] = mapped_column(String(120))
    __table_args__ = (
        UniqueConstraint("connection_id", "entity_type", "local_id", name="uq_integration_map_local"),
        UniqueConstraint("connection_id", "entity_type", "external_id", name="uq_integration_map_external"),
    )
