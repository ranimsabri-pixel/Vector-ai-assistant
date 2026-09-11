# Tests E2E (Playwright)

18 specs au total :

- **`01` à `11`** — parcours historiques (auth, chat, upload, dashboard,
  web search, corpus, gestion d'erreurs, partage). La plupart appellent le
  **vrai** LLM OpenAI (`test.slow()`), donc coûtent des crédits API et
  dépendent du réseau.
- **`12` à `18`** (S5 J52) — auth-flow, personas, corpus multi-format,
  chat image, thème, gestion de compte, suppression de compte. Ces 7 specs
  sont **100% mockées** (aucun appel réseau vers OpenAI/Tavily) et
  s'exécutent offline, déterministes.

## Prérequis

1. Postgres + Redis via Docker (`docker compose up -d db redis` à la racine
   du projet, ou équivalent).
2. Backend démarré (`uvicorn app.main:app --port 8000` depuis `backend/`).
3. Frontend démarré (`pnpm dev`, port 3000).
4. Navigateur Chromium installé pour Playwright :
   ```
   pnpm exec playwright install chromium
   ```
   Ce projet est configuré pour installer les navigateurs sous
   `D:\playwright-browsers` (variable d'environnement utilisateur Windows
   `PLAYWRIGHT_BROWSERS_PATH`), pas sous le chemin par défaut sur `C:`.
   Vérifier avec :
   ```powershell
   [Environment]::GetEnvironmentVariable("PLAYWRIGHT_BROWSERS_PATH", "User")
   ```
   Si vide, la (re)poser puis ouvrir un **nouveau** terminal avant de
   lancer `playwright install` (les variables `User` ne sont lues qu'au
   démarrage du process).

Playwright ne démarre pas les serveurs lui-même (`webServer` non configuré
dans `playwright.config.ts`) — les 2 doivent tourner manuellement avant
`playwright test`.

## Deux modes d'exécution

Les specs `01-11` (vrai LLM) et `12-18` (mock) **ne peuvent pas tourner
dans le même process backend** : un seul backend sert tout un run
Playwright (`workers: 1`, séquentiel), et il est soit en mode réel soit en
mode mock, jamais les deux à la fois.

**Mode réel** (specs `01-11`, comportement historique inchangé) :
```bash
# backend démarré normalement (.env avec une vraie OPENAI_API_KEY)
pnpm test:e2e
```

**Mode mock** (specs `12-18`, offline) :
```bash
# backend démarré avec USE_MOCK_LLM=true
USE_MOCK_LLM=true uvicorn app.main:app --port 8000   # depuis backend/, ou
$env:USE_MOCK_LLM="true"; uvicorn app.main:app --port 8000  # PowerShell

pnpm test:e2e:mocked
```

`USE_MOCK_LLM=true` fait basculer `OpenAIProvider` (chat, streaming,
embeddings, tool calling) et `WebSearchService` (Tavily) sur des réponses
déterministes (`backend/app/ai/providers/mock_responses.py`) — jamais
d'appel réseau externe. Le flag est à `false` par défaut partout ailleurs
(dev normal, tests pytest, prod) : voir `backend/app/core/config.py`.

## Scripts npm

| Script | Effet |
|---|---|
| `pnpm test:e2e` | Toutes les specs, headless |
| `pnpm test:e2e:mocked` | Uniquement les specs `12` à `18` (glob `1[2-8]-*`), nécessite le backend en mode mock |
| `pnpm test:e2e:headed` | Toutes les specs, navigateur visible |
| `pnpm test:e2e:ui` | Mode UI interactif Playwright (debug pas à pas) |
| `pnpm test:e2e:report` | Rouvre le dernier rapport HTML |

Lancer une seule spec :
```bash
pnpm exec playwright test e2e/12-auth-flow.spec.ts
pnpm exec playwright test e2e/12-auth-flow.spec.ts -g "signup avec email valide"
```

Activer les traces même sur succès (par défaut, `trace: retain-on-failure`
dans `playwright.config.ts` — uniquement à l'échec, pour ne pas saturer le
disque) :
```bash
pnpm exec playwright test --trace on
```

## Fixtures et helpers partagés (`e2e/`)

- `helpers/auth.ts` — `registerAndLogin`/`loginExisting`/`logout` (flux UI
  réel), `postMessageViaApi`/`deleteConversationViaApi`/`deleteDatasetViaApi`
  (raccourcis API pour peupler/nettoyer sans dépendre d'un vrai LLM).
- `helpers/api.ts` (J52) — `createTestUser` (inscription directe via API,
  plus rapide que le formulaire quand le test ne porte pas sur le signup),
  `loginAs` (injecte un token en localStorage), `deleteTestUser` (hard
  delete via `DELETE /users/me`).
- `fixtures/test-users.ts` — `uniqueEmail(prefix)` : email unique par test
  (timestamp + random), aucune spec ne doit dépendre d'un état laissé par
  une autre.
- `fixtures/*.pdf` `*.docx` `*.png` — fichiers de test légers. Attention au
  seuil `MIN_CHUNK_TOKENS = 30` du retrieval multi-documents (piège déjà
  rencontré 2 fois) : un paragraphe trop court dans un fixture PDF/DOCX
  voit ses chunks filtrés et disparaît silencieusement des résultats de
  recherche.

## Conventions

- **`data-testid`** sur tout élément sans sélecteur stable autrement
  (texte/rôle/label déjà unique = pas besoin d'en ajouter un). Ajouté au
  composant en même temps que la spec qui en a besoin, jamais après coup.
- **Isolation** : chaque spec crée son propre user (`uniqueEmail`), aucune
  dépendance à un état créé par une autre spec.
- **Pas de `waitForTimeout` arbitraire** sauf cas déjà présents dans les
  specs historiques (attente du chargement Zustand après login) — préférer
  `expect(...).toBeVisible()`, `waitForFunction`, `waitForResponse`.
- **3 runs consécutifs verts** avant commit pour toute nouvelle spec.

## Limites connues

- Cross-browser (Firefox/WebKit) et mobile : hors scope V1, `chromium`
  uniquement dans `playwright.config.ts`.
- Accessibilité automatisée (axe-core) : hors scope, audit Lighthouse
  manuel seulement (cf rapport S5 J50).
- Le mode `system` du thème n'est pas testé (dépend des préférences OS de
  la machine d'exécution, source de flakiness).
