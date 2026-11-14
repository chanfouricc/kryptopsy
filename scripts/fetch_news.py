#!/usr/bin/env python3
"""Construit news.json pour Kryptopsy en agrégeant les flux RSS de médias crypto.

Les navigateurs ne peuvent pas lire ces flux directement (pas d'en-têtes CORS) :
GitHub Actions lance ce script toutes les 30 minutes et publie le résultat à côté
de la page (voir .github/workflows/publier.yml).

À la main :  python scripts/fetch_news.py site/news.json
Bibliothèque standard uniquement, aucune clé d'API.
"""
import concurrent.futures as cf
import email.utils
import html
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

# (nom affiché, langue, adresse du flux)
FLUX = [
    ("CoinDesk", "en", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
    ("Cointelegraph", "en", "https://cointelegraph.com/rss"),
    ("The Block", "en", "https://www.theblock.co/rss.xml"),
    ("Decrypt", "en", "https://decrypt.co/feed"),
    ("Blockworks", "en", "https://blockworks.co/feed"),
    ("The Defiant", "en", "https://thedefiant.io/api/feed"),
    ("Bitcoin Magazine", "en", "https://bitcoinmagazine.com/.rss/full/"),
    ("CryptoSlate", "en", "https://cryptoslate.com/feed/"),
    ("Cryptoast", "fr", "https://cryptoast.fr/feed/"),
    ("Journal du Coin", "fr", "https://journalducoin.com/feed/"),
    ("Cointribune", "fr", "https://www.cointribune.com/feed/"),
]

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
NS = {
    "media": "http://search.yahoo.com/mrss/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
}
MAX_PAR_SOURCE = 25
MAX_TOTAL = 180
AGE_MAX = timedelta(days=5)

IMG_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.I)
TAG_RE = re.compile(r"<[^>]+>")
ESPACES_RE = re.compile(r"\s+")
ENTITE_ORPHELINE_RE = re.compile(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);)")
EXT_IMAGE_RE = re.compile(r"\.(jpe?g|png|webp|gif|avif)(\?|$)", re.I)


def telecharger(url):
    requete = Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
    })
    with urlopen(requete, timeout=20) as reponse:
        return reponse.read()


def texte(element):
    if element is None:
        return ""
    return "".join(element.itertext()).strip()


def nettoyer(fragment, limite=260):
    t = html.unescape(TAG_RE.sub(" ", fragment or ""))
    t = ESPACES_RE.sub(" ", t).strip()
    if len(t) > limite:
        t = t[:limite].rsplit(" ", 1)[0].rstrip(",;:.") + "…"
    return t


def url_web(u):
    u = (u or "").strip()
    if u.startswith("//"):
        u = "https:" + u
    return u if u.startswith(("https://", "http://")) else ""


def date_iso(valeur):
    valeur = (valeur or "").strip()
    if not valeur:
        return None
    try:
        d = email.utils.parsedate_to_datetime(valeur)
    except (TypeError, ValueError, IndexError):
        d = None
    if d is None:
        try:
            d = datetime.fromisoformat(valeur.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def image_de(item, fragments):
    for balise in ("media:content", "media:thumbnail", "media:group/media:content"):
        for el in item.findall(balise, NS):
            url = url_web(el.get("url"))
            genre = (el.get("medium") or el.get("type") or "").lower()
            if url and ("image" in genre or "thumbnail" in balise or EXT_IMAGE_RE.search(url)):
                return url
    enclos = item.find("enclosure")
    if enclos is not None and (enclos.get("type") or "").startswith("image"):
        url = url_web(enclos.get("url"))
        if url:
            return url
    for fragment in fragments:
        m = IMG_RE.search(fragment or "")
        if m:
            return url_web(html.unescape(m.group(1)))
    return ""


def analyser(contenu):
    contenu = contenu.lstrip(b"\xef\xbb\xbf \t\r\n")
    try:
        racine = ET.fromstring(contenu)
    except ET.ParseError:
        repare = ENTITE_ORPHELINE_RE.sub("&amp;", contenu.decode("utf-8", "replace"))
        racine = ET.fromstring(repare.encode("utf-8"))

    articles = []
    items = racine.findall("./channel/item") or racine.findall(".//item")
    for it in items[:MAX_PAR_SOURCE]:
        desc = texte(it.find("description"))
        corps = texte(it.find("content:encoded", NS))
        # Certains flux mettent du HTML échappé dans <description> : on garde le brut pour l'image.
        desc_brut = it.findtext("description") or ""
        lien = url_web(it.findtext("link")) or url_web(it.findtext("guid"))
        articles.append({
            "t": nettoyer(texte(it.find("title")), 300),
            "u": lien,
            "d": date_iso(it.findtext("pubDate") or it.findtext("dc:date", namespaces=NS)),
            "i": image_de(it, [desc_brut, corps]),
            "x": nettoyer(desc or corps),
        })
    if items:
        return articles

    for en in racine.findall("atom:entry", NS)[:MAX_PAR_SOURCE]:
        lien = ""
        for l in en.findall("atom:link", NS):
            if l.get("rel", "alternate") == "alternate":
                lien = url_web(l.get("href"))
                break
        resume = en.findtext("atom:summary", default="", namespaces=NS)
        contenu_html = en.findtext("atom:content", default="", namespaces=NS)
        articles.append({
            "t": nettoyer(texte(en.find("atom:title", NS)), 300),
            "u": lien,
            "d": date_iso(en.findtext("atom:published", namespaces=NS) or en.findtext("atom:updated", namespaces=NS)),
            "i": image_de(en, [resume, contenu_html]),
            "x": nettoyer(resume or contenu_html),
        })
    return articles


def recuperer(nom, langue, url):
    articles = analyser(telecharger(url))
    for a in articles:
        a["s"] = nom
        a["l"] = langue
    return [a for a in articles if a["t"] and a["u"]]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sortie = sys.argv[1] if len(sys.argv) > 1 else "news.json"
    maintenant = datetime.now(timezone.utc)
    tous, sources = [], []

    with cf.ThreadPoolExecutor(max_workers=8) as pool:
        futurs = {pool.submit(recuperer, nom, langue, url): (nom, langue) for nom, langue, url in FLUX}
        for futur in cf.as_completed(futurs):
            nom, langue = futurs[futur]
            try:
                articles = futur.result()
                tous.extend(articles)
                sources.append({"name": nom, "lang": langue, "ok": True, "count": len(articles)})
            except Exception as erreur:  # un média en panne ne doit pas bloquer les autres
                sources.append({"name": nom, "lang": langue, "ok": False, "error": str(erreur)[:160]})

    vus_liens, vus_titres, gardes = set(), set(), []
    for a in tous:
        cle_titre = re.sub(r"\W+", "", a["t"].lower())[:90]
        if a["u"] in vus_liens or cle_titre in vus_titres:
            continue
        if a["d"] is not None and maintenant - a["d"] > AGE_MAX:
            continue
        vus_liens.add(a["u"])
        vus_titres.add(cle_titre)
        gardes.append(a)

    plancher = datetime(1970, 1, 1, tzinfo=timezone.utc)
    gardes.sort(key=lambda a: a["d"] or plancher, reverse=True)
    gardes = gardes[:MAX_TOTAL]
    for a in gardes:
        a["d"] = a["d"].isoformat().replace("+00:00", "Z") if a["d"] else None

    sources.sort(key=lambda s: s["name"])
    resultat = {
        "generated": maintenant.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "sources": sources,
        "items": gardes,
    }
    with open(sortie, "w", encoding="utf-8") as f:
        json.dump(resultat, f, ensure_ascii=False, separators=(",", ":"))

    ok = sum(1 for s in sources if s["ok"])
    print(f"{len(gardes)} articles, {ok}/{len(sources)} médias lus -> {sortie}")
    for s in sources:
        etat = f"{s['count']} articles" if s["ok"] else f"ÉCHEC : {s['error']}"
        print(f"  - {s['name']} ({s['lang']}) : {etat}")


if __name__ == "__main__":
    main()
