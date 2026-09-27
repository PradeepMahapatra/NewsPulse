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

## Phase 4 NLP and sentiment analysis

Stored articles can be enriched locally with the Hugging Face model `cardiffnlp/twitter-xlm-roberta-base-sentiment`. The model is multilingual, does not require an API key, and returns one of `positive`, `neutral`, or `negative` with the model probability as its confidence score. The model is loaded lazily once per application process and reused across analysis requests.

Initialize the additive NLP columns for an existing database, then analyze unprocessed articles:

```bash
python -m backend.app.database.init_db
curl -X POST "http://127.0.0.1:8000/articles/analyze?limit=20"
```

Retrieve the enriched records with `GET /articles`; NLP fields are nullable until processing succeeds: `language_detected`, `analysis_text`, `sentiment_label`, `sentiment_confidence`, and `analyzed_at`.

Currents language metadata is normalized when it is a supported code. When metadata is absent or unsupported, the service uses deterministic lightweight `langdetect` fallback detection; empty text is recorded as a failed analysis rather than sent to the model. Articles are not automatically translated. The classifier was trained for Twitter sentiment, not specifically for news, so its output is an inference signal rather than a guarantee of news sentiment accuracy. It may require a large first download and local disk space.

## FastAPI architecture

The backend uses a small layered REST API:

```text
routers -> article service -> repository -> SQLAlchemy/PostgreSQL
						 -> ingestion and NLP services
```

`backend/app/main.py` creates the FastAPI application and registers the health and article routers. Pydantic response schemas define the public API contract, while repositories keep database access behind short-lived SQLAlchemy sessions. The existing ingestion and NLP services remain responsible for Currents normalization, duplicate handling, language detection, and sentiment analysis.

Available endpoints:

- `GET /` - API liveness response
- `GET /health` - simple health response
- `GET /articles` - list articles with `limit`, `offset`, `sentiment`, `language`, and `category` query parameters
- `GET /articles/{article_id}` - retrieve one stored article
- `POST /articles/fetch` - fetch and persist current news, returning `fetched`, `inserted`, and `duplicates`
- `POST /articles/analyze` - analyze unprocessed articles, returning `processed`, `skipped`, and `failed`

Interactive OpenAPI documentation is available at `/docs`; the machine-readable schema is at `/openapi.json`. For example, `GET /articles?limit=20&offset=0&language=en` returns an `articles` array whose entries include stored article fields and nullable NLP fields: `language_detected`, `analysis_text`, `sentiment_label`, `sentiment_confidence`, and `analyzed_at`.

Run the API from the project root with:

```bash
source .venv/bin/activate
uvicorn backend.app.main:app --reload
```

Phase 5 keeps the current unversioned paths because the application is still a small single API surface; introducing `/api/v1` would add routing overhead without a second public contract to support yet.

Run all backend tests with:

```bash
pytest -q
```

## Phase 6 Streamlit dashboard

The dashboard consumes the FastAPI REST API over HTTP. It never connects directly to PostgreSQL and only needs `API_BASE_URL`; database credentials and the Currents API key remain backend-only settings.

Start the backend in one terminal:

```bash
source .venv/bin/activate
uvicorn backend.app.main:app --reload
```

Start Streamlit in a second terminal:

```bash
streamlit run dashboard/app.py
```

The dashboard opens at the local URL shown by Streamlit, usually <http://localhost:8501>. Configure another local API URL with `API_BASE_URL` in `.env`; the default is `http://127.0.0.1:8000`.

The dashboard provides sentiment, language, country, and category filters; article-volume KPIs; sentiment and language charts; a country-level choropleth; recent article links; article details; manual refresh; and controls that call the existing `/articles/fetch` and `/articles/analyze` endpoints. Countries are mapped only when the API supplies a valid ISO alpha-2 country code; missing country metadata is excluded rather than assigned a location. The dashboard uses the API's current article snapshot, so it does not continuously poll or cache stale records.

Dashboard tests run with:

```bash
pytest -q dashboard/tests
```
