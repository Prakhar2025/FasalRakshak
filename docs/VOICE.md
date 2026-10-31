# Voice Pipeline

Voice is the product. A low-literacy farmer must never be forced to type.

## Input: voice note to text

| Decision | Choice | Why |
|---|---|---|
| Capture | Browser `MediaRecorder`, webm/opus, max 15s | no app install, works on Android Chrome |
| Service | Amazon Transcribe, batch job, `hi-IN` | mature Hindi support, no streaming infra needed |
| Flow | upload to S3, start job, poll `GetTranscriptionJob` | 2 to 5 s typical for short clips |
| Fallback | typed text box, always visible | never block the farmer on voice failure |

Hinglish reality: farmers mix Hindi and English product names. `hi-IN`
handles most of it; symptom keywords for KB pre-filtering include common
Hinglish variants, so partial transcription still routes correctly.

## Output: text to speech

| Decision | Choice | Why |
|---|---|---|
| Service | Amazon Polly, `hi-IN`, Kajal, neural | natural Hindi voice |
| Format | mp3, cached in S3 by text hash | identical plans never pay twice |
| Delivery | pre-signed URL to the browser | no audio bytes through Lambda |

## Spoken text rules

The treatment agent writes the spoken text under hard constraints:

- Short sentences. One instruction per sentence.
- Numbers spoken in a farmer-friendly way (units spelled out).
- Order: what the disease is, what to do today, what to watch for, when to
  call a person.
- Safety addenda from the gate are appended verbatim, never paraphrased.

## Latency budget

| Stage | Budget |
|---|---|
| Upload + triage | 2 s |
| Transcribe (voice path) | 4 s |
| Diagnosis | 4 s |
| Treatment + gate | 2 s |
| Polly + delivery | 2 s |
| **Total, voice path** | **under 12 s, target 10 s** |

Text path skips Transcribe: target under 8 s. Measured numbers are published
with the benchmark in Phase 6, not estimated.
