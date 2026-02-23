# ADR-001: Full CV in Context Over RAG Retrieval

## Status: Accepted
## Date: 2026-02-21

## Context

The scorer needs the user's professional history to evaluate job fit. The initial design used ChromaDB for RAG: chunk the CV into ~25 pieces, embed them, retrieve the top 8 per job via cosine similarity.

The knowledge base is two markdown files totaling ~19K characters (~5K tokens). gpt-4o's context window is 128K tokens.

## Decision

Pass the full CV text to every scoring call. Remove ChromaDB, vectorstore.py, and all embedding API calls.

## Rationale

- **Retrieval caused information loss.** A JD requiring "Kafka + header bidding + stakeholder management" returned 6 Kafka chunks and 0 header bidding chunks. The model scored without seeing relevant experience.
- **Cost difference is negligible.** Full CV adds ~3.4K tokens per call. At gpt-4o-mini rates, that's ~$0.001 extra per job. With 25 jobs/run, $0.025/run difference.
- **Massive complexity reduction.** ChromaDB requires C++ compilation, adds ~200MB disk, causes CI build issues in GitHub Actions, and needs 48 embedding API calls per run.
- **No downside at this document size.** RAG exists to handle documents that don't fit in context. At 5K tokens vs 128K window, there's no compression needed.

## Consequences

- Scoring quality improved: model sees complete profile, no retrieval misses
- Eliminated: chromadb dependency, vectorstore.py, embedding API calls, chunk boundary artifacts
- Pipeline simplified: one fewer module, one fewer failure mode
- If the knowledge base grows beyond ~50K tokens (unlikely for a CV), this decision should be revisited
