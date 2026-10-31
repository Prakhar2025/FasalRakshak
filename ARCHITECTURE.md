# Architecture

FasalRakshak is a voice-first crop advisory system built on the Strands Agents
SDK and AWS. The design principle is stated once and obeyed everywhere:
**models propose, code decides.** Language models handle perception and
language. Deterministic Python handles every decision that can harm a farmer.

## 1. System context

```mermaid
flowchart LR
    F["Farmer, phone browser"] --> UI["Web app, static assets on S3 via CloudFront"]
    W["Demo visitor, judge"] --> UI
    UI -->|"HTTPS, JSON and media"| API["FastAPI on AWS Lambda"]
    API --> AWS["AWS services: Bedrock, Transcribe, Polly"]
    API --> DATA["Local data: knowledge base files, DynamoDB"]
```

Two user classes: the farmer, and the judge or evaluator who exercises demo
mode with pre-loaded sample photos and requires no personal data.

## 2. Agent pipeline

Four Strands agents run inside a code-orchestrated pipeline. A model never
routes the request; Python does.

```mermaid
flowchart TB
    IN["Request: photo, optional voice note"] --> VI["Voice intake: Transcribe, if audio"]
    IN --> T["1. Triage agent"]
    VI --> T
    T -->|"photo unusable"| ASK["Ask for retake, spoken, stop"]
    T -->|"photo usable"| D["2. Diagnosis agent, Nova Lite"]
    D -->|"low confidence"| DP["Escalate: Nova Pro re-check"]
    DP --> D2["Fused diagnosis"]
    D2 --> TR["3. Treatment agent, reads KB advisory"]
    TR --> SG{"4. Safety gate, pure Python"}
    SG -->|"rule triggered"| BLOCK["Block, rewrite or refuse, explain"]
    SG -->|"all rules pass"| OK["Final plan"]
    BLOCK --> OUT["Polly speech, Hindi, to farmer"]
    OK --> OUT
    OUT --> MEM["Save session and field memory, DynamoDB"]
```

Stage notes:

| Stage | Type | Why |
|---|---|---|
| Voice intake | AWS Transcribe, batch job | Hindi speech to text before routing |
| 1. Triage | Strands agent | Reject unusable photos early, saves cost and farmer time |
| 2. Diagnosis | Strands agent, Nova Lite | Multimodal classification, grounded by KB candidates |
| 2b. Escalation | Nova Pro re-check | Only when confidence is low, bounded cost |
| 3. Treatment | Strands agent | Reads the matched KB entry, drafts plain-language steps |
| 4. Safety gate | Pure Python module | Banned list, dose caps, escalation rules. Not an agent. Cannot be talked around |
| Speech out | Amazon Polly, Hindi | Neural voice, cached per text |

## 3. Data flow

```mermaid
flowchart LR
    IMG["Leaf photo"] --> S3[("S3, images and audio, lifecycle-expired")]
    AUD["Voice note"] --> S3
    S3 --> PIPE["Pipeline"]
    KB[("kb/ JSON files, versioned in repo")] --> TRA["Treatment agent"]
    BL[("kb/banned_pesticides.json, from CIB&RC")] --> SG["Safety gate"]
    PIPE --> DBT[("DynamoDB: sessions")]
    PIPE --> DBM[("DynamoDB: field memory and outcomes")]
    DBM --> FOLLOW["Follow-up: did it work?"]
```

Design choices:

- The knowledge base is versioned JSON inside the repository. Curation is a
  reviewed, diffable change, not a database edit.
- Eval images never enter the repo (`data/` is gitignored). Only derived
  numbers and the script that produced them are published.
- Demo mode reads from a fixed sample set, so judges never touch real
  personal data.

## 4. Deployment topology

```mermaid
flowchart TB
    subgraph Client
        B["Browser, mobile first"]
    end
    subgraph Edge
        CF["CloudFront"] --> S3F[("S3: static frontend")]
        CF --> FU["Lambda function URL"]
    end
    subgraph Compute
        L["Lambda: FastAPI via Mangum, arm64"]
    end
    subgraph AI
        BR["Bedrock: Nova Lite, Nova Pro"]
        TS["Transcribe: hi-IN"]
        PL["Polly: hi-IN, Kajal neural"]
    end
    subgraph Storage
        S3I[("S3: images, audio, speech cache")]
        DDB[("DynamoDB: on-demand")]
    end
    B --> CF
    FU --> L
    L --> BR
    L --> TS
    L --> PL
    L --> S3I
    L --> DDB
```

Region: `us-east-1`, chosen for model and voice availability. Full detail and
step-by-step deploy: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## 5. Evaluation methodology

```mermaid
flowchart LR
    PV["PlantVillage, tomato classes"] --> SPLIT["Fixed stratified split, seeded"]
    SPLIT --> HOLD["500 held-out images, never seen in tuning"]
    HOLD --> RUN["eval/run_eval.py"]
    RUN --> RES["Top-1, top-2, calibration, refusal rate on negatives"]
    RES --> REP["docs/EVAL_REPORT.md, regenerated, never hand-edited"]
```

Rules: fixed seed, no cherry-picking, every published number regenerable by
one command. Full plan: [docs/EVAL_PLAN.md](docs/EVAL_PLAN.md).

## Request lifecycle, end to end

1. Farmer opens the app. UI is English chrome, Hindi content, voice-first.
2. She records a short voice note and photographs the leaf. One submit.
3. Transcribe returns Hindi text. Triage validates the image.
4. Diagnosis proposes candidates from the KB, verified by Nova Lite.
5. Treatment agent drafts steps and products from the matched advisory.
6. Safety gate verifies: banned list, dose caps, PHI, PPE, escalation rules.
7. Polly speaks the final plan. Text appears alongside for anyone nearby.
8. Session and field memory persist. A follow-up is scheduled: did it work?

## Failure modes and degraded behavior

| Failure | Behavior |
|---|---|
| Transcribe fails or times out | Text input path remains available |
| Nova Lite unavailable | Nova Pro direct, then Claude fallback on Bedrock |
| KB match below threshold | No treatment spoken. Escalate to agriculture officer |
| Safety gate internal error | Fail closed: spoken answer becomes "show a person this photo" |
| DynamoDB down | Diagnosis still works; memory degrades gracefully, session saved locally and retried |

## Decision records

- [ADR-0001: model choice](docs/adr/ADR-0001-model-choice.md)
- [ADR-0002: orchestration in code, not swarm](docs/adr/ADR-0002-orchestration-in-code.md)
