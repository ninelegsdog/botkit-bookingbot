from aiogram import Router

from src.core.auth import AdminGate
from src.core.database import Database
from src.core.navigation import NavRegistry


def collect_routers(
    *, gate: AdminGate, nav: NavRegistry, db: Database
) -> list[Router]:
    from src.booking.handlers import create_router as booking_router
    from src.admin.handlers import create_router as admin_router

    return [
        booking_router(gate=gate, nav=nav, db=db),
        admin_router(gate=gate, nav=nav, db=db),
    ]
