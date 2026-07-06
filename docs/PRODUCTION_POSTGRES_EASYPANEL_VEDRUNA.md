# Production Postgres EasyPanel - Vedruna

This repository must use durable Postgres in production. The app refuses `APP_ENV=production` without a Postgres-like `DATABASE_URL`.

## Required production variables

```env
APP_ENV=production
TZ=Europe/Madrid
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
RPA_DRY_RUN=false
RPA_BASE_URL=https://vedruna-rpa-rpa.ddxo6v.easypanel.host
RPA_API_KEY=<set in EasyPanel only>
OPENAI_API_KEY=<set in EasyPanel only>
```

Do not commit real values. Do not print them in logs.

## Driver compatibility

`core/persistence/factory.py` accepts URLs beginning with `postgres`, so both of these forms are accepted by the factory:

- `postgresql://USER:PASSWORD@HOST:5432/DBNAME`
- `postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME`

`pyproject.toml` includes the optional Postgres dependency:

```toml
postgres = [
  "psycopg[binary]>=3.2",
]
```

For production images, install the app with the Postgres extra or otherwise ensure `psycopg` is available.

## Readiness checks

Before setting `RPA_DRY_RUN=false`:

1. `/healthz` reports `env=production`.
2. `/healthz` reports `store_type=postgres`.
3. `/healthz` reports `persistence_durable=true`.
4. `/healthz` reports `tables_ready=true`.
5. RPA `/health` has been checked without secrets in output.
6. A controlled RPA availability smoke passes.
7. A controlled create/cancel or create-only smoke is approved by the clinic owner.

## Rollback

If Postgres readiness or RPA smoke is uncertain, keep or restore `RPA_DRY_RUN=true`. Do not switch to memory storage in production.
