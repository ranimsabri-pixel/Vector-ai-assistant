#!/usr/bin/env bash
# Entrypoint du conteneur mono-service Render (S5 J55).
# Ordre strict (cf docs/DEPLOYMENT_RENDER.md decision A) :
#   1. Attente Neon disponible (cold start possible, plan gratuit)
#   2. Migrations Alembic (idempotent)
#   3. Seed agent systeme + seed compte demo (idempotents, zero appel LLM)
#   4. Nginx configure avec $PORT (injecte par Render au runtime)
#   5. Uvicorn en arriere-plan (127.0.0.1:8001, jamais expose directement)
#   6. Nginx en premier plan (PID 1 -- recoit les signaux d'arret Render)
set -euo pipefail

cd /app/backend

DB_WAIT_TIMEOUT_SECONDS="${DB_WAIT_TIMEOUT_SECONDS:-30}"

echo "[entrypoint] Attente de la base de donnees (timeout ${DB_WAIT_TIMEOUT_SECONDS}s)..."
python - <<PYEOF
import asyncio
import os
import sys
import time

import asyncpg

async def wait_for_db() -> None:
    timeout = int(os.environ.get("DB_WAIT_TIMEOUT_SECONDS", "30"))
    dsn = os.environ["DATABASE_URL"].replace("postgresql+asyncpg://", "postgresql://")
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            conn = await asyncpg.connect(dsn, timeout=5)
            await conn.close()
            print("[entrypoint] Base de donnees disponible.")
            return
        except Exception as e:  # noqa: BLE001
            last_error = e
            await asyncio.sleep(2)
    print(f"[entrypoint] ERREUR : base de donnees injoignable apres {timeout}s ({last_error})", file=sys.stderr)
    sys.exit(1)

asyncio.run(wait_for_db())
PYEOF

echo "[entrypoint] Migrations Alembic..."
alembic upgrade head

echo "[entrypoint] Seed agent systeme..."
python -m app.db.seed

echo "[entrypoint] Seed compte demo (idempotent, zero appel LLM)..."
python -m app.db.seed_demo || echo "[entrypoint] AVERTISSEMENT : seed demo echoue, on continue (pas bloquant pour le service)"

echo "[entrypoint] Configuration Nginx (PORT=${PORT:-10000})..."
export PORT="${PORT:-10000}"
envsubst '${PORT}' < /app/deploy/nginx.conf.template > /etc/nginx/nginx.conf

echo "[entrypoint] Lancement Uvicorn (127.0.0.1:8001)..."
uvicorn app.main:app --host 127.0.0.1 --port 8001 --workers 1 &
UVICORN_PID=$!

echo "[entrypoint] Attente disponibilite backend..."
for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:8001/health > /dev/null 2>&1; then
        echo "[entrypoint] Backend pret."
        break
    fi
    if ! kill -0 "$UVICORN_PID" 2>/dev/null; then
        echo "[entrypoint] ERREUR : Uvicorn s'est arrete de facon inattendue." >&2
        exit 1
    fi
    sleep 1
done

echo "[entrypoint] Lancement Nginx (port ${PORT})..."
exec nginx -g "daemon off;"
