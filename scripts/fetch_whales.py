#!/usr/bin/env python3
"""Construit whales.json pour Kryptopsy : les plus gros comptes Hyperliquid et les meilleurs PnL.

Le classement public de Hyperliquid pèse près de 40 Mo, trop pour un téléphone :
GitHub Actions le télécharge toutes les 30 minutes et n'en garde que les comptes utiles.
La page charge ensuite en direct les positions de chaque whale (API publique Hyperliquid).

À la main :  python scripts/fetch_whales.py site/whales.json
Bibliothèque standard uniquement, aucune clé d'API.
"""
import gzip
import json
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen

URL = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
NOMS_CONNUS = {
    "0xdfc24b077bc1425ad1dea75bcb6f8158e10df303": "HLP (coffre Hyperliquid)",
}
N_VALEUR = 40
N_PNL = 30
VALEUR_MIN_PNL = 100_000  # les classements PnL ignorent les comptes de moins de 100 k$
# Les plus gros soldes du classement sont des comptes de ponts (USOL, UAVAX…) ou des comptes
# dormants : on ne garde que les comptes qui ont réellement tradé sur 30 jours.
VOLUME_MIN_30J = 1_000_000


def telecharger():
    requete = Request(URL, headers={"User-Agent": UA, "Accept-Encoding": "gzip"})
    with urlopen(requete, timeout=180) as reponse:
        brut = reponse.read()
        if reponse.headers.get("Content-Encoding", "").lower() == "gzip":
            brut = gzip.decompress(brut)
    return json.loads(brut)["leaderboardRows"]


def nombre(valeur):
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return 0.0


def performances(ligne):
    resultat = {}
    for fenetre, perf in ligne.get("windowPerformances") or []:
        resultat[fenetre] = {
            "pnl": round(nombre(perf.get("pnl")), 2),
            "roi": round(nombre(perf.get("roi")), 5),
            "vlm": round(nombre(perf.get("vlm")), 0),
        }
    return resultat


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sortie = sys.argv[1] if len(sys.argv) > 1 else "whales.json"
    genere = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    try:
        lignes = telecharger()
    except Exception as erreur:  # le site reste publié, la page affichera le message
        with open(sortie, "w", encoding="utf-8") as f:
            json.dump({"generated": genere, "error": str(erreur)[:200]}, f, ensure_ascii=False)
        print("Classement Hyperliquid indisponible :", erreur)
        return

    comptes = []
    for ligne in lignes:
        adresse = str(ligne.get("ethAddress") or "").lower()
        if not adresse.startswith("0x") or len(adresse) != 42:
            continue
        comptes.append({
            "addr": adresse,
            "value": round(nombre(ligne.get("accountValue")), 2),
            "name": NOMS_CONNUS.get(adresse) or ligne.get("displayName") or None,
            "perf": performances(ligne),
        })

    def pnl(compte, fenetre):
        return compte["perf"].get(fenetre, {}).get("pnl", 0.0)

    actifs = [c for c in comptes if c["perf"].get("month", {}).get("vlm", 0) >= VOLUME_MIN_30J]
    par_valeur = sorted(actifs, key=lambda c: c["value"], reverse=True)[:N_VALEUR]
    eligibles = [c for c in actifs if c["value"] >= VALEUR_MIN_PNL]
    par_mois = sorted(eligibles, key=lambda c: pnl(c, "month"), reverse=True)[:N_PNL]
    par_semaine = sorted(eligibles, key=lambda c: pnl(c, "week"), reverse=True)[:N_PNL]

    whales = {}
    for compte in par_valeur + par_mois + par_semaine:
        whales[compte["addr"]] = {k: v for k, v in compte.items() if k != "addr"}

    resultat = {
        "generated": genere,
        "accounts": len(comptes),
        "active": len(actifs),
        "rankings": {
            "value": [c["addr"] for c in par_valeur],
            "month": [c["addr"] for c in par_mois],
            "week": [c["addr"] for c in par_semaine],
        },
        "whales": whales,
    }
    with open(sortie, "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(comptes)} comptes lus, {len(actifs)} actifs sur 30 jours, {len(whales)} whales gardées -> {sortie}")
    for c in par_valeur[:5]:
        print(f"  {c['addr']}  {c['value']:>16,.0f} $  {c['name'] or ''}")


if __name__ == "__main__":
    main()
