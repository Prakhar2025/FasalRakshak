# Demo Video Script

Target: under 3 minutes, public on YouTube. Tone: calm, concrete, farmer
first. Everything on screen is real: live AWS, live Bedrock, real
screenshots captured from the deployed app, no mocks. Render at 1080p from
the hyperframes composition (C:/Users/prakh/brag-output/fasalrakshak/).

Narration: English, kokoro (af_heart). The farmer moment plays the REAL
Polly answer fetched from the live /api/diagnose endpoint, so the viewer
hears the actual product voice.

## Scenes

| Time | On screen | Voiceover |
|---|---|---|
| 0:00-0:08 | Title card: FasalRakshak, the crop protector. | "For a farmer in Maharashtra, a sick leaf is an emergency with no one to call." |
| 0:08-0:23 | Three numbers: 40 percent crop loss, 1:1000 extension workers, 10 languages. | "Forty percent of global crops are lost to pests and disease. One extension worker serves a thousand farming households in India. FasalRakshak is a crop doctor in every farmer's pocket." |
| 0:23-0:39 | Real landing page screenshot; three ways in appear one by one: speak, photograph, demo samples. | "It is voice first, in ten Indian languages, with no typing required. Speak your problem. Photograph the leaf. Or judge a demo sample, with no personal data. Everything you are about to see is live on AWS." |
| 0:39-0:58 | Real spinner screenshot beside the four agents: triage, diagnosis, treatment, safety gate. | "Photograph a leaf, and four Strands agents take over. Triage checks the photo. Diagnosis runs on Amazon Nova, multimodal, against a curated knowledge base of official advisories. The treatment planner restates the plan in plain Hindi." |
| 0:58-1:35 | Real treated result (early blight, 85 percent, dose chips, PHI chips, PPE, citation); callouts appear; then the REAL Polly answer plays in full. | "Before a single word is spoken, a deterministic safety gate checks every product, and every dose. Then the answer is spoken aloud. Listen." + the actual Hindi answer |
| 1:35-1:51 | Two real shots side by side: healthy leaf answered healthy; unsure photo escalated. | "Different leaves get different answers. A healthy leaf is told it is healthy, and no medicine is suggested. An unsure photo is escalated to the agriculture officer. Never guessed. Models propose. Code decides." |
| 1:51-2:07 | The R1-R7 rule card. | "The gate is eight rules in pure Python. Banned pesticides are refused. Doses are capped at the printed label. Pre harvest intervals are enforced. Every plan carries its source advisory. No model can talk its way past it." |
| 2:07-2:24 | Architecture boxes: phone to web to Lambda to agents and gate; Transcribe, Polly, DynamoDB, KB. | "Under the hood, the pipeline is orchestrated in code, on AWS. Strands agents on Bedrock. Lambda. DynamoDB field memory, with a three day follow up asking, did it work. Amazon Transcribe and Polly carry the voice." |
| 2:24-2:42 | Benchmark bars and the honesty card. | "And we measured it. Five hundred held out images against real Bedrock. Treatment family accuracy, sixty one percent. Diagnosis latency, two point one seconds. Every number is reproducible from the repo, including the classes the model gets wrong." |
| 2:42-2:51 | End card: live URL, repo URL. | "It is live right now. No login, no personal data. Judge it yourself. FasalRakshak. The crop protector." |

## Production notes

- Screenshots are captured from the live deployment at 1440x900 with a real
  demo click; the spinner shot is taken mid-request, not staged.
- The escalation and healthy shots are real gate outcomes from the live
  pipeline; if a retry gives a different outcome, re-capture rather than
  faking one.
- Keep the spinner visible: an honest loading state reads as a real
  product.
- Upload to YouTube and set visibility to **Public** (the rules require the
  video be publicly visible; do not use unlisted), add the
  repo link in the description, use docs/YOUTUBE.md as the package.
