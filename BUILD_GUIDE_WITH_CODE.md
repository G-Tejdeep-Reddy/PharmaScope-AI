# PharmaScope AI — run guide

Use the files in this repository; no code needs to be copied from a tutorial. Commands below run from the repository root. **Requirements:** Python 3.12, Node.js 22.12+, npm, internet access, and a compatible LLM API account. Docker is optional.

## 1. Install

Extract the ZIP and enter `pharmascope-ai/` (or clone your own GitHub repository).

```bash
cd /path/to/pharmascope-ai
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
npm --prefix frontend ci
cp .env.example .env
```

**Files:** `backend/requirements.txt`, `frontend/package-lock.json`, `.env.example`.

## 2. Configure the LLM

Edit `.env`: set `LLM_URL` to your provider's full chat-completions endpoint, `LLM_API_KEY` to your private key, and `LLM_MODEL` to its model identifier. Keep the default embedding model initially. Keys stay on the backend; never commit `.env`.

**File:** `backend/app/main.py` expects `messages` in and `choices[0].message.content` out. Providers using a different protocol or unsupported model parameters need an adapter here.

## 3. Fetch and approve evidence

```bash
PYTHONPATH=backend python -m app.ingest fetch
PYTHONPATH=backend python -m app.ingest list
```

Review the listed URLs. Start with SUSTAIN 7 (`NCT02648204` and `29397376`); check drug, formulation, indication, and results availability. Create `data/selected_ids.txt` with one approved **full document_id** from the printed inventory per line. Do not put just the NCT ID or PMID there.

```bash
PYTHONPATH=backend python -m app.ingest approve
PYTHONPATH=backend python -m app.ingest index
```

**Files:** `backend/app/ingest.py` downloads and approves; `backend/app/core.py` builds the index. First indexing downloads the embedding model. Source data and index files are generated locally, not bundled clinical evidence.

## 4. Run the backend — Terminal A

```bash
source .venv/bin/activate
PYTHONPATH=backend uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API documentation: http://127.0.0.1:8000/docs

## 5. Run the frontend — Terminal B

From the same repository root:

```bash
npm --prefix frontend run dev
```

Open http://127.0.0.1:5173. **Generate cited answer** is enabled by default. Ask a question and inspect each cited passage. API requests also default to `generate: true`; disable it only for retrieval debugging. Restart the backend after rebuilding the index or editing `.env`.

**Files:** `frontend/src/main.tsx`, `backend/app/main.py`.

## 6. Populate the comparison table

The bundled SQLite database is initialized but empty. Add real, manually checked JSON rows to `data/curated/outcomes.jsonl`. Each row needs:

`trial_id, drug, arm, population, endpoint, time_point, value, units, measure_type, source_passage_id, validated`

Use a real `chunk_id` from `data/index/chunks.jsonl` as `source_passage_id`; set `validated` to JSON `true` only after checking the original source. Missing clinical results must not be invented.

```bash
PYTHONPATH=backend python -m app.ingest curate
```

Click **Load curated evidence**. Schema/import validation is in `backend/app/core.py` (`load_curated`).

## 7. Check and evaluate

```bash
PYTHONPATH=backend pytest tests -q
npm --prefix frontend run build
```

For retrieval experiments, use `evaluation/question_template.json` to create your own `evaluation/development.jsonl` and held-out `evaluation/test.jsonl`, one question per line, with real gold passage IDs and evidence-family `group_id` values. Then run:

```bash
PYTHONPATH=backend python evaluation/evaluate.py evaluation/test.jsonl
```

Review generated answers using `evaluation/answer_review_template.csv`. Templates are provided; completed benchmark results are not.

## 8. Docker alternative

After steps 1–3, stop the local servers and start Docker Desktop:

```bash
docker compose up --build
```

Open http://127.0.0.1:5173. Stop with `docker compose down`. See `compose.yaml` and the two `Dockerfile` files. This is local hosting; AWS deployment and scheduled refreshes are not included.

**If something fails:** 503 → check `.env` and index; 502 → check provider settings/response format; missing module → activate `.venv`; browser connection/CORS error → confirm ports 5173/8000. See `VERIFICATION.md` for what has actually been tested.
