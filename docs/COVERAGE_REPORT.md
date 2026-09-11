# Rapport de couverture pytest — S5 J53

Audit qualitatif de la couverture backend, réalisé le 12/08/2026. Objectif :
identifier les zones critiques sous-couvertes et les combler, pas atteindre
un pourcentage cible.

## Score global

| | Avant fix mesure | Après fix mesure |
|---|---|---|
| Couverture globale | 67% | **75%** |
| Tests | 298 | **310** |

## Anomalie de mesure corrigée

`coverage.py` sous-rapportait massivement tout endpoint qui écrit en base
(`await db.commit()`/`db.refresh()`) : SQLAlchemy async utilise
`greenlet_spawn` en interne pour ponter le driver asyncpg avec l'ORM
synchrone, et sans `concurrency = ["greenlet", "thread"]` explicite,
coverage.py perd le fil après chaque bascule de greenlet.

Exemple concret : `app/api/auth.py` mesurait **53%** avant le fix, **100%
après**, sans qu'aucun test n'ait changé — les lignes de `register()` et
`login()` étaient bien exécutées, juste jamais comptées. Ce fix
(`pyproject.toml`, `[tool.coverage.run]`) est une correction d'outillage,
pas un changement de code applicatif. Il explique une bonne partie de
l'écart entre le chiffre "67%" initial (sous-estimé) et la réalité.

## Top fichiers les moins couverts (après fix mesure)

| Fichier | Couverture | Rôle |
|---|---|---|
| `app/db/seed.py` | 0% | Script de seed (FAIBLE, cf classification) |
| `app/ai/providers/mock_responses.py` | 16% | Support de test J52, jamais exercé par pytest (USE_MOCK_LLM=false en tests) |
| `app/services/saved_dashboards.py` | 23% | CRUD dashboards sauvegardés |
| `app/services/web_search.py` | 26% | Intégration Tavily (streaming) |
| `app/services/rag.py` | 27% | Génération de réponses RAG (streaming) |
| `app/api/chat.py` | 24% | Endpoint WebSocket chat (non utilisé par le frontend actuellement) |
| `app/api/agent.py` | 29% | Endpoint SSE `/agent/chat-web` (web search) |
| `app/services/kpi_translator.py` | 29% | Traduction KPI → libellés FR (LLM) |
| `app/ai/vector_tools.py` | 34% | Exécution des tool calls (dataset compute) |
| `app/services/dashboards.py` | 34% | Génération de dashboard (LLM) |

## Analyse par catégorie fonctionnelle

**Endpoints API (routers)** — hétérogène. `auth.py`, `corpus.py`,
`personas.py` : 100% après J53. `agent.py`, `chat.py`, `rag.py` : 24-42%,
tous des endpoints SSE/WebSocket de streaming LLM — catégorie
structurellement coûteuse à tester unitairement (il faut consommer un
flux d'événements plutôt qu'une réponse JSON simple), hors scope de ce
sprint.

**Services métier** — `corpus.py` 100%, `personas.py` 92%, `conversations.py`
95%, `retrieval.py` 94% : bien couverts. `datasets.py` (349 lignes, 64%),
`saved_dashboards.py`/`dashboards.py`/`kpi_translator.py` (23-34%) :
grosses zones de logique IA (génération de dashboards, traduction de KPI)
peu couvertes — non prioritaires pour ce sprint (pas dans la liste
critique du brief), mais à garder en tête pour un futur audit.

**Modèles et migrations** — tous les modèles SQLAlchemy à 100% (aucune
logique propre, juste des déclarations de colonnes). `seed.py` à 0%,
volontairement non testé (FAIBLE).

**Extraction/ingestion documents** — `pdf_extractor.py` 96%,
`text_extractor.py` 91% (après J53), `docx_extractor.py` 64%,
`pptx_extractor.py` 67%. Les deux derniers datent de J32/J35 et n'ont
jamais eu de tests unitaires dédiés (seule l'ingestion bout-en-bout via
upload est testée) — noté comme dette, hors scope de ce sprint (pas de
régression connue, juste un manque de tests directs sur ces 2 fichiers).

**Utilitaires et helpers** — `security.py` 100%, `storage.py` 84%,
`profiler.py` 89% : globalement bien couverts.

## Classification des zones critiques

**CRITIQUE (couvert en priorité, ce sprint) :**
- Authentification / JWT : `app/api/auth.py`, `app/core/security.py` →
  **100%**. Edge cases ajoutés : mot de passe sans chiffre/lettre, JWT
  expiré, JWT signature falsifiée, login après suppression de compte.
- Ownership checks : `app/api/personas.py` → **100%**. Association corpus
  (jusque-là non testée du tout) + rejet cross-user ajoutés.
- Cascade delete (`DELETE /users/me`) : le test le plus important du
  sprint. Étendu pour couvrir `dataset_columns`, `analyses`, `dashboards`,
  `kpis`, `kpi_values`, `saved_dashboards`, `dashboard_widgets` — tables
  qui n'étaient pas peuplées par le test J50 original. **Aucun trou de
  cascade trouvé** (chaîne FK déjà correcte depuis J50).
- Upload de documents (`app/api/corpus.py`) → **100%**. Sécurité :
  extension spoofée (`.pdf` avec contenu arbitraire) → échec propre en
  `status=error`, pas de crash ; path traversal dans le nom de fichier →
  confirmé sans effet (le stockage génère toujours un nom `{uuid4()}{ext}`).

**MODÉRÉE (non traité ce sprint, dette notée) :**
- `docx_extractor.py` / `pptx_extractor.py` : pas de tests unitaires
  directs (seulement via upload bout-en-bout).
- `app/services/datasets.py` : gros fichier (349 lignes), 64% — logique
  d'analyse IA et de recommandations peu couverte.
- Endpoints SSE (`agent.py`, `chat.py`, `rag.py`) et services associés
  (`rag.py`, `web_search.py`) : coûteux à tester unitairement (streaming),
  pas dans la liste critique du brief J53.
- Dashboards/KPI générés par IA (`dashboards.py`, `kpi_translator.py`,
  `saved_dashboards.py`) : logique métier réelle mais pas dans le
  périmètre "sécurité/intégrité data" de ce sprint.

**FAIBLE (volontairement non couvert) :**
- `app/db/seed.py` (script de seed, 0%)
- `app/core/config.py`, `app/core/constants.py` (déjà 100%, configuration statique)
- Tous les modèles SQLAlchemy (`app/db/models/*.py`, déjà 100%, pas de logique)
- `app/ai/providers/mock_responses.py` (support de test J52, pas de la
  logique produit — jamais exercé par pytest puisque `USE_MOCK_LLM=false`
  en tests unitaires, uniquement en E2E Playwright mocké)

## Temps d'exécution

Suite complète : **~100-115s** pour 310 tests. Un seul test dépasse 2s
(`test_upload_file_too_large_413`, 2.85s — upload d'un payload 51 Mo en
mémoire, temps normal et non optimisable sans affaiblir le test). Aucun
test au-delà de 5s. Phase 4 (optimisation) jugée non nécessaire.

## 12 tests ajoutés (S5 J53)

| Fichier | Test | Rationale |
|---|---|---|
| `test_users_settings.py` | `test_delete_me_cascades_dataset_children` | Cascade delete sur dataset_columns/analyses/dashboards/kpis/kpi_values/saved_dashboards/widgets — non couvert par le test J50 original |
| `test_corpus_upload.py` | `test_upload_spoofed_pdf_extension_fails_gracefully_at_ingestion` | Extension valide + contenu arbitraire → échec propre, pas de crash |
| `test_corpus_upload.py` | `test_upload_path_traversal_filename_does_not_escape_storage` | Nom de fichier malveillant n'influence jamais le chemin réel sur disque |
| `test_personas.py` | `test_link_and_unlink_corpus` | Association persona↔corpus jamais testée (seule l'association document l'était) |
| `test_personas.py` | `test_link_corpus_not_owned_rejected` | Ownership cross-user sur l'association corpus |
| `test_auth.py` | `test_register_password_without_digit_rejected` | Branche "sans chiffre" de la règle renforcée jamais exercée via l'API |
| `test_auth.py` | `test_register_password_without_letter_rejected` | Branche "sans lettre" symétrique |
| `test_auth.py` | `test_expired_jwt_rejected` | Token structurellement valide mais expiré |
| `test_auth.py` | `test_jwt_wrong_signature_rejected` | Token signé avec une autre clé (config volée/erronée) |
| `test_auth.py` | `test_login_after_account_deletion_generic_error` | Pas de fuite d'info après suppression de compte |
| `test_text_extractor.py` | `test_extract_txt_chardet_confident_but_wrong_falls_back` | chardet confiant mais faux → fallback sans crash |
| `test_text_extractor.py` | `test_extract_txt_single_long_word_without_spaces` | Mot sans espace plus long qu'un bloc entier |

## Fichiers orphelins J48

Déjà traités (commit `25f9a3a`, entre J50 et J51) : rien à faire ce sprint.
