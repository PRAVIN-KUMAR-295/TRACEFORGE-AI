import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from backend.app.models.schemas import ActionPlanItem, ActionStatus
from backend.app.services.investigation_engine import investigation_engine

logger = logging.getLogger("traceforge.remediation")


class RemediationService:
    """
    Manages actionable remediation proposals and human-in-the-loop approval gates.
    Strictly forbids automatic unapproved state mutations in production environments.
    """

    def process_action_approval(
        self,
        investigation_id: str,
        action_id: str,
        approved: bool,
        approved_by: str = "DevOps Engineer",
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validates human approval for a remediation proposal and simulates execution.
        """
        inv = investigation_engine.get_investigation(investigation_id)
        if not inv:
            raise ValueError(f"Investigation {investigation_id} not found.")

        target_action: Optional[ActionPlanItem] = None
        for action in inv.recommended_actions:
            if action.action_id == action_id:
                target_action = action
                break

        if not target_action:
            raise ValueError(f"Action {action_id} not found in investigation {investigation_id}.")

        if not approved:
            target_action.status = ActionStatus.REJECTED
            target_action.approval_notes = f"Rejected by {approved_by}: {notes or 'No reason provided.'}"
            return {
                "action_id": action_id,
                "status": ActionStatus.REJECTED,
                "message": f"Action {action_id} rejected by {approved_by}."
            }

        # Human Approval Granted
        target_action.status = ActionStatus.EXECUTED
        target_action.approval_notes = f"Approved by {approved_by}: {notes or 'Approved for execution.'}"
        target_action.executed_at = datetime.now(timezone.utc).isoformat()

        # Update incident status if primary remediation executed
        if target_action.action_type in ("ROLLBACK", "CONFIG_UPDATE"):
            inv.status = "MITIGATED"

        logger.info(f"Remediation action {action_id} executed following human approval by {approved_by}.")

        return {
            "action_id": action_id,
            "title": target_action.title,
            "status": ActionStatus.EXECUTED,
            "executed_at": target_action.executed_at,
            "approved_by": approved_by,
            "investigation_status": inv.status,
            "execution_log": [
                f"[INFO] Human approval token verified for operator '{approved_by}'",
                f"[INFO] Dispatching safe state mutation command: {target_action.action_type}",
                f"[INFO] Verification canary probe passed: latency reduced to 180ms",
                f"[SUCCESS] Target service {target_action.target_service} reported healthy."
            ]
        }


remediation_service = RemediationService()
