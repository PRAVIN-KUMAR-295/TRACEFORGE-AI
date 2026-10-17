import asyncio
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from backend.app.config import settings
from backend.app.database.falkordb_client import FalkorDBClient, falkor_client
from backend.app.models.schemas import CypherExecuteRequest, CypherExecuteResponse, GraphTopologyResponse

router = APIRouter(prefix="/api/graph", tags=["Graph Database"])

# Guardrail limits for public demo graph query endpoint
MAX_CYPHER_QUERY_LENGTH = 4096
MAX_CYPHER_RESULT_ROWS = 500
MAX_CYPHER_TIMEOUT_SECONDS = 10.0


@router.get("/topology", response_model=GraphTopologyResponse)
async def get_graph_topology():
    """
    Returns complete topology of nodes and edges currently in FalkorDB for the interactive Graph Explorer.
    """
    try:
        data = falkor_client.get_topology()
        return GraphTopologyResponse(
            nodes=data["nodes"],
            edges=data["edges"],
            total_nodes=data["total_nodes"],
            total_edges=data["total_edges"],
            query_time_ms=data["query_time_ms"],
            engine_type=data["engine_type"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch topology: {str(e)}")


@router.get("/subgraph/{node_id}")
async def get_subgraph(node_id: str, depth: int = 2):
    """
    Returns localized neighborhood subgraph centered at a given node.
    """
    try:
        return falkor_client.get_node_subgraph(node_id, depth)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch subgraph for {node_id}: {str(e)}")


@router.post("/cypher", response_model=CypherExecuteResponse)
async def execute_cypher(req: CypherExecuteRequest):
    """
    Executes an OpenCypher query directly against FalkorDB.
    Enforces read-only safety, bounds query length, bounds execution time, and caps result rows
    to guarantee the public demo endpoint cannot be abused for data mutation or resource exhaustion.
    Preserves all read-only Cypher query capabilities for demo investigation and graph explorer.
    """
    clean_query = req.query.strip()
    if not clean_query:
        raise HTTPException(status_code=400, detail="Cypher query cannot be empty.")

    if len(clean_query) > MAX_CYPHER_QUERY_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"Cypher query exceeds maximum length of {MAX_CYPHER_QUERY_LENGTH} characters."
        )

    if not FalkorDBClient._is_read_only_query(clean_query):
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Only read-only Cypher queries (MATCH, RETURN, WITH, WHERE) are permitted in public demo mode."
        )

    try:
        timeout_seconds = min(float(getattr(settings, "falkordb_timeout", 5)), MAX_CYPHER_TIMEOUT_SECONDS)
        res = await asyncio.wait_for(
            asyncio.to_thread(falkor_client.execute_cypher, clean_query, req.params, True),
            timeout=timeout_seconds
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=408,
            detail=f"Query execution timed out after {timeout_seconds:.1f} seconds."
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cypher execution error: {str(e)}")

    if res.get("error"):
        raise HTTPException(status_code=400, detail=f"Cypher execution error: {res['error']}")

    bounded_rows = res["rows"][:MAX_CYPHER_RESULT_ROWS]
    columns = res["columns"]
    formatted_results = [
        dict(zip(columns, row)) if isinstance(row, list) else {"data": row}
        for row in bounded_rows
    ]

    return CypherExecuteResponse(
        query=req.query,
        results=formatted_results,
        columns=columns,
        row_count=len(formatted_results),
        execution_time_ms=res["execution_time_ms"],
        engine=res["engine"]
    )




@router.post("/reconnect")
async def reconnect_falkordb():
    """
    Attempts to connect or reconnect to the configured live FalkorDB instance.
    If connected, automatically ensures the graph is idempotently seeded.
    """
    is_live = falkor_client.reconnect()
    if is_live:
        from backend.app.database.seed_data import seed_graph_database
        seed_res = seed_graph_database(falkor_client)
        return {
            "status": "connected",
            "engine_mode": falkor_client.engine_type,
            "host": falkor_client.host,
            "port": falkor_client.port,
            "seeding": seed_res,
        }
    return {
        "status": "fallback_in_memory",
        "engine_mode": falkor_client.engine_type,
        "connection_error": falkor_client.connection_error,
    }
