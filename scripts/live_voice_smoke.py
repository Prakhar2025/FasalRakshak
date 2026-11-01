"""Live voice round trip: Polly speaks Hindi, Transcribe hears it back.

Proves the whole voice path with real AWS: synthesize a Hindi sentence with
Polly (Kajal neural), upload it to the media bucket, run a Transcribe hi-IN
job, and print what came back. Requires AWS credentials, and creates the dev
media bucket if it does not exist (private, block-public-access on).

Usage:
    python scripts/live_voice_smoke.py [--bucket NAME]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fasalrakshak.voice import synthesize_speech, transcribe_voice_note  # noqa: E402

SAMPLE_TEXT = "मेरी टमाटर की फसल के पत्तों पर भूरे धब्बे हैं, क्या करूँ?"


def ensure_bucket(bucket: str, s3) -> None:
    try:
        s3.head_bucket(Bucket=bucket)
        return
    except ClientError:
        pass
    s3.create_bucket(Bucket=bucket)
    s3.put_public_access_block(
        Bucket=bucket,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )
    print(f"created private bucket {bucket}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", default=None)
    args = parser.parse_args()

    account = boto3.client("sts", region_name="us-east-1").get_caller_identity()["Account"]
    bucket = args.bucket or f"fasalrakshak-dev-media-{account}"

    s3 = boto3.client("s3", region_name="us-east-1")
    ensure_bucket(bucket, s3)

    print("polly: speaking the Hindi sample ...")
    audio = synthesize_speech(SAMPLE_TEXT)
    print(f"polly: {len(audio)} bytes of mp3")

    print("transcribe: running the hi-IN job against the same audio ...")
    text = transcribe_voice_note(audio, audio_format="mp3", bucket=bucket, poll_seconds=3.0)

    summary = {"spoken": SAMPLE_TEXT, "heard_back": text, "bucket": bucket}
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
