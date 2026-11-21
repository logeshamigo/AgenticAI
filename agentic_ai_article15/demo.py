from authorization import FinanceAPI, Grant, Request


def sample() -> tuple[FinanceAPI, Request]:
    api = FinanceAPI()
    api.grants["g-007"] = Grant(
        subject="finance-analyst",
        actor="pricing-specialist",
        audience="finance-api",
        workflow="q3-review-042",
        tenant="enterprise-a",
        resource="q3-renewal-aggregate",
        action="read_aggregate",
        expires_at=110,
    )
    api.active_access.add((
        "finance-analyst", "enterprise-a", "q3-renewal-aggregate", "read_aggregate",
    ))
    request = Request(
        actor="pricing-specialist",
        grant_id="g-007",
        workflow="q3-review-042",
        tenant="enterprise-a",
        resource="q3-renewal-aggregate",
        action="read_aggregate",
    )
    return api, request


if __name__ == "__main__":
    api, request = sample()
    print(api.read(request, now=105))
    api.revoked.add(request.grant_id)
    print(api.read(request, now=106))
    print(api.audit[-1])
