# Verification

## Current package

- Seven automated checks passed: source-version passage identity, claim citation schema, empty retrieval filters, retrieval metrics, rejection of unknown generated citation IDs, curated-passage integration/filtering, and generation enabled by default with a valid cited response.
- The generation check uses a simulated provider response, not a live LLM.
- TypeScript checking and Vite production build passed.
- Python source compilation passed.
- The API and frontend both default to cited answer generation. Retrieval-only mode remains available for diagnostics.

## Earlier pipeline smoke check

The source implementation was previously exercised with live ClinicalTrials.gov, PubMed and openFDA downloads. The Sentence Transformers model encoded text into 384-dimensional vectors. Two selected SUSTAIN 7 sources (NCT02648204 and PMID 29397376) produced 595 indexed passages, and an in-process FastAPI query returned HTTP 200 with six PubMed passages. These were technical smoke checks, not accuracy benchmarks; passage count is not a count of independent studies.

## Not verified

Live LLM generation, factual/citation accuracy on a held-out benchmark, browser visual rendering, macOS execution, Docker execution, AWS deployment and analyst time savings have not been verified. Automated refresh/change monitoring is not implemented.

## Archive contents

All documented source files and data directories are included. The SQLite database is initialized with an empty outcomes table, and `data/curated/outcomes.jsonl` is empty. No clinical numerical outcomes or completed benchmark scores have been invented. Download source records and populate reviewed evidence during setup.

API keys, local `.env`, installed dependencies, model weights, downloaded source text and generated indexes are excluded. The archive root is `pharmascope-ai/`; upload its contents to your own repository.
