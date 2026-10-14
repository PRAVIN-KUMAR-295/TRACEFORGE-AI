import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.routes_graph import router as graph_router
from backend.app.api.routes_health import router as health_router
from backend.app.api.routes_investigation import router as investigation_router
from backend.app.api.routes_memory import router as memory_router
from backend.app.api.routes_remediation import router as remediation_router
from backend.app.config import settings
from backend.app.database.falkordb_client import falkor_client
from backend.app.database.seed_data import seed_graph_database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("traceforge.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} v{settings.app_version}...")
    # Ensure graph is seeded
    seed_graph_database(falkor_client)
    logger.info("FalkorDB Graph initialized and seeded.")
    yield
    logger.info(f"Shutting down {settings.app_name}...")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="TRACEFORGE AI: AI-powered software incident investigator backed by FalkorDB graph relationships and persistent incident memory.",
    lifespan=lifespan
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(health_router)
app.include_router(investigation_router)
app.include_router(graph_router)
app.include_router(memory_router)
app.include_router(remediation_router)


@app.get("/")
async def root():
    return {
        "product": settings.app_name,
        "tagline": "AI-Powered Software Incident Investigator with FalkorDB Graph & Persistent Memory",
        "version": settings.app_version,
        "docs_url": "/docs",
        "demo_endpoint": "/api/investigations/demo",
        "topology_endpoint": "/api/graph/topology"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host=settings.api_host, port=settings.api_port, reload=True)
