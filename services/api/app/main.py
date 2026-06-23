import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import analysis, cases, evidence, graph, health, profiles, search

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s %(name)s  %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="KAAL-ASE API",
    version="0.3.0",
    description="MVP API for the KAAL-ASE intelligence management platform.",
)

@app.on_event("startup")
def on_startup() -> None:
    init_db()
    logger.info("Database tables verified/created")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(cases.router, prefix="/api/v1", tags=["cases"])
app.include_router(profiles.router, prefix="/api/v1", tags=["profiles"])
app.include_router(evidence.router, prefix="/api/v1", tags=["evidence"])
app.include_router(search.router, prefix="/api/v1", tags=["search"])
app.include_router(graph.router, prefix="/api/v1", tags=["graph"])
app.include_router(analysis.router, prefix="/api/v1", tags=["analysis"])

