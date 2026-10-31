# Data Schema

Everything the system reads and writes, defined before Phase 1 writes a
single data file.

## 1. Knowledge base entries

Location: `kb/tomato/*.json`, `kb/cotton/*.json`. One file per disease,
versioned in git, reviewed like code.

```json
{
  "id": "tomato-early-blight",
  "crop": "tomato",
  "disease": "Early blight",
  "pathogen": "Alternaria solani",
  "aliases": ["jhulasa", "मरोड़ा"],
  "symptoms": [
    "Dark brown spots with concentric rings on older leaves",
    "Yellow halo around spots",
    "Defoliation from the bottom upward"
  ],
  "severity_cues": {
    "early": "Few spots, lower leaves only",
    "advanced": "Spots on most leaves, significant defoliation"
  },
  "favorable_conditions": "Warm days, cool nights, long wet periods",
  "treatment": {
    "summary": "Remove affected leaves, apply recommended fungicide on schedule",
    "steps": [
      "Remove and destroy affected leaves, do not compost",
      "Spray recommended fungicide at 7 day intervals",
      "Improve air flow between plants, avoid overhead watering"
    ],
    "products": [
      {
        "name": "Chlorothalonil 75 WP",
        "active_ingredient": "chlorothalonil",
        "dose": "2.0",
        "dose_max": "2.0",
        "unit": "g per litre",
        "phi_days": 7,
        "label_source": "CIB&RC registered label"
      }
    ],
    "organic": [
      "Copper-based spray as per label",
      "Neem-based extract as per label"
    ]
  },
  "source": {
    "org": "ICAR Indian Institute of Horticultural Research / State Horticulture Department",
    "title": "Tomato disease advisory",
    "url": "",
    "accessed": "2026-11-01"
  },
  "safety_notes": [
    "Wear gloves and mask while spraying",
    "Do not harvest within 7 days of spray"
  ]
}
```

Field rules:

- `dose` and `dose_max` are strings with fixed decimal format, always paired
  with `unit`. The safety gate compares numerically and refuses anything
  above `dose_max`.
- `active_ingredient` is lowercase, singular, matches keys in the banned list.
- Every entry carries `source`. No source, no entry, enforced by schema tests.

Scope: 8 tomato diseases, 7 cotton diseases in the first release. The schema
is crop-agnostic: adding a crop is adding files, not changing code.

## 2. Banned pesticides reference

Location: `kb/banned_pesticides.json`.

```json
{
  "snapshot_date": "2026-11-01",
  "source": "Central Insecticides Board and Registration Committee (CIB&RC), banned, refused and restricted lists",
  "entries": [
    {
      "active_ingredient": "endosulfan",
      "status": "banned",
      "citation": "CIB&RC list, banned 2011",
      "notes": ""
    }
  ]
}
```

## 3. DynamoDB tables

Region `us-east-1`, billing mode: on-demand.

### `fasal_sessions`

| Attribute | Type | Notes |
|---|---|---|
| `pk` | S | `SESSION#{session_id}` |
| `created_at` | N | epoch seconds, TTL 30 days |
| `farmer_id` | S | anonymous id in demo mode |
| `crop` | S | |
| `transcript` | S | Hindi text from voice note, if any |
| `diagnosis` | M | disease_id, label, confidence, alternatives |
| `treatment_final` | M | post-gate treatment or escalation text |
| `safety` | M | status, rules_triggered |

### `fasal_field_memory`

| Attribute | Type | Notes |
|---|---|---|
| `pk` | S | `FARMER#{farmer_id}` |
| `sk` | S | `FIELD#{field_id}#{created_at}` |
| `crop` | S | |
| `diagnosis_id` | S | KB id |
| `outcome` | S | empty until follow-up answered: `resolved`, `worse`, `unknown` |
| `followup_due` | N | epoch seconds, drives the "did it work?" question |

## 4. S3 layout

| Prefix | Contents | Lifecycle |
|---|---|---|
| `images/` | farmer leaf photos | expire 30 days |
| `audio/` | voice notes | expire 7 days |
| `speech/` | Polly output, keyed by text hash | no expiry, acts as cache |
| `eval/` | benchmark outputs, JSON reports | versioned |

## 5. Demo mode

- Fixed farmer id `demo-farmer`, fixed sample image set under `app/web/assets/samples/`.
- No writes to field memory beyond the demo namespace.
- No personal data anywhere, stated on the demo screen itself.
