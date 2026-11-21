"""Local policy example for a synthetic finance dataset."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Request:
    actor: str       # supplied by the authenticated transport
    grant_id: str
    workflow: str
    tenant: str
    resource: str
    action: str


@dataclass(frozen=True)
class Grant:
    subject: str
    actor: str
    audience: str
    workflow: str
    tenant: str
    resource: str
    action: str
    expires_at: int


class FinanceAPI:
    audience = "finance-api"

    def __init__(self) -> None:
        self.grants: dict[str, Grant] = {}
        self.active_access: set[tuple[str, str, str, str]] = set()
        self.revoked: set[str] = set()
        self.audit: list[dict] = []

    def read(self, request: Request, *, now: int) -> tuple[float | None, str]:
        """Use the endpoint's trusted clock. Return a result and local reason."""
        grant = self.grants.get(request.grant_id)
        reason = self._decision(request, grant, now)
        self.audit.append({
            "at": now,
            "subject": grant.subject if grant else None,
            "actor": request.actor,
            "grant_id": request.grant_id,
            "workflow": request.workflow,
            "tenant": request.tenant,
            "resource": request.resource,
            "action": request.action,
            "decision": reason,
        })
        # Fixed synthetic aggregate stands in for a query after authorization.
        return (-4.0 if reason == "allowed" else None, reason)

    def _decision(self, request: Request, grant: Grant | None, now: int) -> str:
        if grant is None:
            return "unknown_grant"
        if request.actor != grant.actor:
            return "actor_mismatch"
        if grant.audience != self.audience:
            return "wrong_audience"
        if now >= grant.expires_at:
            return "expired"
        if request.grant_id in self.revoked:
            return "revoked"
        if request.workflow != grant.workflow:
            return "wrong_workflow"
        if request.tenant != grant.tenant:
            return "wrong_tenant"
        if request.resource != grant.resource:
            return "wrong_resource"
        if request.action != "read_aggregate" or request.action != grant.action:
            return "wrong_action"
        access = (grant.subject, grant.tenant, grant.resource, grant.action)
        if access not in self.active_access:
            return "subject_access_removed"
        return "allowed"
