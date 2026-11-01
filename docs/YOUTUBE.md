# YouTube Package

## Title (pick one)

1. FasalRakshak: A Crop Doctor in Every Farmer's Pocket | Strands Agents SDK on AWS
2. Photo of a sick leaf, safe treatment plan in Hindi | FasalRakshak (AWS Strands Hackathon)
3. Models Propose, Code Decides: a voice-first crop doctor on Amazon Bedrock

Recommended: title 1 (clear, searchable, brand-forward).

## Description (paste as-is)

A farmer photographs a sick leaf, speaks her problem in her own language, and
hears a diagnosis with a safe treatment plan, spoken aloud. FasalRakshak is a
voice-first crop advisory built with the Strands Agents SDK on Amazon Bedrock
for the "Strands SDK: Workshop to Ship" hackathon.

Why it is trustworthy:
- A deterministic Python safety gate checks every product and dose against
  India's banned-pesticide list and label caps before anything is spoken.
  Models propose, code decides.
- Every treatment names its source advisory (state agriculture departments,
  ICAR).
- Unsure diagnosis? The system escalates to a human instead of guessing.

Measured on 500 frozen, held-out PlantVillage images (reproducible from the
repo): treatment-family accuracy 0.61 with Nova Lite, published with the full
confusion matrix and calibration tables, including the classes the model
struggles with.

Live demo (no login, no personal data):
https://xodqri8mc2.execute-api.us-east-1.amazonaws.com

Source code (MIT):
https://github.com/Prakhar2025/FasalRakshak

Built with: Strands Agents SDK, Amazon Bedrock (Nova Lite), API Gateway,
Lambda (arm64), DynamoDB, Amazon Transcribe, Amazon Polly.

0:00 The problem
0:23 The app, three ways in
0:39 The pipeline at work
0:58 The result, spoken aloud
1:35 Different leaves, different answers
1:51 The safety gate
2:07 Architecture on AWS
2:24 The benchmark, honestly
2:42 Try it live

#AWS #Strands #Bedrock #AgriTech #AI #Hackathon #OpenSource #SocialGood

## Pinned comment

Every number in this video is reproducible: eval/run_eval.py in the repo.
The safety rules are at docs/SAFETY_RULES.md. Ask me anything.
