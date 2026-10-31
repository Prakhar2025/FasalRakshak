# ADR-0002: Orchestration in code, not a model-led swarm

Status: accepted, 2026-10-31

## Context

The Strands SDK supports swarms and graphs where a model routes work between
agents. FasalRakshak has exactly four stages with a strict safety requirement
between stages 3 and 4. The core product claim is "models propose, code
decides".

## Decision

The pipeline is a plain Python function calling four Strands agents in a
fixed order, with the deterministic safety gate as a hard inline stage.

## Alternatives considered

- Strands Swarm: model-led routing, flexible for open-ended problems, but
  routing here is not open-ended, and a model in the routing path is one more
  thing that can be talked into skipping the gate. Rejected.
- Strands Graph: useful for parallel stages; our stages are strictly
  sequential with one conditional escalation edge. A function with an `if`
  is clearer and fully testable.

## Consequences

- Every stage is unit-testable with mocked agents.
- The gate sits on the only path to speech and cannot be bypassed by
  prompting, because no model decides the path.
- If the product grows parallel stages (multi-crop fan-out), migrating to a
  Strands graph is a contained refactor, documented then.
