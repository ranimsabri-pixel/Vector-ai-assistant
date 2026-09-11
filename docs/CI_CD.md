# CI/CD — GitLab

Documentation du pipeline `.gitlab-ci.yml` (racine du repo). Mis à jour au
S5 J54 (15/08/2026), hébergé sur GitLab.com SaaS.

## Runners : self-hosted, pas les runners partagés GitLab.com

Le namespace `Welyne-Dev` a les **instance runners désactivés**
("Instance runners are disabled in all projects in this namespace",
Settings > Usage Quotas). Ce projet tourne sur des **runners self-hosted
opérés par l'infrastructure Welyne**, pas sur les runners partagés
gratuits de GitLab.com.

Consequence concrète pour tout repreneur du projet : le quota de 400
minutes CI/mois du plan GitLab.com free **ne s'applique pas** ici — la
consommation de ce pipeline (lint + tests + E2E, ~7-8 min par run) n'est
pas plafonnée par ce quota. En contrepartie, la disponibilité et la
performance du pipeline dépendent de l'infrastructure Welyne (runners
self-hosted), pas de la disponibilité des runners partagés GitLab —
à garder en tête pour du debug ("le job est lent/en attente" peut être un
souci runner self-hosted, pas un souci GitLab.com).

## Vue d'ensemble

3 stages séquentiels, déclenchés sur chaque push :

```
lint  ──┬──>  test  ──>  report
        │
   (lint-backend, lint-frontend en parallèle)
        │
   (test-backend, test-frontend-e2e en parallèle,
    chacun avec needs: [lint-backend, lint-frontend])
```

| Job | Stage | Rôle | Durée (pipeline #2762756096) |
|---|---|---|---|
| `lint-backend` | lint | `ruff check app/` | 1:00 |
| `lint-frontend` | lint | `tsc --noEmit` + `eslint` | 1:04 |
| `test-backend` | test | 310 tests pytest + couverture | 2:52 |
| `test-frontend-e2e` | test | 46 tests Playwright (18 specs, backend mocké) | 6:34 |
| `pages` | report | Publie `backend/htmlcov` sur GitLab Pages | absent sur cette branche (voir note) |

**Pipeline complet : 7:39 de bout en bout** (mesuré, branche `ci/gitlab-setup`),
largement sous la cible de 15 min. Somme séquentielle des 4 jobs (si aucune
parallélisation) : 11:30 — la parallélisation lint→test apporte donc un
gain réel d'environ 34% sur le temps-to-feedback, pas juste un gain
théorique.

`test-backend` et `test-frontend-e2e` ont chacun `needs: [lint-backend,
lint-frontend]` explicite plutôt que de dépendre implicitement de l'ordre
des stages — les deux tournent en parallèle dès que les deux lint sont
verts, sans attendre l'un l'autre.

**Note sur `pages`** : absent sur `ci/gitlab-setup` car sa `rule` le
restreint à `$CI_COMMIT_BRANCH == "vector-agent"` — comportement attendu,
pas un job cassé. Il s'exécutera automatiquement une fois la MR mergée
sur `vector-agent`.

## Historique — état avant J54

Le pipeline existait déjà avant ce sprint (`a140bbb`, premier commit CI),
mais **précédait le feature flag `USE_MOCK_LLM`** introduit en J52
(`0742315`). Le job `test-frontend-e2e` lançait `pnpm test:e2e` (toutes les
specs, dont 7 appelant le vrai LLM) avec une fausse `OPENAI_API_KEY` et sans
`USE_MOCK_LLM=true`.

Sans accès direct au dashboard GitLab au moment de l'investigation (token
scopé push/pull uniquement), le statut exact n'a pas pu être vérifié
avant le premier correctif J54. **Par déduction logique** (le pipeline
initial n'a jamais pu appeler OpenAI avec une clé factice) : `test-frontend-e2e`
était très probablement en échec depuis son introduction, ou au mieux
en échec intermittent selon les specs exécutées avant que le mock LLM
n'existe. Le premier correctif J54 (ajout de `USE_MOCK_LLM=true`) corrige
cette situation — confirmé vert sur le pipeline `#2757711609`.

## Bilan J54

6 commits/push sur `ci/gitlab-setup` (MR !1) au total, dont 4 ont
déclenché un pipeline avec une modification fonctionnelle ou de
config CI (les 2 derniers sont des ajustements de formulation
doc-only, sans intérêt pipeline propre) :

1. `610a607` (fix mock LLM + config Playwright robuste + seuil couverture)
   → pipeline `#2757711609` : **1 échec** sur 356 tests exécutés —
   violation de "strict mode" Playwright sur `12-auth-flow.spec.ts`
   (2 éléments matchant la même regex sur `/register`, cf section
   "Preuve de valeur" plus bas). Reste 100% vert par ailleurs (lint,
   test-backend, 45/46 E2E).
2. `e037f53` (fix ciblé : data-testid + assertions) → pipeline vert.
3. `01c6d93` (parallélisation, caches, expire_in, docs) → pipeline
   `#2762756096` vert, **7:39 de bout en bout**, chiffres detailles ci-dessus.
4. `db10b04` (chiffres finaux consignes dans ce document) → doc-only,
   pipeline declenche par le meme mecanisme (`if: $CI_PIPELINE_SOURCE ==
   "push"`, pas de filtre par contenu du diff).
5. Section runners self-hosted (ce paragraphe) → idem, doc-only.

**1 seule itération de correction nécessaire** pour passer au vert la
premiere fois — sous l'estimation du brief (3-5 push-corrections
anticipés pour le job E2E). Les commits 4 et 5, documentation pure, ne
comptent pas comme des itérations de correction.

**356 tests exécutés à chaque push** (310 pytest + 46 Playwright), zéro
régression sur l'ensemble du sprint.

Minutes CI consommées : **non applicable au quota GitLab.com** — ce
namespace utilise des runners self-hosted (instance runners désactivés,
cf section "Runners" ci-dessus), donc pas de decompte sur les 400
minutes/mois du plan free. Consommation reelle sur l'infrastructure
Welyne non mesuree par ce rapport (hors perimetre de ce qui est visible
depuis Settings > Usage Quotas GitLab.com).

## Stratégie de mock LLM en CI

`USE_MOCK_LLM: "true"` est fixé dans les `variables` du job
`test-frontend-e2e` (jamais globalement — reste `false` pour `test-backend`,
qui mock au cas par cas via `unittest.mock.patch`, cf `docs/TESTS_STRATEGY.md`).

Toutes les 18 specs (01-18) tournent en CI, pas seulement les 7 nouvelles
(12-18) : vérifié empiriquement en J52 que les 11 specs historiques passent
aussi sous backend mocké. Aucune raison de les exclure — coût CI identique
(le backend est mocké de toute façon), couverture de régression maximale.

### ⚠️ Distinction importante : plumbing vs qualité des réponses LLM

**Les 7 specs `test.slow()` (03 à 09), sous backend mocké en CI, testent le
PLUMBING — pas la qualité des réponses.** Concrètement, elles vérifient que :
- les endpoints répondent sans erreur serveur
- les sources RAG s'affichent correctement dans l'UI
- le flux upload → ingestion → chat fonctionne de bout en bout
- l'interface réagit correctement aux événements SSE

Elles ne vérifient **jamais** que la réponse du LLM est pertinente,
factuellement correcte, ou bien formulée — sous mock, la réponse est un
texte déterministe générique (`app/ai/providers/mock_responses.py`), pas
une vraie génération. Un changement de prompt système qui dégraderait la
qualité réelle des réponses OpenAI **ne serait pas détecté par la CI**.

Pour valider la qualité réelle des réponses LLM, lancer en local avec de
vraies clés (jamais en CI, coût + non-déterminisme) :
```bash
cd backend && uvicorn app.main:app --port 8000   # backend normal, sans USE_MOCK_LLM
cd frontend && pnpm test:e2e                      # toutes les specs, vrai LLM
```
Tout futur développeur qui reprend ce projet doit garder cette distinction
en tête : CI verte ≠ qualité IA validée, seulement plomberie validée.

## Couverture minimale : 74%

`test-backend` échoue si la couverture pytest descend sous 74%
(`--cov-fail-under=74`). Ce chiffre n'est pas 75 pile : la couverture
réelle mesurée en J53 est 74.95%, affichée arrondie à "75%" dans le
rapport texte, mais `--cov-fail-under` compare la valeur **exacte** —
un seuil à 75 aurait fait échouer ce job dès le premier run. 74 laisse
~1 point de marge.

### Relâcher temporairement le seuil

Si une MR fait légitimement baisser la couverture (gros refactor, code
mort supprimé changeant le dénominateur, nouvelle feature volumineuse
pas encore entièrement testée) :

1. Sur **cette MR uniquement**, baisser `--cov-fail-under` dans
   `.gitlab-ci.yml` à une valeur juste sous la couverture réelle mesurée.
2. Expliquer pourquoi dans la description de la MR.
3. **Ouvrir un ticket/TODO pour remonter le seuil** une fois la dette
   comblée — ne pas laisser un seuil abaissé devenir permanent.
4. Ne **jamais** baisser à une valeur ronde "pour que ça passe" sans
   justification écrite — c'est exactement le genre de dette silencieuse
   que ce garde-fou existe pour éviter.

## Variables CI/CD

Aucun secret nécessaire pour ce pipeline (LLM mocké, pas de déploiement
automatique). Toutes les variables sont définies en clair dans
`.gitlab-ci.yml` (`SECRET_KEY`, `OPENAI_API_KEY` factices, mots de passe
Postgres de test) — **volontairement non sensibles**, jamais réutilisées
hors CI. Si un futur sprint (déploiement, vraies clés API en CI) introduit
de vrais secrets, ils devront passer par Settings > CI/CD > Variables
(masqué + protégé), jamais en dur dans le YAML.

## Débugger localement

Reproduire l'environnement CI backend (Postgres + pgvector + Redis) :
```bash
docker compose up -d db redis   # depuis la racine du projet
cd backend
alembic upgrade head
python -m app.db.seed
pytest -v --cov=app --cov-report=term-missing
```

Reproduire le job E2E (backend mocké) :
```bash
cd backend && USE_MOCK_LLM=true uvicorn app.main:app --port 8000
cd frontend && pnpm test:e2e:mocked   # ou pnpm test:e2e pour les 18 specs
```

## Ajouter un nouveau test au pipeline

Rien à faire côté `.gitlab-ci.yml` : `test-backend` lance `pytest` sur tout
`backend/tests/`, `test-frontend-e2e` lance `pnpm test:e2e` sur tout
`frontend/e2e/`. Un nouveau fichier de test est automatiquement inclus.

Seule exception : une nouvelle spec Playwright mockée (nommage `NN-*.spec.ts`
avec `NN` entre 12 et 18) est aussi automatiquement incluse dans
`playwright.mocked.config.ts` (regex `testMatch`) pour le dev local rapide.
Une spec au-delà de 18 nécessiterait d'étendre cette regex.

## Relancer un job échoué

Dans l'UI GitLab : Pipelines > sélectionner le run > bouton "Retry" sur le
job concerné (icône ↻), ou "Retry" en haut à droite pour tout le pipeline.
Utile si l'échec est un timeout réseau GitLab, un service Postgres lent à
démarrer, ou un pull d'image lent — pas pour un vrai échec de test.

## Bloquer le merge sur pipeline rouge

Configuration manuelle (UI GitLab, pas versionnable dans le YAML) :

1. Aller dans **Settings > Merge requests** du projet.
2. Section "Merge checks", cocher **"Pipelines must succeed"**.
3. Optionnel : cocher **"All threads must be resolved"** pour bloquer
   aussi sur discussions non résolues.
4. Sauvegarder.

Une fois activé, toute MR avec un pipeline rouge affiche le bouton "Merge"
grisé jusqu'à correction ou retry réussi.

## Dette technique connue

- **Warnings SQLAlchemy "pool connection non fermée proprement"** observés
  dans les logs `test-backend` (2 occurrences). Bénin en l'état — la CI
  passe, aucun test n'échoue à cause de ça — mais signale probablement une
  session async non fermée explicitement dans une fixture ou un test
  d'ingestion. À investiguer lors d'un futur audit qualité, pas bloquant
  pour J54.
- Endpoints SSE/WebSocket (`chat.py`, `agent.py`, `rag.py`) restent peu
  couverts par pytest (24-42%, cf `docs/COVERAGE_REPORT.md`) — compensé
  par la couverture E2E qui exerce ces mêmes chemins dans un vrai
  navigateur, mais pas de test unitaire direct sur le streaming SSE lui-même.

## Preuve de valeur de la CI (retour d'expérience J54)

Le tout premier pipeline J54 a révélé une véritable violation de "strict
mode" Playwright sur `12-auth-flow.spec.ts` (2 éléments matchant la même
regex sur `/register` — un label statique "(min 8 caractères)" et le
message d'erreur backend) — un bug qui **n'était jamais apparu en 3 passes
locales consécutives**. La CI, en environnement Chromium headless
réellement isolé (container frais, pas de serveur dev réutilisé pendant
plusieurs jours comme en local), a détecté en un seul run ce que la
procédure de validation locale recommandée n'avait pas révélé. Argument
concret pour la valeur de la CI au-delà de la simple automatisation :
elle teste dans des conditions différentes, pas juste "les mêmes tests
plus souvent".
