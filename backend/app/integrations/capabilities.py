from enum import Enum


class Capability(str, Enum):
    RECEIVE_ORDERS = "receive_orders"
    ORDER_STATUS_SYNC = "order_status_sync"
    MENU_SYNC = "menu_sync"
    ITEM_AVAILABILITY = "item_availability"
    PAYMENT_EVENTS = "payment_events"
    CREATE_PAYMENTS = "create_payments"
    REFUNDS = "refunds"
    ACCOUNTING_EXPORT = "accounting_export"
    SEND_MESSAGES = "send_messages"


class Category(str, Enum):
    FOOD_DELIVERY = "Food Delivery"
    PAYMENTS = "Payments"
    ACCOUNTING = "Accounting"
    COMMUNICATION = "Communication"
    ECOMMERCE = "E-commerce"
    RESERVATIONS = "Reservations"
    LOGISTICS = "Delivery Logistics"
    HARDWARE = "Hardware"
    OTHER = "Other"


# live = real adapter against a documented interface; mock = test double; coming_soon = declared only
STATUSES = ("live", "mock", "coming_soon")
