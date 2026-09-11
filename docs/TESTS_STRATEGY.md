# Stratégie de tests — Vector

Document de référence sur la stratégie de recette du projet, à
destination du jury et de toute personne reprenant le projet. Mis à jour
au S5 J54 (15/08/2026).

## 1. Pyramide de tests

| Niveau | Outil | Volume | Rôle |
|---|---|---|---|
| Tests unitaires | pytest | ~310 tests | Logique métier isolée (extracteurs, calculs KPI, validation Pydantic, sécurité) |
| Tests d'intégration | pytest + httpx AsyncClient | intégrés aux 310 | Endpoints API contre une vraie base Postgres, ownership, cascade delete |
| Tests E2E | Playwright | 46 tests / 18 specs | Parcours utilisateur complets dans un vrai navigateur (Chromium) |

Les tests d'intégration ne sont pas dans un dossier séparé : ils
partagent `backend/tests/`, distingués par le fait qu'ils passent par
`AsyncClient` (appel HTTP réel contre l'app FastAPI) plutôt que d'appeler
une fonction directement. Pas de base de test isolée — chaque test crée
ses propres données avec un email/UUID unique (voir `tests/conftest.py`),
sur la même Postgres que le dev local.

## 2. Stratégie de mock des services externes

**Backend (pytest)** — les appels OpenAI sont mockés au cas par cas via
`unittest.mock.patch` sur `OpenAIProvider.embed`/`.chat_with_tools`
(fixture `mock_embeddings` dans `conftest.py`), jamais de vraie clé API
consommée en test unitaire.

**E2E (Playwright)** — feature flag `USE_MOCK_LLM` (S5 J52,
`app/core/config.py`, défaut `false`). Quand activé au démarrage du
serveur backend, `OpenAIProvider` et `WebSearchService`
(`app/ai/providers/mock_responses.py`) retournent des réponses
déterministes :
- Réponses par pattern simple sur le prompt (image jointe → couleur fixe,
  "ibm" → réponse avec sources fictives, "bonjour" → salutation, fallback
  générique).
- Embeddings pseudo-aléatoires déterministes (hash SHA-256 du texte : le
  même texte produit toujours le même vecteur).
- `chat_with_tools` retourne toujours une réponse finale sans tool call
  (le tool calling réel n'est pas dans le périmètre des specs mockées).

Le flag est `false` partout ailleurs (dev normal, tests pytest, prod) —
aucun risque de mock accidentel en dehors des runs E2E dédiés.

## 3. Deux buckets Playwright

Les 18 specs (`frontend/e2e/`) ne peuvent pas tourner dans le même
process backend, un run Playwright étant séquentiel (`workers: 1`) contre
un seul serveur à la fois :

- **`01` à `11`** (historique) — appellent le vrai LLM OpenAI pour la
  plupart (`test.slow()`), coûtent des crédits API, dépendent du réseau.
  Backend démarré normalement. `pnpm test:e2e`.
- **`12` à `18`** (S5 J52, "fast/mocked") — 100% déterministes, offline.
  Backend démarré avec `USE_MOCK_LLM=true`. `pnpm test:e2e:mocked`
  (filtre via `playwright.mocked.config.ts`, pattern `testMatch` --
  robuste multi-plateforme depuis S5 J54, l'ancien glob shell cassait
  sous Windows/pnpm).

Mise à jour S5 J54 : le constat empirique ci-dessus (les 11 specs
historiques passent aussi sous backend mocké) s'est confirmé stable en
CI — **la CI GitLab fait donc tourner les 18 specs sans filtre**
(`pnpm test:e2e` avec `USE_MOCK_LLM=true`), pas seulement le bucket
"mocked". Le bucket "mocked" local (`test:e2e:mocked`) reste utile pour
un dev qui veut juste re-vérifier vite les 7 nouvelles specs J52 sans
attendre les ~6 minutes des 18. Le bucket "réel" (`pnpm test:e2e` avec
un backend démarré sans `USE_MOCK_LLM`) reste réservé à l'exécution
locale avec de vraies clés OpenAI — jamais en CI (coût + non-déterminisme).
Voir `docs/CI_CD.md` pour la distinction importante entre "CI verte"
(plomberie validée) et "qualité des réponses LLM validée" (nécessite
un run local avec vraies clés).

## 4. Zones critiques prioritaires

Issues de l'audit `COVERAGE_REPORT.md` (S5 J53) :
- Authentification / JWT (`app/api/auth.py`, `app/core/security.py`) : 100%
- Ownership cross-user (personas, corpus, documents) : 100% sur les
  endpoints personas
- Cascade delete de compte (`DELETE /users/me`) : vérifié exhaustivement
  sur toutes les tables liées, y compris les enfants de dataset
  (analyses, KPI, dashboards)
- Upload de documents : validation format + échec propre sur contenu
  corrompu/spoofé + immunité au path traversal

Dette assumée et documentée (non traitée, pas de risque produit
identifié) : logique de génération de dashboards/KPI par IA, extracteurs
DOCX/PPTX sans tests unitaires directs (seulement testés via upload
bout-en-bout), endpoints SSE de streaming (coûteux à tester
unitairement).

## 5. Procédures d'exécution locale

```bash
# Backend — suite complète
cd backend
python -m pytest

# Backend — avec couverture (rapport HTML dans htmlcov/, gitignored)
python -m pytest --cov=app --cov-report=html --cov-report=term-missing

# Frontend E2E — bucket mocké (offline, rapide)
# Terminal 1 :
cd backend && USE_MOCK_LLM=true uvicorn app.main:app --port 8000
# Terminal 2 :
cd frontend && pnpm test:e2e:mocked

# Frontend E2E — suite complète (vrai LLM, coûte des crédits API)
cd backend && uvicorn app.main:app --port 8000   # backend normal
cd frontend && pnpm test:e2e
```

Voir `frontend/e2e/README.md` pour le détail des scripts, fixtures et
conventions (data-testid, isolation par email unique, pas de
`waitForTimeout` arbitraire).

## 6. CI/CD (S5 J54)

Pipeline GitLab (`.gitlab-ci.yml`, racine du repo) : lint → test (backend
+ E2E en parallèle) → report, sur chaque push. Blocage de merge sur
pipeline rouge (config manuelle, cf `docs/CI_CD.md`). Détail complet des
stages, caches, seuil de couverture et procédures de debug :
**voir `docs/CI_CD.md`.**

## 7. Limites assumées

- **Cross-browser / mobile** : Chromium uniquement (`playwright.config.ts`).
  Firefox/WebKit et responsive hors scope V1.
- **Accessibilité automatisée** : pas d'axe-core ni d'audit WCAG
  automatisé. Audit Lighthouse manuel réalisé ponctuellement (S5 J50),
  non intégré à la suite de tests.
- **Performance / charge** : aucun test de performance automatisé.
- **Endpoints SSE/WebSocket** (chat principal, RAG, web search) :
  couverture pytest faible (24-42%), structurellement coûteux à tester
  unitairement (consommer un flux d'événements plutôt qu'une réponse
  JSON). Compensé par la couverture E2E (chat, corpus, image) qui
  exerce ces mêmes chemins de bout en bout dans un vrai navigateur.
- **CI ne valide pas la qualité des réponses LLM**, seulement le
  plumbing (cf section 3 et `docs/CI_CD.md`) — un vrai run avec clés
  OpenAI reste nécessaire pour juger la pertinence des réponses.
