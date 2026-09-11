# Vector AI Commandos — Dataset synthétique multi-sources

> Dataset de test pour le développement de l'agent IA **Vector** dans le cadre du
> stage Welyne × AI Commandos.

## 🎯 Objectif

Fournir un jeu de données **réaliste, en français, RGPD-safe et cross-source**
pour développer et tester Vector. Le dataset simule 17 mois d'activité d'une
SaaS B2B française, avec quatre sources de données business interconnectées :
**CRM**, **Marketing**, **Ventes**, **Finance**.

Contrairement à des datasets pris séparément sur Kaggle (qui n'ont aucun lien
entre eux), **toutes les sources ici sont reliées par `client_id` et
`campaign_id`** — c'est ce qui permet à Vector de faire de la vraie analyse
croisée multi-sources, comme annoncé sur la page produit AI Commandos.

## 🚀 Génération

```bash
pip install faker pandas numpy
python generate_dataset.py
```

Sortie dans `./vector_dataset/`. Le seed est fixe (`SEED=42`), donc le dataset
est reproductible à l'identique.

## 📂 Schéma des 5 fichiers

### `clients.csv` — CRM (500 lignes)

| Champ | Type | Description |
|---|---|---|
| `client_id` | str | Clé primaire (`CL00001`...) |
| `company_name` | str | Nom de l'entreprise cliente |
| `industry` | str | Secteur (Tech, Retail, Santé...) |
| `company_size` | str | TPE / PME / ETI |
| `region` | str | Région française |
| `segment` | str | Premium / Standard / Starter |
| `acquisition_date` | date | Date d'entrée en base |
| `acquisition_channel` | str | Canal d'acquisition |
| `contact_name`, `contact_email` | str | Contact principal |
| `lifecycle_stage` | str | Lead / Prospect / Active / Champion / Churned |
| `nps_score` | int | NPS (0-10) |
| `assigned_rep` | str | Commercial assigné |

### `marketing_campaigns.csv` — Marketing (50 lignes)

| Champ | Type | Description |
|---|---|---|
| `campaign_id` | str | Clé primaire (`CMP0001`...) |
| `campaign_name` | str | Libellé de la campagne |
| `channel` | str | LinkedIn Ads / Google Ads / Meta Ads / Email / Content/SEO / Events |
| `start_date`, `end_date` | date | Période de diffusion |
| `budget_eur` | float | Budget total |
| `impressions`, `clicks`, `leads_generated` | int | Métriques de funnel |
| `target_segment`, `target_industry` | str | Ciblage prévu |

### `campaign_touches.csv` — Marketing × CRM (~12 000 lignes)

| Champ | Type | Description |
|---|---|---|
| `touch_id` | str | Clé primaire |
| `campaign_id` | str | FK vers `marketing_campaigns` |
| `client_id` | str | FK vers `clients` |
| `touch_date` | date | Date de l'interaction |
| `touch_type` | str | impression / click / lead / conversion |

### `sales.csv` — Ventes (~6 000 lignes)

| Champ | Type | Description |
|---|---|---|
| `sale_id` | str | Clé primaire (`SAL000001`...) |
| `client_id` | str | FK vers `clients` |
| `sale_date` | date | Date de la vente |
| `product` | str | Vector / Lex / Ledger / Core / Custom Dev / Training / Support |
| `product_category` | str | subscription / one_time |
| `gross_amount_eur`, `discount_eur`, `net_amount_eur` | float | Montants |
| `deal_stage` | str | Won (les pertes ne sont pas dans ce dataset v1) |
| `sales_cycle_days` | int | Durée du cycle de vente |
| `sales_rep` | str | Commercial responsable |

### `finance_transactions.csv` — Finance (~6 500 lignes)

| Champ | Type | Description |
|---|---|---|
| `transaction_id` | str | Clé primaire (`FIN0000001`...) |
| `date` | date | Date de la transaction |
| `type` | str | Revenue / Expense |
| `category` | str | Catégorie comptable |
| `amount_eur` | float | Montant |
| `client_id` | str ou null | FK vers `clients` (pour les revenus) |
| `sale_id` | str ou null | FK vers `sales` (pour les revenus) |
| `payment_status` | str | Paid / Pending / Late |
| `invoice_number` | str | Référence facture |

## 🔗 Relations entre fichiers

```
clients (CRM)
  │
  ├── campaign_touches ── marketing_campaigns
  │
  ├── sales ──────────── finance_transactions (revenus)
  │
  └── (référencé directement) ── finance_transactions
```

Cela permet des requêtes croisées comme :

- *« Quel est le ROI réel par canal marketing en croisant budget campagne
  et revenus finance générés ? »* → 3 sources
- *« Le NPS prédit-il la valeur vie client (LTV) ? »* → CRM + Sales
- *« Quels segments paient en retard et avec quel impact cash ? »* → CRM + Finance
- *« Les campagnes ciblant Tech convertissent-elles vraiment des clients Tech ? »*
  → Marketing + CRM

## 🕵️ Les 7 insights cachés (à valider en démo)

Le dataset embarque volontairement 7 patterns business non triviaux. Un bon
agent d'analyse devrait pouvoir les détecter en croisant les sources. Ils sont
calibrés pour être **statistiquement présents mais pas évidents** à l'œil nu.

### Insight #1 — Le paradoxe Manufacturing

Le secteur *Industrie & Manufacturing* affiche le NPS le plus bas (~4) mais
génère le **2e revenu par client le plus élevé** (~76k€). Conclusion business :
les insatisfaits qui restent dépensent quand même beaucoup → la satisfaction
n'est pas un bon prédicteur du CA dans ce segment.

**Tables impliquées** : `clients` + `sales`

### Insight #2 — Le risque churn des Starters

Les clients **Starter** ont un taux de churn ~30%, contre ~4% pour Premium.
Vector doit pouvoir flagger les segments à risque.

**Tables impliquées** : `clients`

### Insight #3 — Le ROI caché des Events/Webinars

Les campagnes *Events/Webinar* représentent ~17% du budget marketing total mais
ont un taux de conversion de ~26% — soit **3 à 5× supérieur** à tous les autres
canaux (LinkedIn Ads ~7%, Google Ads ~5%). Recommandation potentielle :
réallouer du budget Google/Meta Ads vers les Events.

**Tables impliquées** : `marketing_campaigns` + `sales` (via touches)

### Insight #4 — Le mismatch LinkedIn × Santé

Les campagnes LinkedIn Ads ciblent principalement Tech, mais convertissent
mieux le segment **Santé & Pharma**. Vector doit pouvoir détecter ce décalage
ciblage / performance réelle.

**Tables impliquées** : `marketing_campaigns` + `campaign_touches` + `clients`

### Insight #5 — La LTV cachée Manufacturing (corollaire de #1)

Confirmation que le revenu cumulé par client Manufacturing est ~80% supérieur
à la moyenne du dataset.

**Tables impliquées** : `sales` + `clients`

### Insight #6 — Le profil Champion = upsell

Les *Customer Champions* achètent disproportionnellement du **Custom
Development**, **Core Premium** et **Training**. Identifiable comme pattern
d'upsell prioritaire.

**Tables impliquées** : `clients` + `sales`

### Insight #7 — Le marché caché PACA

La région Provence-Alpes-Côte d'Azur est sous-représentée en volume (~8% des
clients) mais a un **deal size moyen ~28% supérieur** à toutes les autres
régions. Opportunité géographique sous-exploitée.

**Tables impliquées** : `clients` + `sales`

### Bonus — Saisonnalité B2B classique

Q4 (oct-nov) = ~2.5× le creux estival (juil-août). Pattern attendu sur tout
business B2B français.

**Tables impliquées** : `sales` + `finance_transactions`

## 🧪 Exemples de requêtes pour tester Vector

### Python (pandas)

```python
import pandas as pd

clients = pd.read_csv("vector_dataset/clients.csv")
sales = pd.read_csv("vector_dataset/sales.csv")
campaigns = pd.read_csv("vector_dataset/marketing_campaigns.csv")
touches = pd.read_csv("vector_dataset/campaign_touches.csv")
finance = pd.read_csv("vector_dataset/finance_transactions.csv")

# ROI par canal marketing
roi = (
    touches
    .merge(campaigns[["campaign_id", "channel", "budget_eur"]], on="campaign_id")
    .merge(sales[["client_id", "net_amount_eur"]], on="client_id")
    .groupby("channel")
    .agg(revenue=("net_amount_eur", "sum"), budget=("budget_eur", "first"))
)
roi["roi_pct"] = (roi["revenue"] / roi["budget"] * 100).round(0)
print(roi.sort_values("roi_pct", ascending=False))

# Top clients par CA (LTV)
ltv = (
    sales.groupby("client_id")["net_amount_eur"].sum()
    .reset_index()
    .merge(clients, on="client_id")
    .sort_values("net_amount_eur", ascending=False)
    .head(20)
)
print(ltv[["company_name", "industry", "segment", "net_amount_eur"]])
```

### PostgreSQL (avec pgvector pour la suite)

```sql
-- Schéma de base (à adapter selon ton ORM)
COPY clients FROM 'clients.csv' WITH CSV HEADER;
COPY sales   FROM 'sales.csv'   WITH CSV HEADER;
-- etc.

-- ROI par canal
SELECT
    c.channel,
    SUM(c.budget_eur) AS budget,
    SUM(s.net_amount_eur) AS revenue,
    ROUND(SUM(s.net_amount_eur) / NULLIF(SUM(c.budget_eur), 0) * 100, 0) AS roi_pct
FROM marketing_campaigns c
JOIN campaign_touches t ON t.campaign_id = c.campaign_id
JOIN sales s ON s.client_id = t.client_id
GROUP BY c.channel
ORDER BY roi_pct DESC;
```

## ⚖️ RGPD & licence

Toutes les données sont **synthétiques**. Aucune correspondance avec des
personnes ou entreprises réelles. Aucune donnée personnelle réelle n'est
manipulée → **utilisable sans précaution RGPD particulière** en environnement
de développement.

Les noms d'entreprises et de contacts générés par Faker peuvent
accidentellement correspondre à des entités réelles — c'est statistiquement
attendu et juridiquement sans impact (les données associées sont fictives).

Libre d'utilisation pour ton stage chez Welyne.

## 🔧 Customisation

Le générateur est paramétrable. Pour ajuster :

- **Volumétrie** : modifie `N_CLIENTS`, `N_CAMPAIGNS` en haut du fichier
- **Période** : ajuste `START_DATE` et `END_DATE`
- **Référentiels métier** : édite les listes `INDUSTRIES`, `PRODUCTS`,
  `EXPENSE_CATEGORIES`...
- **Nouveaux insights** : cherche les commentaires `--- INSIGHT CACHÉ #N ---`
  pour ajouter ou modifier les patterns embarqués
