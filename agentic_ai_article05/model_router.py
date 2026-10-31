"""Article 05: executable model-policy and validation demo (Python 3.9+, stdlib).

No live LLM, source system, or benchmarks. All model calls are controlled test
fixtures; the authorized-source adapter reads a separate, access-checked JSON
record to imitate a production trusted reporting API/database.
"""
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Callable, FrozenSet, Mapping, Optional

HERE = Path(__file__).resolve().parent
REPORT_ID = "quarterly-revenue-FY2026"
ACCOUNT = "finance-research"
DATA_CLASS = "internal_financial"


class InvalidOutput(ValueError):
    """A model response failed structural, semantic or evidence checks."""


class TransientProviderError(Exception):
    """Simulated provider timeout, which can justify a bounded retry."""


class PolicyViolation(Exception):
    """An action is not authorized, or required policy input is missing.

    Switching models cannot bypass it."""


class RouterFailure(Exception):
    """Controlled router outcome that the Decision Controller may handle.

    Deliberately NOT a RuntimeError: an unexpected RuntimeError from application
    code is a bug and must not be converted into a normal `blocked` result."""


class NoEligibleModel(RouterFailure):
    """No candidate satisfies the mandatory policy filter."""


class NoValidOutput(RouterFailure):
    """Every eligible candidate was tried and none produced a valid response."""


class AuthorizedFinancialSource:
    """Stand-in for a trusted source API, separate from model output fixtures."""

    def fetch(self, report_id: str, account_id: str) -> dict:
        # Authorization is checked by the source-side adapter, not the model.
        if account_id != ACCOUNT:
            raise PolicyViolation("Account not authorized for the financial report")
        document = json.loads((HERE / "fixtures" / "approved_financial_report.json").read_text())
        if document["account_id"] != account_id or document["report_id"] != report_id:
            raise PolicyViolation("Report not accessible to this account")
        # This local JSON is a fixture for an approved DB/API, NOT a model answer key.
        return document


@dataclass(frozen=True)
class ModelProfile:
    name: str
    stages: FrozenSet[str]
    data_classes: FrozenSet[str]
    structured: bool
    context_chars: int
    p95_latency_ms: int
    quality_approved: bool


# These are illustrative policy metadata, not measured provider benchmarks.
PROFILES = {
    "small_structured": ModelProfile("small_structured", frozenset({"extract"}),
        frozenset({DATA_CLASS}), True, 4000, 450, True),
    "general_structured": ModelProfile("general_structured", frozenset({"extract"}),
        frozenset({DATA_CLASS}), True, 10000, 700, True),
    "general_backup": ModelProfile("general_backup", frozenset({"extract", "summarize"}),
        frozenset({DATA_CLASS}), True, 16000, 950, True),
    "reasoning": ModelProfile("reasoning", frozenset({"interpret"}),
        frozenset({DATA_CLASS}), True, 16000, 1100, True),
    "general": ModelProfile("general", frozenset({"summarize"}),
        frozenset({DATA_CLASS}), True, 10000, 650, True),
}

# Preference is not permission; the profile filter is mandatory before invocation.
ROUTES = {
    "extract": ("small_structured", "general_structured", "general_backup"),
    "interpret": ("reasoning",),
    "summarize": ("general", "general_backup"),
}


def eligible(model: ModelProfile, stage: str, data_class: str, context_chars: int,
             max_p95_ms: int = 1200) -> bool:
    return (stage in model.stages and data_class in model.data_classes
            and model.structured and model.quality_approved
            and context_chars <= model.context_chars
            and model.p95_latency_ms <= max_p95_ms)


def expected_change(record: Mapping) -> float:
    q1, q2 = record["q1"], record["q2"]
    if type(q1) is not int or type(q2) is not int or q1 <= 0:
        raise InvalidOutput("Revenue must be integers with a positive baseline")
    return round((q2 - q1) / q1 * 100, 1)


def format_summary(pct: float) -> str:
    """The ONLY approved summary wording, derived from the verified percentage.

    Used (a) to assemble the simulated model's good response and (b) by the
    validator as an allowlist. It does not fetch or verify data itself.
    """
    verb = "decreased" if pct < 0 else ("increased" if pct > 0 else "was unchanged")
    return (f"Net revenue {verb} {abs(pct):.1f}%; cause not established."
            if pct else "Net revenue was unchanged (0.0%); cause not established.")


# The simulated extraction is a *separate* model response fixture.
BASE_EXTRACTION = {
    "report_id": REPORT_ID, "source": "approved_warehouse", "metric": "net_revenue",
    "fiscal_period": "FY2026-Q1_to_FY2026-Q2", "currency": "USD",
    "unit": "thousands", "q1": 1000, "q2": 920,
}


# The only interpretation wording this demo approves (verified data cannot show a cause).
APPROVED_INTERPRETATION = "Quarterly totals do not establish root cause."


def mock_model(model: str, stage: str, context: Mapping, attempt: int) -> str:
    """Deterministic model-response fixtures; NO real provider inference."""
    if stage == "extract":
        result = dict(BASE_EXTRACTION)
        if model == "small_structured":
            result["q1"] = "1000"  # invalid schema
        elif model == "general_structured":
            result["q2"] = 902  # schema-valid, but factually wrong
        elif model == "general_backup" and attempt == 1:
            raise TransientProviderError("Simulated provider timeout")
        return json.dumps(result)
    if stage == "interpret":
        return json.dumps({"cause_status": "unverified",
            "reason": APPROVED_INTERPRETATION})
    if stage == "summarize":
        pct = -8.0  # simulated model value; validator recomputes independently
        return json.dumps({
            "source": context["extract"]["source"],
            "cause_status": context["interpret"]["cause_status"],
            "change_pct": pct,
            "summary": ("Revenue rose 50% due to promotions." if model == "general"
                        else format_summary(pct)),
        })
    raise InvalidOutput("Unsupported stage")


def _schema(value: dict, keys: set) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise InvalidOutput("Missing or unexpected fields")


# Percentages written as "8.0%", "50 percent" or "50 per cent".
_PERCENT = re.compile(r"(?<!\w)([-+]?\d+(?:\.\d+)?)\s*(?:%|percent\b|per cent\b)")
# Deny-list for readable error messages. It is NOT the safety net: the exact
# wording allowlist at the end of the summarize branch is.
_CAUSAL = re.compile(
    r"\b(due to|because of|driven by|caused by|thanks to|resulted from|result of|"
    r"owing to|attributable to|led to|drove|driving|reason for|stems from)\b")


def validate(stage: str, value: dict, context: Mapping,
             source: AuthorizedFinancialSource) -> None:
    """Raise InvalidOutput for model faults.

    Missing keys in `context` (an application bug) deliberately raise KeyError
    and are NOT converted to InvalidOutput, so they cannot be mistaken for a
    model failure. PolicyViolation from the source also propagates untouched.
    """
    if stage == "extract":
        _schema(value, set(BASE_EXTRACTION))
        for key in ("report_id", "source", "metric", "fiscal_period", "currency", "unit"):
            if not isinstance(value[key], str) or not value[key].strip():
                raise InvalidOutput(f"Invalid {key}")
        if type(value["q1"]) is not int or type(value["q2"]) is not int:
            raise InvalidOutput("Revenue must be integers")
        # Independent source retrieval: do NOT trust a model's claimed source ID.
        authority = source.fetch(context["report_id"], context["account_id"])
        for key in BASE_EXTRACTION:
            if value[key] != authority[key]:
                raise InvalidOutput(f"Evidence mismatch: {key}")
        expected_change(value)
        return

    if stage == "interpret":
        _schema(value, {"cause_status", "reason"})
        if value["cause_status"] != "unverified":
            raise InvalidOutput("Root cause is not supported by the approved report")
        reason = value["reason"]
        if not isinstance(reason, str) or not reason.strip():
            raise InvalidOutput("Missing interpretation")
        # Readable rejection reasons first; the allowlist below is the safety net.
        if _CAUSAL.search(reason.lower()) or _PERCENT.search(reason):
            raise InvalidOutput("Unsupported causal claim in interpretation")
        if " ".join(reason.split()) != APPROVED_INTERPRETATION:
            raise InvalidOutput("Interpretation deviates from approved wording")
        return

    if stage == "summarize":
        _schema(value, {"source", "cause_status", "change_pct", "summary"})
        if value["source"] != context["extract"]["source"]:
            raise InvalidOutput("Summary source mismatch")
        if value["cause_status"] != context["interpret"]["cause_status"]:
            raise InvalidOutput("Summary causal status mismatch")
        # Recheck the authoritative evidence even if extraction was accepted earlier.
        authority = source.fetch(context["report_id"], context["account_id"])
        pct = expected_change(authority)
        if type(value["change_pct"]) not in (int, float) or value["change_pct"] != pct:
            raise InvalidOutput("Incorrect summary calculation")
        prose = value["summary"]
        if not isinstance(prose, str) or not prose.strip():
            raise InvalidOutput("Missing summary")
        # Targeted checks first: they give specific, readable rejection reasons.
        percentages = [float(p) for p in _PERCENT.findall(prose)]
        if not percentages or any(abs(p) != abs(pct) for p in percentages):
            raise InvalidOutput("Unsupported percentage in summary")
        lower = prose.lower()
        required_direction = "decreased" if pct < 0 else ("increased" if pct > 0 else "unchanged")
        if "net revenue" not in lower or required_direction not in lower:
            raise InvalidOutput("Summary contradicts the revenue trend")
        if value["cause_status"] == "unverified":
            if _CAUSAL.search(lower):
                raise InvalidOutput("Unsupported causal claim")
            if "cause not established" not in lower:
                raise InvalidOutput("Unverified cause not disclosed")
        # Safety net: allowlist, not deny-list. Any wording outside the approved,
        # evidence-derived sentence is rejected, so phrasing the regexes above do
        # not anticipate ("promotions drove the decline") still fails.
        # In production, let the model fill structured slots and have trusted
        # code render the sentence; free-form prose needs semantic review.
        if " ".join(prose.split()) != format_summary(pct):
            raise InvalidOutput("Summary deviates from the approved evidence-derived wording")
        return
    raise InvalidOutput("Unknown stage")


def run_stage(stage: str, context: dict, source: AuthorizedFinancialSource,
              invoke: Callable = mock_model, profiles: Optional[dict] = None,
              max_attempts: int = 2, max_p95_ms: int = 1200,
              audit: Optional[list] = None) -> dict:
    profiles = PROFILES if profiles is None else profiles
    audit = [] if audit is None else audit
    # Fail closed: policy inputs are required, never defaulted to an approved value.
    data_class = context.get("data_class")
    context_chars = context.get("context_chars")
    if not isinstance(data_class, str) or not data_class.strip():
        raise PolicyViolation("Data classification missing: refusing to route")
    if type(context_chars) is not int or context_chars <= 0:
        raise PolicyViolation("Context size missing or invalid: refusing to route")
    selected = [name for name in ROUTES[stage] if name in profiles
                and eligible(profiles[name], stage, data_class, context_chars, max_p95_ms)]
    if not selected:
        raise NoEligibleModel(f"{stage}: no eligible model under policy")
    for model in selected:
        for attempt in range(1, max_attempts + 1):
            try:
                result = json.loads(invoke(model, stage, context, attempt))
                validate(stage, result, context, source)
                audit.append((stage, model, "accepted"))
                print(f"{stage}: accepted {model}")
                return result
            except TransientProviderError as exc:
                audit.append((stage, model, "transient"))
                print(f"{stage}: transient {model} attempt {attempt}/{max_attempts} ({exc})")
                # Production would use bounded exponential backoff and jitter.
                continue
            except (InvalidOutput, json.JSONDecodeError) as exc:
                # Only genuine model-output faults land here. KeyError/TypeError
                # from application bugs propagate instead of blaming the model.
                audit.append((stage, model, "invalid"))
                print(f"{stage}: rejected {model} ({exc})")
                break  # same response contract failure => try next eligible model
    raise NoValidOutput(f"{stage}: no valid permitted model output")


def decision_controller(stage: str, context: dict, source: AuthorizedFinancialSource,
                        **kwargs) -> dict:
    """Minimal stand-in for Article 04's controller: maps router outcomes to states.

    Article 04's full controller also retries, replans, validates and pauses; this
    adapter only shows where a router failure re-enters controller policy.
    """
    try:
        return {"state": "continue", "value": run_stage(stage, context, source, **kwargs)}
    except (RouterFailure, PolicyViolation) as exc:
        return {"state": "blocked", "action": "stop_or_escalate", "reason": str(exc)}


def run() -> dict:
    source = AuthorizedFinancialSource()
    context = {"report_id": REPORT_ID, "account_id": ACCOUNT,
               "data_class": DATA_CLASS, "context_chars": 1000}
    audit = []  # (stage, model, outcome) records, returned to the caller
    for stage in ("extract", "interpret", "summarize"):
        decision = decision_controller(stage, context, source, audit=audit)
        if decision["state"] != "continue":
            print(f"Decision Controller: {decision['state']} ({decision['reason']})")
            return {**decision, "audit": audit}
        context[stage] = decision["value"]
    # Article 04's controller, not the router, owns goal-level completion.
    conclusion = {"state": "completed", "summary": context["summarize"], "audit": audit}
    print(f"Decision Controller: completed ({expected_change(source.fetch(REPORT_ID, ACCOUNT)):.1f}%)")
    print(context["summarize"]["summary"])
    return conclusion


if __name__ == "__main__":
    run()
