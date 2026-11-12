from fastapi import APIRouter

from app.ai_operations.router import router as ai_operations_router
from app.auth.router import router as auth_router
from app.core.router import router as core_router
from app.inventory.router import router as inventory_router
from app.onboarding.router import router as onboarding_router
from app.platform_admin.router import public_router as public_router, router as platform_router
from app.pos.menu_admin import router as menu_admin_router
from app.pos.menu_import import router as menu_import_router
from app.pos.cashbook import router as cashbook_router
from app.pos.kot import router as kot_router
from app.pos.table_actions import router as table_actions_router
from app.pos.accounts import router as accounts_router
from app.pos.exceptions import router as exceptions_router
from app.pos.router import router as pos_router
from app.reports.router import router as reports_router
from app.staff.router import router as staff_router
from app.tables.router import router as tables_router
from app.workforce.router import router as workforce_router

from app.billing.router import router as billing_router
from app.delivery.router import router as delivery_router
from app.integrations.router import router as integrations_router
router = APIRouter()
router.include_router(core_router)
router.include_router(auth_router)
router.include_router(pos_router)
router.include_router(cashbook_router)
router.include_router(menu_admin_router)
router.include_router(menu_import_router)
router.include_router(kot_router)
router.include_router(table_actions_router)
router.include_router(accounts_router)
router.include_router(exceptions_router)
router.include_router(reports_router)
router.include_router(ai_operations_router)
router.include_router(inventory_router)
router.include_router(workforce_router)
router.include_router(staff_router)
router.include_router(platform_router)
router.include_router(billing_router)
router.include_router(public_router)
router.include_router(tables_router)
router.include_router(onboarding_router)
router.include_router(delivery_router)
router.include_router(integrations_router)
