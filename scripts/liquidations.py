#!/usr/bin/env python3
"""Plus grosses positions proches de la liquidation, sur Hyperliquid et sur Aave v3.

Aucune des deux plateformes ne publie cette liste : on la calcule.
- Hyperliquid : on lit les positions des plus gros comptes actifs (API publique) et on garde
  les grosses positions dont le prix de liquidation est à moins de 10 % du prix actuel.
- Aave v3 : les plus gros emprunteurs sont les plus gros détenteurs des jetons de dette
  (variableDebt…), lus sur Blockscout ; l'API Aave donne ensuite leur health factor.

Appelé par fetch_whales.py (GitHub Actions, toutes les 30 minutes). Aucune clé d'API.
"""
import concurrent.futures as cf
import json
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
AAVE = "https://api.v3.aave.com/graphql"
HL = "https://api.hyperliquid.xyz/info"
BLOCKSCOUT = {
    1: "https://eth.blockscout.com",
    8453: "https://base.blockscout.com",
    42161: "https://arbitrum.blockscout.com",
}

HL_COMPTES_SCANNES = 600
HL_DISTANCE_MAX = 0.10       # prix de liquidation à moins de 10 % du prix actuel
HL_TAILLE_MIN = 250_000      # position d'au moins 250 k$
AAVE_EMPRUNT_MIN_RESERVE = 20e6
AAVE_HF_MAX = 1.20
AAVE_DETTE_MIN = 1_000_000
N_GARDES = 60


def requete(url, donnees=None, timeout=40, essais=4):
    corps = json.dumps(donnees).encode() if donnees is not None else None
    entetes = {"User-Agent": UA, "Accept": "application/json"}
    if corps is not None:
        entetes["Content-Type"] = "application/json"
    for essai in range(essais):
        try:
            with urlopen(Request(url, data=corps, headers=entetes), timeout=timeout) as r:
                return json.loads(r.read())
        except HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and essai < essais - 1:
                time.sleep(2 ** essai + 1)
                continue
            raise
        except OSError:
            if essai < essais - 1:
                time.sleep(2 ** essai)
                continue
            raise


def gql(q):
    r = requete(AAVE, {"query": q}, timeout=60)
    if r.get("errors") and not r.get("data"):
        raise RuntimeError(r["errors"][0].get("message", "erreur Aave"))
    return r.get("data") or {}


def nombre(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------- Hyperliquid
def hyperliquid(comptes):
    """comptes : comptes actifs triés par valeur décroissante ({addr, value, name})."""
    cibles = comptes[:HL_COMPTES_SCANNES]
    trouvees, erreurs = [], 0

    def scanner(compte):
        etat = requete(HL, {"type": "clearinghouseState", "user": compte["addr"]}, timeout=20)
        resume = etat.get("marginSummary") or {}
        valeur = nombre(resume.get("accountValue"))
        expo = nombre(resume.get("totalNtlPos"))
        sortie = []
        for ap in etat.get("assetPositions") or []:
            p = ap.get("position") or {}
            taille = nombre(p.get("szi"))
            liq = nombre(p.get("liquidationPx"))
            notionnel = abs(nombre(p.get("positionValue")))
            if not taille or liq <= 0 or notionnel < HL_TAILLE_MIN:
                continue
            prix = notionnel / abs(taille)
            distance = (liq - prix) / prix   # négative pour un long, positive pour un short
            if abs(distance) > HL_DISTANCE_MAX:
                continue
            levier = p.get("leverage") or {}
            sortie.append({
                "addr": compte["addr"], "name": compte.get("name"), "coin": p.get("coin"),
                "long": taille > 0, "ntl": round(notionnel), "mark": prix, "liq": liq,
                "dist": round(distance, 5), "entry": nombre(p.get("entryPx")),
                "upnl": round(nombre(p.get("unrealizedPnl"))), "lev": levier.get("value"),
                "levType": levier.get("type"), "av": round(valeur),
                "acctLev": round(expo / valeur, 2) if valeur > 0 else None,
            })
        return sortie

    with cf.ThreadPoolExecutor(max_workers=6) as pool:
        for futur in cf.as_completed([pool.submit(scanner, c) for c in cibles]):
            try:
                trouvees.extend(futur.result())
            except Exception:
                erreurs += 1
    trouvees.sort(key=lambda x: x["ntl"], reverse=True)
    return {"scanned": len(cibles), "errors": erreurs, "items": trouvees[:N_GARDES]}


# ---------------------------------------------------------------- Aave v3
def aave():
    ids = ",".join(str(c) for c in BLOCKSCOUT)
    marches = gql("{ markets(request:{chainIds:[%s]}) { name address chain { chainId name } "
                  "reserves { underlyingToken { symbol decimals } vToken { address } usdExchangeRate "
                  "borrowInfo { total { usd } } } } }" % ids).get("markets") or []

    # 1. Plus gros détenteurs des jetons de dette des grosses réserves
    candidats = {}  # (chainId, adresse du marché) -> {adresse utilisateur: dette estimée en $}
    infos_marche = {}
    jetons = 0
    for m in marches:
        cle = (m["chain"]["chainId"], m["address"])
        infos_marche[cle] = m
        for r in m.get("reserves") or []:
            bi = r.get("borrowInfo")
            if not bi or nombre(bi["total"]["usd"]) < AAVE_EMPRUNT_MIN_RESERVE:
                continue
            jetons += 1
            url = f"{BLOCKSCOUT[m['chain']['chainId']]}/api/v2/tokens/{r['vToken']['address']}/holders"
            decimales = int(r["underlyingToken"]["decimals"])
            prix = nombre(r.get("usdExchangeRate"))
            parametres = None
            for _ in range(2):  # 2 pages de 50 détenteurs
                try:
                    page = requete(url + ("?" + urlencode(parametres) if parametres else ""), timeout=40)
                except Exception:
                    break
                for item in page.get("items") or []:
                    adresse = str(item.get("address", {}).get("hash", "")).lower()
                    if len(adresse) != 42:
                        continue
                    dette = nombre(item.get("value")) / 10 ** decimales * prix
                    groupe = candidats.setdefault(cle, {})
                    groupe[adresse] = groupe.get(adresse, 0) + dette
                parametres = page.get("next_page_params")
                if not parametres:
                    break
                time.sleep(0.4)

    # 2. Health factor de chaque candidat sur ce marché (10 requêtes groupées par appel)
    paires = [(cle, a) for cle, groupe in candidats.items() for a, d in groupe.items() if d >= AAVE_DETTE_MIN]
    etats = {}
    for i in range(0, len(paires), 10):
        lot = paires[i:i + 10]
        q = "{ " + " ".join(
            f'u{j}: userMarketState(request:{{market:"{cle[1]}", user:"{a}", chainId:{cle[0]}}}) '
            "{ healthFactor totalCollateralBase totalDebtBase eModeEnabled }"
            for j, (cle, a) in enumerate(lot)) + " }"
        try:
            d = gql(q)
        except Exception:
            continue
        for j, paire in enumerate(lot):
            if d.get(f"u{j}"):
                etats[paire] = d[f"u{j}"]
        time.sleep(0.15)

    risques = []
    for (cle, a), st in etats.items():
        hf = st.get("healthFactor")
        dette = nombre(st.get("totalDebtBase"))
        if hf is None or dette < AAVE_DETTE_MIN or nombre(hf) >= AAVE_HF_MAX:
            continue
        risques.append({"cle": cle, "addr": a, "hf": nombre(hf), "debt": round(dette),
                        "coll": round(nombre(st.get("totalCollateralBase"))), "emode": bool(st.get("eModeEnabled"))})
    # Les boucles E-Mode (weETH/WETH, USDe/USDC…) ont un HF très bas mais un risque de décrochage
    # entre actifs corrélés ; on garde les plus grosses de chaque type pour ne pas noyer le risque de prix.
    risques.sort(key=lambda x: x["debt"], reverse=True)
    risques = [x for x in risques if not x["emode"]][:40] + [x for x in risques if x["emode"]][:40]

    # 3. Composition (dépôts, emprunts) des positions retenues (5 adresses par appel)
    for i in range(0, len(risques), 5):
        lot = risques[i:i + 5]
        morceaux = []
        for j, x in enumerate(lot):
            marche = f'[{{address:"{x["cle"][1]}", chainId:{x["cle"][0]}}}]'
            morceaux.append(
                f's{j}: userSupplies(request:{{markets:{marche}, user:"{x["addr"]}", collateralsOnly:true, orderBy:{{balance:DESC}}}}) '
                '{ currency { symbol } balance { usd } } '
                f'b{j}: userBorrows(request:{{markets:{marche}, user:"{x["addr"]}", orderBy:{{debt:DESC}}}}) '
                '{ currency { symbol } debt { usd } }')
        try:
            d = gql("{ " + " ".join(morceaux) + " }")
        except Exception:
            d = {}
        for j, x in enumerate(lot):
            x["supplies"] = [[s["currency"]["symbol"], round(nombre(s["balance"]["usd"]))] for s in (d.get(f"s{j}") or [])[:3]]
            x["borrows"] = [[b["currency"]["symbol"], round(nombre(b["debt"]["usd"]))] for b in (d.get(f"b{j}") or [])[:3]]
        time.sleep(0.15)

    elements = []
    for x in risques:
        m = infos_marche[x["cle"]]
        elements.append({
            "addr": x["addr"], "chainId": x["cle"][0], "chain": m["chain"]["name"], "market": m["name"],
            "marketAddr": x["cle"][1], "hf": round(x["hf"], 4), "debt": x["debt"], "coll": x["coll"],
            "emode": x["emode"], "supplies": x.get("supplies", []), "borrows": x.get("borrows", []),
        })
    return {"chains": sorted({m["chain"]["name"] for m in marches}), "debtTokens": jetons,
            "checked": len(etats), "items": elements}


def construire(comptes_actifs, chemin):
    from datetime import datetime, timezone
    resultat = {"generated": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")}
    for nom, fonction in (("hyperliquid", lambda: hyperliquid(comptes_actifs)), ("aave", aave)):
        debut = time.time()
        try:
            resultat[nom] = fonction()
            print(f"  {nom} : {len(resultat[nom]['items'])} positions proches de la liquidation ({time.time() - debut:.0f} s)")
        except Exception as erreur:
            resultat[nom] = {"error": str(erreur)[:200], "items": []}
            print(f"  {nom} : indisponible ({erreur})")
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, separators=(",", ":"))
