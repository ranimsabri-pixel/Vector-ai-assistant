# Vector — Enterprise AI Assistant

[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen)](https://ai-commandos-multi-agent.onrender.com)
[![Tests](https://img.shields.io/badge/tests-310_unit_%2B_46_E2E-blue)](.)
[![Coverage](https://img.shields.io/badge/coverage-75%25-green)](.)
[![Stack](https://img.shields.io/badge/stack-FastAPI_%2B_Next.js-orange)](.)

Vector is an enterprise AI assistant that lets business users interact with their tabular data and internal documents in natural language. Built as an engineering internship project at Welyne within the A.I. Commandos program.

## Live demo

**URL:** https://ai-commandos-multi-agent.onrender.com

**Demo account:**
- Email: `demo@vector.ai`
- Password: `VectorDemo2026!`

The demo runs on a free tier, so the first request after inactivity may take 60-90 seconds to warm up.

## Features

- **Conversational chat** with streaming responses, multimodal image analysis, and web search toggle
- **Tabular data analysis** — CSV/Excel upload with automatic profiling and generated dashboards
- **Document RAG** — PDF, DOCX, PPTX ingestion with vector search and source citations
- **Custom personas** combining instructions, corpora and datasets
- **Auto-generated dashboards** with KPI cards and interactive charts
- **Full RGPD compliance** with total account and data deletion in cascade

## Tech stack

**Backend:** Python 3.11 · FastAPI · SQLAlchemy 2.0 async · PostgreSQL 16 + pgvector · Alembic · pytest · Ruff

**Frontend:** Next.js 16 · TypeScript · Tailwind CSS v4 · Radix UI · shadcn/ui · ApexCharts · Zustand · TanStack Query

**AI:** OpenAI GPT-4o · text-embedding-3-small · Tavily API

**Infra:** Docker (multi-stage) · Nginx · GitLab CI/CD · Render.com · Neon Postgres

## Numbers

- 310 backend unit tests (pytest, 75% coverage)
- 46 end-to-end tests (Playwright)
- Full CI pipeline in 7 min 39 s
- Production cold start: 82 s · warm health check: 75 ms median

## Getting started

### Prerequisites

- Docker Desktop
- An OpenAI API key

### Environment setup

Copy the environment templates and fill in your values:

    cp backend/.env.example backend/.env
    cp frontend/.env.example frontend/.env

Required variables:
- `OPENAI_API_KEY` — your OpenAI API key
- `DATABASE_URL` — PostgreSQL connection string
- `JWT_SECRET` — random string for JWT signing

### Run with Docker Compose

    docker compose up

- Backend: http://localhost:8000
- Frontend: http://localhost:3000
- Swagger docs: http://localhost:8000/docs

### Run tests

    # Backend unit tests
    cd backend && pytest

    # Frontend E2E tests
    cd frontend && pnpm test:e2e

## Documentation

- **Full internship report** (French, 59 pages, PDF): [rapport_stage/main.pdf](rapport_stage/main.pdf)

## Architecture

Three-layer architecture with a mono-container Docker deployment for the free tier:

- **Presentation:** Next.js frontend (statically exported for production)
- **Business logic:** FastAPI backend with async SQLAlchemy
- **Persistence:** PostgreSQL 16 with pgvector for embeddings

See the full report for detailed architecture diagrams and design decisions.

## Author

**SABRI Ranim** — Engineering student at INSAT, Instrumentation and Industrial Maintenance track. Internship at Welyne, A.I. Commandos program, summer 2026.

## Acknowledgements

Developed at Welyne under the supervision of Mohammed Ben Arfa.

## License

This project was developed as an internship project. Rights belong to Welyne. Displayed publicly with permission for portfolio purposes.