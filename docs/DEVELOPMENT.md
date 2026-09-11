# Guide développeur — Vector

## Gestion des secrets

**Contexte** : une vraie clé OpenAI a été committée par erreur dans
`backend/.env.example` dès le tout premier commit du projet, restée
présente dans l'historique git pendant ~8 semaines avant d'être repérée
(S5 J55). La clé a été neutralisée côté OpenAI par le tuteur (compte
propriétaire de la clé) ; le fichier a été assaini en parallèle. Ce
qui suit existe pour que ça ne se reproduise pas.

### Règles

1. **`backend/.env.example` ne doit contenir QUE des placeholders**,
   jamais de vraie valeur — y compris "temporairement pour tester". Le
   style attendu : `TAVILY_API_KEY=tvly-your-api-key-here`,
   `OPENAI_API_KEY=sk-your-openai-api-key-here`,
   `SECRET_KEY=change-me-to-a-random-base64-string-of-48-bytes-or-more`.
   Un placeholder doit être *visiblement* faux à la lecture, jamais un
   format plausible de vraie clé.

2. **`backend/.env` (vraies valeurs) est ignoré par git** — vérifié via
   `git check-ignore -v backend/.env`. Ne jamais forcer son ajout
   (`git add -f`), ne jamais le committer.

3. **Les secrets de production vivent dans les Environment Variables de
   la plateforme d'hébergement** (Render Dashboard > Environment), jamais
   dans un fichier du repo, jamais dans `.gitlab-ci.yml` en clair pour de
   vrais secrets (les valeurs factices de test CI — mots de passe Postgres
   de test, clé OpenAI bidon `sk-mock-ci-test-key` — restent acceptables
   en clair puisqu'elles ne donnent accès à rien de réel).

4. **Toute nouvelle variable d'environnement s'ajoute aux DEUX fichiers**
   en même temps : `backend/.env.example` (placeholder) et `backend/.env`
   local (vraie valeur, jamais committée). Une variable présente dans l'un
   mais pas l'autre est un signal que quelque chose a été oublié.

5. **Avant de committer, lancer le check anti-régression** :
   ```bash
   bash scripts/check_no_secrets.sh
   ```
   Ce script (et le job CI équivalent, cf `.gitlab-ci.yml`) grep les
   fichiers suivis pour les formats de clés connus (OpenAI `sk-proj-…`,
   Tavily `tvly-…`, Hugging Face `hf_…`, GitLab `glpat-…`, AWS `AKIA…`) et
   fait échouer le pipeline si un match sort. Ce n'est pas un outil de
   detection exhaustif (pas de scan d'entropie générique) — juste un
   filet de sécurité simple contre les formats de clés connus du projet.
   Si un vrai secret est trouvé committé : le révoquer chez le
   fournisseur immédiatement, c'est ça qui neutralise la fuite — pas la
   réécriture de l'historique git (qui casse les clones existants et
   n'empêche pas qu'une copie ait déjà été récupérée entre-temps).

## Autres sections

À compléter au fil des sprints (setup local, conventions de code,
structure du projet...) — voir `README.md` pour l'installation de base
en attendant.
