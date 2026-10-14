from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from backend.app.services.memory_service import memory_service

router = APIRouter(prefix="/api/memory", tags=["Persistent Incident Memory"])


class StorePostmortemRequest(BaseModel):
    incident_id: str
    title: str
    affected_service: str
    root_cause_summary: str
    resolution_strategy: str
    transferrable_fix: str
    impacted_services: List[str] = []


@router.get("/incidents")
async def get_historical_incidents():
    """
    Returns all historical incidents and stored postmortems currently indexed in FalkorDB.
    """
    try:
        return memory_service.get_all_historical_incidents()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch historical incidents: {str(e)}")


@router.get("/search")
async def search_memory(term: str = Query(..., min_length=1), service: Optional[str] = None):
    """
    Search historical incident knowledge base by symptom, error signature, or affected service.
    """
    try:
        results = memory_service.search_memory(term, service)
        return {"query": term, "service_filter": service, "matches": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Memory search failed: {str(e)}")


@router.post("/store")
async def store_postmortem(req: StorePostmortemRequest):
    """
    Persists a resolved incident postmortem into FalkorDB graph memory with its resolution node and relationships.
    """
    try:
        result = memory_service.store_postmortem(
            incident_id=req.incident_id,
            title=req.title,
            affected_service=req.affected_service,
            root_cause_summary=req.root_cause_summary,
            resolution_strategy=req.resolution_strategy,
            transferrable_fix=req.transferrable_fix,
            impacted_services=req.impacted_services
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store postmortem: {str(e)}")
