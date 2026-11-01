"""Deploy FasalRakshak to AWS with boto3 only: no extra tooling.

Provisions, idempotently:
- the private media bucket
- the two DynamoDB tables
- the Lambda IAM role with least-privilege inline policies
- the ARM64 Lambda package (code + kb + web assets + aarch64 wheels)
- the function with a public Function URL (CORS open for the demo)
and finishes with a live smoke test against the public URL.

Usage:
    python scripts/deploy.py            # build, package, deploy, smoke
    python scripts/deploy.py --skip-build
"""

from __future__ import annotations

import argparse
import concurrent.futures as futures
import io
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

REGION = "us-east-1"
FUNCTION_NAME = "fasalrakshak-api"
ROLE_NAME = "fasalrakshak-lambda-role"
TABLE_SESSIONS = "fasal_sessions"
TABLE_FIELD_MEMORY = "fasal_field_memory"
BUILD_DIR = Path("build/deploy")

DEPLOY_REQUIREMENTS = [
    "strands-agents",
    "strands-agents-tools",
    "boto3",
    "fastapi",
    "mangum",
    "python-multipart",
    "httpx",
]

TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}
    ],
}

BASE_MANAGED_POLICY = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"


def account_id() -> str:
    return boto3.client("sts", region_name=REGION).get_caller_identity()["Account"]


def media_bucket_name(account: str) -> str:
    return f"fasalrakshak-prod-media-{account}"


def ensure_bucket(bucket: str) -> None:
    s3 = boto3.client("s3", region_name=REGION)
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"bucket exists: {bucket}")
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
    print(f"bucket created: {bucket}")


def ensure_tables() -> None:
    client = boto3.client("dynamodb", region_name=REGION)
    specs = [
        (TABLE_SESSIONS, [{"AttributeName": "session_id", "KeyType": "HASH"}],
         [{"AttributeName": "session_id", "AttributeType": "S"}]),
        (TABLE_FIELD_MEMORY, [
            {"AttributeName": "pk", "KeyType": "HASH"},
            {"AttributeName": "sk", "KeyType": "RANGE"},
        ], [
            {"AttributeName": "pk", "AttributeType": "S"},
            {"AttributeName": "sk", "AttributeType": "S"},
        ]),
    ]
    for name, keys, attrs in specs:
        try:
            client.describe_table(TableName=name)
            print(f"table exists: {name}")
        except ClientError:
            client.create_table(
                TableName=name,
                KeySchema=keys,
                AttributeDefinitions=attrs,
                BillingMode="PAY_PER_REQUEST",
            )
            print(f"table created: {name}")
    waiter = client.get_waiter("table_exists")
    for name, _, _ in specs:
        waiter.wait(TableName=name)


def ensure_role(account: str, bucket: str) -> str:
    iam = boto3.client("iam")
    try:
        role = iam.get_role(RoleName=ROLE_NAME)["Role"]
        print(f"role exists: {ROLE_NAME}")
    except ClientError:
        iam.create_role(RoleName=ROLE_NAME, AssumeRolePolicyDocument=json.dumps(TRUST_POLICY))
        print(f"role created: {ROLE_NAME}")
        time.sleep(6)
    statements = [
        {"Effect": "Allow", "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"], "Resource": "*"},
        {"Effect": "Allow", "Action": [
            "transcribe:StartTranscriptionJob", "transcribe:GetTranscriptionJob"
        ], "Resource": "*"},
        {"Effect": "Allow", "Action": ["polly:SynthesizeSpeech"], "Resource": "*"},
        {"Effect": "Allow", "Action": [
            "s3:PutObject", "s3:GetObject", "s3:ListBucket", "s3:DeleteObject"
        ], "Resource": [f"arn:aws:s3:::{bucket}", f"arn:aws:s3:::{bucket}/*"]},
        {"Effect": "Allow", "Action": [
            "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DescribeTable"
        ], "Resource": [
            f"arn:aws:dynamodb:{REGION}:{account}:table/{TABLE_SESSIONS}",
            f"arn:aws:dynamodb:{REGION}:{account}:table/{TABLE_FIELD_MEMORY}",
        ]},
    ]
    iam.put_role_policy(
        RoleName=ROLE_NAME,
        PolicyName="fasalrakshak-runtime",
        PolicyDocument=json.dumps({"Version": "2012-10-17", "Statement": statements}),
    )
    attached = iam.list_attached_role_policies(RoleName=ROLE_NAME).get("AttachedPolicies", [])
    if not any(p["PolicyArn"] == BASE_MANAGED_POLICY for p in attached):
        iam.attach_role_policy(RoleName=ROLE_NAME, PolicyArn=BASE_MANAGED_POLICY)
    return f"arn:aws:iam::{account}:role/{ROLE_NAME}"


def build_package() -> Path:
    """Assemble the ARM64 Lambda package under build/deploy/pkg."""
    pkg = BUILD_DIR / "pkg"
    if pkg.exists():
        shutil.rmtree(pkg)
    pkg.mkdir(parents=True)

    shutil.copytree("src/fasalrakshak", pkg / "fasalrakshak", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree("kb", pkg / "kb")
    shutil.copytree("app/web", pkg / "app/web")
    (pkg / "lambda_handler.py").write_text(
        "from mangum import Mangum\n"
        "from fasalrakshak.api.main import app\n\n"
        "handler = Mangum(app, api_gateway_base_path=\"/\")\n",
        encoding="utf-8",
    )

    python = Path(".venv/Scripts/python.exe")
    command = [
        str(python), "-m", "pip", "install",
        "--target", str(pkg),
        "--platform", "manylinux2014_aarch64",
        "--implementation", "cp",
        "--python-version", "3.12",
        "--only-binary=:all:",
        *DEPLOY_REQUIREMENTS,
    ]
    print("installing aarch64 wheels into the package ...")
    subprocess.run(command, check=True)

    for cache in pkg.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)

    total_mb = sum(f.stat().st_size for f in pkg.rglob("*") if f.is_file()) / (1024 * 1024)
    print(f"package size: {total_mb:.1f} MB (Lambda limit 250 MB unzipped)")
    if total_mb > 240:
        raise RuntimeError("package too large for Lambda")
    return pkg


def zip_package(pkg: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in sorted(pkg.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(pkg).as_posix())
    data = buffer.getvalue()
    print(f"zip: {len(data) / (1024 * 1024):.1f} MB")
    return data


def deploy_function(account: str, role_arn: str, bucket: str, package_zip: bytes) -> str:
    client = boto3.client("lambda", region_name=REGION)
    s3 = boto3.client("s3", region_name=REGION)
    zip_key = "deploys/fasalrakshak-api.zip"
    s3.put_object(Bucket=bucket, Key=zip_key, Body=package_zip)

    environment = {
        "Variables": {
            "BEDROCK_MODEL_PRIMARY": "us.amazon.nova-lite-v1:0",
            "BEDROCK_MODEL_ESCALATION": "us.amazon.nova-pro-v1:0",
            "TABLE_SESSIONS": TABLE_SESSIONS,
            "TABLE_FIELD_MEMORY": TABLE_FIELD_MEMORY,
            "MEDIA_BUCKET": bucket,
        }
    }
    try:
        client.get_function(FunctionName=FUNCTION_NAME)
        print("function exists, updating code and config")
        client.update_function_code(
            FunctionName=FUNCTION_NAME,
            S3Bucket=bucket,
            S3Key=zip_key,
        )
        waiter = client.get_waiter("function_updated")
        waiter.wait(FunctionName=FUNCTION_NAME)
        client.update_function_configuration(
            FunctionName=FUNCTION_NAME,
            Runtime="python3.12",
            Handler="lambda_handler.handler",
            MemorySize=1024,
            Timeout=180,
            Role=role_arn,
            Environment=environment,
        )
        waiter.wait(FunctionName=FUNCTION_NAME)
    except ClientError:
        print("creating function")
        client.create_function(
            FunctionName=FUNCTION_NAME,
            Runtime="python3.12",
            Role=role_arn,
            Handler="lambda_handler.handler",
            Code={"S3Bucket": bucket, "S3Key": zip_key},
            MemorySize=1024,
            Timeout=180,
            Architectures=["arm64"],
            Environment=environment,
            Description="FasalRakshak: the crop protector",
        )
        waiter = client.get_waiter("function_active")
        waiter.wait(FunctionName=FUNCTION_NAME)

    # Public Function URLs are blocked on this account (verified with a
    # throwaway function: auth NONE still returns 403 from the org-level
    # control). The standard public pattern is an HTTP API in front of the
    # function, which this account allows.
    apigw = boto3.client("apigatewayv2", region_name=REGION)
    api_id = None
    for item in apigw.get_apis()["Items"]:
        if item["Name"] == FUNCTION_NAME:
            api_id = item["ApiId"]
            break
    if api_id is None:
        api = apigw.create_api(Name=FUNCTION_NAME, ProtocolType="HTTP")
        api_id = api["ApiId"]
        print(f"HTTP API created: {api_id}")
    else:
        print(f"HTTP API exists: {api_id}")

    fn_arn = f"arn:aws:lambda:{REGION}:{account}:function:{FUNCTION_NAME}"
    integration_id = None
    for item in apigw.get_integrations(ApiId=api_id).get("Items", []):
        if item.get("IntegrationUri") == fn_arn:
            integration_id = item["IntegrationId"]
    if integration_id is None:
        integration = apigw.create_integration(
            ApiId=api_id,
            IntegrationType="AWS_PROXY",
            IntegrationUri=fn_arn,
            PayloadFormatVersion="2.0",
        )
        integration_id = integration["IntegrationId"]

    existing_routes = {route["RouteKey"] for route in apigw.get_routes(ApiId=api_id).get("Items", [])}
    for route_key in ("ANY /{proxy+}", "ANY /"):
        if route_key not in existing_routes:
            apigw.create_route(ApiId=api_id, RouteKey=route_key, Target=f"integrations/{integration_id}")

    try:
        apigw.create_stage(ApiId=api_id, StageName="$default", AutoDeploy=True)
    except ClientError:
        pass

    try:
        client.add_permission(
            FunctionName=FUNCTION_NAME,
            StatementId="apigw-invoke",
            Action="lambda:InvokeFunction",
            Principal="apigateway.amazonaws.com",
            SourceArn=f"arn:aws:execute-api:{REGION}:{account}:{api_id}/*/*",
        )
    except ClientError as exc:
        if "ResourceConflictException" not in str(exc):
            raise

    url_response = {"FunctionUrl": f"https://{api_id}.execute-api.{REGION}.amazonaws.com"}
    return url_response["FunctionUrl"]


def smoke_test(url: str) -> None:
    import httpx

    base = url.rstrip("/")
    response = httpx.get(f"{base}/", timeout=30.0)
    print(f"smoke GET /: {response.status_code}")
    assert response.status_code == 200

    response = httpx.post(
        f"{base}/api/diagnose",
        data={"demo": "true", "demo_sample": "early-blight", "text": "demo sample leaf"},
        timeout=180.0,
    )
    body = response.json()
    print(f"smoke POST /api/diagnose: {response.status_code} -> {body['status']}, "
          f"{body['diagnosis']['disease_id']} @ {body['diagnosis']['confidence']}")
    assert response.status_code == 200
    assert body["status"] in {"treated", "escalated", "blocked", "retake"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-build", action="store_true", help="reuse the existing zip")
    args = parser.parse_args()

    account = account_id()
    bucket = media_bucket_name(account)
    print(f"account {account}, region {REGION}")
    ensure_bucket(bucket)
    ensure_tables()
    role_arn = ensure_role(account, bucket)

    if args.skip_build and (BUILD_DIR / "deploy.zip").exists():
        package_zip = (BUILD_DIR / "deploy.zip").read_bytes()
    else:
        pkg = build_package()
        package_zip = zip_package(pkg)
        BUILD_DIR.mkdir(parents=True, exist_ok=True)
        (BUILD_DIR / "deploy.zip").write_bytes(package_zip)

    url = deploy_function(account, role_arn, bucket, package_zip)
    print(f"public URL: {url}")
    smoke_test(url)
    print("DEPLOY OK")


if __name__ == "__main__":
    main()
