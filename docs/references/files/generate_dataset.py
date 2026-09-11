"""
Vector AI Commandos — Générateur de dataset synthétique multi-sources
=======================================================================

Génère 5 fichiers CSV cohérents et reliés par IDs, simulant les données
business d'une SaaS B2B française sur ~17 mois :

    clients.csv              → CRM (500 entreprises clientes B2B)
    marketing_campaigns.csv  → Marketing (50 campagnes multi-canaux)
    campaign_touches.csv     → Interactions client × campagne
    sales.csv                → Ventes (transactions commerciales)
    finance_transactions.csv → Finance (revenus + dépenses opérationnelles)

Le dataset est conçu pour tester un agent IA d'analyse de données type Vector :
toutes les sources sont reliées par client_id et/ou campaign_id, ce qui
permet l'analyse croisée multi-sources.

Sept insights métier sont volontairement embarqués dans les données
(voir README.md). Un bon agent d'analyse devrait pouvoir les détecter.

Usage :
    pip install faker pandas numpy
    python generate_dataset.py

Sortie : dossier ./vector_dataset/ avec 5 CSVs + dataset_summary.json
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker


# =====================================================================
# CONFIG
# =====================================================================
SEED = 42
N_CLIENTS = 500
N_CAMPAIGNS = 50
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2026, 5, 31)
OUTPUT_DIR = Path("vector_dataset")

fake = Faker("fr_FR")
Faker.seed(SEED)
random.seed(SEED)
np.random.seed(SEED)

OUTPUT_DIR.mkdir(exist_ok=True)


# =====================================================================
# RÉFÉRENTIELS MÉTIER
# =====================================================================
INDUSTRIES = [
    "Tech & SaaS", "Retail & E-commerce", "Santé & Pharma",
    "Services B2B", "Industrie & Manufacturing", "Finance & Assurance",
    "Education & Formation", "Médias & Communication",
]
INDUSTRY_WEIGHTS = [0.28, 0.18, 0.10, 0.20, 0.12, 0.06, 0.04, 0.02]

COMPANY_SIZES = ["TPE (1-10)", "PME (11-250)", "ETI (251-5000)"]
SIZE_WEIGHTS = [0.45, 0.45, 0.10]

REGIONS = [
    "Île-de-France", "Auvergne-Rhône-Alpes", "Provence-Alpes-Côte d'Azur",
    "Hauts-de-France", "Nouvelle-Aquitaine", "Grand Est", "Occitanie",
    "Pays de la Loire", "Bretagne", "Normandie",
]
REGION_WEIGHTS = [0.35, 0.15, 0.08, 0.07, 0.07, 0.07, 0.06, 0.05, 0.05, 0.05]

ACQUISITION_CHANNELS = [
    "LinkedIn Ads", "Google Ads", "Email Marketing", "Content/SEO",
    "Referral", "Direct", "Events/Salons", "Outbound Sales",
]

SEGMENTS = ["Premium", "Standard", "Starter"]
SEGMENT_WEIGHTS = [0.15, 0.55, 0.30]

LIFECYCLE_STAGES = [
    "Lead", "Prospect", "Customer Active", "Customer Champion", "Churned",
]

PRODUCTS = {
    "Vector Subscription":   {"price_range": (500, 2000),  "category": "subscription"},
    "Lex Subscription":      {"price_range": (400, 1500),  "category": "subscription"},
    "Ledger Subscription":   {"price_range": (300, 1200),  "category": "subscription"},
    "Core Premium":          {"price_range": (1500, 5000), "category": "subscription"},
    "Custom Development":    {"price_range": (5000, 30000),"category": "one_time"},
    "Training & Onboarding": {"price_range": (1000, 4000), "category": "one_time"},
    "Premium Support":       {"price_range": (200, 800),   "category": "subscription"},
}

SALES_REPS = ["Amine B.", "Sophie L.", "Karim T.", "Marie D.", "Yanis F.", "Léa M."]

CAMPAIGN_CHANNELS = {
    "LinkedIn Ads":   {"cpm": (12, 25), "ctr": (0.008, 0.025)},
    "Google Ads":     {"cpm": (8, 18),  "ctr": (0.015, 0.045)},
    "Meta Ads":       {"cpm": (6, 14),  "ctr": (0.010, 0.030)},
    "Email Campaign": {"cpm": (1, 3),   "ctr": (0.020, 0.060)},
    "Content/SEO":    {"cpm": (2, 6),   "ctr": (0.030, 0.080)},
    "Events/Webinar": {"cpm": (40, 120),"ctr": (0.050, 0.150)},
}

EXPENSE_CATEGORIES = {
    "Salaires & charges":              (45000, 85000),
    "Marketing & Publicité":           (6000, 22000),
    "Infrastructure Cloud":            (2500, 7000),
    "Outils SaaS internes":            (800, 2500),
    "Bureaux & équipement":            (3500, 5500),
    "Frais juridiques & conseil":      (400, 3500),
    "Déplacements & événements":       (800, 4500),
    "OpenAI / LLM API":                (1500, 4500),
}


# =====================================================================
# HELPERS
# =====================================================================
def random_date_between(start: datetime, end: datetime) -> datetime:
    delta = (end - start).total_seconds()
    return start + timedelta(seconds=random.uniform(0, delta))


def weighted_choice(items, weights=None):
    return random.choices(items, weights=weights, k=1)[0]


def seasonal_multiplier(date: datetime) -> float:
    """Cycle B2B réaliste : creux estival, pic Q4, redémarrage Q1."""
    month = date.month
    if month in (7, 8):
        return 0.55
    if month == 12:
        return 0.72
    if month in (10, 11):
        return 1.35
    if month in (1, 2, 3):
        return 1.10
    return 1.0


# =====================================================================
# 1. CLIENTS (CRM)
# =====================================================================
def generate_clients(n: int) -> pd.DataFrame:
    rows = []
    for i in range(1, n + 1):
        acquisition_date = random_date_between(START_DATE, END_DATE - timedelta(days=30))
        industry = weighted_choice(INDUSTRIES, INDUSTRY_WEIGHTS)
        size = weighted_choice(COMPANY_SIZES, SIZE_WEIGHTS)
        region = weighted_choice(REGIONS, REGION_WEIGHTS)
        segment = weighted_choice(SEGMENTS, SEGMENT_WEIGHTS)
        channel = weighted_choice(ACQUISITION_CHANNELS)

        # --- INSIGHT CACHÉ #1 ---
        # L'industrie Manufacturing a un NPS faible MAIS une LTV élevée
        # (les insatisfaits qui restent achètent davantage)
        if industry == "Industrie & Manufacturing":
            nps_score = random.randint(2, 6)
        elif segment == "Premium":
            nps_score = random.randint(8, 10)
        elif segment == "Starter":
            nps_score = random.randint(4, 8)
        else:
            nps_score = random.randint(6, 9)

        # Lifecycle stage corrélé à la date d'acquisition + segment
        days_since_acquisition = (END_DATE - acquisition_date).days
        if days_since_acquisition < 30:
            lifecycle = "Lead" if random.random() < 0.7 else "Prospect"
        elif days_since_acquisition < 90:
            lifecycle = weighted_choice(
                ["Prospect", "Customer Active", "Churned"], [0.3, 0.6, 0.1]
            )
        else:
            # --- INSIGHT CACHÉ #2 ---
            # Risque de churn plus élevé pour Starter sans interaction récente
            churn_prob = 0.25 if segment == "Starter" else 0.08
            if segment == "Premium" and nps_score >= 9:
                lifecycle = "Customer Champion"
            elif random.random() < churn_prob:
                lifecycle = "Churned"
            else:
                lifecycle = "Customer Active"

        company_name = fake.company()
        contact_first = fake.first_name()
        contact_last = fake.last_name()
        email_domain = company_name.lower().replace(" ", "").replace(",", "")[:20] + ".fr"

        rows.append({
            "client_id": f"CL{i:05d}",
            "company_name": company_name,
            "industry": industry,
            "company_size": size,
            "region": region,
            "segment": segment,
            "acquisition_date": acquisition_date.date(),
            "acquisition_channel": channel,
            "contact_name": f"{contact_first} {contact_last}",
            "contact_email": f"{contact_first.lower()}.{contact_last.lower()}@{email_domain}",
            "lifecycle_stage": lifecycle,
            "nps_score": nps_score,
            "assigned_rep": weighted_choice(SALES_REPS),
        })

    return pd.DataFrame(rows)


# =====================================================================
# 2. MARKETING CAMPAIGNS
# =====================================================================
def generate_campaigns(n: int) -> pd.DataFrame:
    rows = []
    campaign_names_seen = set()

    for i in range(1, n + 1):
        channel = weighted_choice(list(CAMPAIGN_CHANNELS.keys()))
        config = CAMPAIGN_CHANNELS[channel]

        start = random_date_between(START_DATE, END_DATE - timedelta(days=60))
        duration_days = random.choice([14, 21, 30, 45, 60, 90])
        end = min(start + timedelta(days=duration_days), END_DATE)

        budget = round(random.uniform(2000, 35000), 2)

        # Impressions calculées via budget + CPM
        cpm = random.uniform(*config["cpm"])
        impressions = int(budget / cpm * 1000)

        # CTR
        ctr = random.uniform(*config["ctr"])
        clicks = int(impressions * ctr)

        # --- INSIGHT CACHÉ #3 ---
        # Les campagnes Events/Webinar ont un volume bas mais une conversion
        # exceptionnelle (ROI réel masqué par le faible volume)
        if channel == "Events/Webinar":
            conv_rate = random.uniform(0.18, 0.35)
        elif channel == "LinkedIn Ads":
            conv_rate = random.uniform(0.04, 0.10)
        elif channel == "Email Campaign":
            conv_rate = random.uniform(0.08, 0.18)
        else:
            conv_rate = random.uniform(0.02, 0.07)

        leads = int(clicks * conv_rate)

        target_segment = weighted_choice(SEGMENTS + ["All"], [0.2, 0.3, 0.2, 0.3])
        target_industry = weighted_choice(INDUSTRIES + ["All"],
                                          INDUSTRY_WEIGHTS + [0.4])

        # Génération nom unique
        while True:
            theme = random.choice([
                "Q1 Acquisition", "Spring Push", "Summer Boost", "Back-to-Business",
                "Q4 Sprint", "Year-End Drive", "Product Launch", "Webinar Series",
                "Industry Focus", "Retention Push", "Upsell Drive", "Brand Awareness",
            ])
            name = f"{theme} — {channel} — {start.strftime('%b %Y')}"
            if name not in campaign_names_seen:
                campaign_names_seen.add(name)
                break

        rows.append({
            "campaign_id": f"CMP{i:04d}",
            "campaign_name": name,
            "channel": channel,
            "start_date": start.date(),
            "end_date": end.date(),
            "budget_eur": budget,
            "impressions": impressions,
            "clicks": clicks,
            "leads_generated": leads,
            "target_segment": target_segment,
            "target_industry": target_industry,
        })

    return pd.DataFrame(rows)


# =====================================================================
# 3. CAMPAIGN TOUCHES (liens marketing ↔ clients)
# =====================================================================
def generate_campaign_touches(clients_df: pd.DataFrame,
                              campaigns_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    touch_counter = 1

    for _, campaign in campaigns_df.iterrows():
        leads = campaign["leads_generated"]
        # Sample leads conversion en vrais clients
        n_converted = int(leads * random.uniform(0.10, 0.40))

        # Filtre les clients acquis pendant ou après la campagne (cohérence temporelle)
        cstart = pd.to_datetime(campaign["start_date"])
        eligible = clients_df[
            pd.to_datetime(clients_df["acquisition_date"]) >= (cstart - timedelta(days=14))
        ]
        if len(eligible) == 0:
            continue

        # --- INSIGHT CACHÉ #4 ---
        # LinkedIn Ads ciblent surtout Tech, mais convertissent mieux Santé/Pharma
        if campaign["channel"] == "LinkedIn Ads":
            healthcare_pool = eligible[eligible["industry"] == "Santé & Pharma"]
            if len(healthcare_pool) > 0 and random.random() < 0.4:
                eligible = pd.concat([eligible, healthcare_pool, healthcare_pool])

        sample_size = min(n_converted, len(eligible))
        if sample_size == 0:
            continue
        touched_clients = eligible.sample(n=sample_size, replace=False)

        for _, client in touched_clients.iterrows():
            touch_date = random_date_between(
                max(cstart.to_pydatetime(), START_DATE),
                min(pd.to_datetime(campaign["end_date"]).to_pydatetime()
                    + timedelta(days=30), END_DATE)
            )
            touch_type = weighted_choice(
                ["impression", "click", "lead", "conversion"],
                [0.4, 0.3, 0.2, 0.1]
            )
            rows.append({
                "touch_id": f"TCH{touch_counter:07d}",
                "campaign_id": campaign["campaign_id"],
                "client_id": client["client_id"],
                "touch_date": touch_date.date(),
                "touch_type": touch_type,
            })
            touch_counter += 1

    return pd.DataFrame(rows)


# =====================================================================
# 4. SALES
# =====================================================================
def generate_sales(clients_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    sale_counter = 1

    for _, client in clients_df.iterrows():
        if client["lifecycle_stage"] in ("Lead", "Prospect"):
            continue

        acquisition = pd.to_datetime(client["acquisition_date"]).to_pydatetime()
        is_churned = client["lifecycle_stage"] == "Churned"

        # Date de churn (si applicable)
        churn_date = (acquisition + timedelta(days=random.randint(60, 365))
                      if is_churned else END_DATE)
        last_active_date = min(churn_date, END_DATE)

        # Nb de ventes basé sur segment + ancienneté
        months_active = max(1, (last_active_date - acquisition).days // 30)
        if client["segment"] == "Premium":
            base_purchases = months_active * random.uniform(1.2, 2.0)
        elif client["segment"] == "Standard":
            base_purchases = months_active * random.uniform(0.6, 1.2)
        else:
            base_purchases = months_active * random.uniform(0.3, 0.8)

        # --- INSIGHT CACHÉ #5 ---
        # Les clients Manufacturing achètent plus malgré leur NPS bas
        if client["industry"] == "Industrie & Manufacturing":
            base_purchases *= 1.6

        # --- INSIGHT CACHÉ #6 ---
        # Les Champions sont sur-représentés en upsell (cross-product buying)
        is_champion = client["lifecycle_stage"] == "Customer Champion"
        product_pool = list(PRODUCTS.keys())

        n_sales = max(1, int(base_purchases))

        for _ in range(n_sales):
            sale_date = random_date_between(acquisition, last_active_date)

            # Champion → plus de chances d'acheter du Custom Dev (gros tickets)
            if is_champion and random.random() < 0.35:
                product = random.choice(["Custom Development",
                                         "Training & Onboarding",
                                         "Core Premium"])
            else:
                product = random.choice(product_pool)

            price_min, price_max = PRODUCTS[product]["price_range"]
            base_amount = random.uniform(price_min, price_max)

            # Saisonnalité B2B
            amount = base_amount * seasonal_multiplier(sale_date)

            # --- INSIGHT CACHÉ #7 ---
            # PACA sous-représentée mais avec deal_size supérieur (marché caché)
            if client["region"] == "Provence-Alpes-Côte d'Azur":
                amount *= 1.28

            discount_pct = random.choices([0, 5, 10, 15, 20],
                                          weights=[0.5, 0.2, 0.15, 0.10, 0.05])[0]
            discount = round(amount * discount_pct / 100, 2)
            final_amount = round(amount - discount, 2)

            deal_stage = "Won"
            sales_cycle_days = random.randint(7, 90)
            if client["segment"] == "Premium":
                sales_cycle_days = random.randint(20, 120)

            rows.append({
                "sale_id": f"SAL{sale_counter:06d}",
                "client_id": client["client_id"],
                "sale_date": sale_date.date(),
                "product": product,
                "product_category": PRODUCTS[product]["category"],
                "gross_amount_eur": round(amount, 2),
                "discount_eur": discount,
                "net_amount_eur": final_amount,
                "deal_stage": deal_stage,
                "sales_cycle_days": sales_cycle_days,
                "sales_rep": client["assigned_rep"],
            })
            sale_counter += 1

    return pd.DataFrame(rows).sort_values("sale_date").reset_index(drop=True)


# =====================================================================
# 5. FINANCE TRANSACTIONS
# =====================================================================
def generate_finance(sales_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    tx_counter = 1

    # --- 5a. Revenus liés aux ventes (encaissements) ---
    for _, sale in sales_df.iterrows():
        sale_date = pd.to_datetime(sale["sale_date"]).to_pydatetime()

        # Délai de paiement réaliste : 0-60 jours
        days_delay = random.choices([0, 15, 30, 45, 60, 90],
                                    weights=[0.15, 0.25, 0.35, 0.15, 0.07, 0.03])[0]
        payment_date = sale_date + timedelta(days=days_delay)
        if payment_date > END_DATE:
            payment_status = "Pending"
            payment_date = END_DATE
        elif days_delay > 45:
            payment_status = "Late"
        else:
            payment_status = "Paid"

        rows.append({
            "transaction_id": f"FIN{tx_counter:07d}",
            "date": payment_date.date(),
            "type": "Revenue",
            "category": "Subscription Revenue" if sale["product_category"] == "subscription"
                        else "One-time Revenue",
            "amount_eur": sale["net_amount_eur"],
            "client_id": sale["client_id"],
            "sale_id": sale["sale_id"],
            "payment_status": payment_status,
            "invoice_number": f"FAC-{tx_counter:06d}",
        })
        tx_counter += 1

    # --- 5b. Dépenses mensuelles ---
    current = START_DATE.replace(day=1)
    while current <= END_DATE:
        for category, (min_amt, max_amt) in EXPENSE_CATEGORIES.items():
            n_tx_in_month = random.choices([1, 2, 3, 4],
                                           weights=[0.4, 0.3, 0.2, 0.1])[0]
            monthly_total = random.uniform(min_amt, max_amt)
            # Saisonnalité sur marketing
            if category == "Marketing & Publicité":
                monthly_total *= seasonal_multiplier(current)
            # OpenAI augmente avec le temps (croissance d'usage)
            if category == "OpenAI / LLM API":
                months_in = (current.year - 2024) * 12 + current.month - 1
                monthly_total *= (1 + 0.05 * months_in)

            for _ in range(n_tx_in_month):
                tx_date = current + timedelta(days=random.randint(0, 27))
                if tx_date > END_DATE:
                    continue
                rows.append({
                    "transaction_id": f"FIN{tx_counter:07d}",
                    "date": tx_date.date(),
                    "type": "Expense",
                    "category": category,
                    "amount_eur": round(monthly_total / n_tx_in_month, 2),
                    "client_id": None,
                    "sale_id": None,
                    "payment_status": "Paid",
                    "invoice_number": f"DEP-{tx_counter:06d}",
                })
                tx_counter += 1

        # Mois suivant
        if current.month == 12:
            current = current.replace(year=current.year + 1, month=1)
        else:
            current = current.replace(month=current.month + 1)

    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


# =====================================================================
# MAIN
# =====================================================================
def main():
    print("🚀 Génération du dataset Vector AI Commandos...\n")

    print(f"  → Clients (CRM)...")
    clients_df = generate_clients(N_CLIENTS)
    print(f"     {len(clients_df)} clients générés")

    print(f"  → Campagnes marketing...")
    campaigns_df = generate_campaigns(N_CAMPAIGNS)
    print(f"     {len(campaigns_df)} campagnes générées")

    print(f"  → Touches campagne × client...")
    touches_df = generate_campaign_touches(clients_df, campaigns_df)
    print(f"     {len(touches_df)} interactions générées")

    print(f"  → Ventes...")
    sales_df = generate_sales(clients_df)
    print(f"     {len(sales_df)} ventes générées")

    print(f"  → Transactions financières...")
    finance_df = generate_finance(sales_df)
    print(f"     {len(finance_df)} transactions générées")

    # Sauvegarde
    files = {
        "clients.csv": clients_df,
        "marketing_campaigns.csv": campaigns_df,
        "campaign_touches.csv": touches_df,
        "sales.csv": sales_df,
        "finance_transactions.csv": finance_df,
    }
    for fname, df in files.items():
        df.to_csv(OUTPUT_DIR / fname, index=False, encoding="utf-8")

    # Résumé
    summary = {
        "generated_at": datetime.now().isoformat(),
        "seed": SEED,
        "period": f"{START_DATE.date()} → {END_DATE.date()}",
        "counts": {fname: len(df) for fname, df in files.items()},
        "total_revenue_eur": float(finance_df[finance_df["type"] == "Revenue"]
                                   ["amount_eur"].sum().round(2)),
        "total_expenses_eur": float(finance_df[finance_df["type"] == "Expense"]
                                    ["amount_eur"].sum().round(2)),
        "active_clients": int((clients_df["lifecycle_stage"]
                              .isin(["Customer Active", "Customer Champion"])).sum()),
        "churned_clients": int((clients_df["lifecycle_stage"] == "Churned").sum()),
    }
    with open(OUTPUT_DIR / "dataset_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Dataset généré dans : {OUTPUT_DIR.resolve()}")
    print(f"   Revenu total : {summary['total_revenue_eur']:,.0f} €")
    print(f"   Dépenses totales : {summary['total_expenses_eur']:,.0f} €")
    print(f"   Clients actifs : {summary['active_clients']} | "
          f"Churned : {summary['churned_clients']}")


if __name__ == "__main__":
    main()
