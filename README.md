# JevPR

[![Listed in Awesome Jev](https://awesomejev.vercel.app/badge.svg)](https://awesomejev.vercel.app/p/jevpr/)

JevPR is a GitHub App that routes pull-request review work using [Jev By TypeSafe](https://typesafe.ai/) as the decision engine.

When a pull request is opened or updated, the app ingests the GitHub webhook, normalizes the pull request context, sends it to Jev, and receives a structured decision such as `LOW`, `NORMAL`, or `SPECIALIST`. A deterministic policy layer then maps that decision to an action like auto-approval, a request for review, or a check-run update.

## Architecture

- `api/` exposes FastAPI endpoints for health and webhook ingestion.
- `providers/` isolates Jev behind a provider boundary.
- `decisions/` contains the normalized context model, decision result model, and routing policy.
- `services/` coordinates webhook handling and evaluation.
- `workers/` contains Celery worker wiring for asynchronous GitHub work.
- `db/` contains SQLAlchemy models and repository helpers.

## Configuration

Runtime settings are loaded from environment variables and an optional YAML file at `.github/jevpr.yml` in the repository. If the YAML file is not present, a default policy is used.

The YAML file controls both the action mapping and the GitHub reviewers that may be assigned by policy.

Example:

```yaml
reviewers:
	- username: alice
		github_id: 1001

actions:
	LOW:
		action: approve
	NORMAL:
		action: request_review
		reviewers:
			- alice
```

## Local Development

1. Create a virtual environment.
2. Install the package in editable mode with dev dependencies.
3. Start the API with `uvicorn JevPR.main:app --reload`.

IT IS HIGHLY RECOMMENDED TO DEPLOY WITH DOCKER

## Docker

Use `docker compose up -d --build` to start the API, worker, PostgreSQL, and Redis.

Port rules in Docker mode:

- `API_PORT` controls the host port for the FastAPI service. The container still listens on `8000`.
- `POSTGRES_PORT` controls the host port mapped to the Postgres container. Inside Compose, other services reach it at `db:5432`.
- `REDIS_PORT` controls the host port mapped to the Redis container. Inside Compose, other services reach it at `redis:6379`.

In Docker mode, the app container uses `DATABASE_URL=postgresql+psycopg://jevpr:jevpr@db:5432/jevpr` and `REDIS_URL=redis://redis:6379/0`. The localhost versions in `.env` are for running on your machine outside Docker.

Permissions required for the GitHub App:
- Checks: Read & Write
- Contents: Read
- Issues: Read & Write
- Merge queues: Read & Write
- Pull requests: Read & Write

License: Apache-2.0

Don't forget to leave a Star!

This Project is Under Development and can contain bugs. Additionally Jev is an AI model, and can make mistakes.
