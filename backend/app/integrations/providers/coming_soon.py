"""Declared only. These have no working code and claim no capabilities."""
from app.integrations.base_provider import IntegrationProvider, ProviderInfo
from app.integrations.capabilities import Category
from app.integrations.registry import IntegrationRegistry

PLANNED = (
    ("cashfree", "Cashfree", Category.PAYMENTS, "Payments", ("Payment events", "Refunds")),
    ("phonepe", "PhonePe Payment Gateway", Category.PAYMENTS, "Payments", ("Payment events", "Refunds")),
    ("tally", "Tally", Category.ACCOUNTING, "Accounting export", ("Sales voucher export",)),
    ("zoho_books", "Zoho Books", Category.ACCOUNTING, "Accounting", ("Invoice sync",)),
    ("whatsapp", "WhatsApp Business Platform", Category.COMMUNICATION, "Messaging", ("Approved template notifications",)),
    ("sms", "SMS provider", Category.COMMUNICATION, "Messaging", ("Order notifications",)),
    ("shopify", "Shopify", Category.ECOMMERCE, "E-commerce", ("Order import", "Menu sync")),
    ("woocommerce", "WooCommerce", Category.ECOMMERCE, "E-commerce", ("Order import", "Menu sync")),
    ("swiggy", "Swiggy", Category.FOOD_DELIVERY, "Food delivery", ("Receive orders", "Menu and availability sync")),
    ("zomato", "Zomato", Category.FOOD_DELIVERY, "Food delivery", ("Receive orders", "Menu and availability sync")),
    ("ondc", "ONDC-compatible providers", Category.FOOD_DELIVERY, "Open network commerce", ("Order import",)),
)


class PlannedProvider(IntegrationProvider):
    def __init__(self, slug, name, category, blurb, planned):
        self.info = ProviderInfo(slug=slug, name=name, category=category, status="coming_soon",
                                 description=f"{blurb} integration. Not available yet.", planned_capabilities=planned)


for _row in PLANNED:
    IntegrationRegistry.register(PlannedProvider(*_row))
