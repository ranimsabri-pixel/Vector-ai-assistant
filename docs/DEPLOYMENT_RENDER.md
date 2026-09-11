# Déploiement Render.com — Plan technique (S5 J55, Phase 1)

Audit + plan de déploiement de Vector sur Render.com tier gratuit, en
conteneur mono-service. **Document de cadrage, aucun code modifié.**
À valider avant Phase 2 (implémentation).

---

## 1. Audit de la stack actuelle

### Services (`docker-compose.yml`)

| Service | Image | Port | Volume | Rôle réel |
|---|---|---|---|---|
| `db` | `pgvector/pgvector:pg16` | 5432 | `vector_db_data` | Postgres + extension pgvector |
| `redis` | `redis:7-alpine` | 6379 | `vector_redis_data` | **Déclaré mais jamais utilisé** (voir §6) |

Aucun service `backend`/`frontend` dans le compose — ils tournent nativement
(`uvicorn`, `pnpm dev`) en dev local, jamais dockerisés. **Aucun
`Dockerfile` n'existe nulle part dans le repo** — tout est à créer.

### Versions

- Python : `>=3.11,<3.13` (`pyproject.toml`), CI utilise `python:3.11`
- FastAPI `0.115.4`, Pydantic `2.9.2`, SQLAlchemy `2.0.36` (async, `asyncpg`)
- Node : pas de champ `engines` dans `package.json` — CI pin Node 22
- Next.js `16.2.9` (App Router), React `19.2.4`

### Structure

- `backend/app/` : `api/` (routers), `services/` (logique métier),
  `db/models/` + `migrations/` (Alembic), `ai/` (providers LLM)
- `frontend/app/` : App Router, groupes de routes `(app)`/`(auth)`,
  4 segments dynamiques (voir §3)

---

## 2. Dépendances backend

Depuis `pyproject.toml` (35 deps + 8 dev). Poids notables une fois installés
(estimation, wheels Linux) :

| Paquet | Poids approx. | Note |
|---|---|---|
| `pandas` + `numpy` | ~90 Mo | Cœur de l'analyse de données, incompressible |
| `pymupdf` | ~50 Mo | Extraction PDF, bundle MuPDF |
| `pillow` | ~25 Mo | Traitement images |
| `openai` | ~15 Mo | + dépendances (`httpx`, `pydantic`) déjà présentes |
| `celery` | ~10 Mo (+ `kombu`, `billiard`, `vine`) | **Dead weight** — voir ci-dessous |
| Reste (fastapi, sqlalchemy, alembic, python-docx/pptx, etc.) | ~60 Mo | |

**Dépendances système Linux nécessaires** : aucune trouvée explicitement
requise dans le code (pas de `subprocess` vers `poppler`/`tesseract`/etc. —
`pymupdf` est self-contained, pas de binaire externe). `psycopg2-binary`
inclut déjà ses libs. À confirmer empiriquement au premier build Docker
(l'image `python:3.11-slim` manque parfois `libpq-dev`/`gcc` pour compiler
certaines wheels si un binaire précompilé n'existe pas pour la plateforme
cible — point de vigilance Phase 2, pas bloquant pour le plan).

**Celery et Redis : recherche de code réel** —
```
git grep -n "celery\|Celery" -- '*.py'    → 0 résultat hors dépendance déclarée
git grep -n "redis\|Redis" -- '*.py'      → app/core/config.py uniquement
                                             (REDIS_URL: champ de settings,
                                             jamais consommé ailleurs)
```
**Redis et Celery sont entièrement inutilisés dans le code applicatif.**
Aucune tâche async, aucun cache, aucune session, aucun rate limiting
existant ne dépend de Redis. C'est un déclaré-mais-mort depuis le début du
projet (jamais branché). Ça simplifie radicalement la décision C du plan
— il n'y a rien à migrer, juste à ne pas installer.

---

## 3. Dépendances frontend

Principales : `next`, `react`/`react-dom` 19, `@tanstack/react-query`,
`zustand` (state), `react-pdf` (lecteur PDF), `apexcharts`/`recharts`
(dashboards), `xlsx`/`papaparse` (parsing fichiers), `react-dropzone`,
Radix UI (`@radix-ui/*`), `next-themes`.

### Export statique : faisable, avec une réserve importante

- **Aucune route API** (`app/**/route.ts`) — tout passe par le backend
  FastAPI externe via `fetch`.
- **Aucun `middleware.ts`.**
- **Tous les composants sont `"use client"`**, sauf `app/layout.tsx` et
  `app/(auth)/layout.tsx` — deux wrappers structurels purs (fonts,
  `ThemeProvider`, centrage), zéro fetch serveur. Compatibles export statique
  tels quels.
- **4 segments dynamiques** : `datasets/[id]`, `saved-dashboards/[id]`,
  `dashboard/[id]`, `share/[token]`. Tous 100% client-rendus (l'ID vient de
  l'URL, les données sont fetchées côté client). **Problème réel** :
  `output: 'export'` exige que Next.js sache à la build quels chemins
  générer (`generateStaticParams`) — impossible ici, les IDs sont créés
  dynamiquement par les utilisateurs. Cf. décision F ci-dessous, c'est LE
  point d'architecture le plus structurant de ce plan.

`NEXT_PUBLIC_API_URL` est déjà utilisé exactement comme il faut
(`lib/api.ts`, avec fallback `localhost:8000`) — injectable au build sans
changement de code.

---

## 4. Configuration base de données

- `DATABASE_URL` / `DATABASE_URL_SYNC` : variables d'environnement pures
  (`app/core/config.py`, `pydantic-settings`), lues aussi par
  `migrations/env.py` (`settings.DATABASE_URL`) — **déjà 100% compatible**
  avec un branchement direct sur Neon, aucun hardcode nulle part.
- **Aucun mécanisme d'attente DB** n'existe actuellement (`git grep` sur
  retry/wait/`OperationalError` : rien). En local, Postgres est toujours
  déjà up (docker-compose avec `healthcheck`) avant que le backend démarre
  à la main. **À construire pour Render** — Neon peut avoir une latence de
  connexion (cold start du côté Neon si le projet est en plan gratuit avec
  auto-suspend, à vérifier avec toi) que rien ne gère aujourd'hui.
- Migrations : déclenchées manuellement (`alembic upgrade head`) en dev,
  jamais automatisées au démarrage d'un process. À ajouter dans
  l'entrypoint du conteneur.

---

## 5. CORS et URL backend

- CORS : `CORSMiddleware` déjà configuré (`app/main.py`), origines via
  `CORS_ORIGINS` (CSV → liste). Fonctionne tel quel, il suffira d'y mettre
  l'URL Render en prod.
- Frontend → backend : `NEXT_PUBLIC_API_URL`, voir §3. Si mono-conteneur
  avec Nginx en façade, cette variable pointera vers un chemin relatif
  (`/api`) plutôt qu'une URL absolue — voir décision A.

---

## 6. Redis — conclusion

Confirmé au §2 : **zéro usage réel**. Pas de rate limiting, pas de cache,
pas de sessions, pas de jobs Celery effectifs. Suppression pure et simple
sans rien à remplacer fonctionnellement — seul le **rate limiting**
(inexistant aujourd'hui, demandé neuf pour la démo publique) doit être
ajouté via une solution in-memory (`slowapi`, cf décision D), pas migré
depuis quelque chose d'existant.

---

## 7. Fichiers uploadés

`app/services/storage.py` : `FileStorage`, écrit sur
`Path("uploads")` — **chemin relatif au répertoire de travail du process**,
donc dépendant du `WORKDIR` du conteneur. Stockage 100% disque local,
aucun object storage. Sur Render free tier, le disque est éphémère (perdu
à chaque redéploiement/redémarrage) — cf décision E, qui tranche pour
assumer l'éphémère plutôt qu'introduire un object storage externe pour une
démo.

---

## Plan technique

### A. Architecture Dockerfile mono-conteneur

**Multi-stage, 3 étapes :**
1. `frontend-builder` (`node:22-slim`) — `pnpm install --frozen-lockfile`,
   build frontend
2. `backend-deps` (`python:3.11-slim`) — `pip install` dans un
   virtualenv isolé, copié ensuite (évite d'embarquer les headers/compilos
   de build dans l'image finale)
3. Image finale (`python:3.11-slim` + Nginx + Node **si** mode `next start`,
   sinon juste Nginx statique) — copie le venv, le code backend, les
   assets frontend buildés, configure Nginx, lance `entrypoint.sh`

Cible < 500 Mo : réaliste si le stage final ne réinstalle pas les outils de
build (gcc, headers) utilisés uniquement pour compiler les wheels Python —
`pip install` dans le stage `backend-deps`, puis `COPY --from=backend-deps
/venv /venv` dans le stage final, qui lui n'a besoin que du runtime Python,
pas des compilos.

**Nginx interne** : `/api/*` → `proxy_pass` vers Uvicorn (port interne
`127.0.0.1:8001` par ex.), tout le reste → fichiers statiques (export) ou
`proxy_pass` vers le process Next.js (port interne `127.0.0.1:3001`) selon
la décision F. Nginx écoute sur `$PORT` (injecté par Render), seul port
exposé du conteneur.

**`entrypoint.sh`** (ordre strict) :
1. Boucle d'attente Neon accessible (`pg_isready`-like retry, timeout
   raisonnable — Neon peut avoir un cold start)
2. `alembic upgrade head` (idempotent par nature — Alembic ne rejoue pas
   les migrations déjà appliquées)
3. Seed du compte de démo si absent (décision G, idempotent : check
   d'existence avant création)
4. Lancement Uvicorn (1 seul worker, cf budget RAM) en arrière-plan
5. Lancement Next.js **si** mode `next start` (décision F)
6. `exec nginx -g "daemon off;"` en premier plan (PID 1, pour que Render
   reçoive les signaux d'arrêt correctement)

**Question ouverte 1 — Nginx interne, confirmé ou pas ?**
Nginx règle un vrai problème : le frontend a une page `/personas`
(`app/(app)/personas/page.tsx`) et le backend a un router `/personas`
(même nom). Sans Nginx pour distinguer `/api/personas` (backend) de
`/personas` (page frontend), il faudrait soit préfixer TOUTES les routes
backend en `/api/*` (changement de code, mineur mais réel), soit garder
Nginx qui fait cette distinction sans toucher au code. Je recommande de
garder Nginx tel que prévu dans le brief — confirme ?

---

### B. Adaptation base de données

- `DATABASE_URL`/`DATABASE_URL_SYNC` pointent directement sur la
  connection string Neon (déjà le bon format `postgresql://...`, à
  convertir en `postgresql+asyncpg://...` pour la variable async — Neon
  fournit généralement le format psycopg, une petite transformation de
  préfixe suffit, pas de changement de code, juste la valeur de la
  variable d'env sur Render).
- Attente de disponibilité : script Python/bash simple en boucle
  (`asyncpg.connect` ou `pg_isready` équivalent) avant `alembic upgrade
  head`, avec timeout + messages clairs dans les logs (utile pour
  diagnostiquer un cold-start Neon lent en cas d'échec de démarrage).
- Migrations au démarrage : sûr par construction (Alembic trackant la
  version appliquée en base via sa table `alembic_version`), rejouable à
  chaque redémarrage du conteneur sans effet de bord.

**Question ouverte 2** — Neon a-t-il l'auto-suspend activé (plan gratuit
Neon standard) ? Si oui, le tout premier appel après une période
d'inactivité peut prendre plusieurs secondes (réveil de la instance Neon),
en plus du cold start Render lui-même (15 min d'inactivité) — les deux
cold starts pourraient se cumuler dans le pire cas. Pas bloquant, mais je
veux le savoir pour calibrer le timeout de l'entrypoint et t'avertir si
l'expérience jury risque un double délai au premier chargement.

---

### C. Suppression de Redis

Confirmé : rien à remplacer fonctionnellement (§6). Actions Phase 2 :
retirer `redis` et `celery` de `pyproject.toml`, retirer `REDIS_URL` des
settings (ou le laisser avec une valeur par défaut inoffensive si tu
préfères ne pas toucher `config.py` — à trancher), ne pas inclure de
service Redis dans le déploiement. Le rate limiting (nouveau besoin, pas
une migration) passe par `slowapi` en in-memory — voir D.

---

### D. Sécurisation démo publique

**Rate limiting `slowapi`** — chiffres proposés, à valider :
- Chat/RAG : 10 req/IP/min (le brief le proposait, cohérent avec un usage
  démo normal — largement au-dessus de ce qu'un vrai visiteur ferait,
  assez bas pour limiter un abus scripté)
- Upload : 3/IP/heure (les uploads déclenchent extraction + embeddings
  OpenAI, les plus coûteux — chiffre bas volontaire)
- Inscription : 5/IP/jour

**Question ouverte 3** — Ces 3 chiffres + leur granularité (par IP —
suffisant sachant que Render free tier est mono-instance donc pas de
problème de state partagé entre instances) te conviennent-ils tels quels,
ou tu veux ajuster ?

**Cleanup comptes inactifs 48h** — mécanisme proposé : endpoint interne
protégé (pas exposé publiquement) déclenché par un scheduler simple
(`APScheduler` en tâche de fond dans le process Uvicorn plutôt qu'un cron
externe — Render free tier n'offre pas de cron job séparé sur ce tier).
Supprime les users créés il y a >48h **sauf le compte de démo** (flag
`is_demo_seed` ou email fixe à exclure explicitement). Réutilise le hard
delete + cascade déjà existant et testé (`DELETE /users/me`, J50/J53) —
juste appelé en interne plutôt que par l'utilisateur.

**Question ouverte 4** — Le rythme de ce cleanup (toutes les heures ?
toutes les 6h ?) et le fait qu'il tourne dans le MÊME process Uvicorn (pas
de process séparé sur ce tier) — ok pour toi ?

**Kill switch `DEMO_DISABLED=true`** — middleware/dépendance FastAPI
simple, appliqué aux endpoints coûteux (chat, upload, embeddings), renvoie
503 avec message clair. Directe à implémenter, pas de question ouverte.

**Vérification secrets hardcodés** : déjà faite dans le cadre du fix
sécurité de ce même sprint (`security(env): sanitize .env.example
placeholders`, commit séparé) — `git grep` sur tout le repo, un seul
résultat trouvé (déjà corrigé) et neutralisé. Aucun autre secret en clair
détecté.

---

### E. Fichiers uploadés

Décision proposée (éphémère + cleanup 48h) confirmée cohérente avec le
choix D — un compte supprimé au bout de 48h entraîne déjà la suppression
cascade de ses documents en base (ligne DB), et le fichier physique
disparaît de toute façon au prochain redémarrage du conteneur même sans
cleanup applicatif. **Pas de S3/R2/B2 à mettre en place pour cette V1** —
cohérent avec "priorité à la stabilité", un object storage externe est un
point de défaillance et une complexité supplémentaires pour un gain
marginal sur une démo qui n'a pas vocation à persister les données
utilisateur long terme.

**Point de vigilance à documenter, pas une question** : le dataset IBM
Sales Pipeline et le corpus PDF/DOCX de démo (compte pré-rempli, décision
G) doivent être re-seedés à CHAQUE démarrage de conteneur s'ils sont
perdus au redémarrage — le script de seed (§G) doit re-ingérer ces
fichiers depuis une source qui survit au redémarrage (embarquée dans
l'image Docker elle-même, pas dans `uploads/`), pas les considérer comme
déjà présents.

---

### F. Frontend en production — LA décision structurante

Deux options réelles, avec un vrai compromis RAM/effort :

**Option F1 — Export statique (`output: 'export'`)**
- Nginx sert des fichiers HTML/JS statiques directement, **aucun process
  Node qui tourne à l'exécution**.
- Économise ~80-150 Mo de RAM (empreinte typique d'un process Next.js
  serveur) sur un budget total de 512 Mo — non négligeable vu que le
  backend Python (pandas/numpy/pillow/pymupdf chargés en mémoire) pèse
  déjà lui-même dans les 150-250 Mo estimés.
- **Coût réel** : les 4 routes dynamiques (§3) doivent être restructurées
  en routes à paramètre de requête (`/datasets?id=xxx` au lieu de
  `/datasets/[id]`) plutôt qu'en segment de chemin — un fichier HTML
  statique unique servi quel que soit le param, résolu côté client. Ça
  touche : la structure de dossiers de ces 4 routes, tous les
  `useParams()` → `useSearchParams()`, et **tous les endroits qui
  construisent un lien vers ces pages** (`router.push`, `<Link>`) dans le
  reste du frontend.
- **Cas particulier sensible : `/share/[token]`.** C'est une URL
  **publique, faite pour être partagée/collée** (feature dédiée, J48).
  Passer à `/share?token=xxx` change le format d'URL de cette feature —
  esthétiquement différent, fonctionnellement identique, mais si des
  liens `/share/xxx` existent déjà quelque part (impossible en pratique
  puisque rien n'est encore déployé publiquement, donc **aucun lien
  existant à casser** — bon moment pour ce changement s'il doit être fait).

**Option F2 — `next start` (mode serveur Node)**
- Zéro changement de code sur les routes.
- Un process Node persistant en plus du process Python — budget RAM plus
  serré, risque réel d'OOM-kill si le backend ET le frontend pic de
  mémoire en même temps (ex : un visiteur upload un gros CSV pendant qu'un
  autre charge le dashboard).

**Ma recommandation** : F1 (export statique + refactor des 4 routes). La
consigne du sprint est "priorité absolue à la stabilité" — un OOM-kill en
plein milieu de la démo devant le jury est le pire scénario possible, et
c'est justement le risque que F2 laisse ouvert sur un tier aussi
contraint (512 Mo / 0.1 vCPU). Le coût de F1 est un refactor mécanique
mais réel (4 routes + tous leurs points de navigation), à faire
proprement en Phase 2.

**Question ouverte 5 (la plus importante du document)** — F1 ou F2 ? Si
F1, je le fais en Phase 2 avec le reste. Si tu préfères F2 pour aller plus
vite, je le note et on surveille la RAM de près après déploiement (Render
expose des métriques mémoire, on pourra voir si ça tient).

---

### G. Compte de démo pré-rempli

Décision produit déjà actée par toi (Option A+B) : au démarrage du
conteneur (dans `entrypoint.sh`, après migrations, avant de lancer
Uvicorn en avant-plan), un script de seed **idempotent** (vérifie
l'existence du compte démo par email fixe avant de recréer quoi que ce
soit) crée :
- Le compte démo (email/password fixes, affichés sur la landing page)
- Dataset "IBM Sales Pipeline" (déjà utilisé comme jeu de test dans le
  projet, cf mentions dans les specs Playwright J52) pré-chargé et profilé
- Persona "Vector Analyste Finance IBM" + corpus "Documentation
  Stratégique IBM 2025" (PDF + DOCX) — réutilise très probablement les
  fichiers déjà utilisés comme fixtures E2E (`ibm_strategy_report_2025.pdf`,
  `ibm_technology_whitepaper.docx` mentionnés dans le rapport J51) plutôt
  que d'en créer de nouveaux
- 2-3 conversations d'exemple pré-écrites (peuplées directement en base,
  comme le font déjà les tests E2E via `postMessageViaApi` — pas besoin
  d'un vrai appel LLM pour les pré-remplir)

**Question ouverte 6** — Peux-tu confirmer/fournir : (a) le couple
email/password du compte démo que tu veux afficher publiquement, (b) si
les fichiers IBM PDF/DOCX à utiliser sont bien ceux déjà présents comme
fixtures E2E (`frontend/e2e/fixtures/` — j'ai vu `corpus-doc.pdf` et
`corpus-doc.docx` génériques mais pas de vrais docs "IBM" nommés comme
tels, à vérifier), ou s'il faut en préparer de nouveaux, et (c) le
contenu exact souhaité pour les 2-3 conversations d'exemple (questions +
réponses), ou si je peux les rédiger moi-même en Phase 2 sur la base du
corpus IBM.

---

### H. README.md

Section "Déploiement Render" (process, variables d'env attendues, lien
vers ce document) + badge de statut de déploiement en tête de fichier,
à côté des badges pipeline/coverage déjà présents (J54) :
```
[![Render deploy](https://img.shields.io/badge/deploy-render-46E3B7?logo=render)](https://dashboard.render.com/...)
```
Render n'expose pas nativement un badge de statut de build dynamique
comme GitLab (`pipeline.svg`) sans passer par une API tierce — à
confirmer en Phase 2 ce qui est réellement disponible (badge statique
"powered by Render" vs un vrai statut live). Pas bloquant, détail
d'implémentation.

---

## Résumé des 6 questions ouvertes

1. Nginx interne confirmé (vs restructurer les routes backend en `/api/*`) ?
2. Neon a-t-il l'auto-suspend activé (calibrage du timeout d'attente) ?
3. Chiffres de rate limiting (10 chat/min, 3 upload/h, 5 inscriptions/jour) validés ?
4. Fréquence du cleanup 48h, dans le même process Uvicorn — ok ?
5. **F1 (export statique + refactor 4 routes, recommandé) ou F2 (`next start`) ?**
6. Compte démo : identifiants exacts, fichiers IBM à utiliser, contenu des conversations d'exemple ?

Dès validation (avec ajustements si besoin), je passe Phase 2 :
`Dockerfile`, `entrypoint.sh`, config Nginx, script de seed, middleware
rate limiting + kill switch, job de cleanup, section README.
