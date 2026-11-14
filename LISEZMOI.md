# Kryptopsy

Tableau de bord crypto pensé pour le téléphone (Samsung S26) et utilisable sur ordinateur.
En ligne : https://chanfouricc.github.io/kryptopsy/ (dépôt GitHub `chanfouricc/kryptopsy`)

- **Marchés** : capitalisation, volume, dominance BTC, Fear & Greed, bandeau TradingView et liste de suivi (BTC, ETH, SOL, HYPE, NEAR au départ). Prix en direct via Binance, courbes 7 jours via CoinGecko. « Ajouter » pour suivre n'importe quelle crypto, « Modifier » pour en retirer.
- **Graphique** : graphique TradingView complet et signal technique TradingView de la crypto choisie.
- **Aave** :
  - *Taux* : taux d'emprunt et de dépôt USDT, USDC, ETH et BTC sur toutes les chaînes Aave v3, avec courbe 7 jours, utilisation des pools, pool le moins cher et lien vers chaque actif dans l'appli Aave.
  - *Mes adresses* : suivi d'adresses 0x sur toutes les chaînes Aave v3 : dépôts, emprunts, intérêts nets, health factor (jauge), prix de liquidation de chaque collatéral (et de chaque dette volatile), choc de marché toléré, simulateur de baisse ou de hausse, alerte quand le health factor passe sous 1,25.
  - *À risque* : plus gros emprunteurs proches de la liquidation (HF sous 1,2), séparés entre risque de prix et boucles E-Mode, HF mis à jour en direct.
- **Whales** : les plus gros traders Hyperliquid (plus gros comptes actifs, meilleurs PnL 30 jours et 7 jours), les grosses positions à moins de 10 % de leur liquidation, et tes adresses suivies. Exposition long / short agrégée par crypto, et pour chaque whale : positions perp (taille, entrée, PnL, levier, liquidation, funding), soldes spot, ordres ouverts, derniers trades et courbe de PnL 30 jours, avec liens vers Hyperliquid.
- **Langue** : bouton FR / EN en haut de la page (textes, montants et dates).
- **Actus** : fil des médias (CoinDesk, Cointelegraph, The Block, Decrypt, Blockworks, The Defiant, Bitcoin Magazine, CryptoSlate, Cryptoast, Journal du Coin, Cointribune), filtrable par crypto et par langue, plus le fil TradingView News en direct.

Aucune clé d'API, aucun abonnement. Les adresses suivies restent enregistrées sur l'appareil.

## Contenu du dossier

| Élément | Rôle |
|---|---|
| `site/` | La page publiée (index.html, icônes, manifeste pour l'installer comme une appli). |
| `scripts/fetch_news.py` | Récupère les flux RSS des médias et écrit `site/news.json`. |
| `scripts/fetch_whales.py` | Résume le classement public Hyperliquid (40 Mo) en `site/whales.json`, puis lance `liquidations.py`. |
| `scripts/liquidations.py` | Écrit `site/liquidations.json` : grosses positions Hyperliquid à moins de 10 % de la liquidation (600 plus gros comptes scannés) et plus gros emprunteurs Aave sous un HF de 1,2 (détenteurs des jetons de dette lus sur Blockscout, Ethereum, Base et Arbitrum). |
| `.github/workflows/publier.yml` | Publie `site/` sur GitHub Pages à chaque envoi et toutes les 30 minutes. |

## Mettre à jour la page

1. Sur https://github.com/chanfouricc/kryptopsy/upload/main, glisse les dossiers `site` et `scripts` (et ce fichier), puis **Commit changes**.
2. L'envoi web de GitHub ignore le dossier `.github` : pour modifier la publication, dépose `publier.yml` sur https://github.com/chanfouricc/kryptopsy/upload/main/.github/workflows.

La publication se relance seule à chaque envoi.

## Sur le Samsung

Ouvre le lien dans Chrome, puis menu **⋮ → Ajouter à l'écran d'accueil** (ou **Installer l'application**).

## Bon à savoir

- Les fils des médias et des whales sont régénérés toutes les 30 minutes par GitHub ; positions, taux et prix sont lus en direct par la page.
- GitHub met en pause les tâches planifiées d'un dépôt resté 60 jours sans modification. Si les actus ne bougent plus, relance-les depuis l'onglet **Actions** (**Enable workflow**).
- Pour tester sur ce PC : `python -m http.server 8766 --directory crypto-desk/site`, puis ouvrir http://127.0.0.1:8766/.
- Informations de marché, pas un conseil en investissement.
