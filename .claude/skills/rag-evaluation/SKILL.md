---
name: rag-evaluation
description: Evaluate a retrieval-augmented QA workflow using curated cases and Ragas.
---

# RAG evaluation workflow
1. Validate each dataset row has a question, reference answer, and relevant reference context.
2. Include answerable, ambiguous, stale-document, conflicting-document, and unanswerable cases.
3. Record retrieved contexts and generated answers, not just the final answer.
4. Evaluate retrieval quality separately from answer faithfulness and relevance.
5. Record model, prompt, embedding, chunking, retriever, and dataset versions.
6. Never use a metric score as the only release decision.
7. Compare against the previous baseline and inspect examples behind score changes.
8. Save a machine-readable report and list known limitations.
9. Real Ragas metrics only: never write scores by hand.
