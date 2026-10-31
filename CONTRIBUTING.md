# Contributing

Solo project, but the discipline stays professional.

## Commit convention

Conventional Commits, imperative mood, present tense:

- `feat(scope): add deterministic treatment safety gate`
- `fix(safety): cap dose at label maximum`
- `docs(eval): publish benchmark results`
- `test(safety): cover banned substance refusal`
- `chore: pin dependency versions`
- `ci: run tests on push`

Rules:

1. No phase labels or ticket codes in commit messages. The message describes
   the change, not the plan.
2. Every commit is green: tests pass before every push.
3. One logical change per commit. Multiple commits per phase are expected.
4. Docs change in the same commit as the behavior they describe.

## House rules

- No em dashes anywhere: not in code, not in docs, not in commit messages.
- Fail closed: if a safety check cannot complete, the answer is escalation,
  never a guess.
- Cite sources: every treatment claim in the knowledge base carries its
  originating advisory.
- Honest numbers: never publish a benchmark number that cannot be reproduced
  from a script in this repository.

## Branches

`main` is always deployable. Feature work happens directly on `main` for now
(solo project) with small, frequent, green commits.
