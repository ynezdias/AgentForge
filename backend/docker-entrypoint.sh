#!/bin/sh
# Container start: migrate, create accounts if configured, then serve.
# Running migrations here (not in a pre-deploy hook) works on every hosting plan.
set -e

echo "Applying database migrations"
python -m alembic upgrade head

# Demo accounts: only when configured, and the script itself refuses APP_ENV=production.
if [ -n "${DEMO_ADMIN_EMAIL:-}" ] && [ "${APP_ENV:-development}" != "production" ]; then
  python -m app.db.seed_users || echo "Demo account seeding skipped"
fi

# First real admin: only when configured. Never modifies an existing account.
python -m app.db.bootstrap_admin || echo "Admin bootstrap skipped"

# Hosts such as Render provide PORT; default to 8000 locally.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
