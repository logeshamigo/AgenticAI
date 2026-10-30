"""Self-contained Article 04 demonstration. Python 3.10+, no dependencies."""
from dataclasses import dataclass, field

REPORT = {
    "source": "approved_warehouse", "metric": "net_revenue",
    "periods": ("Q1", "Q2"),
    "segments": {"Retail": (600, 540), "Wholesale": (400, 380)},
}

@dataclass
class Run:
    plan: list[str] = field(default_factory=lambda: ["primary", "analyze", "summarize"])
    attempts: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)
    analysis: dict = field(default_factory=dict)
    summary: str = ""
    status: str = "running"
    events: list[str] = field(default_factory=list)
    steps: int = 0
    replans: int = 0
    max_steps: int = 7
    backup_allowed: bool = True
    approval_needed: bool = False
    approved: bool = False


def verified(s: Run) -> bool:
    r = s.evidence
    if (not r or r.get("source") != "approved_warehouse"
            or r.get("metric") != "net_revenue"
            or r.get("periods") != ("Q1", "Q2")
            or not s.summary or not s.analysis):
        return False
    before = sum(v[0] for v in r["segments"].values())
    after = sum(v[1] for v in r["segments"].values())
    declines = {k: v[0] - v[1] for k, v in r["segments"].items()}
    return (before > 0 and s.analysis["before"] == before
            and s.analysis["after"] == after
            and s.analysis["percent"] == round(100 * (after - before) / before, 1)
            and s.analysis["largest"] == max(declines, key=declines.get)
            and s.analysis["largest"] in s.summary
            and "Root cause unverified" in s.summary
            and r["source"] in s.summary)


def action(step: str, s: Run):
    if step == "primary":
        raise TimeoutError("Primary API unavailable")
    if step == "backup":
        if not s.backup_allowed:
            raise PermissionError("Backup not authorized")
        return REPORT.copy()
    if step == "analyze":
        rows = s.evidence["segments"]
        before, after = (sum(v[i] for v in rows.values()) for i in (0, 1))
        declines = {k: v[0] - v[1] for k, v in rows.items()}
        return {"before": before, "after": after,
                "percent": round(100 * (after - before) / before, 1),
                "largest": max(declines, key=declines.get)}
    if step == "summarize":
        return (f"Net revenue change: {s.analysis['percent']}%; "
                f"largest segment decline: {s.analysis['largest']}. "
                "Root cause unverified. Source: approved_warehouse.")
    raise ValueError("Unknown operation")


def execute(s: Run) -> Run:
    if s.status == "awaiting_approval" and s.approved:
        s.status = "running"  # Resume requires an external trusted approval
    while s.status == "running":
        if verified(s):
            s.status = ("awaiting_approval" if s.approval_needed and not s.approved
                        else "completed")
            break
        if s.steps >= s.max_steps:
            s.status = "budget_exhausted"
            break
        if not s.plan:
            s.status = "blocked"
            break
        step = s.plan[0]
        s.steps += 1
        s.attempts[step] = s.attempts.get(step, 0) + 1
        try:
            result = action(step, s)
            if step in ("primary", "backup"):
                if (result["source"] != "approved_warehouse"
                        or result["metric"] != "net_revenue"
                        or result["periods"] != ("Q1", "Q2")):
                    raise ValueError("Incomparable evidence")
                s.evidence = result
            elif step == "analyze":
                s.analysis = result
            else:
                s.summary = result
        except TimeoutError:
            if s.attempts[step] < 2:
                s.events.append("retry")
            elif step == "primary" and s.backup_allowed and s.replans < 1:
                s.plan[0] = "backup"  # Replan, not retry
                s.replans += 1
                s.events.append("replan")
            else:
                s.status = "blocked"
        except (PermissionError, ValueError, KeyError, ZeroDivisionError):
            s.status = "blocked"
        else:
            s.plan.pop(0)
            if s.plan:
                s.events.append("continue")
    s.events.append(s.status)
    return s


if __name__ == "__main__":
    for label, config in [
        ("Recovered", {}),
        ("No fallback", {"backup_allowed": False}),
        ("Low budget", {"max_steps": 3}),
        ("Approval", {"approval_needed": True}),
    ]:
        s = execute(Run(**config))
        print(label, s.status, s.steps, s.events)
        if label == "Approval":
            s.approved = True  # In reality: verified human authorization
            print("Resumed", execute(s).status)
