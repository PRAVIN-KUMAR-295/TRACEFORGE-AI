from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from backend.app.services.remediation_service import remediation_service

router = APIRouter(prefix="/api/remediation", tags=["Remediation & Human In The Loop"])


class ApproveActionRequest(BaseModel):
    investigation_id: str
    action_id: str
    approved: bool
    notes: Optional[str] = None
    approved_by: str = "DevOps Lead"


@router.post("/approve")
async def approve_remediation_action(req: ApproveActionRequest):
    """
    Processes human-in-the-loop review for an actionable recommendation.
    Enforces that production changes are NEVER executed without explicit human consent.
    """
    try:
        result = remediation_service.process_action_approval(
            investigation_id=req.investigation_id,
            action_id=req.action_id,
            approved=req.approved,
            approved_by=req.approved_by,
            notes=req.notes
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Action processing failed: {str(e)}")
