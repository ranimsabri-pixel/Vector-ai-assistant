# Vector — image mono-conteneur pour Render.com free tier (S5 J55).
# 3 stages : frontend-builder (Next.js export statique), backend-deps
# (venv Python isole), image finale (Python runtime + Nginx, sans les
# outils de build). Cf docs/DEPLOYMENT_RENDER.md pour le detail des
# decisions (Nginx interne, export statique F1, pas de process Node en prod).

# ============================================================
# Stage 1 : frontend-builder
# ============================================================
FROM node:22-slim AS frontend-builder

WORKDIR /app/frontend

# NEXT_PUBLIC_API_URL est inline dans le bundle JS AU BUILD (export
# statique Next.js) -- doit correspondre au prefixe proxy Nginx (decision A).
ENV NEXT_PUBLIC_API_URL=/api

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile

COPY frontend/ ./
RUN pnpm build

# ============================================================
# Stage 2 : backend-deps (venv isole, outils de build jetes ensuite)
# ============================================================
FROM python:3.11-slim AS backend-deps

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
# pip install . a besoin du code source present (setuptools lit app/ pour
# construire le package, cf [tool.setuptools.packages.find] dans
# pyproject.toml) -- pas de cache de layer possible ici sur les deps
# seules, mais priorite a la simplicite/fiabilite pour ce sprint.
COPY backend/pyproject.toml ./
COPY backend/app ./app
RUN python -m venv /venv \
    && /venv/bin/pip install --upgrade pip \
    && /venv/bin/pip install .

# ============================================================
# Stage 3 : image finale
# ============================================================
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    gettext-base \
    curl \
    && rm -rf /var/lib/apt/lists/*

# venv Python (deps deja compilees, pas de gcc/headers dans cette image)
COPY --from=backend-deps /venv /venv
ENV PATH="/venv/bin:$PATH"

WORKDIR /app/backend
COPY backend/app ./app
COPY backend/alembic.ini ./alembic.ini
COPY backend/migrations ./migrations

# Export statique Next.js -- servi directement par Nginx, aucun process
# Node en production (decision F, budget RAM 512 Mo).
COPY --from=frontend-builder /app/frontend/out /app/frontend/out

COPY deploy/nginx.conf.template /app/deploy/nginx.conf.template
COPY deploy/entrypoint.sh /app/deploy/entrypoint.sh
RUN chmod +x /app/deploy/entrypoint.sh

# uploads/ est ephemere (disque non persistant sur le free tier Render) --
# re-seede a chaque demarrage via app.db.seed_demo, cf ce fichier.
RUN mkdir -p /app/backend/uploads

# $PORT est injecte par Render au runtime, pas connu au build -- pas
# d'EXPOSE fixe possible ici (documente dans docs/DEPLOYMENT_RENDER.md).
ENTRYPOINT ["/app/deploy/entrypoint.sh"]
