# ==========================================================
# HyMetDash v3.0 — Professional Hydrometeorological Dashboard
# SODEXAM / DMN / Bureau Hydrométéorologie & Service Énergétique
# Multi-mode: Admin (full) / Client (consultation)
# Auto-sync: File watcher + OGIMET fallback
# ==========================================================

import os
import sys
import json
import hashlib
import time
import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from pathlib import Path

# ── Config paths ──
BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config" / "settings.json"
DATA_DIR = BASE_DIR / "data"
OGIMET_DIR = DATA_DIR / "ogimet_sync"
OBSERVED_DIR = DATA_DIR / "observed"
UPLOAD_DIR = DATA_DIR / "uploads"
ENERGY_DIR = DATA_DIR / "energy"
ASSETS_DIR = BASE_DIR / "assets"

for d in [DATA_DIR, OGIMET_DIR, OBSERVED_DIR, UPLOAD_DIR, ENERGY_DIR,
          ASSETS_DIR, CONFIG_FILE.parent]:
    d.mkdir(parents=True, exist_ok=True)

# ── Default configuration ──
DEFAULT_CONFIG = {
    "admin_password_hash": hashlib.sha256("admin2025".encode()).hexdigest(),
    "client_password_hash": hashlib.sha256("hymetdash".encode()).hexdigest(),
    "app_title": "HyMetDash",
    "org_name": "SODEXAM / DMN / Bureau Hydrométéorologie",
    "data_sources": [
        {"name": "Local Files", "type": "local", "path": str(OBSERVED_DIR)},
    ],
    "ogimet_config": {
        "enabled": True,
        "country": "Cote",
        "window_hours": 6,
        "widen_hours": 12,
        "interval_minutes": 360,
    },
    "station_file": str(DATA_DIR / "stations.xlsx"),
    "mapbox_token": "",
    "auto_refresh_seconds": 300,
}


def load_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        # Merge defaults for missing keys
        for k, v in DEFAULT_CONFIG.items():
            if k not in cfg:
                cfg[k] = v
        return cfg
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2, default=str)


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


# ── Page Config ──
st.set_page_config(
    page_title="HyMetDash — Dashboard Hydrométéorologique Professionnel",
    layout="wide",
    page_icon="🌊",
    initial_sidebar_state="expanded"
)

config = load_config()

# ══════════════════════════════════════════════════════════
# AUTHENTICATION SYSTEM
# ══════════════════════════════════════════════════════════
def authenticate():
    """Multi-role authentication: Admin or Client."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.role = None

    if st.session_state.authenticated:
        return True

    # Login page with professional styling
    st.markdown("""
    <style>
        .login-container {
            max-width: 480px;
            margin: 60px auto;
            padding: 40px;
            background: linear-gradient(145deg, #ffffff 0%, #f8fffe 100%);
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(6,85,53,0.12), 0 1px 3px rgba(0,0,0,0.08);
            border: 1px solid rgba(6,85,53,0.08);
        }
        .login-logo {
            text-align: center;
            margin-bottom: 30px;
        }
        .login-logo h1 {
            font-family: 'Montserrat', sans-serif;
            font-size: 2rem;
            background: linear-gradient(135deg, #065535, #0a8a55);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin: 0;
        }
        .login-logo p {
            color: #6b7c75;
            font-size: 0.9rem;
            margin-top: 8px;
        }
        .role-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            margin: 2px;
        }
        .role-admin { background: #fff3e0; color: #e65100; }
        .role-client { background: #e8f5e9; color: #2e7d32; }
    </style>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div class="login-logo">
            <h1>🌊 HyMetDash</h1>
            <p>Dashboard Hydrométéorologique & Énergétique Professionnel</p>
            <div style="margin-top:12px;">
                <span class="role-badge role-admin">🔐 Admin</span>
                <span class="role-badge role-client">👁️ Consultation</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        role = st.radio("Mode d'accès", ["👁️ Client (Consultation)", "🔐 Administrateur"],
                        horizontal=True, label_visibility="collapsed")
        password = st.text_input("Mot de passe", type="password",
                                 placeholder="Entrez votre mot de passe...")

        if st.button("Se connecter", use_container_width=True, type="primary"):
            cfg = load_config()
            if "Admin" in role:
                if hash_password(password) == cfg["admin_password_hash"]:
                    st.session_state.authenticated = True
                    st.session_state.role = "admin"
                    st.rerun()
                else:
                    st.error("Mot de passe administrateur incorrect.")
            else:
                if hash_password(password) == cfg["client_password_hash"]:
                    st.session_state.authenticated = True
                    st.session_state.role = "client"
                    st.rerun()
                else:
                    st.error("Mot de passe client incorrect.")

        st.markdown("""
        <div style="text-align:center; margin-top:20px; color:#9e9e9e; font-size:0.75rem;">
            HyMetDash v3.0 — SODEXAM/DMN<br>
            Mot de passe par défaut — Admin: <code>admin2025</code> | Client: <code>hymetdash</code>
        </div>
        """, unsafe_allow_html=True)

    return False


if not authenticate():
    st.stop()

IS_ADMIN = st.session_state.role == "admin"

# ══════════════════════════════════════════════════════════
# PROFESSIONAL CSS
# ══════════════════════════════════════════════════════════
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }
    .stApp {
        background: #f6f8fa;
    }

    /* Header bar */
    .hymet-header {
        background: linear-gradient(135deg, #04322a 0%, #065535 40%, #0a7a4a 100%);
        padding: 16px 28px;
        border-radius: 14px;
        margin-bottom: 20px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 8px 32px rgba(4,50,42,0.2);
    }
    .hymet-header-left h1 {
        color: #fff !important;
        font-family: 'DM Sans', sans-serif !important;
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        margin: 0 !important;
        letter-spacing: 0.5px;
    }
    .hymet-header-left p {
        color: rgba(168,230,207,0.9) !important;
        font-size: 0.8rem;
        margin: 2px 0 0;
    }
    .hymet-header-right {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .role-indicator {
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    .role-admin-ind { background: rgba(255,152,0,0.2); color: #ffb74d; }
    .role-client-ind { background: rgba(76,175,80,0.2); color: #81c784; }
    .live-dot {
        width: 8px; height: 8px;
        border-radius: 50%;
        background: #4caf50;
        display: inline-block;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #021f18 0%, #04322a 50%, #065535 100%) !important;
    }
    section[data-testid="stSidebar"] * {
        color: #c8e6d4 !important;
    }
    section[data-testid="stSidebar"] .stRadio label {
        background: rgba(255,255,255,0.05);
        border-radius: 10px;
        padding: 8px 12px;
        margin: 3px 0;
        transition: all 0.2s ease;
        border: 1px solid transparent;
    }
    section[data-testid="stSidebar"] .stRadio label:hover {
        background: rgba(255,255,255,0.12);
        border-color: rgba(168,230,207,0.3);
    }

    /* Metric cards */
    div[data-testid="metric-container"] {
        background: #fff;
        border-radius: 12px;
        padding: 16px;
        border-left: 4px solid #065535;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(0,0,0,0.1);
    }

    /* Section titles */
    h2, h3 {
        font-family: 'DM Sans', sans-serif !important;
        color: #04322a !important;
        font-weight: 700 !important;
    }

    /* Download buttons */
    .stDownloadButton button {
        background: linear-gradient(135deg, #065535, #0a8a55) !important;
        color: #fff !important;
        border: none !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        transition: all 0.2s !important;
    }
    .stDownloadButton button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 16px rgba(6,85,53,0.3) !important;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px 10px 0 0;
        padding: 8px 20px;
        font-weight: 600;
    }

    /* Info boxes */
    .info-card {
        background: #fff;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.06);
        border: 1px solid #e8f0ec;
        margin: 8px 0;
    }
    .data-status {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 14px;
        background: rgba(76,175,80,0.08);
        border-radius: 8px;
        font-size: 0.85rem;
        color: #2e7d32;
        margin: 4px 0;
    }

    hr { border: none; border-top: 2px solid #e0ece6; margin: 24px 0; }
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════
role_class = "role-admin-ind" if IS_ADMIN else "role-client-ind"
role_label = "Administrateur" if IS_ADMIN else "Client"
role_icon = "🔐" if IS_ADMIN else "👁️"

st.markdown(f"""
<div class="hymet-header">
    <div class="hymet-header-left">
        <h1>🌊 HyMetDash — Dashboard Hydrométéorologique & Énergétique</h1>
        <p>{config.get('org_name', 'SODEXAM / DMN')} — Gestion Ressources en Eau & Énergie Renouvelable</p>
    </div>
    <div class="hymet-header-right">
        <span class="live-dot"></span>
        <span class="role-indicator {role_class}">{role_icon} {role_label}</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ══════════════════════════════════════════════════════════
import io
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio


def export_plot(fig, fname_prefix):
    cols = st.columns(3)
    for i, (fmt, mime) in enumerate([
        ("png", "image/png"), ("jpg", "image/jpeg"), ("pdf", "application/pdf")
    ]):
        try:
            buf = io.BytesIO()
            pio.write_image(fig, buf, format=fmt, scale=2)
            with cols[i]:
                st.download_button(
                    f"📥 {fmt.upper()}", buf.getvalue(),
                    file_name=f"{fname_prefix}.{fmt}", mime=mime,
                    key=f"dl_{fname_prefix}_{fmt}_{id(fig)}_{time.time_ns()}"
                )
            buf.close()
        except Exception:
            with cols[i]:
                st.caption(f"Export {fmt.upper()} indisponible")


def _norm_cols(df):
    return df.rename(columns={c: c.strip().lower() for c in df.columns})


def _infer_value_column(df):
    for c in df.columns:
        if c.lower() in ("parametre", "paramètre", "param", "valeur", "value"):
            return c
    ignore = {"date", "année", "annee", "mois", "jour", "year", "month", "day",
              "station", "param"}
    nums = [c for c in df.columns if c.lower() not in ignore
            and pd.api.types.is_numeric_dtype(df[c])]
    return nums[0] if nums else None


def debit_pluie_debit(pluie_mm, C_runoff, area_km2):
    if pluie_mm is None:
        return np.nan
    return (C_runoff * pluie_mm * area_km2) / 86.4


def derive_parameters(df):
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    if "tmin" in df.columns and "tmax" in df.columns:
        tmean = (df["tmin"] + df["tmax"]) / 2.0
        dtr = (df["tmax"] - df["tmin"]).clip(lower=0)
        df["etp"] = 0.0023 * (tmean + 17.8) * np.sqrt(dtr) * 0.408
    else:
        df["etp"] = np.nan

    if "insolation" in df.columns:
        df["rayonnement_global"] = 0.8 * df["insolation"]
        df["rayonnement_direct"] = 0.7 * df["rayonnement_global"]
        df["rayonnement_diffus"] = 0.3 * df["rayonnement_global"]
    else:
        df["rayonnement_global"] = np.nan
        df["rayonnement_direct"] = np.nan
        df["rayonnement_diffus"] = np.nan

    if "pluie" in df.columns:
        df["bilan_hydrique"] = df["pluie"].fillna(0) - df["etp"].fillna(0)
    else:
        df["bilan_hydrique"] = np.nan
    return df


# ══════════════════════════════════════════════════════════
# DATA LOADING — Multi-source with auto-refresh
# ══════════════════════════════════════════════════════════
def _get_data_fingerprint():
    """Fingerprint based on file modification times for cache busting."""
    fps = []
    for src_dir in [OBSERVED_DIR, OGIMET_DIR, UPLOAD_DIR]:
        if src_dir.exists():
            for f in sorted(src_dir.rglob("*.xlsx")):
                fps.append(f"{f}:{f.stat().st_mtime}")
            for f in sorted(src_dir.rglob("*.csv")):
                fps.append(f"{f}:{f.stat().st_mtime}")
    return hashlib.md5("|".join(fps).encode()).hexdigest()


@st.cache_data(show_spinner="Chargement des données météorologiques...")
def load_all_observed(_fingerprint: str):
    """Load data from all configured sources with auto-detection."""
    by_station = {}
    all_dirs = [OBSERVED_DIR, OGIMET_DIR, UPLOAD_DIR]

    # Also check config for additional paths
    cfg = load_config()
    for src in cfg.get("data_sources", []):
        if src.get("type") == "local":
            p = Path(src["path"])
            if p.exists() and p not in all_dirs:
                all_dirs.append(p)

    for data_dir in all_dirs:
        if not data_dir.exists():
            continue

        # Load XLSX files
        for fn in data_dir.rglob("*.xlsx"):
            if fn.name.startswith("~$"):
                continue
            param_name = fn.stem.strip().lower()
            try:
                xls = pd.ExcelFile(fn)
            except Exception:
                continue
            for sheet in xls.sheet_names:
                try:
                    df = pd.read_excel(xls, sheet_name=sheet)
                    if df is None or df.empty:
                        continue
                    df = _norm_cols(df)
                    if "date" in df.columns:
                        d = pd.to_datetime(df["date"], errors="coerce")
                    elif "datetime_utc" in df.columns:
                        d = pd.to_datetime(df["datetime_utc"], errors="coerce")
                    else:
                        y = pd.to_numeric(
                            df.get("annee", df.get("année", df.get("year"))),
                            errors="coerce"
                        )
                        m = pd.to_numeric(df.get("mois", df.get("month")), errors="coerce")
                        dd = pd.to_numeric(df.get("jour", df.get("day")), errors="coerce")
                        d = pd.to_datetime(dict(year=y, month=m, day=dd), errors="coerce")

                    val_col = _infer_value_column(df)
                    if val_col is None:
                        # Try OGIMET columns
                        ogimet_map = {
                            "temp_c": "tmax", "rain_mm": "pluie", "pluie": "pluie",
                            "wind_speed_ms": "vent", "rh_pct": "humidite",
                        }
                        for ocol, pcol in ogimet_map.items():
                            if ocol in df.columns:
                                sub = pd.DataFrame({
                                    "date": d,
                                    pcol: pd.to_numeric(df[ocol], errors="coerce")
                                })
                                sub = sub.dropna(subset=["date"]).sort_values("date")
                                station_key = sheet if sheet != "data" else fn.stem.replace("OGIMET_", "")
                                if station_key not in by_station:
                                    by_station[station_key] = sub.set_index("date")
                                else:
                                    by_station[station_key] = by_station[station_key].join(
                                        sub.set_index("date"), how="outer", rsuffix="_dup"
                                    )
                                    # Remove duplicate columns
                                    dups = [c for c in by_station[station_key].columns if c.endswith("_dup")]
                                    by_station[station_key].drop(columns=dups, inplace=True)
                        continue

                    sub = pd.DataFrame({
                        "date": d,
                        param_name: pd.to_numeric(df[val_col], errors="coerce")
                    })
                    sub = sub.dropna(subset=["date"]).sort_values("date")
                    station_key = sheet if sheet != "data" else fn.stem
                    if station_key not in by_station:
                        by_station[station_key] = sub.set_index("date")
                    else:
                        by_station[station_key] = by_station[station_key].join(
                            sub.set_index("date"), how="outer"
                        )
                except Exception:
                    continue

        # Load CSV files
        for fn in data_dir.rglob("*.csv"):
            try:
                df = pd.read_csv(fn)
                df = _norm_cols(df)
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"], errors="coerce")
                elif "datetime_utc" in df.columns:
                    df["date"] = pd.to_datetime(df["datetime_utc"], errors="coerce")
                else:
                    continue
                df = df.dropna(subset=["date"])
                station_key = fn.stem
                if "station" in df.columns:
                    for stn, grp in df.groupby("station"):
                        if stn not in by_station:
                            by_station[stn] = grp.set_index("date")
                        else:
                            by_station[stn] = by_station[stn].join(
                                grp.set_index("date"), how="outer", rsuffix="_dup"
                            )
                else:
                    if station_key not in by_station:
                        by_station[station_key] = df.set_index("date")
                    else:
                        by_station[station_key] = by_station[station_key].join(
                            df.set_index("date"), how="outer"
                        )
            except Exception:
                continue

    frames = []
    for stn, dfx in by_station.items():
        dfx = dfx.sort_index().reset_index()
        dfx["station"] = stn
        frames.append(dfx)

    if not frames:
        return pd.DataFrame()

    big = pd.concat(frames, ignore_index=True)
    big["date"] = pd.to_datetime(big["date"], errors="coerce")
    big = big.dropna(subset=["date"])
    return big


@st.cache_data(show_spinner=False)
def load_stations_df():
    cfg = load_config()
    sf = cfg.get("station_file", "")
    if sf and Path(sf).exists():
        df = pd.read_excel(sf)
        return df.rename(columns={
            "Stations": "station", "Longitude": "lon", "Latitude": "lat"
        })
    # Generate from data
    return pd.DataFrame(columns=["station", "lon", "lat"])


# ══════════════════════════════════════════════════════════
# OGIMET DATA SYNC MODULE
# ══════════════════════════════════════════════════════════
def ogimet_sync_module():
    """OGIMET data synchronization (integrated from Ogimet_data.py)."""
    import re
    from dataclasses import dataclass

    st.subheader("📡 Synchronisation OGIMET — Données SYNOP")

    cfg = load_config()
    og_cfg = cfg.get("ogimet_config", {})

    c1, c2, c3 = st.columns(3)
    with c1:
        window_h = st.number_input("Fenêtre utile (h)", 1, 48,
                                    og_cfg.get("window_hours", 6))
    with c2:
        widen_h = st.number_input("Fenêtre requête (h)", 1, 96,
                                   og_cfg.get("widen_hours", 12))
    with c3:
        country = st.text_input("Pays OGIMET", og_cfg.get("country", "Cote"))

    # Status
    last_sync_file = OGIMET_DIR / ".last_sync"
    if last_sync_file.exists():
        last_sync = last_sync_file.read_text().strip()
        st.markdown(f"""
        <div class="data-status">
            <span class="live-dot"></span>
            Dernière synchronisation: <b>{last_sync}</b>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Aucune synchronisation effectuée.")

    # List existing OGIMET files
    ogimet_files = list(OGIMET_DIR.glob("OGIMET_*.xlsx"))
    if ogimet_files:
        st.markdown(f"**{len(ogimet_files)} fichier(s) OGIMET disponible(s)**")
        for f in ogimet_files[:10]:
            size_kb = f.stat().st_size / 1024
            st.caption(f"📄 {f.name} — {size_kb:.1f} KB")

    st.warning("La synchronisation OGIMET nécessite un accès réseau. "
               "En mode déployé, configurez un cron job ou un scheduler externe "
               "pour exécuter `python ogimet_sync.py` toutes les 6 heures.")

    # Save config
    if st.button("💾 Sauvegarder la configuration OGIMET"):
        cfg["ogimet_config"] = {
            "enabled": True,
            "country": country,
            "window_hours": window_h,
            "widen_hours": widen_h,
            "interval_minutes": 360,
        }
        save_config(cfg)
        st.success("Configuration OGIMET sauvegardée.")


# ══════════════════════════════════════════════════════════
# ENERGY MODULE — For dam managers & renewable energy
# ══════════════════════════════════════════════════════════
def energy_dashboard_module(df_all):
    """Energy production/consumption dashboard for hydroelectric & renewable."""
    st.subheader("⚡ Tableau de Bord Énergétique")
    st.markdown("Suivi de la production hydroélectrique, solaire, et de la consommation énergétique.")

    tabs = st.tabs(["🏗️ Hydroélectricité", "☀️ Solaire / PV", "📊 Bilan Énergétique"])

    # ── Tab 1: Hydroelectric ──
    with tabs[0]:
        st.markdown("### 🏗️ Production Hydroélectrique")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            hauteur_chute = st.number_input("Hauteur de chute H (m)", 0.0, 500.0, 50.0, 1.0)
        with c2:
            debit_turbine = st.number_input("Débit turbine Q (m³/s)", 0.0, 10000.0, 100.0, 10.0)
        with c3:
            rendement = st.slider("Rendement global η", 0.0, 1.0, 0.85, 0.01)
        with c4:
            rho = st.number_input("Densité eau ρ (kg/m³)", 900.0, 1100.0, 1000.0, 1.0)

        g_acc = 9.81
        puissance_kw = rho * g_acc * debit_turbine * hauteur_chute * rendement / 1000
        puissance_mw = puissance_kw / 1000

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("⚡ Puissance", f"{puissance_mw:.2f} MW")
        m2.metric("💡 Puissance", f"{puissance_kw:.1f} kW")
        m3.metric("🔋 Énergie/jour", f"{puissance_mw * 24:.1f} MWh")
        m4.metric("📅 Énergie/an", f"{puissance_mw * 8760:.0f} MWh")

        # Link with rainfall data
        if not df_all.empty and "pluie" in df_all.columns:
            st.markdown("---")
            st.markdown("#### 📈 Corrélation Pluie → Débit → Production")

            stations = sorted(df_all["station"].unique())
            sel_stn = st.selectbox("Station pluviométrique", stations,
                                    key="hydro_station")
            df_stn = df_all[df_all["station"] == sel_stn].dropna(subset=["date"]).sort_values("date")

            if "pluie" in df_stn.columns and not df_stn["pluie"].dropna().empty:
                c1, c2 = st.columns(2)
                with c1:
                    C_hydro = st.slider("Coef. ruissellement", 0.0, 1.0, 0.6, 0.05,
                                         key="C_hydro")
                with c2:
                    area_bv = st.number_input("Aire BV (km²)", 0.0, 1e6, 3000.0, 100.0,
                                               key="area_hydro")

                df_stn = df_stn.copy()
                df_stn["Q_est"] = (C_hydro * df_stn["pluie"].fillna(0) * area_bv) / 86.4
                df_stn["P_MW"] = rho * g_acc * df_stn["Q_est"] * hauteur_chute * rendement / 1e6

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=df_stn["date"], y=df_stn["pluie"],
                    name="Pluie (mm)", yaxis="y",
                    marker_color="rgba(30,136,229,0.5)"
                ))
                fig.add_trace(go.Scatter(
                    x=df_stn["date"], y=df_stn["P_MW"],
                    name="Puissance (MW)", yaxis="y2",
                    line=dict(color="#ff6f00", width=2),
                    mode="lines"
                ))
                fig.update_layout(
                    title=f"Pluie vs Production — {sel_stn}",
                    yaxis=dict(title="Pluie (mm)", side="left"),
                    yaxis2=dict(title="Puissance (MW)", side="right", overlaying="y"),
                    plot_bgcolor="rgba(246,248,250,0.8)",
                    paper_bgcolor="white",
                    font=dict(family="DM Sans"),
                    title_font=dict(family="DM Sans", size=16, color="#04322a"),
                    height=450
                )
                st.plotly_chart(fig, use_container_width=True)

    # ── Tab 2: Solar ──
    with tabs[1]:
        st.markdown("### ☀️ Énergie Solaire / Photovoltaïque")

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            surface_pv = st.number_input("Surface PV (m²)", 0.0, 100000.0, 500.0, 10.0)
        with c2:
            eff_pv = st.slider("Rendement PV (%)", 5, 30, 18, 1)
        with c3:
            irradiance = st.number_input("Irradiance (kWh/m²/j)", 0.0, 10.0, 5.5, 0.1)
        with c4:
            perf_ratio = st.slider("Performance Ratio", 0.5, 1.0, 0.80, 0.01)

        prod_jour_kwh = surface_pv * (eff_pv / 100) * irradiance * perf_ratio
        prod_mois_kwh = prod_jour_kwh * 30
        prod_an_kwh = prod_jour_kwh * 365

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("☀️ Production/jour", f"{prod_jour_kwh:.1f} kWh")
        m2.metric("📅 Production/mois", f"{prod_mois_kwh:.0f} kWh")
        m3.metric("📆 Production/an", f"{prod_an_kwh:.0f} kWh")
        m4.metric("⚡ Puissance crête", f"{surface_pv * (eff_pv/100):.1f} kWc")

        # Solar radiation from data
        if not df_all.empty and "rayonnement_global" in df_all.columns:
            st.markdown("---")
            st.markdown("#### 📈 Rayonnement Global Mesuré")
            stations = sorted(df_all["station"].unique())
            sel_stn_sol = st.selectbox("Station", stations, key="solar_station")
            df_sol = df_all[df_all["station"] == sel_stn_sol].dropna(subset=["date"])
            if "rayonnement_global" in df_sol.columns:
                df_sol = df_sol.sort_values("date")
                fig_sol = px.area(
                    df_sol, x="date", y="rayonnement_global",
                    color_discrete_sequence=["#ffa726"],
                    title=f"Rayonnement Global — {sel_stn_sol}"
                )
                fig_sol.update_layout(
                    plot_bgcolor="rgba(246,248,250,0.8)",
                    paper_bgcolor="white",
                    font=dict(family="DM Sans"),
                    title_font=dict(family="DM Sans", size=16, color="#04322a"),
                )
                st.plotly_chart(fig_sol, use_container_width=True)

    # ── Tab 3: Energy Balance ──
    with tabs[2]:
        st.markdown("### 📊 Bilan Énergétique Intégré")

        c1, c2 = st.columns(2)
        with c1:
            conso_mwh = st.number_input("Consommation totale (MWh/an)", 0.0, 1e6, 5000.0, 100.0)
        with c2:
            tarif_kwh = st.number_input("Tarif électrique (FCFA/kWh)", 0.0, 500.0, 65.0, 1.0)

        prod_hydro_an = puissance_mw * 8760
        prod_solaire_an = prod_an_kwh / 1000  # MWh

        total_renew = prod_hydro_an + prod_solaire_an
        taux_couv = (total_renew / conso_mwh * 100) if conso_mwh > 0 else 0

        m1, m2, m3 = st.columns(3)
        m1.metric("🏗️ Hydro (MWh/an)", f"{prod_hydro_an:,.0f}")
        m2.metric("☀️ Solaire (MWh/an)", f"{prod_solaire_an:,.0f}")
        m3.metric("📊 Taux couverture ENR", f"{taux_couv:.1f}%")

        # Pie chart
        fig_pie = go.Figure(data=[go.Pie(
            labels=["Hydroélectricité", "Solaire PV", "Autres sources"],
            values=[prod_hydro_an, prod_solaire_an,
                    max(0, conso_mwh - total_renew)],
            hole=0.45,
            marker_colors=["#1565c0", "#ffa726", "#90a4ae"],
            textinfo="label+percent",
            textfont=dict(family="DM Sans", size=13)
        )])
        fig_pie.update_layout(
            title="Répartition des Sources Énergétiques",
            font=dict(family="DM Sans"),
            title_font=dict(family="DM Sans", size=16, color="#04322a"),
            height=400
        )
        st.plotly_chart(fig_pie, use_container_width=True)

        # Cost analysis
        st.markdown("---")
        st.markdown("#### 💰 Analyse Économique")
        eco_renew = total_renew * 1000 * tarif_kwh
        eco_total = conso_mwh * 1000 * tarif_kwh
        economie = eco_renew

        e1, e2, e3 = st.columns(3)
        e1.metric("💰 Coût total réseau", f"{eco_total:,.0f} FCFA")
        e2.metric("💚 Économie ENR", f"{economie:,.0f} FCFA")
        e3.metric("📊 Économie (%)", f"{(economie/eco_total*100) if eco_total > 0 else 0:.1f}%")


# ══════════════════════════════════════════════════════════
# ADMIN PANEL
# ══════════════════════════════════════════════════════════
def admin_panel():
    """Administration panel for configuration."""
    st.subheader("🔧 Administration — Configuration HyMetDash")

    tabs = st.tabs([
        "🔑 Mots de passe",
        "📂 Sources de données",
        "📡 OGIMET",
        "📤 Upload données",
        "⚙️ Général"
    ])

    cfg = load_config()

    with tabs[0]:
        st.markdown("### Modifier les mots de passe")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Mot de passe Admin**")
            new_admin_pw = st.text_input("Nouveau mot de passe admin", type="password",
                                          key="new_admin_pw")
            confirm_admin_pw = st.text_input("Confirmer", type="password",
                                              key="confirm_admin_pw")
            if st.button("Mettre à jour (Admin)"):
                if new_admin_pw and new_admin_pw == confirm_admin_pw:
                    cfg["admin_password_hash"] = hash_password(new_admin_pw)
                    save_config(cfg)
                    st.success("Mot de passe admin mis à jour.")
                else:
                    st.error("Les mots de passe ne correspondent pas.")

        with c2:
            st.markdown("**Mot de passe Client**")
            new_client_pw = st.text_input("Nouveau mot de passe client", type="password",
                                           key="new_client_pw")
            confirm_client_pw = st.text_input("Confirmer", type="password",
                                               key="confirm_client_pw")
            if st.button("Mettre à jour (Client)"):
                if new_client_pw and new_client_pw == confirm_client_pw:
                    cfg["client_password_hash"] = hash_password(new_client_pw)
                    save_config(cfg)
                    st.success("Mot de passe client mis à jour.")
                else:
                    st.error("Les mots de passe ne correspondent pas.")

    with tabs[1]:
        st.markdown("### Sources de données configurées")

        sources = cfg.get("data_sources", [])
        for i, src in enumerate(sources):
            st.markdown(f"**{i+1}. {src.get('name', 'Sans nom')}** — "
                        f"Type: `{src.get('type')}` — "
                        f"Chemin: `{src.get('path', 'N/A')}`")

        st.markdown("---")
        st.markdown("#### Ajouter une source")
        c1, c2, c3 = st.columns(3)
        with c1:
            new_name = st.text_input("Nom de la source")
        with c2:
            new_type = st.selectbox("Type", ["local", "remote", "ogimet"])
        with c3:
            new_path = st.text_input("Chemin / URL")

        if st.button("➕ Ajouter la source"):
            if new_name and new_path:
                sources.append({"name": new_name, "type": new_type, "path": new_path})
                cfg["data_sources"] = sources
                save_config(cfg)
                st.success(f"Source '{new_name}' ajoutée.")
                st.rerun()

    with tabs[2]:
        ogimet_sync_module()

    with tabs[3]:
        st.markdown("### 📤 Téléverser des données")
        st.info("Les fichiers uploadés seront intégrés automatiquement au dashboard.")

        uploaded = st.file_uploader(
            "Glissez vos fichiers de données ici",
            type=["xlsx", "csv", "xls"],
            accept_multiple_files=True
        )
        if uploaded:
            for f in uploaded:
                dest = UPLOAD_DIR / f.name
                dest.write_bytes(f.read())
                st.success(f"✅ {f.name} sauvegardé dans le dossier uploads.")
            # Clear cache
            load_all_observed.clear()
            st.rerun()

    with tabs[4]:
        st.markdown("### Paramètres généraux")
        new_title = st.text_input("Titre de l'application", cfg.get("app_title", "HyMetDash"))
        new_org = st.text_input("Organisation", cfg.get("org_name", "SODEXAM / DMN"))
        refresh_s = st.number_input("Auto-refresh (secondes)", 30, 3600,
                                     cfg.get("auto_refresh_seconds", 300))
        station_file = st.text_input("Fichier stations (.xlsx)",
                                      cfg.get("station_file", ""))

        if st.button("💾 Sauvegarder les paramètres"):
            cfg["app_title"] = new_title
            cfg["org_name"] = new_org
            cfg["auto_refresh_seconds"] = refresh_s
            cfg["station_file"] = station_file
            save_config(cfg)
            st.success("Paramètres sauvegardés.")


# ══════════════════════════════════════════════════════════
# SIDEBAR NAVIGATION
# ══════════════════════════════════════════════════════════
with st.sidebar:
    logo_path = ASSETS_DIR / "logo_SODEXAM.png"
    if logo_path.exists():
        st.image(str(logo_path), use_container_width=True)
    else:
        st.markdown("""
        <div style="text-align:center; padding:20px 0;">
            <span style="font-size:2.5rem;">🌊</span>
            <h2 style="margin:4px 0 0; font-size:1.3rem;">HyMetDash</h2>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🧭 Navigation")

    SECTIONS = {
        "🗺️ Carte & Vigilance": "carte",
        "📊 Stations & Graphiques": "stations",
        "💧 Débit & Hydraulique": "debit",
        "🔮 Prévisions": "previsions",
        "⚡ Énergie": "energie",
    }

    if IS_ADMIN:
        SECTIONS["🔧 Administration"] = "admin"

    section_label = st.radio("", list(SECTIONS.keys()), label_visibility="collapsed")
    section = SECTIONS[section_label]

    st.markdown("---")

    # Data status indicator
    fp = _get_data_fingerprint()
    n_files = sum(1 for d in [OBSERVED_DIR, OGIMET_DIR, UPLOAD_DIR]
                  if d.exists()
                  for _ in d.rglob("*.xlsx"))
    n_csv = sum(1 for d in [OBSERVED_DIR, OGIMET_DIR, UPLOAD_DIR]
                if d.exists()
                for _ in d.rglob("*.csv"))

    st.markdown(f"""
    <div style="font-size:0.78rem; color:#a8e6cf; padding:8px 0; line-height:1.6;">
        <div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">
            <span class="live-dot"></span> <b>Données en temps réel</b>
        </div>
        📁 {n_files} fichiers Excel, {n_csv} CSV<br>
        🕐 Dernière vérification: {datetime.now().strftime('%H:%M:%S')}<br>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    if st.button("🔓 Déconnexion", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.role = None
        st.rerun()

    st.markdown(f"""
    <div style="font-size:0.7rem; color:#6b8a7a; padding:8px 0; text-align:center;">
        <b>HyMetDash v3.0</b> — Pro<br>
        {config.get('org_name', 'SODEXAM / DMN')}<br>
        Côte d'Ivoire 🇨🇮
    </div>
    """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# LOAD DATA
# ══════════════════════════════════════════════════════════
fp = _get_data_fingerprint()
df_all = load_all_observed(fp)
stations_df = load_stations_df()

has_data = not df_all.empty

if has_data:
    df_all = derive_parameters(df_all)


# ══════════════════════════════════════════════════════════
# SECTION: CARTE & VIGILANCE
# ══════════════════════════════════════════════════════════
if section == "carte":
    st.subheader("🗺️ Carte de Vigilance Hydrométéorologique")

    if not has_data:
        st.warning("Aucune donnée chargée. Ajoutez des données via l'onglet Administration "
                   "ou placez des fichiers dans le dossier `data/observed/`.")
        st.stop()

    with st.expander("⚙️ Paramètres d'alerte", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            rain_thr_2d = st.number_input("Seuil pluie 2j (mm)", 0.0, 600.0, 50.0, 10.0)
        with c2:
            q_thr = st.number_input("Seuil débit (m³/s)", 0.0, 1000.0, 10.0, 5.0)
        with c3:
            C_runoff = st.slider("Coef. ruissellement C", 0.0, 1.0, 0.5, 0.05, key="C_carte")
        with c4:
            area_km2_def = st.number_input("Aire BV (km²)", 0.0, 10000.0, 5000.0, 10.0)

    df_all = df_all.sort_values("date")
    if "pluie" in df_all.columns:
        df_all["pluie_2d"] = df_all.groupby("station")["pluie"].transform(
            lambda s: s.fillna(0).rolling(2, min_periods=1).sum()
        )
    else:
        df_all["pluie_2d"] = np.nan

    df_all["Q_rr"] = debit_pluie_debit(
        df_all.get("pluie", np.nan), C_runoff, area_km2_def
    )

    def alert_color(pl2d, q):
        if (pd.notna(pl2d) and pl2d >= rain_thr_2d) and (pd.notna(q) and q >= q_thr):
            return "red"
        elif (pd.notna(pl2d) and pl2d >= 0.75 * rain_thr_2d) or \
             (pd.notna(q) and q >= 0.75 * q_thr):
            return "orange"
        elif (pd.notna(pl2d) and pl2d >= 0.5 * rain_thr_2d) or \
             (pd.notna(q) and q >= 0.5 * q_thr):
            return "yellow"
        return "green"

    latest = df_all.groupby("station").tail(1).copy()
    latest["alert_color"] = latest.apply(
        lambda r: alert_color(r.get("pluie_2d"), r.get("Q_rr")), axis=1
    )

    # Station alert display
    color_map = {"green": "#4caf50", "yellow": "#ffeb3b", "orange": "#ff9800", "red": "#f44336"}
    counts = latest["alert_color"].value_counts().to_dict()

    st.markdown(f"""
    <div style="background:#fff; border-radius:12px; padding:14px 20px; margin:8px 0;
                box-shadow:0 2px 8px rgba(0,0,0,0.06); display:flex; gap:20px; align-items:center;">
        <b>Vigilance :</b>
        <span>🟢 Aucun: <b>{counts.get('green',0)}</b></span>
        <span>🟡 Faible: <b>{counts.get('yellow',0)}</b></span>
        <span>🟠 Moyen: <b>{counts.get('orange',0)}</b></span>
        <span>🔴 Élevé: <b>{counts.get('red',0)}</b></span>
    </div>
    """, unsafe_allow_html=True)

    # Map with stations
    if not stations_df.empty and "lat" in stations_df.columns:
        import geopandas as gpd

        gdf_st = stations_df.merge(
            latest[["station", "alert_color", "pluie_2d", "Q_rr"]],
            on="station", how="left"
        )
        gdf_st["alert_color"] = gdf_st["alert_color"].fillna("green")

        station_colors = gdf_st["alert_color"].map(color_map).fillna("#2196f3")
        popup_texts = [
            f"<b>{r['station']}</b><br>"
            f"Alerte: {str(r.get('alert_color','green')).upper()}<br>"
            f"Pluie 2j: {0 if pd.isna(r.get('pluie_2d')) else round(float(r.get('pluie_2d')),1)} mm<br>"
            f"Q_rr: {0 if pd.isna(r.get('Q_rr')) else round(float(r.get('Q_rr')),2)} m³/s"
            for _, r in gdf_st.iterrows()
        ]

        fig = go.Figure()
        fig.add_trace(go.Scattermapbox(
            lon=gdf_st["lon"], lat=gdf_st["lat"],
            mode="markers",
            marker=dict(size=12, color=list(station_colors), opacity=0.9),
            text=popup_texts, hoverinfo="text",
            name="Stations"
        ))
        fig.update_layout(
            mapbox=dict(style="open-street-map", center=dict(lat=7.5, lon=-5.5), zoom=5.5),
            margin=dict(l=0, r=0, t=40, b=0),
            height=550,
            title="Vigilance Hydrométéorologique — Côte d'Ivoire",
            title_font=dict(family="DM Sans", size=16, color="#04322a"),
        )
        st.plotly_chart(fig, use_container_width=True, key="map_main")
        export_plot(fig, "carte_vigilance_CIV")
    else:
        st.info("Fichier stations non trouvé. Configurez-le dans l'onglet Administration.")

    # Alert table
    alerts = latest[latest["alert_color"].isin(["yellow", "orange", "red"])]
    if not alerts.empty:
        st.markdown("---")
        st.markdown("#### 🔔 Stations en vigilance active")
        for _, row in alerts.iterrows():
            badge = {"yellow": "🟡", "orange": "🟠", "red": "🔴"}.get(row["alert_color"], "⚠️")
            label = {"yellow": "Faible", "orange": "Moyen", "red": "Élevé"}.get(row["alert_color"], "")
            pluie_2d_val = round(float(row.get("pluie_2d", 0)), 1) if pd.notna(row.get("pluie_2d")) else 0
            st.markdown(f"{badge} **{row['station']}** — Vigilance *{label}* — "
                        f"Pluie 2j: {pluie_2d_val} mm")
    else:
        st.success("✅ Aucune station en vigilance active.")


# ══════════════════════════════════════════════════════════
# SECTION: STATIONS & GRAPHIQUES
# ══════════════════════════════════════════════════════════
elif section == "stations":
    st.subheader("📊 Visualisation par Station et Paramètre")

    if not has_data:
        st.warning("Aucune donnée chargée.")
        st.stop()

    col_sel, col_param = st.columns(2)
    with col_sel:
        station_sel = st.selectbox("🏢 Station", sorted(df_all["station"].unique()))

    num_cols = [c for c in df_all.columns
                if c not in ("station", "date") and pd.api.types.is_numeric_dtype(df_all[c])]
    preferred = ["pluie", "etp", "bilan_hydrique", "rayonnement_global",
                 "rayonnement_direct", "rayonnement_diffus", "tmax", "tmin",
                 "vent", "insolation", "humidite"]
    ordered = [p for p in preferred if p in num_cols] + \
              [c for c in num_cols if c not in preferred]
    with col_param:
        param_sel = st.selectbox("📏 Paramètre", ordered)

    df_st = df_all[df_all["station"] == station_sel].dropna(subset=["date"]).sort_values("date")
    if df_st.empty:
        st.warning("Pas de données pour cette station.")
        st.stop()

    min_d, max_d = df_st["date"].min().date(), df_st["date"].max().date()
    dr = st.date_input("🗓️ Période", [min_d, max_d], format="DD/MM/YYYY")
    if isinstance(dr, (tuple, list)) and len(dr) == 2:
        start_d, end_d = pd.to_datetime(dr[0]), pd.to_datetime(dr[1])
    else:
        start_d, end_d = pd.to_datetime(min_d), pd.to_datetime(max_d)

    data = df_st[(df_st["date"] >= start_d) & (df_st["date"] <= end_d)].copy()

    if param_sel in data.columns and not data[param_sel].dropna().empty:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📈 Max", f"{data[param_sel].max():.2f}")
        m2.metric("📉 Min", f"{data[param_sel].min():.2f}")
        m3.metric("📊 Moyenne", f"{data[param_sel].mean():.2f}")
        m4.metric("🔢 N obs.", f"{data[param_sel].count()}")

    graph_type = st.selectbox("📉 Type de graphique",
                               ["Courbe", "Histogramme", "Box-plot", "Nuage de points"])

    color_palette = {
        "pluie": "#1565c0", "tmax": "#d32f2f", "tmin": "#42a5f5",
        "rayonnement_global": "#ffa726", "rayonnement_direct": "#ff7043",
        "rayonnement_diffus": "#bdbdbd", "etp": "#ab47bc",
        "bilan_hydrique": "#2e7d32", "vent": "#00acc1", "insolation": "#ffca28"
    }
    base_color = color_palette.get(param_sel, "#065535")

    if graph_type == "Courbe":
        fig = px.line(data, x="date", y=param_sel, markers=True,
                      color_discrete_sequence=[base_color],
                      title=f"{param_sel.capitalize()} — {station_sel}")
    elif graph_type == "Histogramme":
        fig = px.bar(data, x="date", y=param_sel,
                     color_discrete_sequence=[base_color],
                     title=f"{param_sel.capitalize()} — {station_sel}")
    elif graph_type == "Box-plot":
        fig = px.box(data, y=param_sel, color_discrete_sequence=[base_color],
                     title=f"Distribution {param_sel.capitalize()} — {station_sel}")
    else:
        fig = px.scatter(data, x="date", y=param_sel,
                         color_discrete_sequence=[base_color],
                         title=f"{param_sel.capitalize()} — {station_sel}")

    fig.update_layout(
        plot_bgcolor="rgba(246,248,250,0.8)",
        paper_bgcolor="white",
        font=dict(family="DM Sans"),
        title_font=dict(family="DM Sans", size=16, color="#04322a"),
        margin=dict(t=60, b=40),
        height=450
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("**📥 Exporter :**")
    export_plot(fig, f"{station_sel}_{param_sel}")
    st.download_button(
        "📥 CSV (données filtrées)",
        data.to_csv(index=False).encode("utf-8"),
        file_name=f"{station_sel}_{param_sel}_{start_d.date()}_{end_d.date()}.csv",
        mime="text/csv",
        key=f"csv_dl_{time.time_ns()}"
    )


# ══════════════════════════════════════════════════════════
# SECTION: DÉBIT & HYDRAULIQUE
# ══════════════════════════════════════════════════════════
elif section == "debit":
    st.subheader("💧 Débit — Pluie → Débit + Manning/Strickler")

    if not has_data:
        st.warning("Aucune donnée chargée.")
        st.stop()

    station_q = st.selectbox("🏢 Station (pluie pour Q_rr)",
                              sorted(df_all["station"].unique()))
    dfq = df_all[df_all["station"] == station_q].dropna(subset=["date"]).sort_values("date")

    c1, c2, c3 = st.columns(3)
    with c1:
        C_run = st.slider("Coef. ruissellement C", 0.0, 1.0, 0.5, 0.05, key="C_debit")
    with c2:
        area_km2 = st.number_input("Aire BV (km²)", 0.0, 1e6, 5000.0, 10.0, key="area_debit")
    with c3:
        agg = st.selectbox("Agrégation", ["journalière", "hebdomadaire", "mensuelle"])

    if "pluie" in dfq.columns:
        dfq = dfq.copy()
        dfq["Q_rr"] = debit_pluie_debit(dfq["pluie"], C_run, area_km2)
    else:
        dfq["Q_rr"] = np.nan

    if agg == "hebdomadaire":
        q_plot = dfq.set_index("date")["Q_rr"].resample("W").mean().reset_index()
    elif agg == "mensuelle":
        q_plot = dfq.set_index("date")["Q_rr"].resample("MS").mean().reset_index()
    else:
        q_plot = dfq[["date", "Q_rr"]].copy()

    fig_q = px.line(q_plot, x="date", y="Q_rr", markers=True,
                    color_discrete_sequence=["#065535"],
                    title=f"Débit estimé (C={C_run:.2f}, A={area_km2:.0f} km²) — {station_q}")
    fig_q.update_layout(
        plot_bgcolor="rgba(246,248,250,0.8)", paper_bgcolor="white",
        font=dict(family="DM Sans"),
        title_font=dict(family="DM Sans", size=16, color="#04322a"),
        height=420
    )
    st.plotly_chart(fig_q, use_container_width=True)
    export_plot(fig_q, f"Qrr_{station_q}")

    st.markdown("---")
    st.subheader("⚙️ Manning / Strickler")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        use_n = st.toggle("Utiliser n (Manning)", value=True)
    with c2:
        n_manning = st.number_input("n (Manning)", 0.010, 0.150, 0.035, 0.001)
    with c3:
        k_strick = st.number_input("k (Strickler)", 5.0, 150.0, 28.6, 0.1)
    with c4:
        use_k = st.toggle("Utiliser k (Strickler)", value=False)

    c5, c6, c7 = st.columns(3)
    with c5:
        A_m2 = st.number_input("Aire mouillée A (m²)", 0.0, 1e5, 50.0, 1.0)
    with c6:
        R_m = st.number_input("Rayon hydraulique R (m)", 0.0, 1000.0, 1.0, 0.01)
    with c7:
        S = st.number_input("Pente S (m/m)", 0.0, 1.0, 0.001, 0.0001, format="%.4f")

    k_use = (1.0 / n_manning) if (use_n and not use_k) else (k_strick if use_k else None)
    Q_man = (k_use * A_m2 * (R_m ** (2/3.0)) * (S ** 0.5)) \
        if (k_use and A_m2 and R_m and S) else np.nan

    col_r1, col_r2 = st.columns(2)
    col_r1.metric("💧 Débit Manning/Strickler",
                   f"{(Q_man if pd.notna(Q_man) else 0):.3f} m³/s")
    col_r2.metric("⚡ Vitesse V=Q/A",
                   f"{(Q_man/A_m2 if pd.notna(Q_man) and A_m2 > 0 else 0):.3f} m/s")


# ══════════════════════════════════════════════════════════
# SECTION: PRÉVISIONS
# ══════════════════════════════════════════════════════════
elif section == "previsions":
    st.subheader("🔮 Prévisions Météorologiques et Hydrologiques")
    st.info("📡 Mode démonstration — Intégration GFS/données réelles prochainement.")

    if has_data:
        stations_list = sorted(df_all["station"].unique().tolist())
    else:
        stations_list = ["Station_Demo"]

    start_time = pd.Timestamp.now().floor("H")
    dates = pd.date_range(start_time, periods=80, freq="3h")

    @st.cache_data
    def generate_forecast(station_list, dates_tuple):
        rows = []
        for stn in station_list:
            for t in dates_tuple:
                precip = np.random.uniform(0, 20)
                hour_frac = (t.hour + t.minute / 60) / 24.0 * 2 * np.pi
                temp = 22 + 6 * np.sin(hour_frac) + np.random.normal(0, 1)
                rows.append((stn, t, "Précipitation (mm)", round(precip, 2)))
                rows.append((stn, t, "Température (°C)", round(temp, 2)))
        return pd.DataFrame(rows, columns=["Station", "Datetime", "Parameter", "Value"])

    forecast_df = generate_forecast(tuple(stations_list), tuple(dates))

    c1, c2, c3 = st.columns(3)
    with c1:
        sel_stn_fc = st.selectbox("🏢 Station", stations_list, key="fc_station")
    with c2:
        sel_param_fc = st.selectbox("📏 Paramètre",
                                     ["Précipitation (mm)", "Température (°C)"], key="fc_param")
    with c3:
        all_dates = sorted({d.date() for d in dates})
        date_opts = ["Toutes"] + [str(d) for d in all_dates]
        sel_date_fc = st.selectbox("📅 Date", date_opts, key="fc_date")

    fc_filtered = forecast_df[
        (forecast_df["Station"] == sel_stn_fc) &
        (forecast_df["Parameter"] == sel_param_fc)
    ]

    if sel_date_fc != "Toutes":
        filter_date = pd.to_datetime(sel_date_fc).date()
        fc_data = fc_filtered[fc_filtered["Datetime"].dt.date == filter_date]
    else:
        fc_data = fc_filtered

    if sel_date_fc == "Toutes":
        pivot = fc_data.pivot_table(
            index=fc_data["Datetime"].dt.date,
            columns=fc_data["Datetime"].dt.hour,
            values="Value"
        )
        fig_fc = go.Figure(data=go.Heatmap(
            z=pivot.values,
            x=[f"{h}h" for h in pivot.columns],
            y=pivot.index.astype(str).tolist(),
            colorscale="YlGnBu",
            colorbar_title=sel_param_fc
        ))
        fig_fc.update_layout(
            title=f"{sel_param_fc} — {sel_stn_fc} (10 jours)",
            font=dict(family="DM Sans"),
            title_font=dict(family="DM Sans", size=16, color="#04322a"),
        )
    else:
        fig_fc = px.line(fc_data, x="Datetime", y="Value",
                         color_discrete_sequence=["#065535"],
                         title=f"{sel_param_fc} — {sel_stn_fc} ({sel_date_fc})")
        fig_fc.update_layout(
            plot_bgcolor="rgba(246,248,250,0.8)", paper_bgcolor="white",
            font=dict(family="DM Sans"),
            title_font=dict(family="DM Sans", size=16, color="#04322a"),
        )

    st.plotly_chart(fig_fc, use_container_width=True)


# ══════════════════════════════════════════════════════════
# SECTION: ÉNERGIE
# ══════════════════════════════════════════════════════════
elif section == "energie":
    energy_dashboard_module(df_all if has_data else pd.DataFrame())


# ══════════════════════════════════════════════════════════
# SECTION: ADMINISTRATION (Admin only)
# ══════════════════════════════════════════════════════════
elif section == "admin" and IS_ADMIN:
    admin_panel()


# ══════════════════════════════════════════════════════════
# FOOTER
# ══════════════════════════════════════════════════════════
st.markdown("---")
st.markdown(f"""
<div style="text-align:center; color:#6b8a7a; font-size:0.75rem; padding:10px 0;">
    🌊 <b>HyMetDash v3.0</b> — Dashboard Hydrométéorologique & Énergétique Professionnel<br>
    {config.get('org_name', 'SODEXAM / DMN')} — Côte d'Ivoire 🇨🇮<br>
    © {datetime.now().year} — Tous droits réservés
</div>
""", unsafe_allow_html=True)