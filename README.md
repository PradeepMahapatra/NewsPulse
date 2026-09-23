# NewsPulse

NewsPulse is being built as a real-time multilingual news sentiment analytics platform.

The project is being developed incrementally. Phase 3 adds PostgreSQL persistence to the Currents API ingestion layer; the FastAPI and Streamlit shells remain independently runnable.

## Local setup

Create and activate the Python virtual environment:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

Install backend dependencies:

```bash
python -m pip install -r backend/requirements.txt
```

Install dashboard dependencies:

```bash
python -m pip install -r dashboard/requirements.txt
```

Configure the Currents API key locally:

```bash
cp .env.example .env
```

Set `CURRENTS_API_KEY` in `.env`. The file is ignored by Git, and the key is never returned by the API or written to logs.

## PostgreSQL with Neon

Create a free Neon project and copy its pooled PostgreSQL connection string from the Neon dashboard. Set it locally in `.env` as `DATABASE_URL`. Never put the connection string in `.env.example`, source control, tests, or logs. The `.env` file must never be committed.

Initialize the schema from the project root:

```bash
python -m backend.app.database.init_db
```

## Run the backend

From the project root:

```bash
uvicorn backend.app.main:app --reload
```

The API is available at <http://127.0.0.1:8000/>. Interactive API documentation is available at <http://127.0.0.1:8000/docs>.

## Test news ingestion

Run the tests from the project root:

```bash
pytest -q
```

With the API server running and a valid `CURRENTS_API_KEY` configured, request a small batch of current articles:

```bash
curl "http://127.0.0.1:8000/articles/fetch?limit=5"
```

The endpoint fetches articles from Currents, normalizes them, removes duplicates within the ingestion run, and stores them in PostgreSQL. Retrieve persisted records with:

```bash
curl "http://127.0.0.1:8000/articles?limit=20"
```

Repeated articles are ignored using Currents article ID and URL uniqueness constraints. This phase does not perform NLP or sentiment analysis, schedule requests, or call AWS services.

## Run the dashboard

From the project root, in a separate terminal:

```bash
streamlit run dashboard/app.py
```

The dashboard opens at the local URL shown by Streamlit, usually <http://localhost:8501>.

The backend and dashboard are currently independent. The dashboard does not call the backend yet; that integration will be added in a later phase.
