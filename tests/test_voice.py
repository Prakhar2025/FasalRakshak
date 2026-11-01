"""Voice loop tests with fake AWS clients: no credentials, no network."""

from __future__ import annotations

import gzip as gzip_module
import io
import json
from typing import Any

import pytest

from fasalrakshak.voice import VoiceError, synthesize_speech, transcribe_voice_note


class FakePolly:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def synthesize_speech(self, **kwargs: Any) -> dict:
        self.calls.append(kwargs)
        return {"AudioStream": io.BytesIO(b"FAKEMP3")}


class FakeTranscribe:
    def __init__(self, statuses: list[str]) -> None:
        self.statuses = list(statuses)
        self.started: dict | None = None
        self.polled = 0

    def start_transcription_job(self, **kwargs: Any) -> dict:
        self.started = kwargs
        return {}

    def get_transcription_job(self, **kwargs: Any) -> dict:
        status = self.statuses[min(self.polled, len(self.statuses) - 1)]
        self.polled += 1
        job: dict = {"TranscriptionJobStatus": status}
        if status == "COMPLETED":
            job["Transcript"] = {"TranscriptFileUri": "https://fake/tx.json"}
        if status == "FAILED":
            job["FailureReason"] = "bad audio"
        return {"TranscriptionJob": job}


class FakeS3:
    def __init__(self, transcript_payload: bytes = b"{}") -> None:
        self.objects: list[tuple[str, str]] = []
        self.transcript_payload = transcript_payload
        self.fetched: list[str] = []

    def put_object(self, **kwargs: Any) -> dict:
        self.objects.append((kwargs["Bucket"], kwargs["Key"]))
        return {}

    def get_object(self, **kwargs: Any) -> dict:
        self.fetched.append(f"{kwargs['Bucket']}/{kwargs['Key']}")
        return {"Body": io.BytesIO(self.transcript_payload)}


def make_transcript_payload(text: str) -> bytes:
    return json.dumps({"results": {"transcripts": [{"transcript": text}]}}).encode("utf-8")


def test_polly_uses_hindi_kajal_neural() -> None:
    polly = FakePolly()

    audio = synthesize_speech("नमस्ते किसान भाई", polly_client=polly)

    assert audio == b"FAKEMP3"
    call = polly.calls[0]
    assert call["VoiceId"] == "Kajal"
    assert call["LanguageCode"] == "hi-IN"
    assert call["Engine"] == "neural"
    assert call["OutputFormat"] == "mp3"


def test_polly_empty_text_raises() -> None:
    with pytest.raises(VoiceError):
        synthesize_speech("   ", polly_client=FakePolly())


def test_transcribe_round_trip_returns_hindi_text() -> None:
    s3 = FakeS3(transcript_payload=make_transcript_payload("मेरी फसल के पत्तों पर धब्बे हैं"))
    transcribe = FakeTranscribe(["IN_PROGRESS", "COMPLETED"])

    text = transcribe_voice_note(
        b"fakeaudio",
        audio_format="webm",
        bucket="media-bucket",
        s3_client=s3,
        transcribe_client=transcribe,
        poll_seconds=0.0,
    )

    assert text == "मेरी फसल के पत्तों पर धब्बे हैं"
    assert transcribe.started is not None
    call = transcribe.started
    assert call["LanguageCode"] == "hi-IN"
    assert call["MediaFormat"] == "webm"
    assert call["Media"]["MediaFileUri"].startswith("s3://media-bucket/audio/")
    assert call["OutputBucketName"] == "media-bucket"
    assert len(s3.objects) == 1
    assert s3.objects[0][0] == "media-bucket"
    assert s3.fetched == [
        f"media-bucket/transcripts/{transcribe.started['TranscriptionJobName']}.json"
    ], "transcript must be read through authenticated S3, never a public URL"


def test_transcribe_failed_job_raises() -> None:
    with pytest.raises(VoiceError, match="failed"):
        transcribe_voice_note(
            b"fakeaudio",
            bucket="media-bucket",
            s3_client=FakeS3(),
            transcribe_client=FakeTranscribe(["FAILED"]),
            poll_seconds=0.0,
        )


def test_transcribe_empty_audio_raises() -> None:
    with pytest.raises(VoiceError, match="empty"):
        transcribe_voice_note(
            b"",
            bucket="media-bucket",
            s3_client=FakeS3(),
            transcribe_client=FakeTranscribe(["COMPLETED"]),
        )


def test_transcribe_gzip_payload_is_decoded() -> None:
    gzipped = gzip_module.compress(
        json.dumps({"results": {"transcripts": [{"transcript": "gzip से आया टेक्स्ट"}]}}).encode()
    )
    s3 = FakeS3(transcript_payload=gzipped)

    text = transcribe_voice_note(
        b"fakeaudio",
        bucket="media-bucket",
        s3_client=s3,
        transcribe_client=FakeTranscribe(["COMPLETED"]),
        poll_seconds=0.0,
    )

    assert text == "gzip से आया टेक्स्ट"
