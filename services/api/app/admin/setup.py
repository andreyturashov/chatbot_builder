from fastapi import FastAPI
from sqladmin import Admin
from sqlalchemy.ext.asyncio import AsyncEngine

from app.admin.views import BotAdmin, UserAdmin
from app.core.config import settings


def setup_admin(app: FastAPI, engine: AsyncEngine) -> Admin | None:
    """Initialize SQLAdmin dashboard mounted on /admin."""
    if not settings.ADMIN_ENABLED:
        return None

    admin = Admin(
        app=app,
        engine=engine,
        title=f"{settings.APP_NAME} Admin",
        base_url="/admin",
    )
    admin.add_view(UserAdmin)
    admin.add_view(BotAdmin)
    return admin
