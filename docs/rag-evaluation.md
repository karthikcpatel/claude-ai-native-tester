# RAG evaluation (Ragas) - rag-eval-v1

This page records how the knowledge-base assistant was evaluated, what the results were, and what they do and do not prove.
All knowledge-base content and test cases are synthetic capstone material.

## What was evaluated

| Item | Value |
|---|---|
| Dataset | `rag/eval/rag-eval-v1.jsonl`, 16 cases (11 answerable, 2 unanswerable, 1 open question, 2 prompt injection) |
| Dataset hash (SHA-256 of the LF-normalised file) | `563257e2f086ad197fde95f0ad6582a7a27b76b39e523b5e52e121d4a41b8e54` (frozen; the runner refuses to run if it changes) |
| Knowledge base | 5 markdown files, 26 chunks, index version `f14e3103c329` |
| Retrieval | local ONNX MiniLM-L6-v2 embeddings, cosine similarity, top 4 chunks |
| Generator | `claude-sonnet-5-5`, prompt `rag-prompt-v1`, answers must cite chunk ids or abstain |
| Judge (Ragas) | `claude-sonnet-5-5` via Ragas 0.4.4 (instructor 1.15.4) |
| Environment | Windows 11, Python 3.12.0, anthropic 2.10.0, chromadb 1.5.9, pydantic 2.12.5 |

Run it with `python -m rag.evaluate --out reports` (needs `ANTHROPIC_API_KEY` in a git-ignored `.env`).
It writes `reports/ragas-results.csv`, `reports/ragas-examples.jsonl` (full per-case evidence) and `reports/ragas-run-meta.json`.
`reports/` is git-ignored, so the numbers that matter are copied here.

## Two kinds of checks

1. **Ragas metrics** (LLM judge) on answerable and open-question cases: faithfulness, context precision, context recall, factual correctness, answer relevancy.
2. **Deterministic code checks** on every case, including the two prompt-injection cases that Ragas does not score: forbidden patterns (for example an invented lockout duration, a key-like string, the injected word), required wording, and abstention. These do not depend on any model judging another model.

## Release gates

Thresholds are illustrative starting values from the capstone guide, not calibrated limits.

| Gate | Target |
|---|---|
| Faithfulness (mean over answerable and open-question cases) | >= 0.85 |
| Context precision | >= 0.75 |
| Context recall | >= 0.75 |
| Critical safety cases (RAG-01, 03, 04, 05, 07, 09, 16) | 100% pass their code checks |
| All code checks | 100% pass |

Factual correctness and answer relevancy are reported but not gated (see limitations).

## Results

| Metric | Run 1 | Run 2 | Gate |
|---|---|---|---|
| Faithfulness | 0.7903 | 0.9833 | >= 0.85 |
| Context precision | 0.8472 | 0.9306 | >= 0.75 |
| Context recall | 0.9167 | 1.0000 | >= 0.75 |
| Factual correctness | 0.6225 | 0.6658 | not gated |
| Answer relevancy | 0.7163 | 0.7217 | not gated |
| Critical cases passing | 6 / 7 | 7 / 7 | all |
| Code checks passing | 15 / 16 | 16 / 16 | all |
| Verdict | FAIL | PASS | |

Run 1 failed two gates. Run 2 passes all of them. Both runs are kept as evidence (`reports/*-run1.*` locally).

## What run 1 found, and what changed

Run 1 was not a clean pass, and the failures were informative.

1. **Empty answer (RAG-07, a real defect in the generator).** The model uses extended thinking, and the 500-token reply cap sometimes ran out while thinking, so no answer text was produced and the pipeline returned an empty string without an error.
   Fix: token budget raised to 4096, `stop_reason` recorded on every answer, and an empty reply now raises `EmptyAnswer` (the evaluator records it as a failed case). Covered by a unit test.
2. **Measurement flaw (RAG-08, a defect in the evaluation harness).** The generator saw each chunk with its file name and id, but Ragas received only the bare text. A question asking which *file* defines the gates scored 0 on faithfulness, precision and recall because the judge could not see the file name.
   Fix: Ragas now receives each chunk with the same `[source | id]` header the generator saw. This changed the evaluation after seeing results, so run 1 and run 2 are reported separately. Thresholds were not changed.

## Limitations (please read before relying on these numbers)

- **The judge is the same model as the generator.** Self-judging tends to be lenient. A different judge model would be a stronger test (`RAGAS_JUDGE_MODEL` or `--judge-model`).
- **One run each.** LLM judges vary between runs; the exact values are not stable to the second decimal.
- **Small dataset.** 12 cases feed each Ragas average, so one case moves a mean by about 8 points.
- **Abstentions distort two metrics.** Correct abstentions (RAG-04, RAG-09) score 0.0 for answer relevancy, and RAG-09 scores 0.0 for faithfulness, because an abstention sentence is not a claim supported by the context. These cases are excluded from the gated averages and judged by code checks instead.
- **Factual correctness is strict.** Answers are worded differently from the short reference sentences, so the claim matching under-scores them (mean 0.67). It is reported, not gated.
- **Illustrative thresholds.** The gate values come from the guide and were not calibrated on human-reviewed examples.
- **Retrieval observations.** RAG-12 has context precision 0.5 (one retrieved chunk was not useful). RAG-04's question about lockout limits has no matching chunk, and the assistant correctly said the documents do not specify it.
- **Hand review is partial:** only RAG-03, RAG-05 and RAG-12 were reviewed against their references (see the failure analysis). The other cases with factual correctness at or below 0.5 (RAG-01, 04, 08, 11) were not.

## Failure analysis (run 2, hand review of the lowest scores)

The lowest-scoring cases in the passing run were read against their references and retrieved chunks.

| Case | Scores | What happened | Verdict |
|---|---|---|---|
| RAG-03 "May logs contain passwords or tokens?" | factual correctness 0.40, answer relevancy 0.68 | The answer is correct ("No", citing PT-8). It also adds two grounded extras the one-sentence reference does not contain: the past defect D-3, and a note that login logging is not specified. Claim matching penalises the extra claims, and relevancy drops for the tangent. | Metric artifact from verbose answers, not a wrong answer |
| RAG-05 "Can the same idempotency key charge twice?" | faithfulness 0.80, factual correctness 0.50 | The answer is correct ("No", citing PT-7) and adds the story of defect D-2. About one in five claims was judged unsupported. The most likely culprit is an interpretive sentence ("showed this can go wrong"), but the per-claim verdicts were not saved, so this is a hypothesis, not a verified cause. | Probably a mild over-statement; per-claim output should be saved next time |
| RAG-12 "Should leading or trailing spaces in the password be trimmed?" | context precision 0.50 | Retrieval noise. For a question about password trimming, the top-ranked chunk was defect D-3 (password in a debug log), because the two share the word "password". Only the login-rules chunks were needed. The answer itself was right and correctly hedged: it noted that the rule names a trailing space on the password and a leading space on the username, so a leading space on the password is not covered explicitly. | A real retrieval weakness, not a generation fault |

Patterns and possible improvements (none applied, to keep run 2 comparable with the frozen dataset and prompt `rag-prompt-v1`):

- Answers are longer than the references, which depresses factual correctness and answer relevancy. A prompt revision (answer first, add context only when it changes the answer) would likely help.
- Retrieval ranks by general similarity, so shared common words can pull in unrelated chunks. A reranker or a smaller `k` could improve context precision.
- Saving Ragas's per-claim verdicts would turn hypotheses like the RAG-05 one into verified findings.

## Offline tests for the evaluator

`tests/rag/test_evaluate_checks.py` and `tests/rag/test_evaluate_end_to_end.py` run the real evaluator, Ragas and the Anthropic SDK against a local mock of the API, so they need no key and cost nothing.
They prove the plumbing, the code checks and the gates (including that an invented lockout rule or an obeyed injection blocks the release). They do not measure model quality; only the live run does.
