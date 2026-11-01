"""FasalRakshak API: FastAPI service around the code-owned pipeline.

Endpoints per docs/API_CONTRACT.md. The pipeline is injected through
``app.state.pipeline`` so tests run the full HTTP surface with fake agents
and no AWS. Deployed on Lambda via Mangum in Phase 7 (docs/DEPLOYMENT.md).
"""

from __future__ import annotations

import base64
import os
import uuid
from pathlib import Path
from typing import Any, Callable, Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from fasalrakshak.pipeline import PipelineResult, run_diagnosis_pipeline
from fasalrakshak.store import load_store
from fasalrakshak.voice import VoiceError, synthesize_speech

def _find_web_dir() -> Path:
    """Locate app/web by walking upward from this file.

    The layout depth differs between the repository (src/fasalrakshak/api/)
    and the Lambda package (fasalrakshak/api/ under the handler root), so a
    fixed parent count breaks in one of the two. A marker search works in
    both.
    """
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        candidate = parent / "app" / "web"
        if (candidate / "index.html").is_file():
            return candidate
    raise RuntimeError("app/web not found: run from the repository or the deploy package")


WEB_DIR = _find_web_dir()
SAMPLES_DIR = WEB_DIR / "assets" / "samples"

MAX_IMAGE_BYTES = 8 * 1024 * 1024

DEMO_SAMPLES = {
    "early-blight": {
        "label_hi": "झुलसा (अल्टरनेरिया)",
        "label_en": "Early blight",
        "file": "early-blight.jpg",
        "expected": "tomato-early-blight",
    },
    "late-blight": {
        "label_hi": "देर से झुलसा",
        "label_en": "Late blight",
        "file": "late-blight.jpg",
        "expected": "tomato-late-blight",
    },
    "healthy": {
        "label_hi": "स्वस्थ पत्ती",
        "label_en": "Healthy leaf",
        "file": "healthy.jpg",
        "expected": "healthy",
    },
}


class TriageOut(BaseModel):
    usable: bool
    reason: str = ""
    crop_hint: str = ""


class DiagnosisOut(BaseModel):
    disease_id: str
    label: str
    label_hi: str = ""
    pathogen: str = ""
    confidence: float
    alternatives: list[dict] = Field(default_factory=list)


class CitationOut(BaseModel):
    org: str
    title: str


class ProductOut(BaseModel):
    name: str
    dose: str
    unit: str
    phi_days: int


class TreatmentOut(BaseModel):
    summary: str
    steps: list[str]
    products: list[ProductOut] = Field(default_factory=list)
    citations: list[CitationOut] = Field(default_factory=list)


class SafetyOut(BaseModel):
    status: str
    rules_triggered: list[dict] = Field(default_factory=list)
    spoken_addendum: list[str] = Field(default_factory=list)


class AudioOut(BaseModel):
    data_uri: str
    format: str = "mp3"


class DiagnoseResponse(BaseModel):
    session_id: str
    status: Literal["treated", "retake", "escalated", "blocked"]
    triage: Optional[TriageOut] = None
    diagnosis: Optional[DiagnosisOut] = None
    treatment: Optional[TreatmentOut] = None
    safety: Optional[SafetyOut] = None
    spoken_text: str = ""
    audio: Optional[AudioOut] = None


class FeedbackBody(BaseModel):
    session_id: str
    outcome: Literal["resolved", "worse", "unknown"]


def _media_bucket() -> str | None:
    return os.environ.get("MEDIA_BUCKET")


def build_spoken_text(result: PipelineResult, label_hi: str) -> str:
    """One spoken script for Polly: what it is, what to do, the cautions."""
    parts: list[str] = []
    if result.status == "treated" and result.treatment_final is not None:
        if label_hi:
            parts.append(f"समस्या: {label_hi}।")
        elif result.diagnosis is not None:
            parts.append(f"समस्या: {result.diagnosis.label}।")
        parts.append(result.treatment_final.summary)
        parts.extend(result.treatment_final.steps)
    parts.extend(result.spoken_addendum)
    return " ".join(part for part in parts if part)


def _audio_data_uri(result: PipelineResult, label_hi: str, spoken_lang: str = "hi") -> Optional[AudioOut]:
    spoken = build_spoken_text(result, label_hi)
    if not spoken:
        return None
    voices = {"hi": ("Kajal", "neural"), "en": ("Aditi", "standard")}
    voice_id, engine = voices.get(spoken_lang, ("Kajal", "neural"))
    try:
        audio = synthesize_speech(spoken, voice_id=voice_id, engine=engine)
    except VoiceError:
        return None
    encoded = base64.b64encode(audio).decode("ascii")
    return AudioOut(data_uri=f"data:audio/mp3;base64,{encoded}")


def create_app() -> FastAPI:
    app = FastAPI(title="FasalRakshak API", version="0.5.0", docs_url="/api/docs")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[os.environ.get("FRONTEND_ORIGIN", "*")],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.store = load_store()
    app.state.pipeline: Callable[..., PipelineResult] = run_diagnosis_pipeline

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/api/demo/samples")
    def demo_samples() -> dict:
        return {
            "samples": [
                {
                    "id": sample_id,
                    "label_hi": meta["label_hi"],
                    "label_en": meta["label_en"],
                    "image_url": f"/assets/samples/{meta['file']}",
                }
                for sample_id, meta in DEMO_SAMPLES.items()
            ]
        }

    @app.post("/api/diagnose", response_model=DiagnoseResponse)
    def diagnose(
        request: Request,
        image: Optional[UploadFile] = File(None),
        demo_sample: Optional[str] = Form(None),
        audio: Optional[UploadFile] = File(None),
        text: Optional[str] = Form(None),
        demo: bool = Form(False),
        session_id: Optional[str] = Form(None),
        lang: str = Form("hi"),
    ) -> DiagnoseResponse:
        image_bytes: bytes | None = None
        farmer_id = "demo-farmer" if demo else f"farmer-{uuid.uuid4().hex[:8]}"

        if demo:
            meta = DEMO_SAMPLES.get(demo_sample or "")
            if meta is None:
                raise HTTPException(status_code=400, detail="unknown demo sample")
            image_bytes = (SAMPLES_DIR / meta["file"]).read_bytes()
        elif image is not None:
            image_bytes = image.file.read()

        if not image_bytes:
            raise HTTPException(status_code=400, detail="a leaf photo is required")
        if len(image_bytes) > MAX_IMAGE_BYTES:
            raise HTTPException(status_code=413, detail="photo larger than 8 MB")
        if not (image_bytes.startswith(b"\xff\xd8") or image_bytes.startswith(b"\x89PNG")):
            raise HTTPException(status_code=400, detail="photo must be JPEG or PNG")

        transcript = (text or "").strip()
        if audio is not None and audio.file.read(1):
            bucket = _media_bucket()
            if not bucket:
                raise HTTPException(
                    status_code=400,
                    detail="voice is not configured on this deployment, use text",
                )
            audio.file.seek(0)
            from fasalrakshak.voice import transcribe_voice_note

            try:
                transcript = transcribe_voice_note(
                    audio.file.read(), audio_format="webm", bucket=bucket
                )
            except VoiceError as exc:
                raise HTTPException(
                    status_code=503, detail=f"voice transcription failed: {exc}"
                ) from exc

        result = request.app.state.pipeline(
            image_bytes,
            transcript=transcript,
            lang=lang,
        )

        label_hi = ""
        if result.kb_entry_id:
            from fasalrakshak.kb import load_entry

            entry = load_entry(result.kb_entry_id)
            label_hi = entry.aliases[0] if entry.aliases else entry.disease

        response = DiagnoseResponse(
            session_id=session_id or f"s_{uuid.uuid4().hex[:12]}",
            status=result.status,  # type: ignore[arg-type]
            triage=TriageOut(
                usable=result.triage.usable,
                reason=result.triage.reason,
                crop_hint=result.triage.crop_hint,
            ) if result.triage else None,
            diagnosis=DiagnosisOut(
                disease_id=result.diagnosis.disease_id,
                label=result.diagnosis.label,
                label_hi=label_hi,
                confidence=result.diagnosis.confidence,
                alternatives=[
                    {"disease_id": result.diagnosis.runner_up_id,
                     "confidence": result.diagnosis.runner_up_confidence}
                ] if result.diagnosis.runner_up_id else [],
            ) if result.diagnosis else None,
            treatment=TreatmentOut(
                summary=result.treatment_final.summary,
                steps=result.treatment_final.steps,
                products=[
                    ProductOut(name=p.name, dose=p.dose, unit=p.unit, phi_days=p.phi_days)
                    for p in result.treatment_final.products
                ],
                citations=[CitationOut(org=entry.source.org, title=entry.source.title)]
                if result.kb_entry_id else [],
            ) if result.treatment_final else None,
            safety=SafetyOut(
                status=result.safety.status,
                rules_triggered=[
                    {"rule_id": hit.rule_id, "action": hit.action, "message": hit.message}
                    for hit in result.safety.rules_triggered
                ],
                spoken_addendum=result.safety.spoken_addendum,
            ) if result.safety else None,
            spoken_text=build_spoken_text(result, label_hi),
            audio=_audio_data_uri(result, label_hi, lang) if not demo or os.environ.get("DEMO_AUDIO", "1") == "1" else None,
        )

        request.app.state.store.put(
            response.session_id,
            {
                "farmer_id": farmer_id,
                "status": response.status,
                "kb_entry_id": result.kb_entry_id,
                "outcome": "unknown",
            },
        )
        return response

    @app.get("/api/session/{session_id}")
    def get_session(session_id: str, request: Request) -> dict:
        record = request.app.state.store.get(session_id)
        if record is None:
            raise HTTPException(status_code=404, detail="unknown session")
        return {"session_id": session_id, **{k: str(v) for k, v in record.items()}}

    @app.post("/api/feedback")
    def feedback(body: FeedbackBody, request: Request) -> dict:
        updated = request.app.state.store.set_outcome(body.session_id, body.outcome)
        if not updated:
            raise HTTPException(status_code=404, detail="unknown session")
        return {"session_id": body.session_id, "outcome": body.outcome}

    app.mount("/assets", StaticFiles(directory=WEB_DIR / "assets"), name="assets")
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
    return app


app = create_app()
