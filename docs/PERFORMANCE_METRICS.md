# Métriques de performance — démo publique Vector

Mesuré le 2026-08-30 00:00:52 CEST (Europe/Paris)

## Environnement testé

- URL : https://ai-commandos-multi-agent.onrender.com
- Région : Frankfurt (eu-central)
- Tier : Render.com Free

## Résumé

| Métrique | Min | Médiane (p50) | Moyenne | p95 | p99 | Max | Écart-type |
|---|---|---|---|---|---|---|---|
| Cold start | — | — | — | — | — | 82.43s | — |
| Warm /health (30x) | 62.5ms | 74.8ms | 109.7ms | 320.0ms | 426.4ms | 428.6ms | 91.2ms |
| Login (10x) | 1594.5ms | 1681.3ms | 1792.5ms | 2341.7ms | — | 2643.5ms | 319.3ms |
| Static / (10x) | 61.1ms | 68.3ms | 76.9ms | 116.3ms | — | 130.2ms | — |

## Disponibilité (baseline courte)

30/30 requêtes réussies sur une fenêtre de ~60s espacées de 2s → **100.0%** uptime.

> Baseline courte terme, à comparer avec une mesure sur une fenêtre plus longue (heures/jours) si besoin de chiffres de disponibilité plus robustes.

## Interprétation pour le CV

- Temps de réponse médian de 74.8ms (p95 : 320.0ms) sur l'endpoint de santé en conditions chaudes, sur une instance gratuite Render (0.1 vCPU, 512 Mo RAM).
- Authentification (hash bcrypt + génération JWT) mesurée à 1681.3ms médian sur 10 tentatives réelles.
- Livraison des assets statiques (export Next.js via Nginx) en 68.3ms médian, cohérent avec le choix architectural d'un export statique plutôt qu'un serveur Node en production (contrainte RAM du tier gratuit).
- Cold start (reprise après mise en veille, tier gratuit) mesuré à 82.43s, documenté et mitigé côté produit (kill switch, recommandation de warm-up avant démonstration).
- Disponibilité de 100.0% observée sur la fenêtre de test (30/30 requêtes).
