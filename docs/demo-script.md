# Demo script (about 8 minutes)

Goal: show one passing test, one intentionally failing test, one cited RAG answer, one unanswerable question, and one CI
failure with recovery. Open a Command Prompt in the repository root and have GitHub open in a browser.

## Before you start (not shown)

- `git checkout main` and `git pull`. Run `.venv\Scripts\python -m rag.cli check-key` once to confirm the key works.
- Have the failing demo pull request ready, or the steps to create it (section 5).

## 1. The workbench (1 min)

Show `CLAUDE.md` (safety rules), the `.claude/skills` and `.claude/agents` folders, and `.mcp.json`. Say: Claude works under
written rules, restricted agents and a least-privilege browser tool. Everything is synthetic; no live payments.

## 2. One successful test (1 min)

```
.venv\Scripts\python -m pytest tests\ui -q
```

Expect 31 passed. Point out that tests use accessible roles and labels, and that "was anyone charged?" is read from the
mock's ledger, not from the page.

## 3. One intentionally failing test (1.5 min)

```
set MOCK_APP_FAULT=decline_as_success
.venv\Scripts\python -m pytest tests\ui -q --tracing retain-on-failure --screenshot only-on-failure --output reports\playwright-demo
set MOCK_APP_FAULT=
```

Expect `1 failed, 30 passed`: `test_declined_payment_never_shows_success`. Explain: the seeded fault records a declined card as
approved, and the suite catches it. Open the screenshot from `reports\playwright-demo`. Mention that the logout fault exposed a
real gap in the first version of the suite, now covered.

## 4. RAG answer with citations, and an unanswerable question (2 min)

```
.venv\Scripts\python -m rag.cli retrieve "May logs contain passwords or tokens?"
.venv\Scripts\python -m rag.cli ask "May logs contain passwords or tokens?"
.venv\Scripts\python -m rag.cli ask "What is the account lockout duration after failed login attempts?"
```

First show the retrieved chunk ids and scores, then the answer with its `[file#chunk]` citations ("No", logs must not contain
passwords, tokens or full card numbers). For the second question the assistant should say the documents do not specify it
instead of inventing a number. Mention the prompt-injection cases (RAG-07, RAG-16) that attack the assistant with injected
instructions, and that the code checks fail the release if it obeys them.

## 5. CI failure and recovery (2 min)

On GitHub, open the "DEMO ONLY" pull request that plants a clearly fake key.

- Show **Secret scan** and **Quality gate** red and the merge button blocked.
- Push a commit that removes the file: the same pull request turns green. Do not merge it; close it.

To create it: on a branch, add a file containing a fake `sk-ant-api03-...` style string, push, and open a pull request.

## 6. Evidence and limits (30 s)

Show the evaluation numbers in `docs/rag-evaluation.md` (run 1 failed two gates, run 2 passes) and say plainly what they do not
prove: the judge is the same model as the generator, one run each, a small dataset, and the UI target is a mock.

## What to say if asked

- *Why a mock app?* The starter project has no web UI; the mock is recorded as an assumption awaiting trainer sign-off.
- *Can Claude merge or deploy?* No. `main` is protected, the required check must be green, and a human merges.
- *Are the Ragas scores trustworthy?* They are evidence, not proof; the release also depends on deterministic code checks.
