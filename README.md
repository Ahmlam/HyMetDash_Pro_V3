# 🌊 HyMetDash v3.0 — Dashboard Hydrométéorologique & Énergétique Professionnel

**SODEXAM / Direction de la Météorologie Nationale / Bureau Hydrométéorologie & Service Énergétique**

Dashboard professionnel de suivi hydrométéorologique et énergétique pour gestionnaires de barrages hydroélectriques et énergéticiens.

---

## ✨ Fonctionnalités

### 🔐 Authentification Multi-rôles
- **Administrateur** : accès complet (configuration, upload, gestion données, mots de passe)
- **Client (Consultation)** : accès lecture seule aux tableaux de bord et graphiques
- Mots de passe configurables depuis le panneau admin

### 🗺️ Carte de Vigilance
- Carte interactive OSM avec stations météorologiques
- Système d'alerte 4 niveaux (vert/jaune/orange/rouge)
- Calcul automatique pluie cumulée 2 jours + débit estimé

### 📊 Visualisation Stations
- Graphiques interactifs (courbe, histogramme, box-plot, nuage de points)
- Filtrage par station, paramètre, période
- Export PNG/JPG/PDF/CSV

### 💧 Débit & Hydraulique
- Conversion Pluie → Débit (méthode rationnelle)
- Calcul Manning/Strickler
- Agrégation temporelle configurable

### 🔮 Prévisions
- Module de prévisions (mode démonstration, intégration GFS prévue)
- Heatmaps et courbes temporelles

### ⚡ Module Énergie (NOUVEAU)
- **Hydroélectricité** : calcul puissance/énergie (P = ρgQHη)
- **Solaire PV** : production estimée selon surface, rendement, irradiance
- **Bilan énergétique** : taux de couverture ENR, analyse économique en FCFA
- Corrélation Pluie → Débit → Production

### 📡 Synchronisation OGIMET
- Récupération automatique des SYNOP (Côte d'Ivoire)
- Décodage robuste des messages AAXX
- Script cron pour mise à jour toutes les 6 heures
- Fallback quand les données locales sont absentes

### 📂 Multi-sources de données
- Dossier local (xlsx, csv)
- Upload via interface admin
- OGIMET automatique
- Sources distantes configurables

---

## 🚀 Déploiement sur Streamlit Cloud (depuis GitHub)

### Étape 1 : Préparer le dépôt GitHub

```bash
# Cloner ou créer votre repo
git init hymetdash
cd hymetdash

# Copier tous les fichiers du projet
# (app.py, ogimet_sync.py, requirements.txt, packages.txt, .streamlit/, data/, etc.)

# Ajouter vos données dans data/observed/
# Ajouter le logo dans assets/logo_SODEXAM.png
# Ajouter le fichier stations dans data/stations.xlsx

git add .
git commit -m "HyMetDash v3.0 - Initial deployment"
git remote add origin https://github.com/VOTRE_USER/hymetdash.git
git push -u origin main
```

### Étape 2 : Déployer sur Streamlit Cloud

1. Allez sur [share.streamlit.io](https://share.streamlit.io)
2. Connectez-vous avec votre compte GitHub
3. Cliquez "New app"
4. Sélectionnez :
   - **Repository** : `VOTRE_USER/hymetdash`
   - **Branch** : `main`
   - **Main file path** : `app.py`
5. Cliquez "Deploy"

### Étape 3 : Configurer les mots de passe

Après le premier déploiement :
1. Connectez-vous avec le mot de passe admin par défaut : `admin2025`
2. Allez dans 🔧 Administration → 🔑 Mots de passe
3. Changez les mots de passe admin et client

### Étape 4 : Configurer la synchronisation OGIMET (optionnel)

Sur un serveur (VPS, Raspberry Pi, etc.) :

```bash
# Installer les dépendances
pip install requests pandas openpyxl

# Configurer le cron (toutes les 6 heures)
crontab -e
# Ajouter :
0 */6 * * * cd /chemin/vers/hymetdash && python ogimet_sync.py >> /var/log/ogimet_sync.log 2>&1

# Variables d'environnement optionnelles :
export OGIMET_COUNTRY="Cote"
export OGIMET_WINDOW_HOURS=6
export OGIMET_WIDEN_HOURS=12
```

---

## 📁 Structure du Projet

```
hymetdash/
├── app.py                    # Application principale
├── ogimet_sync.py            # Script de synchronisation OGIMET
├── requirements.txt          # Dépendances Python
├── packages.txt              # Dépendances système (Streamlit Cloud)
├── .gitignore
├── .streamlit/
│   └── config.toml           # Configuration Streamlit
├── config/
│   └── settings.json         # Configuration app (auto-généré)
├── data/
│   ├── observed/             # ← Placez vos fichiers xlsx/csv ici
│   ├── ogimet_sync/          # Données OGIMET automatiques
│   ├── uploads/              # Fichiers uploadés via l'admin
│   ├── energy/               # Données énergétiques
│   └── stations.xlsx         # Fichier des stations (optionnel)
└── assets/
    └── logo_SODEXAM.png      # Logo (optionnel)
```

---

## 📊 Format des Données Attendues

### Fichiers Excel (data/observed/)
Chaque fichier `.xlsx` = un paramètre météo. Nom du fichier = nom du paramètre.
Chaque onglet = une station.

Colonnes attendues :
- `Date` ou `Annee` + `mois` + `jour`
- Colonne de valeurs (numérique)

### Fichiers CSV
- Colonnes : `date`, `station`, `parametre`, `valeur` (ou noms de paramètres)

### Données OGIMET (auto-générées)
- `datetime_utc`, `temp_c`, `rain_mm`, `wind_speed_ms`, `rh_pct`, etc.

---

## 🔐 Mots de passe par défaut

| Rôle | Mot de passe |
|------|-------------|
| Admin | `admin2025` |
| Client | `hymetdash` |

⚠️ **Changez-les immédiatement après le premier déploiement !**

---

## 🛠️ Développement Local

```bash
# Installer les dépendances
pip install -r requirements.txt

# Lancer l'application
streamlit run app.py

# L'app sera accessible sur http://localhost:8501
```

---

## 📝 Licence

© 2025-2026 SODEXAM / Direction de la Météorologie Nationale — Côte d'Ivoire
Tous droits réservés.
