# Demo Video Script

Target: under 3 minutes, public on YouTube. Tone: calm, concrete, farmer
first. Everything on screen is real: live AWS, live Bedrock, no mocks.
Record at 1080p. Browser window at mobile width (430 px) for the app
segments, full width for the benchmark segment.

Before recording: server or deployed URL open, demo samples visible, mic
permission already granted (so no permission popups on camera), benchmark
report open in another tab.

## Script, second by second

| Time | On screen | Voiceover (Hindi-flavored English is fine, or full English) |
|---|---|---|
| 0:00-0:05 | Title card: FasalRakshak, the crop protector. A crop doctor in every farmer's pocket. | "For a farmer in Maharashtra, a sick leaf is an emergency with no one to call." |
| 0:05-0:15 | The app: tagline, mic button, photo zone. | "FasalRakshak is voice-first, Hindi-first, built for farmers the system does not reach. No typing required." |
| 0:15-0:45 | Click sample leaf 1. Spinner: "जाँच हो रही है...". Result appears. Play the audio aloud. | "Photograph the leaf, and four Strands agents take over. Triage checks the photo. Diagnosis runs on Amazon Nova multimodal on Bedrock, against a curated, cited knowledge base. Treatment reads the official advisory." |
| 0:45-0:55 | Highlight: confidence badge, dose chip, PHI chip, PPE notice, source citation. | "Every dose is checked. Every advice carries its source." |
| 0:55-1:20 | Second sample leaf, different disease. Play audio. | "Different leaf, different answer. Same pipeline." |
| 1:20-1:40 | The safety gate on camera: docs/SAFETY_RULES.md open beside the app; show the R1-R8 table, then a blocked or capped case from the test suite output. | "Here is the rule that makes it trustworthy. The safety gate is pure Python, not a model. Models propose, code decides. A banned pesticide is refused. A dose above the label is capped. A low-confidence photo is escalated to a human, never guessed." |
| 1:40-2:05 | Architecture diagram (ARCHITECTURE.md). | "Under the hood: the pipeline is orchestrated in code. Triage, diagnosis, treatment, then the deterministic gate as the last hard stage. Field memory follows up in three days: did it work?" |
| 2:05-2:30 | docs/EVAL_REPORT.md tables scrolling. | "And we measured it. Top-1 accuracy on five hundred held-out images, [TOP1] percent. Every number reproducible from the repo, one command." |
| 2:30-2:50 | The live deployed URL, demo click one more time. | "It is live on AWS, right now. Judge it yourself." |
| 2:50-2:58 | End card: repo URL, "FasalRakshak. Models propose, code decides." | "FasalRakshak. The crop protector." |

## Production notes

- No copyrighted music. Keep room tone; speak close to the mic.
- Zoom to 110 percent in the browser before recording so text is readable.
- The audio playback is the emotional peak: let the Hindi voice play at full
  volume for at least five seconds, twice.
- Do not trim the spinner out of the video: an honest loading state reads as
  a real product. Cut only silence.
- Upload to YouTube, unlisted is acceptable per the rules as long as the
  link is publicly accessible; add the repo link in the description.
