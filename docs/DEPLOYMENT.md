# Deployment

Executed in Phase 7, designed now. Everything fits the AWS Free Tier for a
hackathon-scale demo, with a hard cost ceiling.

## Region and account

- Region: `us-east-1`. Chosen for Nova model availability, Polly `hi-IN`
  neural voices, and Transcribe `hi-IN`, all required.
- Budget alarm: USD 10, alarm to email before any deploy.

## Resources

| Resource | Purpose | Free tier status |
|---|---|---|
| S3: static frontend | web app assets | 5 GB free |
| S3: images, audio, speech cache | media, lifecycle-expired | 5 GB free |
| CloudFront | HTTPS edge for frontend and API | 1 TB transfer free |
| Lambda (arm64, FastAPI via Mangum) | the whole backend | 1M requests free |
| DynamoDB on-demand: sessions, field memory | memory | 25 GB free |
| Bedrock: Nova Lite / Nova Pro | diagnosis | pay per token, pennies at demo scale |
| Transcribe `hi-IN` | voice notes | 60 min/month free tier era-dependent, small |
| Polly `hi-IN` Kajal neural | spoken answers | 1M characters free first 12 months |
| CloudWatch alarms | spend and error alarms | free |

Estimated total for the hackathon window: under USD 2, dominated by Bedrock
tokens during the 500-image benchmark.

## Deploy steps (Phase 7)

1. `sam build && sam deploy --guided` with `template.yaml` (SAM), which
   provisions: two DynamoDB tables, Lambda, function URL, S3 buckets, budget
   alarm, and IAM roles scoped to the specific resources above.
2. Frontend: `app/web` static assets synced to the frontend bucket.
3. CloudFront distribution in front of the function URL and the static
   bucket, OAC, HTTPS only.
4. Secrets: none in the repo. AWS credentials live in the environment only.
5. Smoke tests: `tests/smoke/` hits the live URL with each demo sample and
   asserts gate status and latency budget.

## Environment variables (Lambda)

| Var | Meaning |
|---|---|
| `BEDROCK_MODEL_PRIMARY` | Nova Lite model id |
| `BEDROCK_MODEL_ESCALATION` | Nova Pro model id |
| `KB_DIR` | knowledge base path inside the deployment package |
| `TABLE_SESSIONS`, `TABLE_FIELD_MEMORY` | DynamoDB names |
| `BUCKET_MEDIA` | S3 media bucket |
| `DEMO_MODE` | flag for anonymous demo behavior |

## Teardown

`sam delete` plus bucket empties. Scripted in `scripts/teardown.sh` so the
account is clean after the hackathon if desired.
