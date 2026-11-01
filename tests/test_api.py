"""API surface tests: full HTTP stack with a fake pipeline, no AWS."""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from fasalrakshak.api.main import app, create_app
from fasalrakshak.kb import load_entry
from fasalrakshak.pipeline import DiagnosisOutcome, PipelineResult, TriageOutcome
from fasalrakshak.safety import SafetyVerdict


def treated_result() -> PipelineResult:
    entry = load_entry("tomato-early-blight")
    draft = entry.treatment
    return PipelineResult(
        status="treated",
        triage=TriageOutcome(usable=True, reason="", crop_hint="tomato"),
        diagnosis=DiagnosisOutcome(
            disease_id="tomato-early-blight",
            label="Early blight",
            confidence=0.92,
            runner_up_id="tomato-septoria-leaf-spot",
            runner_up_confidence=0.05,
        ),
        treatment_final=draft,
        safety=SafetyVerdict(
            status="passed",
            rules_triggered=[],
            final_treatment=draft,
            spoken_addendum=["छिड़काव करते समय दस्ताने, मास्क और पूरे कपड़े पहनें।"],
        ),
        spoken_addendum=["छिड़काव करते समय दस्ताने, मास्क और पूरे कपड़े पहनें।"],
        kb_entry_id="tomato-early-blight",
    )


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    test_app = create_app()
    test_app.state.pipeline = lambda image, **kwargs: treated_result()
    # No Polly calls from tests: patch synthesis at the API module boundary.
    monkeypatch.setattr(
        "fasalrakshak.api.main.synthesize_speech",
        lambda text, voice_id="Kajal", engine="neural": b"FAKEMP3",
    )
    return TestClient(test_app)


def test_demo_sample_returns_full_treatment(client: TestClient) -> None:
    response = client.post(
        "/api/diagnose",
        data={"demo": "true", "demo_sample": "early-blight", "text": "demo sample leaf"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "treated"
    assert body["session_id"].startswith("s_")
    assert body["diagnosis"]["disease_id"] == "tomato-early-blight"
    assert body["diagnosis"]["label_hi"], "Hindi label must be present for the farmer"
    assert body["treatment"]["products"], "products must travel to the UI"
    assert body["treatment"]["citations"][0]["org"], "citations must travel to the UI"
    assert any("दस्ताने" in line for line in body["safety"]["spoken_addendum"])
    assert body["audio"]["data_uri"].startswith("data:audio/mp3;base64,")
    assert "समस्या" in body["spoken_text"]


def test_demo_samples_listing(client: TestClient) -> None:
    response = client.get("/api/demo/samples")

    assert response.status_code == 200
    samples = response.json()["samples"]
    assert {s["id"] for s in samples} == {"early-blight", "late-blight", "healthy"}
    assert all(s["image_url"].startswith("/assets/samples/") for s in samples)


def test_missing_image_is_rejected(client: TestClient) -> None:
    response = client.post("/api/diagnose", data={"text": "no photo"})

    assert response.status_code == 400


def test_unknown_demo_sample_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/diagnose", data={"demo": "true", "demo_sample": "not-real", "text": "x"}
    )

    assert response.status_code == 400


def test_non_image_bytes_are_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/diagnose",
        files={"image": ("leaf.jpg", io.BytesIO(b"not an image"), "image/jpeg")},
        data={"text": "x"},
    )

    assert response.status_code == 400


def test_retake_result_has_no_diagnosis() -> None:
    test_app = create_app()
    test_app.state.pipeline = lambda image, **kwargs: PipelineResult(
        status="retake",
        triage=TriageOutcome(usable=False, reason="blurry", crop_hint=""),
        spoken_addendum=["यह फोटो ठीक से नहीं आई।"],
    )
    client = TestClient(test_app)

    response = client.post(
        "/api/diagnose",
        data={"demo": "true", "demo_sample": "early-blight", "text": "demo"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "retake"
    assert body["diagnosis"] is None
    assert body["treatment"] is None
    assert body["audio"] is not None, "the retake request must be spoken to the farmer"
    assert "फोटो" in body["spoken_text"]


def test_feedback_round_trip(client: TestClient) -> None:
    first = client.post(
        "/api/diagnose",
        data={"demo": "true", "demo_sample": "early-blight", "text": "demo"},
    ).json()

    feedback = client.post(
        "/api/feedback",
        json={"session_id": first["session_id"], "outcome": "resolved"},
    )
    assert feedback.status_code == 200

    session = client.get(f"/api/session/{first['session_id']}")
    assert session.status_code == 200
    assert session.json()["outcome"] == "resolved"


def test_unknown_session_is_404(client: TestClient) -> None:
    assert client.get("/api/session/does-not-exist").status_code == 404


def test_index_serves_the_app(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "FasalRakshak" in response.text


def test_app_module_exports_default_app() -> None:
    assert app.title == "FasalRakshak API"
