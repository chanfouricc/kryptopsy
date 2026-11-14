# Crypto Desk

Tableau de bord crypto pensé pour le téléphone (Samsung S26) et utilisable sur ordinateur.

- **Marchés** : capitalisation, volume, dominance BTC, Fear & Greed, bandeau TradingView et liste de suivi (BTC, ETH, SOL, HYPE, NEAR au départ). Prix en direct via Binance, courbes 7 jours via CoinGecko. Bouton « Ajouter » pour suivre n'importe quelle crypto, « Modifier » pour en retirer.
- **Graphique** : graphique TradingView complet et signal technique TradingView de la crypto choisie.
- **Aave** : taux variables d'emprunt USDT, USDC, ETH et BTC sur toutes les chaînes Aave v3, avec courbe 7 jours, utilisation des pools et pool le moins cher.
- **Actus** : fil des médias (CoinDesk, Cointelegraph, The Block, Decrypt, Blockworks, The Defiant, Bitcoin Magazine, CryptoSlate, Cryptoast, Journal du Coin, Cointribune), filtrable par crypto et par langue, plus le fil TradingView News en direct.

Aucune clé d'API, aucun abonnement.

## Contenu du dossier

| Élément | Rôle |
|---|---|
| `site/` | La page publiée (index.html, icônes, manifeste pour l'installer comme une appli). |
| `scripts/fetch_news.py` | Récupère les flux RSS des médias et écrit `site/news.json`. |
| `.github/workflows/publier.yml` | Publie `site/` sur GitHub Pages à chaque envoi et toutes les 30 minutes (pour rafraîchir les actus). |

## Mise en ligne sur GitHub Pages (une seule fois)

1. Connecte-toi sur https://github.com (compte gratuit).
2. Crée un dépôt : https://github.com/new, nom `crypto-desk`, visibilité **Public**, puis **Create repository**.
3. Sur la page du dépôt vide, clique **uploading an existing file**, puis glisse **le contenu** du dossier `crypto-desk` (les dossiers `site`, `scripts`, `.github` et ce fichier). Clique **Commit changes**.
4. Va dans **Settings → Pages**. Dans **Build and deployment → Source**, choisis **GitHub Actions**.
5. Va dans l'onglet **Actions**, ouvre **Publier Crypto Desk**, puis **Run workflow**. Au bout d'une minute environ, le lien du site apparaît dans le résultat : `https://<ton-pseudo>.github.io/crypto-desk/`.

## Sur le Samsung

Ouvre le lien dans Chrome, puis menu **⋮ → Ajouter à l'écran d'accueil** (ou **Installer l'application**). Crypto Desk s'ouvre ensuite en plein écran comme une appli. Ta liste de suivi est gardée sur le téléphone.

## Mettre à jour la page

Remplace le fichier dans GitHub (bouton **Add file → Upload files** dans le dossier `site`) : la publication se relance seule.

## Bon à savoir

- Le fil des médias est régénéré toutes les 30 minutes par GitHub ; l'onglet TradingView des actus est en direct.
- GitHub met en pause les tâches planifiées d'un dépôt resté 60 jours sans modification. Si les actus ne bougent plus, relance-les depuis l'onglet **Actions** (**Enable workflow**).
- Pour tester sur ce PC : `python -m http.server 8766 --directory crypto-desk/site`, puis ouvrir http://127.0.0.1:8766/.
- Informations de marché, pas un conseil en investissement.
