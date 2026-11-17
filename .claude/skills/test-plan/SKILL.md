---
name: test-plan
description: Inspect requirements or code changes and create a risk-based test plan.
---

# Test planning workflow
1. Read the issue/acceptance criteria and inspect relevant code.
2. Separate confirmed facts from assumptions and open questions.
3. Cover happy path, negative path, boundaries, permissions, state transitions,
   accessibility/usability where relevant, and regression risks.
4. Map each test to a requirement and expected observable result.
5. Identify what should be unit-tested, API-tested, browser-tested, or evaluated
   as an LLM/RAG behavior.
6. Do not invent selectors, APIs, credentials, or business rules.
7. Return a table: ID, risk, preconditions, steps, expected result, automation layer.
8. Flag any case that cannot be tested safely or deterministically.
9. If a requirement is missing or unclear, ask a question instead of guessing.
