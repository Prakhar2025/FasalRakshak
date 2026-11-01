# API Contract

FastAPI service, deployed on Lambda via Mangum in Phase 7. All endpoints
return JSON. Errors follow one shape:

```json
{ "error": { "code": "invalid_image", "message": "Photo could not be read" } }
```

## Endpoints

### `POST /api/diagnose`

The main pipeline. Multipart form:

| Field | Type | Required | Notes |
|---|---|---|---|
| `image` | binary | yes | jpeg or png, max 8 MB |
| `audio` | binary | no | webm or ogg voice note |
| `text` | string | no | typed fallback for the voice note |
| `session_id` | string | no | continues a session |
| `demo` | boolean | no | demo mode flag, anonymous ids |

Response 200:

```json
{
  "session_id": "s_20261101_abc123",
  "triage": { "usable": true, "reason": "", "crop_hint": "tomato" },
  "diagnosis": {
    "disease_id": "tomato-early-blight",
    "label": "Early blight",
    "confidence": 0.91,
    "alternatives": [{ "disease_id": "tomato-septoria", "confidence": 0.06 }]
  },
  "treatment": {
    "summary": "…",
    "steps": ["…"],
    "products": [{ "name": "…", "dose": "2.0", "unit": "g per litre", "phi_days": 7 }],
    "citations": [{ "org": "…", "title": "…" }]
  },
  "safety": { "status": "passed", "rules_triggered": [], "spoken_addendum": ["…"] },
  "spoken_text": "…",
  "audio": { "url": "https://…/speech/abc.mp3", "format": "mp3" }
}
```

Blocked and escalated responses are 200 too, with `safety.status` of
`blocked` or `escalated`, `treatment: null`, and `spoken_text` carrying the
escalation message. A confident "no disease" answer returns
`status: "healthy"` with `treatment: null` and a spoken line telling the
farmer the leaf looks healthy and no medicine is needed. The farmer always
gets a spoken, useful answer.

### `GET /api/session/{session_id}`

Returns the stored session record (diagnosis, treatment, safety, outcome).

### `POST /api/feedback`

```json
{ "session_id": "s_20261101_abc123", "outcome": "resolved" }
```

`outcome` in `resolved | worse | unknown`. Writes field memory.

### `GET /api/demo/samples`

Fixed sample set for demo mode: id, crop, expected diagnosis, image URL.
Lets judges and the video reproduce results in one click.

## Constraints

- No auth for the public demo; per-ip rate limit and request size cap.
- No personal data stored in demo mode. Stated on the demo screen.
- CORS: frontend origin only.
- Every handler wraps the pipeline; pipeline exceptions return the
  fail-closed escalation payload, never a raw 500 to the farmer.
