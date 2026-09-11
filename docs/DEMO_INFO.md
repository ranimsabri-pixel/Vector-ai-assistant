# Démo publique Vector — informations jury

## URL et accès

- URL publique : https://ai-commandos-multi-agent.onrender.com
- Hébergement : Render.com tier Free (Frankfurt, région eu-central)
- Base de données : Neon Postgres (Frankfurt) avec extension pgvector

## Compte démo pré-rempli

- Email : demo@vector.ai
- Mot de passe : VectorDemo2026!

Contenu pré-chargé :
- 1 dataset : ibm_sales_pipeline_2025.csv (1000+ lignes)
- 1 corpus : IBM Documentation Stratégique 2025 (2 documents)
- 1 persona : Vector Analyste Finance IBM
- 3 conversations d'exemple avec messages pré-remplis

## Comportement cold start

Le tier Free Render met le service en veille après 15 min sans trafic.
La première requête après veille prend [À COMPLÉTER APRÈS TEST] secondes
(mesuré le [À COMPLÉTER], chronomètre depuis clic navigateur jusqu'à
affichage complet de la page /login).

> Non mesuré à la rédaction de ce document : le service vient d'enchaîner
> plusieurs redéploiements (derniers fixes migrations/seed), donc toute
> requête faite maintenant mesurerait une instance déjà chaude, pas un
> vrai cold start. À mesurer après ≥15 min sans trafic sur le service.

Recommandation pour la soutenance : pinger l'URL 3 minutes avant la démo
pour réveiller le service en amont.

## Kill switch en cas d'incident

En cas de problème pendant la soutenance (spam, contenu inapproprié,
comportement inattendu), désactivation en 60 secondes maximum :

1. Se connecter sur https://dashboard.render.com
2. Sélectionner le service "ai-commandos-multi-agent"
3. Menu de gauche : Environment
4. Ajouter ou modifier : DEMO_DISABLED = true
5. Save Changes
6. Attendre 60 secondes que Render prenne en compte le changement

Restauration après incident : mettre DEMO_DISABLED = false (ou supprimer
la variable) et Save Changes.

## Code source

- Repository : https://gitlab.com/Welyne-Dev/ai-commandos-multi-agent
- Branche principale : vector-agent
- Dernier commit stable au déploiement : `67616c1` — fix(seed_demo): use
  live vector_agent.id instead of stale fixture uuid (2026-08-28)

## Stack technique

Backend :
- Python 3.11
- FastAPI + Uvicorn
- SQLAlchemy 2.0 async + asyncpg
- Alembic (migrations)
- OpenAI SDK (gpt-4o, gpt-4o-mini, text-embedding-3-small)
- slowapi (rate limiting)
- APScheduler (tâches planifiées, cleanup 48h des comptes invités)

Frontend :
- Next.js 16 (static export)
- TypeScript
- Tailwind CSS v4
- Zustand + TanStack Query
- ApexCharts

Base de données :
- PostgreSQL 16 avec extension pgvector
- Extension Postgres pgvector : 0.8.6 (managée par Neon, vérifiée via
  SELECT extversion FROM pg_extension WHERE extname = 'vector')
- Client Python pgvector-python : 0.3.6 (backend/pyproject.toml)
- Neon (managed Postgres serverless)

Conteneurisation :
- Docker multi-stage (frontend-builder + backend-deps + stage-2 avec
  Nginx + Uvicorn)
- Nginx interne (reverse proxy /api → 127.0.0.1:8001, / → static frontend)

Hébergement :
- Render.com (compute)
- Neon.tech (base)
- GitLab.com (source)

Coût mensuel : 0 € (tiers gratuits + clé OpenAI démo perso plafonnée à $15)

## Configuration Render du service

- Runtime : Docker
- Region : Frankfurt
- Instance : Free (512 MB RAM, 0.1 CPU)
- Health check path : /health
- Auto-deploy : On Commit (branche vector-agent)

Variables d'environnement configurées :
- OPENAI_API_KEY (secret)
- DATABASE_URL (secret, connection string Neon avec sslmode=require)
- SECRET_KEY (secret, pour JWT)

## Contact

Ranim SABRI
Étudiante 5A INSAT — Instrumentation et Maintenance Industrielle
Stagiaire Welyne — Programme A.I. Commandos, été 2026
Email : ranim.sabri@insat.ucar.tn
