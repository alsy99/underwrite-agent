from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.routes import cases, health, los, policies
from packages.config import get_settings
from packages.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Underwrite Agent",
    description="AI Underwriting Assistant — Agentic Fraud Investigation MVP",
    version="0.1.0",
    lifespan=lifespan,
)

_settings = get_settings()
_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
if _settings.cors_allow_all:
    _cors_kwargs: dict = {
        "allow_origins": ["*"],
        "allow_credentials": False,
    }
elif _settings.cors_origins.strip():
    _cors_kwargs = {
        "allow_origins": [o.strip() for o in _settings.cors_origins.split(",") if o.strip()],
        "allow_credentials": True,
    }
else:
    _cors_kwargs = {"allow_origins": _default_origins, "allow_credentials": True}

_origin_regex = _settings.cors_origin_regex.strip()
if _settings.cors_github_pages:
    _origin_regex = r"https://([a-zA-Z0-9-]+\.)?github\.io"
if _origin_regex:
    _cors_kwargs["allow_origin_regex"] = _origin_regex

app.add_middleware(
    CORSMiddleware,
    allow_methods=["*"],
    allow_headers=["*"],
    **_cors_kwargs,
)

app.include_router(health.router)
app.include_router(cases.router)
app.include_router(policies.router)
app.include_router(los.router)
