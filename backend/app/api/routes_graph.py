from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from backend.app.database.falkordb_client import falkor_client
from backend.app.models.schemas import CypherExecuteRequest, CypherExecuteResponse, GraphTopologyResponse

router = APIRouter(prefix="/api/graph", tags=["Graph Database"])


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
    Returns column names, result rows, execution time, and active engine.
    """
    try:
        res = falkor_client.execute_cypher(req.query, req.params)
        if res.get("error"):
            raise HTTPException(status_code=400, detail=f"Cypher execution error: {res['error']}")
        return CypherExecuteResponse(
            query=req.query,
            results=[dict(zip(res["columns"], row)) if isinstance(row, list) else {"data": row} for row in res["rows"]],
            columns=res["columns"],
            row_count=res["row_count"],
            execution_time_ms=res["execution_time_ms"],
            engine=res["engine"]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cypher execution error: {str(e)}")


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
