"""API routers."""
from .auth import router as auth
from .health import router as health
from .jobs import router as jobs
from .system import router as system
from .uploads import router as uploads

__all__ = ["auth", "health", "jobs", "system", "uploads"]
