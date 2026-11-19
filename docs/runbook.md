# Runbook

How to run, check and troubleshoot the workbench. Commands use the Windows virtual environment (`.venv\Scripts\python`).

## Daily checks

| Goal | Command | Healthy result |
|---|---|---|
| Java tests | `cd java-app` then `mvn test` | 36 tests, 0 failures |
| All Python tests | `.venv\Scripts\python -m pytest tests -q` | all pass (92 tests: 41 RAG, 31 UI, 20 unit) |
| Secret scan | `.venv\Scripts\python scripts\check_secrets.py` | "No secrets found" |
| Dependency health | `.venv\Scripts\python -m pip check` | "No broken requirements found" |
| API key present (never printed) | `.venv\Scripts\python -m rag.cli check-key` | says the key is available |

## RAG operations

- **Rebuild the index** after any change to `rag/knowledge/`: `python -m rag.cli index`. The index version (a hash of the chunks)
  is printed and recorded in every evaluation run.
- **Inspect retrieval before blaming the model:** `python -m rag.cli retrieve "<question>"` shows chunk ids and scores.
- **Evaluate:** `python -m rag.evaluate --out reports`. It calls the paid API, so run it deliberately. Use `--limit 1` for a smoke
  test and `--no-ragas` to skip the judge.
- **The dataset is frozen.** `rag/eval/rag-eval-v1.jsonl` has a stored hash and the runner refuses to run if it changes.
  To change cases, create `rag-eval-v2` and a new hash; never edit v1.
- **Reading the output:** each gate prints PASS, FAIL or SKIPPED. Exit code 1 means a gate failed. Per-case evidence is in
  `reports/ragas-examples.jsonl` (question, answer, retrieved chunk ids and text, checks, scores, errors).

## Browser tests

- The suite starts the mock app on a free local port by itself. Set `BASE_URL` only to test an app that is already running.
- Failure evidence: run with `--tracing retain-on-failure --screenshot only-on-failure --output reports\playwright`, then open a
  trace with `.venv\Scripts\python -m playwright show-trace <path-to-trace.zip>`.
- Mutation challenge (prove the tests can fail): set `MOCK_APP_FAULT` to `decline_as_success`, `duplicate_charge` or
  `logout_keeps_session`, run the UI tests, expect exactly one named failure, then clear it (`set MOCK_APP_FAULT=`).

## CI triage

| Symptom | Likely cause | Action |
|---|---|---|
| Secret scan red | A key-like string in a tracked file or artifact | Do not merge. Remove it, rotate the secret if real, rerun. The scan prints file and line, never the value |
| Evidence check says "expected at least N passed" | Tests skipped, not collected, or the suite did not start | Open the pytest step log; check imports and installed packages |
| Python job fails at Chromium install | Runner dependency step failed | Rerun; check the `playwright install --with-deps chromium` step |
| Java job fails | Maven or test failure | Open the Surefire artifact |
| Quality gate red, jobs green | A job was skipped or cancelled | Rerun all jobs |
| Cannot merge | The required check is not green | Fix the failing job; the rule applies to administrators too |

Recovery from a red run: fix on the same branch, push, and the pipeline reruns on the same pull request.

## Secrets

- The key lives only in the git-ignored `.env` and the GitHub repository secret `ANTHROPIC_API_KEY`.
- If a key appears anywhere it should not: stop publishing, rotate it in the Anthropic console, remove the leak, add a
  regression check, and rerun the secret scan.
- Never paste a key into a chat, a report, a commit message or an issue.

## Windows and Application Control

If a Python install or import fails with "An Application Control policy has blocked this file", do not try to bypass it. Find
which compiled module is blocked, pin an older release of that package that loads, run `pip check`, and record the pin in
`requirements.txt` and the README. This resolved `pydantic_core`, `grpcio` and `pyarrow` on the development machine.

## Common failures

| Symptom | Cause | Fix |
|---|---|---|
| Playwright browser will not launch | Browser binary missing | `.venv\Scripts\python -m playwright install chromium` |
| `ask` or `evaluate` says the key is missing | `.env` absent or run from another folder | Run from the repository root; check with `rag.cli check-key` |
| Ragas judge errors on construction | `instructor` version mismatch | Use `instructor==1.15.4` |
| Empty answer error from the generator | Token budget consumed by model thinking | `MAX_TOKENS` is 4096; raise it if it recurs |
| Wrong document retrieved | Weak match or stale index | Rebuild the index, inspect chunk ids and scores |
