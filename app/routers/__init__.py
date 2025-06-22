"""
Kiddos - API Routers
Clean separation of concerns for API endpoints
"""

from .auth import router as auth_router
from .user import router as user_router
from .children import router as children_router
from .content import router as content_router
from .credits import router as credits_router
from .dashboard import router as dashboard_router
from .admin import router as admin_router
from .system import router as system_router
from .images import router as images_router
from .fixed_content import router as fixed_content_router

__all__ = [
    "auth_router",
    "user_router",
    "children_router",
    "content_router",
    "credits_router",
    "dashboard_router",
    "admin_router",
    "system_router",
    "images_router",
    "fixed_content_router",
]
