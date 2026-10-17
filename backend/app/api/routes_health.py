import time
from fastapi import APIRouter
from backend.app.config import settings
from backend.app.database.falkordb_client import falkor_client
from backend.app.services.llm_provider import llm_provider

router = APIRouter(prefix="/api/health", tags=["System Health"])

start_time = time.time()


@router.get("")
async def get_health_status():
    """
    Returns system status, active FalkorDB graph engine, and configured LLM provider.
    """
    uptime_sec = round(time.time() - start_time, 1)
    topo = falkor_client.get_topology()

    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "uptime_seconds": uptime_sec,
        "falkordb": {
            "is_live_connected": falkor_client.is_connected,
            "engine_mode": falkor_client.engine_type,
            "host": falkor_client.host,
            "port": falkor_client.port,
            "graph_name": settings.falkordb_graph_name,
            "total_nodes": topo["total_nodes"],
            "total_edges": topo["total_edges"],
            "connection_error": getattr(falkor_client, "connection_error", None),
        },
        "llm": {
            "provider": llm_provider.provider,
            "model": llm_provider.model,
            "is_demo_mode": settings.demo_mode or llm_provider.provider == "demo",
        }
    }
