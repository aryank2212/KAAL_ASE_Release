import logging
from secrets import compare_digest

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.routers import analysis, cases, evidence, graph, health, profiles, search

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s %(name)s  %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="KAAL-ASE API",
    version="0.4.0",
    description="API for the KAAL-ASE intelligence management platform.",
)

PUBLIC_PATHS = {"/health", "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    logger.info("Database tables verified/created")


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    """Protect data routes and refuse to run them without configured auth."""
    path = request.url.path
    if request.method == "OPTIONS" or path in PUBLIC_PATHS or not path.startswith("/api/"):
        return await call_next(request)

    expected = settings.kaal_api_key.strip()
    if not expected:
        return JSONResponse(
            status_code=503,
            content={"detail": "API authentication is not configured. Set KAAL_API_KEY."},
        )

    supplied = request.headers.get("X-API-Key", "")
    if not supplied or not compare_digest(supplied, expected):
        return JSONResponse(
            status_code=401,
            headers={"WWW-Authenticate": "ApiKey"},
            content={"detail": "Missing or invalid API key."},
        )
    return await call_next(request)


origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)

app.include_router(health.router)
app.include_router(cases.router, prefix="/api/v1", tags=["cases"])
app.include_router(profiles.router, prefix="/api/v1", tags=["profiles"])
app.include_router(evidence.router, prefix="/api/v1", tags=["evidence"])
app.include_router(search.router, prefix="/api/v1", tags=["search"])
app.include_router(graph.router, prefix="/api/v1", tags=["graph"])
app.include_router(analysis.router, prefix="/api/v1", tags=["analysis"])
