"""The Hindi voice loop: Transcribe in, Polly out.

Per docs/VOICE.md: a browser voice note becomes Hindi text through Amazon
Transcribe (batch job against S3), and the final plan becomes speech through
Amazon Polly (Kajal, neural, hi-IN). Both functions accept injected boto3
clients so tests run without AWS; with no clients injected, real ones are
constructed lazily in us-east-1.
"""

from __future__ import annotations

import gzip
import json
import time
import uuid
from typing import Any

import boto3
import httpx

REGION = "us-east-1"
VOICE_ID = "Kajal"
TRANSCRIBE_LANGUAGE = "hi-IN"
POLL_SECONDS = 3
POLL_TIMEOUT_SECONDS = 120

AudioFormat = str  # webm | ogg | mp3 | mp4 | wav | flac


class VoiceError(Exception):
    """The voice stage failed and the caller must fall back to text."""


def _s3(client: Any = None):
    return client or boto3.client("s3", region_name=REGION)


def _transcribe(client: Any = None):
    return client or boto3.client("transcribe", region_name=REGION)


def _polly(client: Any = None):
    return client or boto3.client("polly", region_name=REGION)


def synthesize_speech(
    text: str,
    *,
    polly_client: Any = None,
    voice_id: str = VOICE_ID,
    engine: str = "neural",
    output_format: str = "mp3",
) -> bytes:
    """Speak one plan aloud. Returns audio bytes; caching lives at the API layer."""
    if not text.strip():
        raise VoiceError("nothing to speak")
    try:
        response = _polly(polly_client).synthesize_speech(
            Text=text,
            TextType="text",
            LanguageCode="hi-IN",
            VoiceId=voice_id,
            Engine=engine,
            OutputFormat=output_format,
        )
        stream = response.get("AudioStream")
        if stream is None:
            raise VoiceError("polly returned no audio stream")
        return stream.read()
    except VoiceError:
        raise
    except Exception as exc:  # noqa: BLE001 - any AWS failure means text fallback
        raise VoiceError(f"polly synthesis failed: {exc}") from exc


def _read_transcript_payload(raw: bytes) -> dict:
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return json.loads(raw)


def _extract_text(payload: dict) -> str:
    transcripts = payload.get("results", {}).get("transcripts", [])
    if not transcripts:
        return ""
    return str(transcripts[0].get("transcript", "")).strip()


def transcribe_voice_note(
    audio: bytes,
    *,
    audio_format: AudioFormat = "webm",
    bucket: str,
    s3_client: Any = None,
    transcribe_client: Any = None,
    poll_seconds: float = POLL_SECONDS,
    poll_timeout: float = POLL_TIMEOUT_SECONDS,
) -> str:
    """One voice note in, Hindi text out. Raises VoiceError on any failure.

    The transcript is read back through the authenticated S3 API from the
    output key we set ourselves, never through an unauthenticated HTTP GET.
    """
    if not audio:
        raise VoiceError("empty audio")

    s3 = _s3(s3_client)
    transcribe = _transcribe(transcribe_client)
    key = f"audio/{uuid.uuid4().hex}.{audio_format}"
    job_name = f"fasalrakshak-{uuid.uuid4().hex[:12]}"
    output_key = f"transcripts/{job_name}.json"

    try:
        s3.put_object(Bucket=bucket, Key=key, Body=audio, ContentType=f"audio/{audio_format}")
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            LanguageCode=TRANSCRIBE_LANGUAGE,
            MediaFormat=audio_format,
            Media={"MediaFileUri": f"s3://{bucket}/{key}"},
            OutputBucketName=bucket,
            OutputKey=output_key,
        )
    except Exception as exc:  # noqa: BLE001 - any AWS failure means text fallback
        raise VoiceError(f"transcription job could not start: {exc}") from exc

    deadline = time.monotonic() + poll_timeout
    while time.monotonic() < deadline:
        time.sleep(poll_seconds)
        job = transcribe.get_transcription_job(TranscriptionJobName=job_name).get(
            "TranscriptionJob", {}
        )
        status = job.get("TranscriptionJobStatus")
        if status == "COMPLETED":
            obj = s3.get_object(Bucket=bucket, Key=output_key)
            return _extract_text(_read_transcript_payload(obj["Body"].read()))
        if status == "FAILED":
            raise VoiceError(f"transcription job failed: {job.get('FailureReason', 'unknown')}")
    raise VoiceError("transcription job timed out")
