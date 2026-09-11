"""ONE-OFF (S5 J55+) — mesure objective des performances de la démo Vector
publique sur Render, pour alimenter le rapport de stage / CV de Ranim.

Ne fait PAS partie du runtime de l'app — à lancer manuellement :
    cd backend
    python scripts/measure_demo_performance.py

Produit :
    docs/PERFORMANCE_METRICS.md   -- rapport lisible (tableau récap + blurb CV)
    docs/performance_metrics.json -- données brutes (re-parse futur)

Durée totale attendue : 2-5 min (jusqu'à ~5 min si /auth/login est rate
limité et déclenche le fallback avec pauses de 30s).
"""
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

BASE_URL = "https://ai-commandos-multi-agent.onrender.com"
DEMO_EMAIL = "demo@vector.ai"
DEMO_PASSWORD = "VectorDemo2026!"

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DOCS_DIR = REPO_ROOT / "docs"
MD_OUTPUT = DOCS_DIR / "PERFORMANCE_METRICS.md"
JSON_OUTPUT = DOCS_DIR / "performance_metrics.json"

PARIS_TZ = ZoneInfo("Europe/Paris")


def log(msg: str) -> None:
    print(msg, flush=True)


def percentile(data: list[float], p: float) -> float:
    """p-ème percentile (0-100). numpy si dispo, sinon statistics.quantiles."""
    if not data:
        return 0.0
    if len(data) == 1:
        return data[0]
    if HAS_NUMPY:
        return float(np.percentile(data, p))
    # statistics.quantiles(n=100) donne 99 points de coupure entre 100
    # groupes -- le point d'index (p-1) approxime le p-eme percentile.
    cuts = statistics.quantiles(data, n=100, method="inclusive")
    idx = max(0, min(len(cuts) - 1, int(round(p)) - 1))
    return cuts[idx]


def compute_stats(samples_seconds: list[float]) -> dict:
    """Stats complètes en millisecondes. Le formatting Markdown choisit
    ensuite quelles colonnes afficher par section (cf spec du brief)."""
    if not samples_seconds:
        return {"count": 0}
    ms = [s * 1000 for s in samples_seconds]
    return {
        "count": len(ms),
        "min_ms": round(min(ms), 1),
        "median_ms": round(statistics.median(ms), 1),
        "mean_ms": round(statistics.mean(ms), 1),
        "p95_ms": round(percentile(ms, 95), 1),
        "p99_ms": round(percentile(ms, 99), 1),
        "max_ms": round(max(ms), 1),
        "stdev_ms": round(statistics.stdev(ms), 1) if len(ms) > 1 else 0.0,
    }


def timed_request(
    client: httpx.Client, method: str, path: str, **kwargs
) -> tuple[float | None, int | None, str | None]:
    """Retourne (duree_secondes, status_code, erreur). duree=None si échec réseau."""
    url = f"{BASE_URL}{path}"
    t0 = time.perf_counter()
    try:
        resp = client.request(method, url, **kwargs)
        elapsed = time.perf_counter() - t0
        return elapsed, resp.status_code, None
    except httpx.TimeoutException:
        return None, None, "timeout"
    except httpx.RequestError as e:
        return None, None, f"{type(e).__name__}: {e}"


# ============================================================
# Section 1 -- Cold start
# ============================================================


def measure_cold_start() -> dict | None:
    log("\n=== Section 1/5 : Cold start ===")
    answer = (
        input("Le service est-il idle depuis 15+ min (aucun trafic) ? [y/n] : ")
        .strip()
        .lower()
    )
    if answer != "y":
        log("Skip -- mesure cold start non pertinente sur un service déjà chaud.")
        return {"measured": False}

    log("Requête unique GET /health (timeout 120s)...")
    with httpx.Client(timeout=120.0) as client:
        elapsed, status, error = timed_request(client, "GET", "/health")

    if error:
        log(f"ÉCHEC : {error}")
        return {"measured": False, "error": error}

    log(f"-> {elapsed:.2f}s (status {status})")
    return {
        "measured": True,
        "cold_start_seconds": round(elapsed, 2),
        "status_code": status,
    }


# ============================================================
# Section 2 -- Warm response time (/health)
# ============================================================


def measure_warm_health(n: int = 30, spacing_s: float = 0.5) -> dict:
    log(
        f"\n=== Section 2/5 : Warm response time "
        f"({n}x GET /health, {spacing_s * 1000:.0f}ms apart) ==="
    )
    samples: list[float] = []
    failures = 0
    with httpx.Client(timeout=30.0) as client:
        for i in range(n):
            elapsed, status, error = timed_request(client, "GET", "/health")
            if error or status is None or status >= 300:
                failures += 1
                log(f"  [{i + 1}/{n}] échec ({error or status})")
            else:
                samples.append(elapsed)
                log(f"  [{i + 1}/{n}] {elapsed * 1000:.0f}ms")
            if i < n - 1:
                time.sleep(spacing_s)

    stats = compute_stats(samples)
    stats["failures"] = failures
    log(
        f"-> median={stats.get('median_ms')}ms  "
        f"p95={stats.get('p95_ms')}ms  p99={stats.get('p99_ms')}ms"
    )
    return stats


# ============================================================
# Section 3 -- Login latency
# ============================================================


def measure_login_latency() -> dict:
    log("\n=== Section 3/5 : Login latency (10x POST /auth/login, 300ms apart) ===")
    form_data = {
        "username": DEMO_EMAIL,
        "password": DEMO_PASSWORD,
        "grant_type": "password",
    }

    samples: list[float] = []
    failures = 0

    def attempt(client: httpx.Client, i: int, total: int) -> bool:
        """Exécute une tentative, retourne True si rate-limitée (429)."""
        nonlocal failures
        elapsed, status, error = timed_request(
            client, "POST", "/api/auth/login", data=form_data
        )
        if error:
            failures += 1
            log(f"  [{i}/{total}] échec réseau ({error})")
            return False
        if status == 429:
            log(f"  [{i}/{total}] 429 rate limited")
            return True
        if status != 200:
            failures += 1
            log(f"  [{i}/{total}] échec (status {status})")
            return False
        samples.append(elapsed)
        log(f"  [{i}/{total}] {elapsed * 1000:.0f}ms")
        return False

    rate_limited = False
    with httpx.Client(timeout=30.0) as client:
        n = 10
        for i in range(n):
            if attempt(client, i + 1, n):
                rate_limited = True
                break
            if i < n - 1:
                time.sleep(0.3)

        if rate_limited:
            log(
                "Rate limit atteint -- fallback : 5 essais avec 30s de pause "
                "entre chaque."
            )
            samples = []
            failures = 0
            n = 5
            for i in range(n):
                attempt(client, i + 1, n)
                if i < n - 1:
                    time.sleep(30)

    stats = compute_stats(samples)
    stats["failures"] = failures
    stats["rate_limited"] = rate_limited
    log(f"-> median={stats.get('median_ms')}ms  p95={stats.get('p95_ms')}ms")
    return stats


# ============================================================
# Section 4 -- Static asset delivery (/)
# ============================================================


def measure_static_delivery(n: int = 10) -> dict:
    log(f"\n=== Section 4/5 : Static asset delivery ({n}x GET /) ===")
    samples: list[float] = []
    failures = 0
    with httpx.Client(timeout=15.0) as client:
        for i in range(n):
            elapsed, status, error = timed_request(client, "GET", "/")
            if error or status is None or status >= 300:
                failures += 1
                log(f"  [{i + 1}/{n}] échec ({error or status})")
            else:
                samples.append(elapsed)
                log(f"  [{i + 1}/{n}] {elapsed * 1000:.0f}ms")

    stats = compute_stats(samples)
    stats["failures"] = failures
    log(
        f"-> median={stats.get('median_ms')}ms  "
        f"p95={stats.get('p95_ms')}ms  max={stats.get('max_ms')}ms"
    )
    if stats.get("median_ms", 0) >= 100:
        log("  (!) médiane >= 100ms -- au-dessus de l'objectif <100ms")
    return stats


# ============================================================
# Section 5 -- Availability baseline
# ============================================================


def measure_availability(n: int = 30, spacing_s: float = 2.0) -> dict:
    log(
        f"\n=== Section 5/5 : Availability baseline "
        f"({n}x GET /health, {spacing_s}s apart) ==="
    )
    successes = 0
    failures = 0
    with httpx.Client(timeout=15.0) as client:
        for i in range(n):
            _, status, error = timed_request(client, "GET", "/health")
            ok = error is None and status is not None and 200 <= status < 300
            if ok:
                successes += 1
                log(f"  [{i + 1}/{n}] OK ({status})")
            else:
                failures += 1
                log(f"  [{i + 1}/{n}] échec ({error or status})")
            if i < n - 1:
                time.sleep(spacing_s)

    uptime_pct = round(100 * successes / n, 1) if n else 0.0
    log(f"-> uptime {uptime_pct}% ({successes}/{n})")
    return {
        "count": n,
        "successes": successes,
        "failures": failures,
        "uptime_pct": uptime_pct,
    }


# ============================================================
# Report generation
# ============================================================


def _row(name: str, s: dict, cols: set[str]) -> str:
    def cell(key: str, ms_key: str) -> str:
        return f"{s.get(ms_key)}ms" if key in cols and s.get(ms_key) is not None else "—"

    return (
        f"| {name} | {cell('min', 'min_ms')} | {cell('median', 'median_ms')} | "
        f"{cell('mean', 'mean_ms')} | {cell('p95', 'p95_ms')} | "
        f"{cell('p99', 'p99_ms')} | {cell('max', 'max_ms')} | "
        f"{cell('stdev', 'stdev_ms')} |"
    )


def build_cv_blurb(report: dict) -> list[str]:
    warm = report["warm_health"]
    login = report["login_latency"]
    static = report["static_delivery"]
    avail = report["availability"]
    cold = report["cold_start"]

    blurb = []
    if warm.get("median_ms") is not None:
        blurb.append(
            f"- Temps de réponse médian de {warm['median_ms']}ms "
            f"(p95 : {warm.get('p95_ms')}ms) sur l'endpoint de santé en conditions "
            "chaudes, sur une instance gratuite Render (0.1 vCPU, 512 Mo RAM)."
        )
    if login.get("median_ms") is not None:
        blurb.append(
            f"- Authentification (hash bcrypt + génération JWT) mesurée à "
            f"{login['median_ms']}ms médian sur {login.get('count', 0)} tentatives réelles."
        )
    if static.get("median_ms") is not None:
        blurb.append(
            f"- Livraison des assets statiques (export Next.js via Nginx) en "
            f"{static['median_ms']}ms médian, cohérent avec le choix architectural "
            "d'un export statique plutôt qu'un serveur Node en production "
            "(contrainte RAM du tier gratuit)."
        )
    if cold.get("measured"):
        blurb.append(
            f"- Cold start (reprise après mise en veille, tier gratuit) mesuré à "
            f"{cold['cold_start_seconds']}s, documenté et mitigé côté produit "
            "(kill switch, recommandation de warm-up avant démonstration)."
        )
    blurb.append(
        f"- Disponibilité de {avail['uptime_pct']}% observée sur la fenêtre de test "
        f"({avail['successes']}/{avail['count']} requêtes)."
    )
    return blurb


def build_markdown(report: dict) -> str:
    ts = report["measured_at"]
    cold = report["cold_start"]
    warm = report["warm_health"]
    login = report["login_latency"]
    static = report["static_delivery"]
    avail = report["availability"]

    lines: list[str] = []
    lines.append("# Métriques de performance — démo publique Vector")
    lines.append("")
    lines.append(f"Mesuré le {ts} (Europe/Paris)")
    lines.append("")
    lines.append("## Environnement testé")
    lines.append("")
    lines.append(f"- URL : {BASE_URL}")
    lines.append("- Région : Frankfurt (eu-central)")
    lines.append("- Tier : Render.com Free")
    lines.append("")

    lines.append("## Résumé")
    lines.append("")
    lines.append("| Métrique | Min | Médiane (p50) | Moyenne | p95 | p99 | Max | Écart-type |")
    lines.append("|---|---|---|---|---|---|---|---|")

    if cold.get("measured"):
        lines.append(
            f"| Cold start | — | — | — | — | — | {cold['cold_start_seconds']}s | — |"
        )
    else:
        lines.append("| Cold start | *non mesuré (service non idle 15+ min)* | | | | | | |")

    lines.append(_row("Warm /health (30x)", warm, {"min", "median", "mean", "p95", "p99", "max", "stdev"}))
    lines.append(_row("Login (10x)", login, {"min", "median", "mean", "p95", "max", "stdev"}))
    lines.append(_row("Static / (10x)", static, {"min", "median", "mean", "p95", "max"}))
    lines.append("")

    if login.get("rate_limited"):
        lines.append(
            "> Login : rate limit (429) atteint pendant la mesure — les 10 "
            "premières tentatives, basculé sur 5 essais espacés de 30s.\n"
        )

    lines.append("## Disponibilité (baseline courte)")
    lines.append("")
    lines.append(
        f"{avail['successes']}/{avail['count']} requêtes réussies sur une fenêtre de "
        f"~{avail['count'] * 2}s espacées de 2s → **{avail['uptime_pct']}%** uptime."
    )
    lines.append("")
    lines.append(
        "> Baseline courte terme, à comparer avec une mesure sur une fenêtre plus "
        "longue (heures/jours) si besoin de chiffres de disponibilité plus robustes."
    )
    lines.append("")

    lines.append("## Interprétation pour le CV")
    lines.append("")
    lines.extend(build_cv_blurb(report))
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    log(f"Mesure de performance -- {BASE_URL}")
    log("Ce script peut prendre 2 à 5 minutes (plus si rate limit sur /auth/login).")

    started_at = datetime.now(PARIS_TZ)

    cold = measure_cold_start()
    warm = measure_warm_health()
    login = measure_login_latency()
    static = measure_static_delivery()
    avail = measure_availability()

    report = {
        "measured_at": started_at.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "base_url": BASE_URL,
        "cold_start": cold,
        "warm_health": warm,
        "login_latency": login,
        "static_delivery": static,
        "availability": avail,
    }

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    log(f"\nJSON écrit : {JSON_OUTPUT}")

    md = build_markdown(report)
    MD_OUTPUT.write_text(md, encoding="utf-8")
    log(f"Markdown écrit : {MD_OUTPUT}")

    log("\nTerminé.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("\nInterrompu par l'utilisateur.")
        sys.exit(1)
