import json

import httpx
from pydantic import SecretStr
from sqlalchemy import select

from datalight import models as m
from datalight import providers, service
from datalight.schemas import ReportView


def prepare(store):
    settings, factory = store
    settings.llm_enabled = True
    settings.llm_api_key = SecretStr("fixture-only-secret")
    service.bootstrap(factory, settings)
    service.replay(factory, settings, *service.claim(factory, "replay"))
    with factory() as session:
        report = ReportView.model_validate(session.scalar(select(m.Run)).report)
    return settings, factory, providers.summarize(report)


def response_for(summary, bad=False):
    profile = summary.profiles[0]
    hypothesis = {
        "channel_id": profile.channel_id,
        "role": "Varying numeric signal",
        "explanation": "Observed variability supports a changing signal, but no physical identity is established.",
        "confidence": "low",
        "evidence_ids": ["invented" if bad else profile.evidence_id],
        "assumptions": ["No physical units are known."],
    }
    return {"choices": [{"message": {"content": json.dumps({"hypotheses": [hypothesis]})}}]}


def test_egress_payload_and_persisted_call_contain_only_derived_summaries(store):
    settings, factory, summary = prepare(store)
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        assert request.headers["authorization"] == "Bearer fixture-only-secret"
        data = json.loads(body["messages"][1]["content"])
        assert set(data) == {
            "profiles",
            "relationships",
            "selected_findings",
            "reference_assumption",
        }
        assert all("name" not in p and p["valid_count"] >= 32 for p in data["profiles"])
        for forbidden in (
            "faultNumber",
            "simulationRun",
            "fault_status",
            "signal_a",
            "evaluation-only",
            "fixture-only-secret",
            '"rows"',
            '"samples"',
        ):
            assert forbidden not in json.dumps(body)
        return httpx.Response(200, json=response_for(summary))

    job = service.claim(factory, "interpretation")
    service.interpret(factory, settings, *job, transport=httpx.MockTransport(handler))
    with factory() as session:
        call = session.scalar(select(m.ModelCall))
        assert call.status == "succeeded" and call.request == seen[0]
        assert session.scalar(select(m.Run)).report["interpretation_status"] == "available"
        finding = session.scalar(select(m.Finding).where(m.Finding.category == "interpretation"))
        assert session.get(m.Evidence, finding.evidence_ids[0]) is not None


def test_invalid_evidence_and_timeout_degrade_without_stopping_monitoring(store):
    settings, factory, summary = prepare(store)
    job = service.claim(factory, "interpretation")
    service.interpret(
        factory,
        settings,
        *job,
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, json=response_for(summary, bad=True))
        ),
    )
    with factory() as session:
        run = session.scalar(select(m.Run))
        assert run.status == "running" and run.report["interpretation_status"] == "unavailable"
        assert session.scalar(select(m.ModelCall)).status == "invalid"
        assert (
            session.scalar(select(m.Finding).where(m.Finding.category == "interpretation")) is None
        )
    service.replay(factory, settings, *service.claim(factory, "replay"))

    def timeout(request):
        raise httpx.ReadTimeout("fixture timeout", request=request)

    outcome = providers.invoke(
        settings,
        summary,
        providers.request_payload(summary, settings.llm_model),
        httpx.MockTransport(timeout),
    )
    assert outcome.status == "timeout"


def test_bad_json_redirects_and_missing_credentials_are_explicit(store):
    settings, _, summary = prepare(store)
    payload = providers.request_payload(summary, settings.llm_model)
    for response in [
        httpx.Response(200, text="not JSON"),
        httpx.Response(200, json={"choices": []}),
    ]:
        assert (
            providers.invoke(
                settings, summary, payload, httpx.MockTransport(lambda _, reply=response: reply)
            ).status
            == "invalid"
        )
    redirect = httpx.MockTransport(
        lambda _: httpx.Response(307, headers={"Location": "https://other.invalid"})
    )
    assert providers.invoke(settings, summary, payload, redirect).status == "failed"
    settings.llm_api_key = SecretStr("")
    assert "LLM_API_KEY" in settings.interpretation_unavailable


def test_provider_errors_are_auditable_without_reflected_credentials(store):
    settings, _, summary = prepare(store)
    outcome = providers.invoke(
        settings,
        summary,
        providers.request_payload(summary, settings.llm_model),
        httpx.MockTransport(
            lambda _: httpx.Response(
                404, json={"error": "Unknown model; reflected fixture-only-secret"}
            )
        ),
    )
    assert outcome.status == "failed" and "404" in outcome.error
    assert outcome.response == {"error": "Unknown model; reflected [REDACTED]"}


def test_complete_json_fence_is_accepted_but_surrounding_prose_is_not(store):
    settings, _, summary = prepare(store)
    payload = providers.request_payload(summary, settings.llm_model)
    reply = response_for(summary)
    content = reply["choices"][0]["message"]["content"]
    for wrapped, expected in [
        (f"```json\n{content}\n```", "succeeded"),
        (f"Here is my answer: {content}", "invalid"),
    ]:
        reply["choices"][0]["message"]["content"] = wrapped
        outcome = providers.invoke(
            settings,
            summary,
            payload,
            httpx.MockTransport(lambda _: httpx.Response(200, json=reply)),
        )
        assert outcome.status == expected


def test_selected_deviation_is_bounded_and_requires_both_evidence_records(store):
    settings, factory, _ = prepare(store)
    while job := service.claim(factory, "replay"):
        service.replay(factory, settings, *job)
    with factory() as session:
        jobs = session.scalars(select(m.Job).where(m.Job.kind == "finding_interpretation")).all()
        assert len(jobs) == 1
        assert session.scalar(select(m.Run)).status == "completed"
    seen = []

    def handler(request):
        payload = json.loads(request.content)
        summary = providers.SummaryPayload.model_validate_json(payload["messages"][1]["content"])
        seen.append(summary)
        assert len(summary.profiles) == 1 and len(summary.selected_findings) == 1
        assert not summary.relationships
        reply = response_for(summary)
        content = json.loads(reply["choices"][0]["message"]["content"])
        content["hypotheses"][0]["evidence_ids"].append(
            summary.selected_findings[0].reference_evidence_id
        )
        reply["choices"][0]["message"]["content"] = json.dumps(content)
        return httpx.Response(200, json=reply)

    service.interpret(
        factory,
        settings,
        *service.claim(factory, "finding_interpretation"),
        transport=httpx.MockTransport(handler),
    )
    assert service.claim(factory, "finding_interpretation") is None
    with factory() as session:
        call = session.scalar(select(m.ModelCall))
        assert call.purpose == "selected_deviation" and call.status == "succeeded"
        finding = session.scalar(select(m.Finding).where(m.Finding.category == "interpretation"))
        assert session.get(m.Finding, finding.details["related_finding_id"]).category == "deviation"
        assert finding.batch_index > 0
    # A conclusion missing its reference citation must not be published.
    outcome = providers.invoke(
        settings,
        seen[0],
        providers.request_payload(seen[0], settings.llm_model),
        httpx.MockTransport(lambda _: httpx.Response(200, json=response_for(seen[0]))),
    )
    assert outcome.status == "invalid"
