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

## Phase 7 AWS integration

Phase 7 adds small, optional AWS integration without replacing Neon PostgreSQL, FastAPI, or Streamlit:

```text
Neon PostgreSQL -> FastAPI snapshot service -> private S3 snapshots
									  -> Lambda payload handler -> private S3
```

S3 stores safe article/NLP JSON snapshots under `newspulse/snapshots/YYYY/MM/DD/`. The API endpoint is `POST /articles/snapshot`; it reads existing article records, excludes database internals and credentials, and returns the bucket name, object key, article count, and timestamp. The Lambda entry point is `backend.lambda_handler.handler`. It accepts a small payload such as `{"snapshot_type": "articles", "articles": []}` and does not connect to Neon or load the transformer model.

Required non-secret settings are `AWS_REGION` and `S3_BUCKET_NAME`. They may be placed in local `.env`; AWS access keys must not be placed in `.env`, source code, tests, or this repository. boto3 uses the standard AWS credential provider chain, such as an AWS CLI profile or an attached runtime role. Configure local credentials with the AWS CLI or another supported local mechanism without sharing credential values in chat.

The policy in `docs/iam/news-pulse-snapshot-lambda-policy.json` grants only `s3:PutObject` on `newspulse/snapshots/*` in the configured bucket. It does not grant bucket administration, public access, reads, deletes, or `s3:*`. S3 objects are written with private default ACL behavior and AES-256 server-side encryption. Lambda logs safe invocation, validation, count, key, and failure information through its normal CloudWatch log stream; no detailed monitoring or custom paid observability is enabled.

No AWS resources are created by the local application or test suite. Before creating a bucket, Lambda function, IAM role, or other AWS resource, review the AWS Free Tier, credits, and Billing console. S3 storage/requests, Lambda invocations, CloudWatch logs, and IAM-related setup can incur charges outside applicable allowances. Keep snapshots tiny and use a billing alert or budget according to the account's current pricing and budget terms.

AWS tests use mocked clients:

```bash
pytest -q backend/tests/test_snapshot.py backend/tests/test_api_snapshot.py
```

The optional API endpoint requires an already-created private bucket and valid standard-chain AWS credentials. For this development setup, AWS CLI authentication is used locally through the CLI login/profile provider; the Python dependency uses `boto3[crt]` so boto3 can consume that provider. The configured deployment region is `ap-south-1`.

The real Phase 7 development resources are one private S3 bucket following `newspulse-<account-id>-ap-south-1`, one `newspulse-phase7-snapshot` Lambda function, one `NewsPulsePhase7LambdaRole` execution role, and the Lambda-created `/aws/lambda/newspulse-phase7-snapshot` CloudWatch log group. Neon remains the database; no AWS database or application hosting resources are used.

To invoke the deployed Lambda with a tiny local payload, use a file containing only safe article data and the standard AWS CLI credential provider:

```bash
aws lambda invoke --function-name newspulse-phase7-snapshot \
	--cli-binary-format raw-in-base64-out \
	--payload fileb://event.json response.json
```

To clean up the Phase 7 development resources after review, first empty the bucket and then delete the Lambda, inline role policy, role, and bucket. Verify each name against the AWS console before running cleanup:

```bash
aws s3 rm s3://newspulse-<account-id>-ap-south-1 --recursive
aws lambda delete-function --function-name newspulse-phase7-snapshot
aws iam delete-role-policy --role-name NewsPulsePhase7LambdaRole --policy-name NewsPulsePhase7LambdaPolicy
aws iam delete-role --role-name NewsPulsePhase7LambdaRole
aws s3api delete-bucket --bucket newspulse-<account-id>-ap-south-1
```

CloudWatch log retention and deletion can be managed separately with the AWS console or `aws logs delete-log-group --log-group-name /aws/lambda/newspulse-phase7-snapshot` after confirming the log group belongs to this project.

## Phase 8 Docker containers

Docker packages the application layer only. Neon PostgreSQL, Currents, S3, Lambda, and CloudWatch remain external services reached through runtime configuration; no database or AWS service is placed inside a container.

The backend image uses Python 3.12 and starts `backend.app.main:app` with Uvicorn on container port `8000`. Its Dockerfile installs the CPU-only Torch wheel because the container has no GPU and does not need CUDA packages; the required Hugging Face model and sentiment architecture are unchanged. The dashboard image uses Python 3.12 and starts `dashboard/app.py` with Streamlit on container port `8501`. Both Dockerfiles use the repository root as their build context so the existing Python package paths remain valid.

Build the local images from the project root:

```bash
docker build -f backend/Dockerfile -t newspulse-backend .
docker build -f dashboard/Dockerfile -t newspulse-dashboard .
```

Run the backend with the existing external-service settings supplied at runtime. Do not use `COPY .env` or put secrets in a Dockerfile:

```bash
docker network create newspulse-net
docker run --rm --name backend --network newspulse-net --env-file .env -p 8000:8000 newspulse-backend
```

Run the dashboard on the same Docker network. Inside a container, `localhost` means that container, so the dashboard must use the backend service/container name rather than `127.0.0.1`:

```bash
docker run --rm --name dashboard --network newspulse-net \
	-e API_BASE_URL=http://backend:8000 -p 8501:8501 newspulse-dashboard
```

The backend is available from the host at <http://127.0.0.1:8000/docs>; the dashboard is available at <http://127.0.0.1:8501>. Required backend runtime variables include `DATABASE_URL`, `CURRENTS_API_KEY`, `AWS_REGION`, and `S3_BUCKET_NAME`; the dashboard needs only `API_BASE_URL`. These values are passed at runtime and are never embedded in images. The root `.dockerignore` excludes `.env`, virtual environments, Git metadata, caches, bytecode, and local artifacts while retaining application source and requirements.

This phase does not add Docker Compose, CI/CD, deployment, or production infrastructure. Inspect local images with `docker images` and `docker inspect`; do not use `docker history` or logs to share secret-bearing command lines.
