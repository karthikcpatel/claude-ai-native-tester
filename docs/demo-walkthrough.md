# Demo walkthrough (written)

A written record of the five demonstration items, with the real output from the author's Windows 11 machine on 19 November 2026.
It can stand in for a recording, and `docs/demo-script.md` is the matching live script. Everything shown is synthetic.

Environment: Windows 11, Python 3.12.0, Chromium (Playwright 1.65.2), `main` branch, all commands run from the repository root.

## 1. One successful test

```
.venv\Scripts\python -m pytest tests\ui -q --tracing retain-on-failure --screenshot only-on-failure --output reports\playwright
...............................
31 passed in 16.67s
```

All 31 browser tests pass against the local mock app: login (valid, wrong password, unknown email, empty fields, malformed and
overlong input, logout, protected pages, keyboard-only), and payment (validation, amount boundaries, approved, declined,
timeout, double-click, idempotency replay, real-card refusal, API requires a session). The tests use accessible roles and labels,
and "was anyone charged?" is read from the mock's own ledger, not from the page.

## 2. One intentionally failing test (mutation challenge)

The mock app has a seeded fault that records a declined card as approved. With the fault switched on, the suite must fail:

```
set MOCK_APP_FAULT=decline_as_success
.venv\Scripts\python -m pytest tests\ui -q ... | findstr /i "FAILED passed failed"
FAILED tests/ui/test_payment.py::test_declined_payment_never_shows_success[chromium]
1 failed, 30 passed in 20.48s
set MOCK_APP_FAULT=
```

Exactly one named test fails and the rest pass, so the failure is attributable to the seeded defect. The other two seeded faults
behave the same way (`duplicate_charge` fails `test_replaying_the_same_idempotency_key_charges_once`, `logout_keeps_session`
fails `test_logout_invalidates_the_session_on_the_server`, each `1 failed, 30 passed`). The logout fault exposed a gap in the first
version of the suite, which passed with the fault on; a test that replays the old session cookie now covers it. Trace and
screenshot evidence from these failures is described in `docs/ui-test-report.md`.

## 3. One RAG answer with citations

```
.venv\Scripts\python -m rag.cli retrieve "May logs contain passwords or tokens?"
1. known_defects.md#d-3-password-in-debug-log  score=0.5274
2. login_requirements.md#not-specified-do-not-assume-or-test  score=0.4343
3. payment_test_policy.md#logging-and-artifacts-pt-8  score=0.398
4. login_requirements.md#rules  score=0.3566
```

```
.venv\Scripts\python -m rag.cli ask "May logs contain passwords or tokens?"

No. Logs and test artifacts must not contain passwords, tokens, or full card numbers
[payment_test_policy.md#logging-and-artifacts-pt-8]. A past defect, D-3, involved a debug log line that contained a password
value, and its expected regression check is the same rule [known_defects.md#d-3-password-in-debug-log].

Note that the login requirements do not specify any logging behaviour for login
[login_requirements.md#not-specified-do-not-assume-or-test].

abstained=False model=claude-sonnet-5-5 prompt=rag-prompt-v1 latency=2.093s
```

Every claim carries a `[file#chunk]` citation that can be checked against the retrieved chunks. The retrieval output is shown
first so the sources can be inspected before generation. One honest observation: the top-ranked chunk was the defect record D-3,
not the policy chunk (PT-8), which ranked third. The answer still cited the policy correctly, but this is the retrieval weakness
noted in the failure analysis in `docs/rag-evaluation.md`.

## 4. One unanswerable question

```
.venv\Scripts\python -m rag.cli ask "What is the account lockout duration after failed login attempts?"

The login requirements do not specify any lockout duration. They list "Lockout or rate limiting after failed attempts" as
"no rule specified" and say not to assume or test it [login_requirements.md#not-specified-do-not-assume-or-test].

abstained=False model=claude-sonnet-5-5 prompt=rag-prompt-v1 latency=4.972s
```

The assistant does not invent a number. It reports that the requirements leave lockout unspecified and cites the chunk that says
so. The `abstained=False` flag only means it did not need the fixed "does not contain enough information" sentence, because the
knowledge base itself states that lockout is unspecified. A question with no related content at all (dataset case RAG-09, about
refunds) triggers the fixed abstention sentence. The prompt-injection cases RAG-07 and RAG-16 attack the assistant with
injected instructions, and the evaluation's code checks pass for both.

## 5. One CI failure and recovery

Pull request #14, "DEMO ONLY: plant a fake key to prove the secret gate fails", was opened from a throwaway branch and then
closed without merging (`https://github.com/karthikcpatel/claude-ai-native-tester/pull/14`).

| Commit | What it did | Result |
|---|---|---|
| `17aee51` | Added a file containing a clearly fake key-shaped string | **Secret scan failed**, **Quality gate (required check) failed**; Java and Python/Playwright jobs stayed green; the merge button was disabled |
| `f2602f4` | Removed the file | All checks passed on the same pull request; the merge button was enabled again |

The failing run proves the gate blocks a leak, and that branch protection applies to the administrator too. The recovery run
proves a fix on the same branch clears it. The pull request was not merged, so the fake key never reached `main`. A limit of
this check: the scanner reads the current files, not history, so a real leak would also need the key rotated, not only deleted.

## What this does not prove

- The Ragas judge is the same model as the generator, results come from one run each, and the dataset is small.
- The browser target is a mock app written for this project; trainer sign-off on that assumption is still pending.
- The live Ragas job in CI has not been run (it needs a repository secret and is optional).
