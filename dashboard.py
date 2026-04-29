import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
import io
import warnings
import requests
import re
import html
import base64
import unicodedata
from pathlib import Path
from datetime import date, datetime, timedelta
def _image_to_base64(image_path):
    try:
        return base64.b64encode(Path(image_path).read_bytes()).decode('utf-8')
    except Exception:
        return None

def _youtube_embed_url(video_url):
    if not video_url:
        return ""

    url = str(video_url).strip()
    youtube_patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([A-Za-z0-9_-]{11})",
        r"youtube\.com/shorts/([A-Za-z0-9_-]{11})",
    ]

    for pattern in youtube_patterns:
        match = re.search(pattern, url)
        if match:
            return f"https://www.youtube.com/embed/{match.group(1)}"

    return ""

SENSOR_VARIABLES = ['Temperatura', 'Humedad Relativa', 'Radiación PAR', 'Gramos de agua']
VARIABLE_LABELS = {
    'Temperatura': 'Temperatura (°C)',
    'Humedad Relativa': 'Humedad Relativa (%)',
    'Radiación PAR': 'Radiación PAR (µmol m⁻² s⁻¹)',
    'Gramos de agua': 'Gramos de agua (g)'
}
VARIABLE_UNITS = {
    'Temperatura': '°C',
    'Humedad Relativa': '%',
    'Radiación PAR': 'µmol m⁻² s⁻¹',
    'Gramos de agua': 'g'
}
VARIABLE_COLORS = {
    'Temperatura': '#6E97F2',
    'Humedad Relativa': '#5B6275',
    'Radiación PAR': '#8CBD63',
    'Gramos de agua': '#D39A58'
}
CORTINA_COLORS = {
    'FRENTE 1': '#524B82',
    'FRENTE 2': '#8077AE',
    'PUERTA 1': '#9E6F7F',
    'PUERTA 2': '#D8B7C0'
}
MOTOR_VARIABLES = list(CORTINA_COLORS.keys())
MOTOR_AREA_REFERENCE = {
    'FRENTE 1': {'row_key': 'ventilacion frontal', 'divisor': 1},
    'FRENTE 2': {'row_key': 'ventilacion frontal', 'divisor': 1},
    'PUERTA 1': {'row_key': 'ventilacion lateral', 'divisor': 1},
    'PUERTA 2': {'row_key': 'ventilacion lateral', 'divisor': 1}
}
VARIABLE_SELECTOR_LABELS = {
    'Temperatura': 'Temperatura (°C)',
    'Humedad Relativa': 'Humedad Relativa (%)',
    'Radiación PAR': 'Radiación PAR',
    'Gramos de agua': 'Gramos de agua (g)',
    'FRENTE 1': 'Frente 1',
    'FRENTE 2': 'Frente 2',
    'PUERTA 1': 'Puerta 1',
    'PUERTA 2': 'Puerta 2'
}
FILTER_HELP_TEXTS = {
    'modo_dashboard': 'Elige entre la vista de correlación por bloque y la vista comparativa de varianza y promedio por franja horaria.',
    'modo_fechas': 'Define si quieres analizar un solo día o un rango de varios días.',
    'fecha': 'Selecciona la fecha o el rango que se usará para filtrar los registros visibles en la vista actual.',
    'bloque': 'Selecciona el bloque principal que quieres analizar en la correlación.',
    'bloques_comparados': 'Activa o desactiva los bloques que quieres incluir en la comparación de varianza y promedio.',
    'series_visibles': 'Activa las variables ambientales y operativas que deseas mostrar en la gráfica.',
    'comparar_almacen': 'Muestra la serie equivalente de la Estación externa para cada variable ambiental seleccionada.',
    'aperturas_ideales': 'Superpone la apertura ideal calculada sobre las series de frentes y puertas cuando exista la referencia del bloque.'
}
VARIABLE_FILTER_HELP = {
    'Temperatura': 'Muestra la temperatura del bloque seleccionado.',
    'Humedad Relativa': 'Muestra la humedad relativa del bloque seleccionado.',
    'Radiación PAR': 'Muestra la radiación PAR del bloque seleccionado.',
    'Gramos de agua': 'Muestra los gramos de agua del bloque seleccionado.',
    'FRENTE 1': 'Muestra la apertura del Frente 1.',
    'FRENTE 2': 'Muestra la apertura del Frente 2.',
    'PUERTA 1': 'Muestra la apertura de la Puerta 1.',
    'PUERTA 2': 'Muestra la apertura de la Puerta 2.'
}
BRAND_COLORS = {
    'hero': '#4C4678',
    'sky': '#D6E5EC',
    'rose': '#E7D2DA',
    'beige': '#D9CDBA',
    'graphite': '#2D3040',
    'ink': '#1F2430',
    'paper': '#F7F4EE',
    'white': '#FFFFFF'
}
APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / 'logo elite.png'
LOGO_URL_LARGE = "https://raw.githubusercontent.com/juandavdidtejedormedina-rgb/dashboard-invernaderos/main/logo%20elite.png"
LOGO_URL_SMALL = LOGO_URL_LARGE
DASHBOARD_VIDEO_URL = ""
STREAMLIT_LOGO_WIDTH = 74
STREAMLIT_LOGO_HEIGHT = 74
STREAMLIT_LOGO_BORDER_RADIUS = 10
CORR_AXIS_TITLES = {
    'Temperatura': 'Temp.',
    'Humedad Relativa': 'Humedad',
    'Radiación PAR': 'Rad. PAR',
    'Gramos de agua': 'Gramos',
    '% Apertura Cortinas': 'Cortinas %'
}
CORTINAS_NUMERIC_COLUMNS = [
    '% Apertura A', '% Cierre A', '% Apertura B', '% Cierre B',
    'Duracion Apertura A', 'Duracion Cierre A', 'Duracion Apertura B', 'Duracion Cierre B', 'Culatas %'
]
CORTINAS_TIME_COLUMNS = ['Hora Apertura A', 'Hora Cierre A', 'Hora Apertura B', 'Hora Cierre B']
CORTINAS_COLUMNAS_CON_DIA = [
    'Dia',
    'Fecha', 'Hora Apertura A', '% Apertura A', 'Duracion Apertura A',
    'Hora Cierre A', '% Cierre A', 'Duracion Cierre A', 'Frente A', 'Anotacion A',
    'Hora Apertura B', '% Apertura B', 'Duracion Apertura B', 'Hora Cierre B',
    '% Cierre B', 'Duracion Cierre B', 'Puerta B', 'Anotacion B', 'Culatas %'
]
CORTINAS_COLUMNAS = [
    'Fecha', 'Hora Apertura A', '% Apertura A', 'Duracion Apertura A',
    'Hora Cierre A', '% Cierre A', 'Duracion Cierre A', 'Frente A', 'Anotacion A',
    'Hora Apertura B', '% Apertura B', 'Duracion Apertura B', 'Hora Cierre B',
    '% Cierre B', 'Duracion Cierre B', 'Puerta B', 'Anotacion B', 'Culatas %'
]
BLOCK_MODIFICATIONS = {
    '34': 'Sistema de apertura y cierre de cortinas bidireccionales y automatizadas, incluyendo cortinas móviles en culatas.',
    '35': 'Sistema de extractores y ventiladores, incluyendo cortinas móviles en culatas.',
    '27': 'Sin modificación alguna.',
    '38': 'Sistema de apertura y cierre de cortinas bidireccionales manuales, incluyendo cortinas móviles en culatas.'
}
BLOCK_VENTILATION_DATA = {
    '34': [
        {'label': 'Ventilacion lateral', 'ideal': 523.6, 'real': 482.8},
        {'label': 'Ventilacion frontal', 'ideal': 938.0, 'real': 884.4},
        {'label': 'Ventilacion culatas', 'ideal': 201.6, 'real': 196.0}
    ],
    '27': [
        {'label': 'Ventilacion lateral', 'ideal': 503.2, 'real': 435.2},
        {'label': 'Ventilacion frontal', 'ideal': 1072.0, 'real': 956.76},
        {'label': 'Ventilacion culatas', 'ideal': None, 'real': None}
    ],
    '38': [
        {'label': 'Ventilacion lateral', 'ideal': 489.6, 'real': 435.2},
        {'label': 'Ventilacion frontal', 'ideal': 1018.4, 'real': 938.0},
        {'label': 'Ventilacion culatas', 'ideal': 201.6, 'real': 196.0}
    ],
    '35': [
        {'label': 'Ventilacion lateral', 'ideal': 530.4, 'real': 462.4},
        {'label': 'Ventilacion frontal', 'ideal': 951.4, 'real': 737.0},
        {'label': 'Ventilacion culatas', 'ideal': 201.6, 'real': 98.0}
    ]
}
BLOCK_ANALYSIS_COLORS = {
    '27': '#8077AE',
    '34': '#6E97F2',
    '35': '#8CBD63',
    '38': '#D39A58',
    'ALMACEN': '#B56576'
}
SPECIAL_BLOCK_LABELS = {
    'ALMACEN': 'Estación externa'
}
WEEKDAY_ES = {
    0: 'Lunes',
    1: 'Martes',
    2: 'Miércoles',
    3: 'Jueves',
    4: 'Viernes',
    5: 'Sábado',
    6: 'Domingo'
}
SIDE_CONFIGS = {
    'A': {
        'title': 'Lado A — Culatas / Frontales',
        'element_col': 'Frente A',
        'open_time_col': 'Hora Apertura A',
        'open_pct_col': '% Apertura A',
        'open_duration_col': 'Duracion Apertura A',
        'close_time_col': 'Hora Cierre A',
        'close_pct_col': '% Cierre A',
        'close_duration_col': 'Duracion Cierre A',
        'note_col': 'Anotacion A',
        'open_duration_label': 'Duracion Abierto A',
        'chart_color': '#2ecc71'
    },
    'B': {
        'title': 'Lado B — Laterales / Puertas',
        'element_col': 'Puerta B',
        'open_time_col': 'Hora Apertura B',
        'open_pct_col': '% Apertura B',
        'open_duration_col': 'Duracion Apertura B',
        'close_time_col': 'Hora Cierre B',
        'close_pct_col': '% Cierre B',
        'close_duration_col': 'Duracion Cierre B',
        'note_col': 'Anotacion B',
        'open_duration_label': 'Duracion Abierto B',
        'chart_color': '#3498db'
    }
}

# 1. Configuración de la página
st.set_page_config(
    page_title="The Elite Flower | Dashboard Ejecutivo",
    page_icon="📊",
    layout="wide"
)
st.logo(
    LOGO_URL_LARGE,
    link="https://streamlit.io/gallery",
    icon_image=LOGO_URL_SMALL,
)
logo_base64 = _image_to_base64(LOGO_PATH)
logo_html = (
    f'<img src="data:image/png;base64,{logo_base64}" alt="The Elite Flower" class="hero-logo-image">'
    if logo_base64 else '<div class="hero-logo-fallback">THE ELITE FLOWER</div>'
)

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600;700&family=Manrope:wght@400;500;600;700;800&display=swap');

:root {{
    --elite-hero: {BRAND_COLORS['hero']};
    --elite-sky: {BRAND_COLORS['sky']};
    --elite-rose: {BRAND_COLORS['rose']};
    --elite-beige: {BRAND_COLORS['beige']};
    --elite-graphite: {BRAND_COLORS['graphite']};
    --elite-ink: {BRAND_COLORS['ink']};
    --elite-paper: {BRAND_COLORS['paper']};
    --elite-white: {BRAND_COLORS['white']};
    --font-display: 'Manrope', sans-serif;
    --font-body: 'Manrope', sans-serif;
    --font-brand: 'Cormorant Garamond', serif;
    --streamlit-logo-width: {STREAMLIT_LOGO_WIDTH}px;
    --streamlit-logo-height: {STREAMLIT_LOGO_HEIGHT}px;
    --streamlit-logo-radius: {STREAMLIT_LOGO_BORDER_RADIUS}px;
}}

.stApp {{
    background:
        radial-gradient(circle at 12% 18%, rgba(217, 205, 186, 0.22), transparent 22%),
        radial-gradient(circle at 88% 10%, rgba(214, 229, 236, 0.34), transparent 28%),
        linear-gradient(180deg, #fcfaf6 0%, var(--elite-paper) 58%, #f2eee6 100%);
    color: var(--elite-ink);
    font-family: var(--font-body);
}}
[data-testid="stAppViewContainer"] > .main {{
    padding-top: 1.4rem;
}}
[data-testid="stAppViewContainer"] > .main .block-container {{
    max-width: 1180px;
    margin-left: auto;
    margin-right: auto;
    padding-left: 1rem;
    padding-right: 1rem;
}}
[data-testid="stAppViewContainer"] > section[data-testid="stSidebar"][aria-expanded="false"] {{
    min-width: 0 !important;
    max-width: 0 !important;
    width: 0 !important;
}}
[data-testid="stAppViewContainer"] > section[data-testid="stSidebar"][aria-expanded="false"] > div {{
    width: 0 !important;
    padding: 0 !important;
    overflow: hidden;
}}
[data-testid="stAppViewContainer"] > section[data-testid="stSidebar"][aria-expanded="false"] ~ .main {{
    padding-left: 0;
    padding-right: 0;
}}
[data-testid="stAppViewContainer"] > section[data-testid="stSidebar"][aria-expanded="false"] ~ .main .block-container {{
    margin-left: auto;
    margin-right: auto;
}}
section[data-testid="stSidebar"] {{
    min-width: 268px !important;
    max-width: 268px !important;
}}
section[data-testid="stSidebar"] > div {{
    width: 268px !important;
}}
[data-testid="stSidebar"] .block-container {{
    padding: 3.1rem 0.7rem 1rem 0.7rem;
}}
[data-testid="stSidebar"] {{
    background:
        radial-gradient(circle at top left, rgba(231, 210, 218, 0.18), transparent 24%),
        linear-gradient(180deg, rgba(76, 70, 120, 0.98) 0%, rgba(31, 36, 48, 0.99) 100%);
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 18px 0 42px rgba(31, 36, 48, 0.18);
}}
[data-testid="stSidebar"] * {{
    color: #f7f7fb;
}}
[data-testid="stSidebarHeader"] {{
    padding-top: 2.1rem !important;
    padding-bottom: 0.6rem !important;
    overflow: visible !important;
    position: relative !important;
}}
[data-testid="stSidebarHeader"] > div {{
    width: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    overflow: visible !important;
}}
[data-testid="stSidebarCollapseButton"] {{
    position: absolute !important;
    top: 1.35rem !important;
    right: 0.45rem !important;
    left: auto !important;
    z-index: 20 !important;
}}
[data-testid="stSidebarHeader"] button {{
    position: absolute !important;
    top: 1.35rem !important;
    right: 0.45rem !important;
    left: auto !important;
    z-index: 20 !important;
}}
[data-testid="stSidebarHeader"] a {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    margin: 1.1rem auto 1rem auto !important;
    padding: 0.28rem;
    border: 1px solid rgba(255, 255, 255, 0.42);
    border-radius: calc(var(--streamlit-logo-radius) + 6px);
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.08) 0%, rgba(255, 255, 255, 0.03) 100%);
    box-shadow: 0 10px 22px rgba(16, 18, 32, 0.16);
    transform: translateY(10px);
}}
[data-testid="stSidebarHeader"] img,
[data-testid="stSidebarHeader"] [data-testid="stLogo"] img {{
    width: var(--streamlit-logo-width) !important;
    height: var(--streamlit-logo-height) !important;
    max-width: none !important;
    object-fit: contain;
    border-radius: var(--streamlit-logo-radius);
}}
.sidebar-title {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin: 1.65rem 0 1.2rem 0.15rem;
    color: #ffffff;
    font-family: var(--font-display);
    font-size: 1.42rem;
    font-weight: 800;
    letter-spacing: 0.02em;
}}
.sidebar-title-icon {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.05rem;
    height: 1.05rem;
    color: rgba(255, 255, 255, 0.92);
}}
.sidebar-field-label {{
    display: flex;
    align-items: center;
    gap: 0.42rem;
    margin: 0.05rem 0 0.3rem 0.15rem;
    color: rgba(247, 247, 251, 0.92);
    font-family: var(--font-display);
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}}
.sidebar-field-icon {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1rem;
    height: 1rem;
    color: rgba(247, 247, 251, 0.88);
}}
.sidebar-title-icon svg,
.sidebar-field-icon svg {{
    width: 100%;
    height: 100%;
    stroke: currentColor;
    fill: none;
    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
}}
[data-testid="stSidebar"] .stExpander {{
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.10), rgba(255, 255, 255, 0.05));
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 18px;
    overflow: hidden;
    box-shadow: 0 18px 34px rgba(0, 0, 0, 0.16);
    margin-bottom: 0.78rem;
}}
[data-testid="stSidebar"] .stExpander details summary {{
    background: rgba(255, 255, 255, 0.08);
    padding: 0.42rem 0.75rem;
}}
[data-testid="stSidebar"] .stExpander details summary p {{
    font-family: var(--font-display);
    font-size: 0.95rem;
    font-weight: 700;
}}
[data-testid="stSidebar"] [data-testid="stCheckbox"] {{
    margin-bottom: 0.14rem;
}}
[data-testid="stSidebar"] [data-testid="stCheckbox"] label {{
    width: 100%;
    min-height: 2.42rem;
    padding: 0.38rem 0.46rem 0.38rem 0.52rem;
    border-radius: 18px;
    border: 1px solid rgba(255, 255, 255, 0.10);
    background: linear-gradient(180deg, rgba(255,255,255,0.13), rgba(255,255,255,0.06));
    box-shadow: 0 10px 20px rgba(0, 0, 0, 0.12);
    transition: background 0.2s ease, transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}}
[data-testid="stSidebar"] [data-testid="stCheckbox"] label:hover {{
    background: linear-gradient(180deg, rgba(255,255,255,0.18), rgba(255,255,255,0.10));
    border-color: rgba(214, 229, 236, 0.42);
    box-shadow: 0 14px 28px rgba(0, 0, 0, 0.16);
    transform: translateX(2px);
}}
[data-testid="stSidebar"] [data-testid="stCheckbox"] label:has([aria-checked="true"]) {{
    border-color: rgba(255, 255, 255, 0.24);
    background: linear-gradient(135deg, rgba(116, 108, 170, 0.84), rgba(82, 75, 130, 0.96));
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.16), 0 16px 30px rgba(27, 23, 53, 0.30);
}}
[data-testid="stSidebar"] [data-testid="stCheckbox"] p {{
    font-size: 0.82rem;
    font-weight: 600;
    letter-spacing: 0.01em;
    line-height: 1.15;
    white-space: nowrap;
}}
[data-testid="stSidebar"] [data-testid="stCheckbox"] label > div {{
    flex: 0 0 auto;
}}
[data-testid="stSidebar"] [data-testid="stCheckbox"] label > div:last-child {{
    min-width: 0;
    flex: 1 1 auto;
}}
[data-testid="stSidebar"] [data-testid="stCheckbox"] [data-testid="stTooltipIcon"] {{
    margin-left: auto;
    flex: 0 0 auto;
}}
[data-testid="stSidebar"] [data-testid="stCheckbox"] svg {{
    fill: var(--elite-white);
}}
[data-testid="stSidebar"] .stCheckbox [role="checkbox"] {{
    border-radius: 12px;
}}
[data-testid="stSidebar"] div.stButton > button {{
    width: 100%;
    min-height: 2.95rem;
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    background: linear-gradient(135deg, #6a639c 0%, #4c4678 100%);
    color: var(--elite-white);
    font-family: var(--font-display);
    font-weight: 800;
    font-size: 0.92rem;
    letter-spacing: 0.02em;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.16), 0 18px 32px rgba(27, 23, 53, 0.32);
}}
[data-testid="stSidebar"] div.stButton > button:hover {{
    border-color: rgba(255, 255, 255, 0.22);
    background: linear-gradient(135deg, #776fb0 0%, #575184 100%);
    color: var(--elite-white);
    transform: translateY(-1px);
}}
.hero-card {{
    position: relative;
    display: none;
    grid-template-columns: 200px minmax(0, 1fr);
    gap: 1.15rem;
    align-items: stretch;
    padding: 1.45rem 1.5rem;
    margin: 0 0 1.35rem 0;
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 30px;
    background:
        radial-gradient(circle at 18% 18%, rgba(255,255,255,0.16), transparent 18%),
        linear-gradient(135deg, #5f598f 0%, #4c4678 38%, #2d3040 100%);
    box-shadow: 0 28px 68px rgba(35, 30, 58, 0.22);
    overflow: hidden;
}}
.hero-card::before {{
    content: '';
    position: absolute;
    inset: 1px;
    border-radius: 29px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    pointer-events: none;
}}
.hero-logo-shell {{
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 24px;
    border: 1px solid rgba(255, 255, 255, 0.18);
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(247, 244, 238, 0.95));
    min-height: 150px;
    padding: 1.1rem;
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.70), 0 20px 34px rgba(36, 31, 61, 0.18);
}}
.hero-logo-image {{
    width: 100%;
    max-width: 165px;
    height: auto;
    object-fit: contain;
}}
.hero-logo-fallback {{
    font-family: var(--font-brand);
    font-weight: 700;
    color: var(--elite-hero);
    text-align: center;
    letter-spacing: 0.08em;
    line-height: 1.3;
}}
.hero-copy {{
    display: flex;
    flex-direction: column;
    justify-content: center;
}}
.hero-kicker {{
    margin: 0 0 0.45rem 0;
    color: rgba(255, 244, 238, 0.84);
    font-family: var(--font-brand);
    font-size: 1rem;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    font-weight: 700;
}}
.hero-copy h1 {{
    margin: 0;
    color: var(--elite-white);
    font-family: var(--font-display);
    font-weight: 800;
    font-size: 2.35rem;
    line-height: 1.02;
    letter-spacing: -0.04em;
}}
.hero-subtitle {{
    margin: 0.85rem 0 0.1rem 0;
    max-width: 44rem;
    color: rgba(255, 255, 255, 0.82);
    font-size: 1.03rem;
    line-height: 1.7;
}}
.video-panel {{
    margin: -0.35rem 0 1.25rem 0;
    padding: 1rem;
    border-radius: 20px;
    border: 1px solid rgba(76, 70, 120, 0.12);
    background: rgba(255, 255, 255, 0.78);
    box-shadow: 0 16px 36px rgba(45, 48, 64, 0.08);
}}
.video-panel-title {{
    margin: 0 0 0.75rem 0;
    color: var(--elite-ink);
    font-family: var(--font-display);
    font-size: 1.02rem;
    font-weight: 800;
}}
.summary-grid {{
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.85rem;
    margin: 0.35rem 0 1.15rem 0;
}}
.summary-card {{
    position: relative;
    display: flex;
    flex-direction: column;
    padding: 1.08rem 1.08rem 1rem 1.08rem;
    border-radius: 24px;
    border: 1px solid rgba(76, 70, 120, 0.10);
    background: linear-gradient(180deg, rgba(255,255,255,0.92) 0%, rgba(247,244,238,0.96) 100%);
    box-shadow: 0 18px 40px rgba(45, 48, 64, 0.09);
    overflow: hidden;
    backdrop-filter: blur(12px);
}}
.summary-card::before {{
    content: '';
    position: absolute;
    inset: 0 0 auto 0;
    height: 5px;
    background: linear-gradient(90deg, var(--summary-accent), var(--summary-accent-soft));
}}
.summary-card::after {{
    content: '';
    position: absolute;
    top: -34px;
    right: -20px;
    width: 118px;
    height: 118px;
    background: radial-gradient(circle, var(--summary-accent-soft) 0%, rgba(255,255,255,0) 72%);
    pointer-events: none;
}}
.summary-card-header {{
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    gap: 0.68rem;
    margin-bottom: 0.9rem;
}}
.summary-card-icon {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.45rem;
    height: 2.45rem;
    border-radius: 16px;
    background: var(--summary-accent-soft);
    color: var(--summary-accent);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.62), 0 10px 22px rgba(56, 58, 53, 0.06);
}}
.summary-card-icon svg {{
    width: 1.18rem;
    height: 1.18rem;
    stroke: currentColor;
    fill: none;
    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
}}
.summary-card-label {{
    color: #646874;
    font-family: var(--font-display);
    font-size: 0.88rem;
    font-weight: 700;
    letter-spacing: 0.01em;
}}
.summary-card-value {{
    position: relative;
    z-index: 1;
    display: flex;
    align-items: flex-end;
    gap: 0.34rem;
    min-height: 3.1rem;
}}
.summary-card-value.is-empty {{
    align-items: center;
}}
.summary-card-number {{
    color: var(--elite-graphite);
    font-family: var(--font-display);
    font-size: 2.18rem;
    font-weight: 800;
    line-height: 1;
    font-variant-numeric: tabular-nums;
    letter-spacing: -0.04em;
}}
.summary-card-unit {{
    margin-bottom: 0.3rem;
    color: #5f6472;
    font-size: 0.88rem;
    font-weight: 600;
}}
.summary-card-empty {{
    color: #757985;
    font-size: 1rem;
    font-weight: 600;
}}
.summary-card-footer {{
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    margin-top: auto;
    padding-top: 0.72rem;
}}
.summary-card-chip {{
    display: inline-flex;
    align-items: center;
    padding: 0.24rem 0.62rem;
    border-radius: 999px;
    background: var(--summary-accent-soft);
    color: var(--summary-accent);
    font-size: 0.74rem;
    font-weight: 700;
    letter-spacing: 0.02em;
}}
.summary-card-period {{
    color: #6a6d76;
    font-size: 0.78rem;
    font-weight: 500;
    text-align: right;
}}
.summary-card-day-list-wrap {{
    position: relative;
    z-index: 1;
    max-height: 198px;
    overflow: auto;
    padding-right: 0.15rem;
}}
.summary-card-day-list {{
    display: flex;
    flex-direction: column;
    gap: 0.18rem;
}}
.summary-card-day-item {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.7rem;
    padding: 0.52rem 0.04rem;
    border-bottom: 1px solid rgba(76, 70, 120, 0.08);
}}
.summary-card-day-item:last-child {{
    border-bottom: none;
    padding-bottom: 0.08rem;
}}
.summary-card-day-date {{
    color: #676c79;
    font-size: 0.8rem;
    font-weight: 700;
    line-height: 1.35;
}}
.summary-card-day-reading {{
    display: inline-flex;
    align-items: baseline;
    gap: 0.2rem;
    justify-content: flex-end;
    text-align: right;
    flex: 0 0 auto;
}}
.summary-card-day-number {{
    color: var(--elite-graphite);
    font-family: var(--font-display);
    font-size: 0.96rem;
    font-weight: 800;
    line-height: 1;
    letter-spacing: -0.02em;
}}
.summary-card-day-unit {{
    color: #6a6e78;
    font-size: 0.76rem;
    font-weight: 600;
    line-height: 1.2;
}}
.summary-card-day-empty {{
    color: #8a8d97;
    font-size: 0.84rem;
    font-weight: 600;
}}
.info-panels-layout {{
    margin: 0.4rem 0 1.15rem 0;
}}
.info-panels-grid {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1rem;
    align-items: stretch;
}}
.info-panel-card {{
    position: relative;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    min-height: 232px;
    padding: 1.18rem 1.22rem 1.14rem 1.22rem;
    border-radius: 26px;
    border: 1px solid rgba(76, 70, 120, 0.08);
    background:
        linear-gradient(180deg, rgba(255,255,255,0.94) 0%, rgba(247,244,238,0.96) 100%);
    box-shadow:
        0 20px 42px rgba(45, 48, 64, 0.08),
        inset 0 1px 0 rgba(255,255,255,0.70);
    backdrop-filter: blur(12px);
}}
.info-panel-card::before {{
    content: '';
    position: absolute;
    inset: 0 0 auto 0;
    height: 4px;
    background: linear-gradient(90deg, var(--info-accent), var(--info-accent-soft));
}}
.info-panel-card::after {{
    content: '';
    position: absolute;
    right: -22px;
    bottom: -30px;
    width: 165px;
    height: 165px;
    background: radial-gradient(circle, var(--info-accent-soft) 0%, rgba(255,255,255,0) 70%);
    pointer-events: none;
}}
.info-panel-card--compact {{
    min-height: 232px;
}}
.info-panel-card--observaciones {{
    height: 100%;
}}
.info-panel-card * {{
    position: relative;
    z-index: 1;
}}
.info-panel-header {{
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.85rem;
    margin-bottom: 0.8rem;
}}
.info-panel-header-main {{
    display: flex;
    align-items: flex-start;
    gap: 0.68rem;
    min-width: 0;
    flex: 1 1 auto;
}}
.info-panel-heading {{
    display: flex;
    flex-direction: column;
    gap: 0;
    min-width: 0;
}}
.info-panel-icon {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2.55rem;
    height: 2.55rem;
    border-radius: 17px;
    background: var(--info-accent-soft);
    color: var(--info-accent);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.62), 0 10px 22px rgba(56, 58, 53, 0.05);
}}
.info-panel-icon svg {{
    width: 1.08rem;
    height: 1.08rem;
    stroke: currentColor;
    fill: none;
    stroke-width: 1.8;
    stroke-linecap: round;
    stroke-linejoin: round;
}}
.info-panel-title {{
    margin: 0;
    color: var(--elite-graphite);
    font-family: var(--font-display);
    font-size: 1.02rem;
    font-weight: 800;
    line-height: 1.16;
    letter-spacing: -0.03em;
    word-break: keep-all;
    overflow-wrap: normal;
    hyphens: none;
}}
.info-panel-tag {{
    display: inline-flex;
    align-items: center;
    padding: 0.28rem 0.64rem;
    border-radius: 999px;
    background: var(--info-accent-soft);
    color: var(--info-accent);
    border: 1px solid rgba(76, 70, 120, 0.08);
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.62);
    font-size: 0.68rem;
    font-weight: 800;
    letter-spacing: 0.05em;
    white-space: nowrap;
    text-transform: uppercase;
}}
.info-panel-body {{
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    gap: 0.78rem;
    justify-content: flex-start;
    color: #555963;
    font-size: 0.93rem;
    line-height: 1.58;
}}
.info-panel-body p {{
    margin: 0;
}}
.info-panel-body p + p {{
    margin-top: 0.5rem;
}}
.info-panel-copy {{
    color: #4f545f;
    font-size: 0.91rem;
    line-height: 1.56;
}}
.info-panel-stat-row {{
    display: flex;
    align-items: flex-end;
    gap: 0.55rem;
}}
.info-panel-stat-value {{
    color: var(--elite-graphite);
    font-family: var(--font-display);
    font-size: 2.15rem;
    font-weight: 800;
    line-height: 1;
    letter-spacing: -0.04em;
}}
.info-panel-stat-caption {{
    margin-bottom: 0.22rem;
    color: #747884;
    font-size: 0.84rem;
    font-weight: 600;
}}
.info-panel-empty-state {{
    display: flex;
    flex-direction: column;
    gap: 0.62rem;
    justify-content: center;
    min-height: 100%;
}}
.info-panel-empty-state--centered {{
    align-items: flex-start;
}}
.info-panel-empty-title {{
    color: var(--elite-graphite);
    font-family: var(--font-display);
    font-size: 1rem;
    font-weight: 800;
    line-height: 1.3;
}}
.info-panel-empty {{
    color: #7b7f8a;
    font-style: normal;
}}
.info-panel-list {{
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.18rem;
}}
.info-panel-list-wrap {{
    max-height: 144px;
    overflow: auto;
    padding-right: 0.2rem;
}}
.info-panel-day-scroll {{
    max-height: 168px;
    overflow: auto;
    padding-right: 0.2rem;
}}
.info-panel-day-groups {{
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
}}
.info-panel-day-card {{
    padding: 0.72rem 0.78rem;
    border-radius: 16px;
    border: 1px solid rgba(76, 70, 120, 0.07);
    background: linear-gradient(180deg, rgba(255,255,255,0.86), rgba(246,242,235,0.84));
}}
.info-panel-day-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.65rem;
    margin-bottom: 0.45rem;
}}
.info-panel-day-date {{
    color: var(--elite-graphite);
    font-family: var(--font-display);
    font-size: 0.8rem;
    font-weight: 700;
    line-height: 1.3;
}}
.info-panel-day-chip {{
    display: inline-flex;
    align-items: center;
    padding: 0.22rem 0.56rem;
    border-radius: 999px;
    background: rgba(76, 70, 120, 0.08);
    color: var(--elite-hero);
    font-size: 0.68rem;
    font-weight: 700;
    white-space: nowrap;
}}
.info-panel-day-lines {{
    display: flex;
    flex-direction: column;
    gap: 0.28rem;
}}
.info-panel-day-line {{
    color: #4f545f;
    font-size: 0.88rem;
    line-height: 1.42;
}}
.info-panel-day-line.is-muted {{
    color: #7a7e89;
}}
.info-panel-day-state-row {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.55rem;
}}
.info-panel-list-item {{
    display: flex;
    align-items: flex-start;
    gap: 0.7rem;
    padding: 0.52rem 0;
    border-bottom: 1px solid rgba(84, 83, 134, 0.08);
}}
.info-panel-list-item:last-child {{
    border-bottom: none;
    padding-bottom: 0;
}}
.info-panel-dot {{
    width: 0.62rem;
    height: 0.62rem;
    border-radius: 999px;
    margin-top: 0.42rem;
    background: var(--info-accent);
    box-shadow: 0 0 0 6px var(--info-accent-soft);
    flex: 0 0 auto;
}}
.info-panel-list-text {{
    color: #4f545f;
    font-size: 0.95rem;
    line-height: 1.5;
}}
.info-panel-state {{
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 0.7rem;
    margin-bottom: 0.72rem;
}}
.info-panel-state-badge {{
    display: inline-flex;
    align-items: center;
    padding: 0.34rem 0.78rem;
    border-radius: 999px;
    font-size: 0.82rem;
    font-weight: 700;
    letter-spacing: 0.01em;
}}
.info-panel-state-text {{
    color: var(--elite-graphite);
    font-family: var(--font-display);
    font-size: 0.98rem;
    font-weight: 800;
    line-height: 1.3;
}}
.info-panel-footer-note {{
    margin-top: auto;
    color: #727783;
    font-size: 0.84rem;
    line-height: 1.5;
}}
div.stButton > button {{
    border-radius: 999px;
    border: 1px solid rgba(76, 70, 120, 0.18);
    background: linear-gradient(135deg, #5e578f 0%, #433d6b 100%);
    color: var(--elite-white);
    font-family: var(--font-display);
    font-weight: 800;
    padding: 0.56rem 1.1rem;
    letter-spacing: 0.01em;
    box-shadow: 0 14px 30px rgba(46, 39, 79, 0.24);
}}
div.stButton > button:hover {{
    border-color: rgba(76, 70, 120, 0.30);
    color: var(--elite-white);
    background: linear-gradient(135deg, #6a639c 0%, #4c4678 100%);
    transform: translateY(-1px);
}}
div[data-testid="stTabs"] [data-baseweb="tab-list"] {{
    gap: 0.55rem;
}}
button[data-baseweb="tab"] {{
    border-radius: 999px;
    padding: 0.58rem 0.96rem;
    border: 1px solid rgba(76, 70, 120, 0.12) !important;
    background: linear-gradient(180deg, rgba(255,255,255,0.74), rgba(247,244,238,0.94));
    box-shadow: 0 12px 26px rgba(45, 48, 64, 0.05);
    font-family: var(--font-display);
    font-weight: 800;
}}
button[data-baseweb="tab"]:hover {{
    border-color: rgba(76, 70, 120, 0.24) !important;
    background: linear-gradient(180deg, rgba(255,255,255,0.92), rgba(247,244,238,1));
}}
button[data-baseweb="tab"][aria-selected="true"] {{
    color: var(--elite-white) !important;
    background: linear-gradient(135deg, #655e98 0%, #4c4678 100%);
    border-color: rgba(76, 70, 120, 0.18) !important;
    box-shadow: 0 16px 30px rgba(46, 39, 79, 0.18);
}}
div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{
    display: none !important;
}}
div[data-testid="stTabs"] [data-baseweb="tab-border"] {{
    background: rgba(76, 70, 120, 0.10) !important;
}}
div[data-testid="stPlotlyChart"],
div[data-testid="stDataFrame"] {{
    border-radius: 24px;
    border: 1px solid rgba(76, 70, 120, 0.08);
    background: linear-gradient(180deg, rgba(255, 255, 255, 0.86), rgba(247, 244, 238, 0.82));
    box-shadow: 0 20px 46px rgba(45, 48, 64, 0.07);
    padding: 0.45rem 0.45rem 0.2rem 0.45rem;
    backdrop-filter: blur(12px);
}}
[data-testid="stMetric"] {{
    background: rgba(255, 255, 255, 0.82);
    border-radius: 18px;
    border: 1px solid rgba(76, 70, 120, 0.08);
    box-shadow: 0 12px 28px rgba(45, 48, 64, 0.06);
    padding: 0.35rem 0.6rem;
}}
[data-testid="stInfo"],
[data-testid="stWarning"],
[data-testid="stSuccess"],
[data-testid="stError"] {{
    border-radius: 18px;
    border-width: 1px;
}}
.analysis-hero {{
    position: relative;
    overflow: hidden;
    margin: 0.2rem 0 1rem 0;
    padding: 1.2rem 1.22rem 1.08rem 1.22rem;
    border-radius: 28px;
    border: 1px solid rgba(76, 70, 120, 0.10);
    background:
        radial-gradient(circle at top right, rgba(214, 229, 236, 0.45), rgba(255,255,255,0) 34%),
        linear-gradient(180deg, rgba(255,255,255,0.94), rgba(247,244,238,0.96));
    box-shadow: 0 24px 48px rgba(45, 48, 64, 0.08);
}}
.analysis-hero::before {{
    content: '';
    position: absolute;
    inset: 0 0 auto 0;
    height: 5px;
    background: linear-gradient(90deg, var(--elite-hero), rgba(214, 229, 236, 0.82));
}}
.analysis-hero-header {{
    position: relative;
    z-index: 1;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 0.9rem;
    margin-bottom: 0.8rem;
}}
.analysis-kicker {{
    margin: 0 0 0.18rem 0;
    color: var(--elite-hero);
    font-size: 0.76rem;
    font-weight: 800;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}}
.analysis-title {{
    margin: 0;
    color: var(--elite-graphite);
    font-family: var(--font-display);
    font-size: 2rem;
    font-weight: 800;
    line-height: 1.05;
}}
.analysis-pill {{
    display: inline-flex;
    align-items: center;
    padding: 0.48rem 0.88rem;
    border-radius: 999px;
    background: rgba(76, 70, 120, 0.10);
    color: var(--elite-hero);
    font-size: 0.77rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    white-space: nowrap;
}}
.analysis-copy {{
    position: relative;
    z-index: 1;
    margin: 0;
    max-width: 58rem;
    color: #5e6471;
    font-size: 1rem;
    line-height: 1.72;
}}
.analysis-meta {{
    position: relative;
    z-index: 1;
    display: flex;
    flex-wrap: wrap;
    gap: 0.45rem;
    margin-top: 0.95rem;
}}
.analysis-meta-chip {{
    display: inline-flex;
    align-items: center;
    padding: 0.34rem 0.72rem;
    border-radius: 999px;
    background: rgba(255,255,255,0.76);
    border: 1px solid rgba(76, 70, 120, 0.10);
    color: #626777;
    font-size: 0.82rem;
    font-weight: 600;
}}
.analysis-metrics-grid {{
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.85rem;
    margin: 0 0 1rem 0;
}}
.analysis-metric-card {{
    position: relative;
    overflow: hidden;
    padding: 0.95rem 1rem 1rem 1rem;
    border-radius: 22px;
    border: 1px solid rgba(76, 70, 120, 0.08);
    background: linear-gradient(180deg, rgba(255,255,255,0.90), rgba(247,244,238,0.94));
    box-shadow: 0 18px 36px rgba(45, 48, 64, 0.06);
}}
.analysis-metric-card::before {{
    content: '';
    position: absolute;
    inset: 0 0 auto 0;
    height: 4px;
    background: linear-gradient(90deg, var(--analysis-accent), rgba(255,255,255,0.20));
}}
.analysis-metric-label {{
    margin: 0;
    color: #676c79;
    font-size: 0.84rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    text-transform: uppercase;
}}
.analysis-metric-value {{
    margin: 0.45rem 0 0 0;
    color: var(--elite-graphite);
    font-family: var(--font-display);
    font-size: 2.42rem;
    font-weight: 800;
    line-height: 1;
    letter-spacing: -0.04em;
}}
.analysis-note {{
    margin: 0.1rem 0 0.95rem 0;
    color: #6d727f;
    font-size: 0.9rem;
}}
[data-testid="stRadio"] label,
[data-testid="stSelectbox"] label,
[data-testid="stDateInput"] label {{
    font-family: var(--font-body);
    font-weight: 500;
}}
[data-testid="stSidebar"] .stRadio > div,
[data-testid="stSidebar"] .stDateInput > div,
[data-testid="stSidebar"] .stSelectbox > div[data-baseweb="select"] {{
    background: rgba(255, 255, 255, 0.08);
    border-radius: 13px;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] {{
    display: grid;
    gap: 0.24rem;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label {{
    width: 100%;
    margin: 0;
    padding: 0.42rem 0.56rem;
    border-radius: 18px;
    border: 1px solid rgba(255, 255, 255, 0.10);
    background: linear-gradient(180deg, rgba(255,255,255,0.12), rgba(255,255,255,0.06));
    box-shadow: 0 10px 20px rgba(0, 0, 0, 0.12);
    transition: background 0.2s ease, transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}}
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:hover {{
    background: linear-gradient(180deg, rgba(255,255,255,0.18), rgba(255,255,255,0.10));
    border-color: rgba(214, 229, 236, 0.42);
    box-shadow: 0 14px 28px rgba(0, 0, 0, 0.16);
    transform: translateX(2px);
}}
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {{
    border-color: rgba(255, 255, 255, 0.26);
    background: linear-gradient(135deg, rgba(124, 115, 177, 0.92), rgba(82, 75, 130, 0.96));
    box-shadow: inset 0 1px 0 rgba(255,255,255,0.20), 0 16px 30px rgba(27, 23, 53, 0.30);
}}
[data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label p {{
    font-size: 0.92rem;
    font-weight: 700;
}}
[data-testid="stSidebar"] .stDateInput > label,
[data-testid="stSidebar"] .stSelectbox > label {{
    display: none;
}}
[data-testid="stSidebar"] .stSelectbox > div[data-baseweb="select"] span,
[data-testid="stSidebar"] .stSelectbox > div[data-baseweb="select"] div,
[data-testid="stSidebar"] .stMultiSelect > div[data-baseweb="select"] span,
[data-testid="stSidebar"] .stMultiSelect > div[data-baseweb="select"] div,
[data-testid="stSidebar"] .stDateInput input {{
    color: var(--elite-ink) !important;
    -webkit-text-fill-color: var(--elite-ink) !important;
    font-weight: 500;
    font-size: 0.94rem;
}}
[data-testid="stSidebar"] .stDateInput input::placeholder {{
    color: rgba(56, 58, 53, 0.70) !important;
    -webkit-text-fill-color: rgba(56, 58, 53, 0.70) !important;
}}
[data-testid="stSidebar"] .stSelectbox svg,
[data-testid="stSidebar"] .stMultiSelect svg,
[data-testid="stSidebar"] .stDateInput svg {{
    fill: var(--elite-hero) !important;
}}
@media (max-width: 980px) {{
    .hero-card {{
        grid-template-columns: 1fr;
    }}
    .hero-copy h1 {{
        font-size: 1.7rem;
    }}
    .analysis-metrics-grid {{
        grid-template-columns: 1fr;
    }}
    .analysis-hero-header {{
        flex-direction: column;
    }}
    .analysis-pill {{
        align-self: flex-start;
    }}
}}
@media (max-width: 1180px) {{
    .summary-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .info-panels-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .info-panel-card--observaciones {{
        grid-column: 1 / -1;
    }}
    .info-panel-card,
    .info-panel-card--compact {{
        min-height: auto;
    }}
}}
@media (max-width: 760px) {{
    .info-panels-grid {{
        grid-template-columns: 1fr;
    }}
    .info-panel-card--observaciones {{
        grid-column: auto;
    }}
}}
@media (max-width: 680px) {{
    .summary-grid {{
        grid-template-columns: 1fr;
    }}
    .summary-card-footer {{
        flex-direction: column;
        align-items: flex-start;
    }}
    .summary-card-period {{
        text-align: left;
    }}
    .info-panel-header {{
        flex-direction: column;
        align-items: flex-start;
    }}
    .info-panel-header-main {{
        width: 100%;
    }}
}}
</style>
""", unsafe_allow_html=True)
st.markdown(
    f"""
    <div class="hero-card">
        <div class="hero-logo-shell">
            {logo_html}
        </div>
        <div class="hero-copy">
            <p class="hero-kicker">The Elite Flower • Dashboard Ejecutivo</p>
            <h1>Monitoreo de Variables y Automatización</h1>
            <p class="hero-subtitle">
                Vista ejecutiva para el seguimiento de variables ambientales, cortinas y operación por bloques.
            </p>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

if DASHBOARD_VIDEO_URL.strip():
    youtube_embed_url = _youtube_embed_url(DASHBOARD_VIDEO_URL)
    if youtube_embed_url:
        components.iframe(youtube_embed_url, height=430, scrolling=False)
    else:
        st.video(DASHBOARD_VIDEO_URL)

# --- Configuracion de URLs (Mover aqui para evitar NameError) ---
URL_VARIABLES = "https://raw.githubusercontent.com/juandavdidtejedormedina-rgb/dashboard-invernaderos/main/Datos_variables.xlsx"
URL_CORTINAS = "https://raw.githubusercontent.com/juandavdidtejedormedina-rgb/dashboard-invernaderos/main/Registro_Cortinas_Final.xlsx"

# Definición de la función de descarga
@st.cache_data(show_spinner="Descargando datos desde el repositorio...")
def descargar_desde_github(url):
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content
    except Exception as e:
        st.error(f"Error al conectar con GitHub: {e}")
        return None

archivo_variables_bytes = descargar_desde_github(URL_VARIABLES)
archivo_cortinas_bytes = descargar_desde_github(URL_CORTINAS)

# 3. Funciones de carga de datos con corrección de FECHAS

def _limpiar_columnas(df):
    df = df.copy()
    df.columns = (
        df.columns.str.strip()
            .str.replace(r'\s*B\d+\s*$', '', regex=True)
            .str.replace(r'\s+', ' ', regex=True)
    )
    return df


def _leer_excel_desde_bytes(ruta_bytes, sheet_name, **kwargs):
    return pd.read_excel(
        io.BytesIO(ruta_bytes),
        sheet_name=sheet_name,
        engine="openpyxl",
        **kwargs
    )


def _build_normalized_text_key(value):
    normalized = unicodedata.normalize('NFKD', str(value))
    normalized = ''.join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace('µ', 'u').replace('°', ' ')
    normalized = normalized.lower()
    normalized = re.sub(r'[^a-z0-9]+', ' ', normalized)
    return re.sub(r'\s+', ' ', normalized).strip()


def _normalize_variable_column_name(column_name):
    text = re.sub(r'\s+', ' ', str(column_name).strip())
    normalized_key = _build_normalized_text_key(text)

    if normalized_key == 'datetime':
        return 'DateTime'
    if normalized_key == 'fecha':
        return 'Fecha'
    if normalized_key == 'hora':
        return 'Hora'

    normalized_key = re.sub(r'\bb\d+\b', ' ', normalized_key)
    normalized_key = re.sub(r'\bumol\b.*$', ' ', normalized_key)
    normalized_key = re.sub(r'\bg\b$', ' ', normalized_key)
    normalized_key = re.sub(r'\bc\b$', ' ', normalized_key)
    normalized_key = re.sub(r'\s+', ' ', normalized_key).strip()

    if 'temperatura' in normalized_key:
        return 'Temperatura'
    if 'humedad relativa' in normalized_key:
        return 'Humedad Relativa'
    if 'radiacion par' in normalized_key:
        return 'Radiación PAR'
    if 'gramos de agua' in normalized_key:
        return 'Gramos de agua'

    return text


def _combine_fecha_hora_columns(df):
    if 'Fecha' not in df.columns or 'Hora' not in df.columns:
        return df

    df = df.copy()
    fecha_series = pd.to_datetime(df['Fecha'], errors='coerce', dayfirst=True)
    hora_series = df['Hora'].astype(str).str.strip().replace({'NaT': '', 'nan': '', 'None': ''})
    df['DateTime'] = pd.to_datetime(
        fecha_series.dt.strftime('%Y-%m-%d') + ' ' + hora_series,
        errors='coerce'
    )
    return df


def _prepare_variables_sheet(df_sheet):
    df_sheet = df_sheet.copy()
    df_sheet.columns = [_normalize_variable_column_name(col) for col in df_sheet.columns]
    if 'DateTime' not in df_sheet.columns and {'Fecha', 'Hora'}.issubset(df_sheet.columns):
        df_sheet = _combine_fecha_hora_columns(df_sheet)
    return df_sheet


@st.cache_data
def cargar_datos(ruta_bytes):
    if not ruta_bytes:
        return pd.DataFrame()

    try:
        xls = pd.ExcelFile(io.BytesIO(ruta_bytes), engine="openpyxl")
        registros = []

        for sheet in [s for s in xls.sheet_names if s.lower() != 'plantilla']:
            df_sheet = pd.DataFrame()

            for read_kwargs in ({}, {'skiprows': 1}):
                candidate = _leer_excel_desde_bytes(ruta_bytes, sheet_name=sheet, **read_kwargs)
                candidate = _prepare_variables_sheet(candidate)
                candidate = _limpiar_columnas(candidate)
                if 'DateTime' in candidate.columns:
                    df_sheet = candidate
                    break

            if 'DateTime' not in df_sheet.columns:
                continue

            df_sheet['DateTime'] = pd.to_datetime(df_sheet['DateTime'], errors='coerce', dayfirst=True)
            df_sheet = df_sheet.dropna(subset=['DateTime']).sort_values('DateTime')
            df_sheet['Fecha_Filtro'] = df_sheet['DateTime'].dt.date
            df_sheet['Bloque'] = sheet

            for col in SENSOR_VARIABLES:
                if col in df_sheet.columns:
                    df_sheet[col] = pd.to_numeric(df_sheet[col].astype(str).str.replace(',', '.'), errors='coerce')

            registros.append(df_sheet)

        return pd.concat(registros, ignore_index=True) if registros else pd.DataFrame()
    except Exception as e:
        st.error(f"Error técnico: {e}")
        return pd.DataFrame()


def parse_time(value):
    if pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.time()
    if hasattr(value, 'hour') and hasattr(value, 'minute'):
        return value
    text = str(value).strip()
    text = text.replace('a.m.', 'AM').replace('p.m.', 'PM').replace('a. m.', 'AM').replace('p. m.', 'PM')
    try:
        parsed = pd.to_datetime(text, errors='coerce')
        return parsed.time() if not pd.isna(parsed) else None
    except Exception:
        return None


def _coerce_sidebar_date(value, fallback):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, date):
        return value
    return fallback


def _sidebar_icon_svg(icon_name):
    icons = {
        'filter': (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="M4 7h16"></path>'
            '<path d="M7 12h10"></path>'
            '<path d="M10 17h4"></path>'
            '</svg>'
        ),
        'calendar': (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<rect x="3" y="5" width="18" height="16" rx="2"></rect>'
            '<path d="M16 3v4"></path>'
            '<path d="M8 3v4"></path>'
            '<path d="M3 10h18"></path>'
            '</svg>'
        ),
        'location': (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="M12 21s6-5.2 6-11a6 6 0 1 0-12 0c0 5.8 6 11 6 11Z"></path>'
            '<circle cx="12" cy="10" r="2.4"></circle>'
            '</svg>'
        )
    }
    return icons.get(icon_name, '')


def _sidebar_field_label(icon_name, text):
    st.markdown(
        (
            f'<div class="sidebar-field-label">'
            f'<span class="sidebar-field-icon">{_sidebar_icon_svg(icon_name)}</span>'
            f'<span>{html.escape(text)}</span>'
            f'</div>'
        ),
        unsafe_allow_html=True
    )


def _hex_to_rgba(hex_color, alpha):
    color = str(hex_color).strip().lstrip('#')
    if len(color) != 6:
        return f'rgba(84, 83, 134, {alpha})'

    try:
        red = int(color[0:2], 16)
        green = int(color[2:4], 16)
        blue = int(color[4:6], 16)
    except ValueError:
        return f'rgba(84, 83, 134, {alpha})'

    return f'rgba({red}, {green}, {blue}, {alpha})'


def _format_summary_number(value, decimals):
    if decimals <= 0:
        return f"{round(value):,.0f}".replace(',', '.')

    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(',', '_').replace('.', ',').replace('_', '.')


def _get_summary_metric_config(var_name):
    normalized_key = _build_normalized_text_key(var_name)

    if normalized_key.startswith('temperatura'):
        return {
            'label': 'Temperatura',
            'unit_html': '&deg;C',
            'decimals': 1,
            'icon_svg': (
                '<svg viewBox="0 0 24 24" aria-hidden="true">'
                '<path d="M10 14.5V6a2 2 0 1 1 4 0v8.5a4 4 0 1 1-4 0Z"></path>'
                '<path d="M12 9v5"></path>'
                '</svg>'
            )
        }
    if normalized_key.startswith('humedad relativa'):
        return {
            'label': 'Humedad Relativa',
            'unit_html': '%',
            'decimals': 1,
            'icon_svg': (
                '<svg viewBox="0 0 24 24" aria-hidden="true">'
                '<path d="M12 3C9.2 7.1 6.5 9.8 6.5 13a5.5 5.5 0 0 0 11 0C17.5 9.8 14.8 7.1 12 3Z"></path>'
                '</svg>'
            )
        }
    if normalized_key.startswith('radiacion par'):
        return {
            'label': 'Radiación PAR',
            'unit_html': 'umol m<sup>-2</sup> s<sup>-1</sup>',
            'decimals': 0,
            'icon_svg': (
                '<svg viewBox="0 0 24 24" aria-hidden="true">'
                '<circle cx="12" cy="12" r="3.5"></circle>'
                '<path d="M12 2.5v2.4"></path>'
                '<path d="M12 19.1v2.4"></path>'
                '<path d="M4.9 4.9 6.6 6.6"></path>'
                '<path d="M17.4 17.4 19.1 19.1"></path>'
                '<path d="M2.5 12h2.4"></path>'
                '<path d="M19.1 12h2.4"></path>'
                '<path d="M4.9 19.1 6.6 17.4"></path>'
                '<path d="M17.4 6.6 19.1 4.9"></path>'
                '</svg>'
            )
        }
    if normalized_key.startswith('gramos de agua'):
        return {
            'label': 'Gramos de agua',
            'unit_html': 'g',
            'decimals': 1,
            'icon_svg': (
                '<svg viewBox="0 0 24 24" aria-hidden="true">'
                '<path d="M4 15c1.4 0 1.4-1.8 2.8-1.8S8.2 15 9.6 15s1.4-1.8 2.8-1.8S13.8 15 15.2 15s1.4-1.8 2.8-1.8S19.4 15 20.8 15"></path>'
                '<path d="M4 18.8c1.4 0 1.4-1.8 2.8-1.8s1.4 1.8 2.8 1.8 1.4-1.8 2.8-1.8 1.4 1.8 2.8 1.8 1.4-1.8 2.8-1.8 1.4 1.8 2.8 1.8"></path>'
                '<path d="M7 9.2h10"></path>'
                '</svg>'
            )
        }

    return {
        'label': str(var_name),
        'unit_html': '',
        'decimals': 1,
        'icon_svg': (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<circle cx="12" cy="12" r="5"></circle>'
            '</svg>'
        )
    }


def _get_summary_mode_config(summary_mode, single_day):
    mode_key = str(summary_mode).strip().lower()
    mode_map = {
        'promedio': {
            'label': 'Promedio',
            'calculator': lambda serie: float(serie.mean())
        },
        'máximo': {
            'label': 'Máximo',
            'calculator': lambda serie: float(serie.max())
        },
        'maximo': {
            'label': 'Máximo',
            'calculator': lambda serie: float(serie.max())
        },
        'mínimo': {
            'label': 'Mínimo',
            'calculator': lambda serie: float(serie.min())
        },
        'minimo': {
            'label': 'Mínimo',
            'calculator': lambda serie: float(serie.min())
        }
    }
    selected_mode = mode_map.get(mode_key, mode_map['promedio'])
    chip_text = (
        f"{selected_mode['label']} diario"
        if single_day else
        f"{selected_mode['label']} por día"
    )
    return {
        'label': selected_mode['label'],
        'calculator': selected_mode['calculator'],
        'chip_text': chip_text
    }


def _get_summary_selected_dates(fecha_variables):
    if fecha_variables is None:
        return []

    fecha_inicio, fecha_fin = fecha_variables
    return [item.date() for item in pd.date_range(start=fecha_inicio, end=fecha_fin, freq='D')]


def _get_summary_daily_values(df_variables, var_name, fecha_variables, summary_mode_config):
    if df_variables.empty or var_name not in df_variables.columns or fecha_variables is None:
        return []

    if 'Fecha_Filtro' in df_variables.columns:
        fechas = pd.Series(df_variables['Fecha_Filtro'])
    elif 'DateTime' in df_variables.columns:
        fechas = pd.to_datetime(df_variables['DateTime'], errors='coerce').dt.date
    else:
        return []

    working_df = pd.DataFrame({
        'Fecha': fechas,
        'Valor': pd.to_numeric(df_variables[var_name], errors='coerce')
    }).dropna(subset=['Fecha'])

    valores_por_dia = {}
    for fecha, datos_dia in working_df.groupby('Fecha', sort=True):
        serie = datos_dia['Valor'].dropna()
        valores_por_dia[fecha] = (
            summary_mode_config['calculator'](serie)
            if not serie.empty else None
        )

    return [
        {
            'fecha': fecha,
            'value': valores_por_dia.get(fecha)
        }
        for fecha in _get_summary_selected_dates(fecha_variables)
    ]


def _build_summary_daily_list_html(daily_values, config):
    if not daily_values:
        return (
            '<div class="summary-card-value is-empty">'
            '<span class="summary-card-empty">Sin datos</span>'
            '</div>'
        )

    rows = []
    for item in daily_values:
        fecha_label = _format_info_day_label(item.get('fecha'))
        value = item.get('value')

        if value is None or pd.isna(value):
            value_html = '<span class="summary-card-day-empty">Sin datos</span>'
        else:
            number_text = _format_summary_number(float(value), config['decimals'])
            value_html = (
                '<span class="summary-card-day-reading">'
                f'<span class="summary-card-day-number">{number_text}</span>'
                f'<span class="summary-card-day-unit">{config["unit_html"]}</span>'
                '</span>'
            )

        rows.append(
            (
                '<div class="summary-card-day-item">'
                f'<span class="summary-card-day-date">{html.escape(fecha_label)}</span>'
                f'{value_html}'
                '</div>'
            )
        )

    return (
        '<div class="summary-card-day-list-wrap">'
        f'<div class="summary-card-day-list">{"".join(rows)}</div>'
        '</div>'
    )


def _build_summary_cards_html(df_variables, fecha_variables, summary_mode='Promedio'):
    if fecha_variables is None:
        return ''

    fecha_inicio, fecha_fin = fecha_variables
    single_day = fecha_inicio == fecha_fin
    summary_mode_config = _get_summary_mode_config(summary_mode, single_day)
    period_chip = summary_mode_config['chip_text']
    period_text = (
        fecha_inicio.strftime('%d/%m/%Y')
        if single_day else
        f"{fecha_inicio.strftime('%d/%m/%Y')} - {fecha_fin.strftime('%d/%m/%Y')}"
    )

    cards_html = []

    for var_name in SENSOR_VARIABLES:
        config = _get_summary_metric_config(var_name)
        accent_color = VARIABLE_COLORS.get(var_name, BRAND_COLORS['hero'])
        accent_soft = _hex_to_rgba(accent_color, 0.14)
        value_markup = (
            '<div class="summary-card-value is-empty">'
            '<span class="summary-card-empty">Sin datos</span>'
            '</div>'
        )

        if not df_variables.empty and var_name in df_variables.columns:
            if single_day:
                serie = pd.to_numeric(df_variables[var_name], errors='coerce').dropna()
                if not serie.empty:
                    summary_value = summary_mode_config['calculator'](serie)
                    number_text = _format_summary_number(summary_value, config['decimals'])
                    value_markup = (
                        '<div class="summary-card-value">'
                        f'<span class="summary-card-number">{number_text}</span>'
                        f'<span class="summary-card-unit">{config["unit_html"]}</span>'
                        '</div>'
                    )
            else:
                daily_values = _get_summary_daily_values(
                    df_variables,
                    var_name,
                    fecha_variables,
                    summary_mode_config
                )
                value_markup = _build_summary_daily_list_html(daily_values, config)

        cards_html.append(
            (
                f'<div class="summary-card" style="--summary-accent: {accent_color}; --summary-accent-soft: {accent_soft};">'
                '<div class="summary-card-header">'
                f'<span class="summary-card-icon">{config["icon_svg"]}</span>'
                f'<span class="summary-card-label">{html.escape(config["label"])}</span>'
                '</div>'
                f'{value_markup}'
                '<div class="summary-card-footer">'
                f'<span class="summary-card-chip">{html.escape(period_chip)}</span>'
                f'<span class="summary-card-period">{html.escape(period_text)}</span>'
                '</div>'
                '</div>'
            )
        )

    return f'<div class="summary-grid">{"".join(cards_html)}</div>'


def _render_summary_cards(df_variables, fecha_variables, summary_mode='Promedio'):
    cards_html = _build_summary_cards_html(df_variables, fecha_variables, summary_mode=summary_mode)
    if cards_html:
        st.markdown(cards_html, unsafe_allow_html=True)


def _render_summary_cards_selector(df_variables, fecha_variables):
    tab_promedio, tab_maximo, tab_minimo = st.tabs(["Promedio", "Máximo", "Mínimo"])

    with tab_promedio:
        _render_summary_cards(df_variables, fecha_variables, summary_mode='Promedio')

    with tab_maximo:
        _render_summary_cards(df_variables, fecha_variables, summary_mode='Máximo')

    with tab_minimo:
        _render_summary_cards(df_variables, fecha_variables, summary_mode='Mínimo')


def _info_panel_icon_svg(icon_name):
    icons = {
        'modificacion': (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="M4 7.5h16"></path>'
            '<path d="M7 12h10"></path>'
            '<path d="M10 16.5h4"></path>'
            '</svg>'
        ),
        'observaciones': (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="M8 9h8"></path>'
            '<path d="M8 13h5"></path>'
            '<path d="M6 20V5.8A1.8 1.8 0 0 1 7.8 4h8.4A1.8 1.8 0 0 1 18 5.8V20l-6-3-6 3Z"></path>'
            '</svg>'
        ),
        'culatas': (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="M12 3C9.2 7.1 6.5 9.8 6.5 13a5.5 5.5 0 0 0 11 0C17.5 9.8 14.8 7.1 12 3Z"></path>'
            '<path d="M12 9.2v5.2"></path>'
            '</svg>'
        )
    }
    return icons.get(icon_name, '')


def _render_info_panels(
    block_label,
    block_modification,
    culatas_observation,
    daily_annotations,
    rango_multiple,
    annotations_by_day=None,
    culatas_by_day=None
):
    period_context = 'del periodo' if rango_multiple else 'del día'
    period_tag = 'Periodo' if rango_multiple else 'Día'
    observation_title = 'Observaciones'
    culatas_title = 'Estado de culatas'
    block_title = 'Modificación aplicada'
    block_tag_text = str(block_label) if block_label else 'Sin bloque'
    block_tag = html.escape(block_tag_text)
    annotations_by_day = annotations_by_day or []
    culatas_by_day = culatas_by_day or []

    observations_html = ''
    if rango_multiple and annotations_by_day:
        annotation_count = sum(len(item.get('entries', [])) for item in annotations_by_day)
        annotation_label = 'evento registrado' if annotation_count == 1 else 'eventos registrados'
        day_groups = []

        for item in annotations_by_day:
            fecha_label = _format_info_day_label(item.get('fecha'))
            entries = item.get('entries', [])
            day_chip_text = 'Sin novedades' if not entries else (
                '1 evento' if len(entries) == 1 else f'{len(entries)} eventos'
            )
            day_lines = (
                ''.join(
                    f'<p class="info-panel-day-line">{html.escape(entry)}</p>'
                    for entry in entries
                )
                if entries else
                '<p class="info-panel-day-line is-muted">Sin anotaciones registradas.</p>'
            )
            day_groups.append(
                (
                    '<div class="info-panel-day-card">'
                    '<div class="info-panel-day-header">'
                    f'<span class="info-panel-day-date">{html.escape(fecha_label)}</span>'
                    f'<span class="info-panel-day-chip">{html.escape(day_chip_text)}</span>'
                    '</div>'
                    f'<div class="info-panel-day-lines">{day_lines}</div>'
                    '</div>'
                )
            )

        observations_html = (
            '<div class="info-panel-body">'
            '<div class="info-panel-stat-row">'
            f'<span class="info-panel-stat-value">{annotation_count}</span>'
            f'<span class="info-panel-stat-caption">{html.escape(annotation_label)}</span>'
            '</div>'
            f'<div class="info-panel-day-scroll"><div class="info-panel-day-groups">{"".join(day_groups)}</div></div>'
            '<p class="info-panel-footer-note">Eventos organizados por fecha dentro del periodo seleccionado.</p>'
            '</div>'
        )
    elif daily_annotations:
        annotation_count = len(daily_annotations)
        annotation_label = 'evento registrado' if annotation_count == 1 else 'eventos registrados'
        observation_items = []
        for item in daily_annotations:
            observation_items.append(
                (
                    '<li class="info-panel-list-item">'
                    '<span class="info-panel-dot"></span>'
                    f'<span class="info-panel-list-text">{html.escape(item)}</span>'
                    '</li>'
                )
            )
        observations_html = (
            '<div class="info-panel-body">'
            '<div class="info-panel-stat-row">'
            f'<span class="info-panel-stat-value">{annotation_count}</span>'
            f'<span class="info-panel-stat-caption">{html.escape(annotation_label)}</span>'
            '</div>'
            f'<div class="info-panel-list-wrap"><ul class="info-panel-list">{"".join(observation_items)}</ul></div>'
            f'<p class="info-panel-footer-note">Eventos registrados {period_context}.</p>'
            '</div>'
        )
    else:
        observations_html = (
            '<div class="info-panel-body">'
            '<div class="info-panel-empty-state info-panel-empty-state--centered">'
            '<span class="info-panel-state-badge" style="background: rgba(244, 199, 206, 0.18); color: #B56576;">Sin novedades</span>'
            '<p class="info-panel-empty-title">Sin novedades operativas</p>'
            f'<p class="info-panel-empty">No se registran anotaciones {period_context}.</p>'
            '</div>'
            '</div>'
        )

    mod_text = block_modification or 'No hay una modificación documentada para este bloque.'
    mod_html = (
        '<div class="info-panel-body">'
        f'<p class="info-panel-copy">{html.escape(mod_text)}</p>'
        f'<p class="info-panel-footer-note">Configuración de referencia para {block_tag}.</p>'
        '</div>'
    )

    culatas_state = culatas_observation or 'Sin información disponible'
    culatas_style = _get_culatas_state_style(culatas_state)
    culatas_badge_bg = culatas_style['badge_bg']
    culatas_badge_color = culatas_style['badge_color']
    culatas_tag = culatas_style['tag']

    if rango_multiple and culatas_by_day:
        day_states = []
        for item in culatas_by_day:
            fecha_label = _format_info_day_label(item.get('fecha'))
            state_text = item.get('state') or 'Sin información disponible'
            state_style = _get_culatas_state_style(state_text)
            day_states.append(
                (
                    '<div class="info-panel-day-card">'
                    '<div class="info-panel-day-header">'
                    f'<span class="info-panel-day-date">{html.escape(fecha_label)}</span>'
                    '</div>'
                    '<div class="info-panel-day-state-row">'
                    f'<span class="info-panel-state-badge" style="background:{state_style["badge_bg"]}; color:{state_style["badge_color"]};">{html.escape(state_style["tag"])}</span>'
                    f'<span class="info-panel-day-line">{html.escape(state_text)}</span>'
                    '</div>'
                    '</div>'
                )
            )

        culatas_html = (
            '<div class="info-panel-body">'
            f'<div class="info-panel-day-scroll"><div class="info-panel-day-groups">{"".join(day_states)}</div></div>'
            '<p class="info-panel-footer-note">Estado consolidado por fecha dentro del periodo seleccionado.</p>'
            '</div>'
        )
    else:
        culatas_html = (
            '<div class="info-panel-body">'
            '<div class="info-panel-state">'
            f'<span class="info-panel-state-badge" style="background:{culatas_badge_bg}; color:{culatas_badge_color};">{html.escape(culatas_tag)}</span>'
            f'<span class="info-panel-state-text">{html.escape(culatas_state)}</span>'
            '</div>'
            f'<p class="info-panel-copy">Estado operativo {period_context} para {html.escape(block_tag_text.lower()) if block_label else "el bloque seleccionado"}.</p>'
            '</div>'
        )

    info_cards = {
        'observaciones': (
            f'<div class="info-panel-card info-panel-card--observaciones" style="--info-accent: {BRAND_COLORS["rose"]}; --info-accent-soft: rgba(231, 210, 218, 0.22);">'
            '<div class="info-panel-header">'
            '<div class="info-panel-header-main">'
            f'<span class="info-panel-icon">{_info_panel_icon_svg("observaciones")}</span>'
            '<div class="info-panel-heading">'
            f'<h3 class="info-panel-title">{html.escape(observation_title)}</h3>'
            '</div>'
            '</div>'
            f'<span class="info-panel-tag">{html.escape(period_tag)}</span>'
            '</div>'
            f'{observations_html}'
            '</div>'
        ),
        'modificacion': (
            f'<div class="info-panel-card info-panel-card--compact" style="--info-accent: {BRAND_COLORS["hero"]}; --info-accent-soft: rgba(76, 70, 120, 0.15);">'
            '<div class="info-panel-header">'
            '<div class="info-panel-header-main">'
            f'<span class="info-panel-icon">{_info_panel_icon_svg("modificacion")}</span>'
            '<div class="info-panel-heading">'
            f'<h3 class="info-panel-title">{html.escape(block_title)}</h3>'
            '</div>'
            '</div>'
            f'<span class="info-panel-tag">{block_tag}</span>'
            '</div>'
            f'{mod_html}'
            '</div>'
        ),
        'culatas': (
            f'<div class="info-panel-card info-panel-card--compact" style="--info-accent: {BRAND_COLORS["sky"]}; --info-accent-soft: rgba(214, 229, 236, 0.28);">'
            '<div class="info-panel-header">'
            '<div class="info-panel-header-main">'
            f'<span class="info-panel-icon">{_info_panel_icon_svg("culatas")}</span>'
            '<div class="info-panel-heading">'
            f'<h3 class="info-panel-title">{html.escape(culatas_title)}</h3>'
            '</div>'
            '</div>'
            f'<span class="info-panel-tag">{html.escape(period_tag)}</span>'
            '</div>'
            f'{culatas_html}'
            '</div>'
        )
    }

    st.markdown(
        (
            '<div class="info-panels-layout">'
            '<div class="info-panels-grid">'
            f'{info_cards["observaciones"]}'
            f'{info_cards["modificacion"]}'
            f'{info_cards["culatas"]}'
            '</div>'
            '</div>'
        ),
        unsafe_allow_html=True
    )


def _selector_state_key(var_name):
    safe_name = re.sub(r'[^a-z0-9]+', '_', str(var_name).lower()).strip('_')
    return f'variables_correlacion_{safe_name}'


def _reset_correlacion_selector(options):
    st.session_state['variables_correlacion'] = options.copy()
    known_options = list(dict.fromkeys((SENSOR_VARIABLES + MOTOR_VARIABLES) + list(options)))
    for option in known_options:
        st.session_state[_selector_state_key(option)] = option in options


def _get_selected_correlacion_vars(options):
    selected_vars = [option for option in options if st.session_state.get(_selector_state_key(option), True)]
    st.session_state['variables_correlacion'] = selected_vars
    return selected_vars


def _analysis_block_state_key(block_code):
    safe_code = re.sub(r'[^a-z0-9]+', '_', str(block_code).lower()).strip('_')
    return f'bloques_analisis_{safe_code}'


def _reset_analysis_block_selector(block_codes):
    st.session_state['bloques_analisis'] = block_codes.copy()
    for block_code in block_codes:
        st.session_state[_analysis_block_state_key(block_code)] = True


def _get_selected_analysis_blocks(block_codes):
    selected_blocks = [block_code for block_code in block_codes if st.session_state.get(_analysis_block_state_key(block_code), True)]
    st.session_state['bloques_analisis'] = selected_blocks
    return selected_blocks


def _get_block_modification(block_name):
    block_code = _extract_block_code(block_name)
    return BLOCK_MODIFICATIONS.get(block_code) if block_code else None


def _get_block_ventilation_rows(block_name):
    block_code = _extract_block_code(block_name)
    if not block_code:
        return []
    return BLOCK_VENTILATION_DATA.get(block_code, [])


def _get_block_ventilation_row(block_name, expected_row_key):
    for row in _get_block_ventilation_rows(block_name):
        row_key = _build_normalized_text_key(row.get('label', ''))
        if row_key == expected_row_key:
            return row
    return None


def _get_motor_area_reference(block_name, motor_name):
    motor_key = _normalize_cortina_name(motor_name)
    reference_config = MOTOR_AREA_REFERENCE.get(motor_key)
    if not reference_config:
        return None

    row = _get_block_ventilation_row(block_name, reference_config['row_key'])
    if not row:
        return None

    real_value = row.get('real')
    ideal_value = row.get('ideal')
    if real_value is None or pd.isna(real_value):
        return None

    return {
        'real_max_area': float(real_value) / float(reference_config['divisor']),
        'ideal_max_area': (
            float(ideal_value) / float(reference_config['divisor'])
            if ideal_value is not None and not pd.isna(ideal_value)
            else None
        )
    }


def _get_culatas_area_reference(block_name):
    row = _get_block_ventilation_row(block_name, 'ventilacion culatas')
    if not row:
        return None

    real_value = row.get('real')
    if real_value is None or pd.isna(real_value):
        return None

    return float(real_value)


def _build_culatas_state_text(open_percent, block_name=None):
    percent_value = _normalize_percent_value(open_percent)
    if percent_value is None:
        return 'Sin información disponible'

    if percent_value <= 0:
        return 'Culatas cerradas'

    max_area = _get_culatas_area_reference(block_name)
    if max_area is None:
        return 'Culatas abiertas'

    open_area = max_area * percent_value / 100.0
    area_text = _format_area_value(open_area)
    percent_text = _format_summary_number(percent_value, 0)
    return f'Culatas abiertas - {area_text} m2 abiertos ({percent_text}%)'


def _convert_cortina_profile_to_area(df_state, real_max_area, ideal_max_area=None):
    if df_state.empty:
        return df_state

    df_area = df_state.copy()
    apertura_pct = pd.to_numeric(df_area['Apertura'], errors='coerce')
    df_area['Apertura_m2'] = apertura_pct * float(real_max_area) / 100.0
    if ideal_max_area is not None:
        df_area['Apertura_ideal_m2'] = apertura_pct * float(ideal_max_area) / 100.0
    else:
        df_area['Apertura_ideal_m2'] = pd.NA

    detail_values = []
    for detail in df_area['Detalle'].fillna(''):
        detail_text = str(detail).strip()
        if detail_text:
            detail_values.append(detail_text.replace(' | ', ' - '))
        else:
            detail_values.append('')

    df_area['DetalleGrafico'] = detail_values
    apertura_ideal_series = pd.to_numeric(df_area['Apertura_ideal_m2'], errors='coerce')
    brecha_ideal_series = pd.to_numeric(df_area['Apertura_m2'], errors='coerce') - apertura_ideal_series
    df_area['ResumenIdealTexto'] = [
        (
            f'Ideal: {_format_area_value(ideal_value)} m2 | Brecha: {_format_area_value(gap_value)} m2'
            if not pd.isna(ideal_value) and not pd.isna(gap_value) else
            'Ideal: Sin dato'
        )
        for ideal_value, gap_value in zip(apertura_ideal_series, brecha_ideal_series)
    ]
    return df_area


def _format_area_value(value):
    if value is None or pd.isna(value):
        return 'No aplica'

    numeric_value = round(float(value), 2)
    if abs(numeric_value - round(numeric_value)) < 1e-6:
        decimals = 0
    elif abs(numeric_value - round(numeric_value, 1)) < 1e-6:
        decimals = 1
    else:
        decimals = 2

    return _format_summary_number(numeric_value, decimals)


def _extract_block_code(block_name):
    if not block_name:
        return None
    match = re.search(r'(\d+)', str(block_name))
    return match.group(1) if match else None


def _extract_block_identifier(block_name):
    block_code = _extract_block_code(block_name)
    if block_code:
        return block_code

    normalized_key = _build_normalized_text_key(block_name)
    if 'almacen' in normalized_key:
        return 'ALMACEN'

    return None


def _get_block_options(df_variables_all, df_cortinas_all):
    variable_map = {}
    cortina_map = {}

    if not df_variables_all.empty and 'Bloque' in df_variables_all.columns:
        for block_name in sorted(df_variables_all['Bloque'].dropna().unique()):
            block_identifier = _extract_block_identifier(block_name)
            if block_identifier:
                variable_map[block_identifier] = block_name

    if not df_cortinas_all.empty and 'Bloque' in df_cortinas_all.columns:
        for block_name in sorted(df_cortinas_all['Bloque'].dropna().unique()):
            block_identifier = _extract_block_identifier(block_name)
            if block_identifier:
                cortina_map[block_identifier] = block_name

    block_codes = _sort_block_names(list(variable_map.keys()))
    return block_codes, variable_map, cortina_map


def _find_cortinas_data_start(raw_df):
    search_limit = min(10, len(raw_df))
    for idx in range(search_limit):
        row_values = [str(v).strip().upper() for v in raw_df.iloc[idx].tolist() if pd.notna(v)]
        if 'FECHA' in row_values and any('PUERTA' in v for v in row_values):
            next_idx = idx + 1
            while next_idx < len(raw_df) and raw_df.iloc[next_idx].isna().all():
                next_idx += 1
            return next_idx
    return 5


def _assign_cortinas_columns(data):
    num_cols = data.shape[1]
    if num_cols == len(CORTINAS_COLUMNAS_CON_DIA):
        data.columns = CORTINAS_COLUMNAS_CON_DIA
    elif num_cols <= len(CORTINAS_COLUMNAS):
        data.columns = CORTINAS_COLUMNAS[:num_cols]
    else:
        extra_cols = [f'Columna extra {i+1}' for i in range(num_cols - len(CORTINAS_COLUMNAS))]
        data.columns = CORTINAS_COLUMNAS + extra_cols
    return data


def _normalize_percent_value(value):
    if pd.isna(value):
        return None
    return max(0.0, min(100.0, float(value)))


def _normalize_cortina_name(value):
    if pd.isna(value):
        return None

    normalized_key = _build_normalized_text_key(value)
    normalized_key = re.sub(r'\s+', ' ', normalized_key).strip()
    cortina_name_map = {
        'frente 1': 'FRENTE 1',
        'frente 2': 'FRENTE 2',
        'puerta 1': 'PUERTA 1',
        'puerta 2': 'PUERTA 2'
    }
    return cortina_name_map.get(normalized_key, str(value).strip())


def _build_cortina_apertura_profile(df_cortinas, elemento, config):
    elemento_col = config['element_col']
    apertura_col = config['open_time_col']
    apertura_pct_col = config['open_pct_col']
    duracion_apertura_col = config['open_duration_col']
    cierre_col = config['close_time_col']
    cierre_pct_col = config['close_pct_col']
    duracion_cierre_col = config['close_duration_col']

    if elemento_col not in df_cortinas.columns:
        return pd.DataFrame()

    elemento_normalizado = _normalize_cortina_name(elemento)
    elementos_normalizados = df_cortinas[elemento_col].apply(_normalize_cortina_name)
    datos_elem = df_cortinas[elementos_normalizados == elemento_normalizado].copy()
    if datos_elem.empty or 'Fecha' not in datos_elem.columns:
        return pd.DataFrame()

    datos_elem = datos_elem.sort_values(['Fecha', apertura_col, cierre_col], na_position='last').reset_index(drop=True)
    fechas_elem = [fecha for fecha in datos_elem['Fecha'].dropna().drop_duplicates().tolist()]
    profile = []

    for day_index, fecha_dia in enumerate(fechas_elem):
        datos_dia = datos_elem[datos_elem['Fecha'] == fecha_dia].copy()
        if datos_dia.empty:
            continue

        if day_index > 0:
            profile.append({
                'Hora': datetime.combine(fecha_dia, datetime.min.time()),
                'Apertura': None,
                'Evento': 'Cambio de día',
                'Detalle': ''
            })

        inicio_dia = datetime.combine(fecha_dia, datetime.min.time())
        fin_dia = datetime.combine(fecha_dia, datetime.max.time().replace(microsecond=0))
        current_level = 0.0
        profile.append({
            'Hora': inicio_dia,
            'Apertura': current_level,
            'Evento': 'Inicio del día',
            'Detalle': 'Estado inicial: 0% abierto'
        })

        for _, evt in datos_dia.iterrows():
            apertura_pct = _normalize_percent_value(evt[apertura_pct_col])
            cierre_pct = _normalize_percent_value(evt[cierre_pct_col])
            target_open_level = apertura_pct if apertura_pct is not None else current_level
            target_close_level = 100.0 - cierre_pct if cierre_pct is not None else current_level

            if pd.notna(evt[apertura_col]):
                inicio_apertura = datetime.combine(fecha_dia, evt[apertura_col])
                duracion_ap = float(evt[duracion_apertura_col]) if pd.notna(evt[duracion_apertura_col]) else 0.0
                fin_apertura = inicio_apertura + timedelta(minutes=duracion_ap)
                profile.append({
                    'Hora': inicio_apertura,
                    'Apertura': current_level,
                    'Evento': 'Inicio Apertura',
                    'Detalle': f"Objetivo: {target_open_level:.0f}% abierto | Duración: {duracion_ap:.0f} min"
                })
                profile.append({
                    'Hora': fin_apertura,
                    'Apertura': target_open_level,
                    'Evento': 'Fin Apertura',
                    'Detalle': f"Nivel alcanzado: {target_open_level:.0f}% abierto"
                })
                current_level = target_open_level

            if pd.notna(evt[cierre_col]):
                inicio_cierre = datetime.combine(fecha_dia, evt[cierre_col])
                duracion_ci = float(evt[duracion_cierre_col]) if pd.notna(evt[duracion_cierre_col]) else 0.0
                fin_cierre = inicio_cierre + timedelta(minutes=duracion_ci)
                profile.append({
                    'Hora': inicio_cierre,
                    'Apertura': current_level,
                    'Evento': 'Inicio Cierre',
                    'Detalle': f"Cierre: {cierre_pct:.0f}% | Duración: {duracion_ci:.0f} min"
                    if cierre_pct is not None else f"Duración: {duracion_ci:.0f} min"
                })
                profile.append({
                    'Hora': fin_cierre,
                    'Apertura': target_close_level,
                    'Evento': 'Fin Cierre',
                    'Detalle': f"Nivel final: {target_close_level:.0f}% abierto"
                })
                current_level = target_close_level

        profile.append({
            'Hora': fin_dia,
            'Apertura': current_level,
            'Evento': 'Fin del día',
            'Detalle': f"Estado final: {current_level:.0f}% abierto"
        })

    return pd.DataFrame(profile).sort_values('Hora').reset_index(drop=True)


def _get_culatas_daily_observation(datos_cortinas, block_label=None):
    if datos_cortinas.empty or 'Culatas %' not in datos_cortinas.columns:
        return None

    valores_culatas = datos_cortinas['Culatas %'].dropna()
    if valores_culatas.empty:
        return None

    ultimo_valor = _normalize_percent_value(valores_culatas.iloc[-1])
    if ultimo_valor is None:
        return None
    return _build_culatas_state_text(ultimo_valor, block_label)


def _get_culatas_observation_by_day(datos_cortinas, block_label=None):
    if (
        datos_cortinas.empty or
        'Fecha' not in datos_cortinas.columns or
        'Culatas %' not in datos_cortinas.columns
    ):
        return []

    observations = []
    datos_ordenados = datos_cortinas.sort_values('Fecha')

    for fecha, datos_dia in datos_ordenados.groupby('Fecha', sort=True):
        valores_culatas = datos_dia['Culatas %'].dropna()
        if valores_culatas.empty:
            state = 'Sin información disponible'
        else:
            ultimo_valor = _normalize_percent_value(valores_culatas.iloc[-1])
            if ultimo_valor is None:
                state = 'Sin información disponible'
            else:
                state = _build_culatas_state_text(ultimo_valor, block_label)

        observations.append({
            'fecha': fecha,
            'state': state
        })

    return observations


def _get_available_cortina_vars(datos_cortinas):
    if datos_cortinas.empty:
        return []

    available = []
    for config in SIDE_CONFIGS.values():
        element_col = config['element_col']
        if element_col in datos_cortinas.columns:
            for value in datos_cortinas[element_col].dropna().unique():
                normalized_name = _normalize_cortina_name(value)
                if normalized_name:
                    available.append(normalized_name)
    available_set = set(available)
    ordered_known = [motor for motor in MOTOR_VARIABLES if motor in available_set]
    extras = sorted(available_set - set(MOTOR_VARIABLES))
    return ordered_known + extras


def _get_available_sensor_vars(df_variables):
    if df_variables.empty:
        return []

    return [
        var_name for var_name in SENSOR_VARIABLES
        if var_name in df_variables.columns and df_variables[var_name].notna().any()
    ]


def _get_available_correlacion_vars(df_variables, datos_cortinas):
    sensor_vars = _get_available_sensor_vars(df_variables)
    if not sensor_vars:
        return []
    motor_vars = _get_available_cortina_vars(datos_cortinas)
    return list(dict.fromkeys(sensor_vars + motor_vars))


def _get_available_variable_dates(df_variables_all, bloque_variables):
    if bloque_variables is None:
        return []

    fechas_variables = set(
        pd.Series(
            df_variables_all[df_variables_all['Bloque'] == bloque_variables]['Fecha_Filtro'].dropna().unique()
        ).tolist()
    )
    return sorted(fechas_variables)


def _get_all_variable_dates(df_variables_all):
    if df_variables_all.empty or 'Fecha_Filtro' not in df_variables_all.columns:
        return []

    fechas_variables = pd.Series(df_variables_all['Fecha_Filtro'].dropna().unique()).tolist()
    return sorted(fechas_variables)


def _filter_variables_range(df_variables_all, bloque_variables, fecha_inicio, fecha_fin):
    if (
        df_variables_all.empty or
        'Fecha_Filtro' not in df_variables_all.columns or
        'Bloque' not in df_variables_all.columns or
        bloque_variables is None or
        fecha_inicio is None or
        fecha_fin is None
    ):
        return pd.DataFrame()

    return df_variables_all[
        (df_variables_all['Fecha_Filtro'] >= fecha_inicio) &
        (df_variables_all['Fecha_Filtro'] <= fecha_fin) &
        (df_variables_all['Bloque'] == bloque_variables)
    ].copy()


def _filter_variables_multi_block_range(df_variables_all, fecha_inicio, fecha_fin, bloques=None):
    if (
        df_variables_all.empty or
        'Fecha_Filtro' not in df_variables_all.columns or
        'Bloque' not in df_variables_all.columns or
        fecha_inicio is None or
        fecha_fin is None
    ):
        return pd.DataFrame()

    mask = (
        (df_variables_all['Fecha_Filtro'] >= fecha_inicio) &
        (df_variables_all['Fecha_Filtro'] <= fecha_fin)
    )

    if bloques:
        mask &= df_variables_all['Bloque'].isin(bloques)

    return df_variables_all[mask].copy()


def _filter_cortinas_range(df_cortinas_all, bloque_seleccionado, fecha_inicio, fecha_fin):
    if (
        df_cortinas_all.empty or
        'Fecha' not in df_cortinas_all.columns or
        'Bloque' not in df_cortinas_all.columns or
        bloque_seleccionado is None or
        fecha_inicio is None or
        fecha_fin is None
    ):
        return pd.DataFrame()

    return df_cortinas_all[
        (df_cortinas_all['Bloque'] == bloque_seleccionado) &
        (df_cortinas_all['Fecha'] >= fecha_inicio) &
        (df_cortinas_all['Fecha'] <= fecha_fin)
    ].copy()


def _get_daily_annotations(datos_cortinas):
    if datos_cortinas.empty:
        return []

    annotation_pairs = [
        ('Frente A', 'Anotacion A'),
        ('Puerta B', 'Anotacion B')
    ]
    annotations = []

    for _, row in datos_cortinas.iterrows():
        for label_col, note_col in annotation_pairs:
            note_value = row.get(note_col)
            if pd.isna(note_value):
                continue

            note_text = str(note_value).strip()
            if not note_text or note_text.lower() in {'nan', 'none'}:
                continue

            label_value = row.get(label_col)
            label_text = str(label_value).strip() if pd.notna(label_value) else label_col
            entry = f"{label_text}: {note_text}"
            if entry not in annotations:
                annotations.append(entry)

    return annotations


def _get_annotations_by_day(datos_cortinas):
    if datos_cortinas.empty or 'Fecha' not in datos_cortinas.columns:
        return []

    annotation_pairs = [
        ('Frente A', 'Anotacion A'),
        ('Puerta B', 'Anotacion B')
    ]
    grouped_annotations = []
    datos_ordenados = datos_cortinas.sort_values('Fecha')

    for fecha, datos_dia in datos_ordenados.groupby('Fecha', sort=True):
        entries = []

        for _, row in datos_dia.iterrows():
            for label_col, note_col in annotation_pairs:
                note_value = row.get(note_col)
                if pd.isna(note_value):
                    continue

                note_text = str(note_value).strip()
                if not note_text or note_text.lower() in {'nan', 'none'}:
                    continue

                label_value = row.get(label_col)
                label_text = str(label_value).strip() if pd.notna(label_value) else label_col
                entry = f"{label_text}: {note_text}"
                if entry not in entries:
                    entries.append(entry)

        grouped_annotations.append({
            'fecha': fecha,
            'entries': entries
        })

    return grouped_annotations


def _format_info_day_label(fecha_value):
    timestamp = pd.to_datetime(fecha_value, errors='coerce')
    if pd.isna(timestamp):
        return str(fecha_value)

    weekday = WEEKDAY_ES.get(timestamp.weekday())
    if weekday:
        return f"{weekday} {timestamp.strftime('%d/%m/%Y')}"
    return timestamp.strftime('%d/%m/%Y')


def _get_culatas_state_style(culatas_state):
    culatas_state_lower = str(culatas_state).lower()
    if 'abiertas' in culatas_state_lower:
        return {
            'badge_bg': 'rgba(112, 200, 140, 0.18)',
            'badge_color': '#3C8C57',
            'tag': 'Estado abierto'
        }
    if 'cerradas' in culatas_state_lower:
        return {
            'badge_bg': 'rgba(84, 83, 134, 0.16)',
            'badge_color': BRAND_COLORS['hero'],
            'tag': 'Estado cerrado'
        }
    return {
        'badge_bg': 'rgba(124, 129, 138, 0.16)',
        'badge_color': '#6D727D',
        'tag': 'Sin dato'
    }


def _add_day_breaks_to_series(serie, value_col):
    if serie.empty or 'DateTime' not in serie.columns:
        return serie

    serie = serie.sort_values('DateTime').reset_index(drop=True)
    if serie['DateTime'].dt.date.nunique() <= 1:
        return serie

    rows = []
    previous_date = None

    for _, row in serie.iterrows():
        current_date = row['DateTime'].date()
        if previous_date is not None and current_date != previous_date:
            rows.append({'DateTime': row['DateTime'], value_col: None})
        rows.append({'DateTime': row['DateTime'], value_col: row[value_col]})
        previous_date = current_date

    return pd.DataFrame(rows)


@st.cache_data
def cargar_cortinas(ruta_bytes):
    if not ruta_bytes:
        return pd.DataFrame()

    try:
        xls = pd.ExcelFile(io.BytesIO(ruta_bytes), engine="openpyxl")
        registros = []

        for sheet in [s for s in xls.sheet_names if s.lower() != 'plantilla']:
            raw = _leer_excel_desde_bytes(ruta_bytes, sheet_name=sheet, header=None)
            if raw.shape[0] < 4:
                continue
            raw = raw.dropna(axis=1, how='all')
            data_start = _find_cortinas_data_start(raw)
            data = raw.iloc[data_start:].copy().reset_index(drop=True)
            data = data.dropna(how='all').reset_index(drop=True)
            if data.shape[1] == 0 or data.empty:
                continue
            data = _assign_cortinas_columns(data)
            data['Bloque'] = sheet
            data = data[data['Fecha'].notna()].copy()
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                data['Fecha'] = pd.to_datetime(data['Fecha'], errors='coerce').dt.date
            data = data[data['Fecha'].notna()].copy()
            data['Dia'] = pd.to_datetime(data['Fecha'], errors='coerce').dt.weekday.map(WEEKDAY_ES)

            for col in CORTINAS_NUMERIC_COLUMNS:
                if col in data.columns:
                    raw_values = data[col].astype(str).str.replace(',', '.').str.replace('%', '').str.strip()
                    data[col] = pd.to_numeric(raw_values.replace({'nan': '', 'None': ''}), errors='coerce')
                    if col in ['% Apertura A', '% Cierre A', '% Apertura B', '% Cierre B', 'Culatas %']:
                        mask = data[col].notna() & (data[col] <= 1)
                        data.loc[mask, col] = data.loc[mask, col] * 100

            for col in CORTINAS_TIME_COLUMNS:
                if col in data.columns:
                    data[col] = data[col].apply(parse_time)

            registros.append(data)

        return pd.concat(registros, ignore_index=True) if registros else pd.DataFrame()
    except Exception as e:
        st.error(f"Error técnico en cortinas: {e}")
        return pd.DataFrame()


def _render_correlacion(
    df_variables,
    datos_cortinas_sel,
    fecha_variables,
    variables_seleccionadas=None,
    block_label=None,
    show_ideal_aperturas=False,
    df_variables_almacen=None,
    compare_with_almacen=False
):
    fecha_inicio, fecha_fin = fecha_variables
    multi_day_view = fecha_inicio != fecha_fin
    hover_time_format = '%d/%m %H:%M' if multi_day_view else '%H:%M'
    xaxis_tickformat = '%H:%M\n%d/%m' if multi_day_view else '%H:%M'
    xaxis_title_text = '<b>Fecha y hora</b>' if multi_day_view else '<b>Hora del Día</b>'

    sensor_vars = _get_available_sensor_vars(df_variables)
    almacen_sensor_vars = _get_available_sensor_vars(df_variables_almacen) if isinstance(df_variables_almacen, pd.DataFrame) else []
    available_cortinas = _get_available_cortina_vars(datos_cortinas_sel)
    available_vars = list(dict.fromkeys(sensor_vars + available_cortinas))
    selected_vars = variables_seleccionadas or []

    if df_variables.empty or not sensor_vars:
        st.warning("No hay datos de variables disponibles para la combinación seleccionada.")
        return

    if not selected_vars:
        st.warning("Selecciona al menos una variable para mostrar la correlación.")
        return

    selected_sensors = [v for v in selected_vars if v in sensor_vars]
    selected_cortinas = [v for v in selected_vars if v in available_cortinas]
    cortina_reference_map = {
        var_name: _get_motor_area_reference(block_label, var_name)
        for var_name in selected_cortinas
    }
    use_cortina_area = bool(selected_cortinas) and all(
        cortina_reference_map.get(var_name) for var_name in selected_cortinas
    )
    show_ideal_lines = bool(show_ideal_aperturas and use_cortina_area)

    if not selected_sensors and not selected_cortinas:
        if available_vars:
            disponibles_texto = ', '.join(VARIABLE_SELECTOR_LABELS.get(var, var) for var in available_vars)
            st.warning(f"No se detectaron variables seleccionadas válidas para graficar. Disponibles en este rango: {disponibles_texto}.")
        else:
            st.warning("No se detectaron variables válidas para graficar en el rango seleccionado.")
        return

    df_plot = df_variables[['DateTime'] + selected_sensors].copy() if selected_sensors else pd.DataFrame()
    if selected_sensors:
        df_plot = df_plot.dropna(how='all', subset=selected_sensors)
        if df_plot.empty:
            st.warning("No hay registros de sensores para las variables seleccionadas.")
            return

    compare_sensor_vars = []
    df_plot_almacen = pd.DataFrame()
    if compare_with_almacen and not str(block_label).strip().lower() == 'estación externa':
        compare_sensor_vars = [var_name for var_name in selected_sensors if var_name in almacen_sensor_vars]
        if compare_sensor_vars:
            df_plot_almacen = df_variables_almacen[['DateTime'] + compare_sensor_vars].copy()
            df_plot_almacen = df_plot_almacen.dropna(how='all', subset=compare_sensor_vars)

    fig_corr = go.Figure()
    palette = ['#d62728', '#9467bd', '#8c564b', '#e377c2']
    sensor_render_priority = {
        'Gramos de agua': 1,
        'Temperatura': 2,
        'Humedad Relativa': 3,
        'Radiación PAR': 4
    }
    sensor_traces = []
    compare_sensor_traces = []
    cortina_traces = []
    cortina_axis_max = 100.0 if not use_cortina_area else 0.0
    sensor_legend_title_added = False
    cortina_legend_title_added = False

    for order, var_name in enumerate(selected_vars):
        if var_name in selected_sensors:
            serie = df_plot[['DateTime', var_name]].dropna(subset=[var_name]).copy()
            if serie.empty:
                continue
            serie_plot = _add_day_breaks_to_series(serie, var_name) if multi_day_view else serie
            trace = dict(
                x=serie_plot['DateTime'],
                y=serie_plot[var_name],
                name=var_name,
                mode='lines+markers',
                line=dict(
                    color=VARIABLE_COLORS.get(var_name, palette[order % len(palette)]),
                    width=3 if var_name == 'Radiación PAR' else 2
                ),
                marker=dict(
                    size=7 if var_name == 'Radiación PAR' else 5,
                    color=VARIABLE_COLORS.get(var_name, palette[order % len(palette)])
                ),
                opacity=0.78 if var_name == 'Gramos de agua' else 1.0,
                legendrank=order,
                hovertemplate=(
                    f'<b>%{{x|{hover_time_format}}}</b><br>' +
                    var_name + ': %{y:.2f} ' +
                    VARIABLE_UNITS.get(var_name, '') +
                    '<extra></extra>'
                ),
                legendgroup=f'sensor_{var_name}'
            )
            if not sensor_legend_title_added:
                trace['legendgrouptitle_text'] = 'Sensores'
                sensor_legend_title_added = True
            sensor_traces.append((
                var_name,
                trace,
                VARIABLE_COLORS.get(var_name, palette[order % len(palette)]),
                sensor_render_priority.get(var_name, 0)
            ))

            if var_name in compare_sensor_vars and not df_plot_almacen.empty:
                serie_almacen = df_plot_almacen[['DateTime', var_name]].dropna(subset=[var_name]).copy()
                if not serie_almacen.empty:
                    serie_almacen_plot = _add_day_breaks_to_series(serie_almacen, var_name) if multi_day_view else serie_almacen
                    almacen_trace = dict(
                        x=serie_almacen_plot['DateTime'],
                        y=serie_almacen_plot[var_name],
                        name=f'{var_name} - Estación externa',
                        mode='lines+markers',
                        line=dict(
                            color=VARIABLE_COLORS.get(var_name, palette[order % len(palette)]),
                            width=2,
                            dash='dot'
                        ),
                        marker=dict(
                            size=4,
                            color=VARIABLE_COLORS.get(var_name, palette[order % len(palette)]),
                            symbol='diamond-open'
                        ),
                        opacity=0.95,
                        legendrank=order + 0.5,
                        hovertemplate=(
                            f'<b>%{{x|{hover_time_format}}}</b><br>' +
                            f'{var_name} - Estación externa: ' +
                            '%{y:.2f} ' +
                            VARIABLE_UNITS.get(var_name, '') +
                            '<extra></extra>'
                        ),
                        legendgroup=f'sensor_{var_name}_almacen'
                    )
                    compare_sensor_traces.append((
                        f'{var_name}_almacen',
                        almacen_trace,
                        VARIABLE_COLORS.get(var_name, palette[order % len(palette)]),
                        sensor_render_priority.get(var_name, 0)
                    ))
        elif var_name in selected_cortinas:
            for config in SIDE_CONFIGS.values():
                if config['element_col'] not in datos_cortinas_sel.columns:
                    continue
                df_state = _build_cortina_apertura_profile(datos_cortinas_sel, var_name, config)
                if df_state.empty:
                    continue

                y_col = 'Apertura'
                detail_col = 'Detalle'
                trace_name = str(var_name)
                hover_value_line = 'Apertura: %{y:.0f}%'
                customdata_columns = ['Evento', detail_col]

                if use_cortina_area:
                    motor_reference = cortina_reference_map.get(var_name)
                    df_state = _convert_cortina_profile_to_area(
                        df_state,
                        motor_reference['real_max_area'],
                        motor_reference.get('ideal_max_area')
                    )
                    y_col = 'Apertura_m2'
                    detail_col = 'DetalleGrafico'
                    trace_name = f'{var_name} (m2)'
                    hover_value_line = 'Real: %{y:.1f} m2'
                    customdata_columns = (
                        ['Evento', detail_col, 'ResumenIdealTexto']
                        if show_ideal_lines else
                        ['Evento', detail_col]
                    )
                    serie_area = pd.to_numeric(df_state[y_col], errors='coerce').dropna()
                    if not serie_area.empty:
                        cortina_axis_max = max(cortina_axis_max, float(serie_area.max()))

                color = CORTINA_COLORS.get(str(var_name).upper(), palette[order % len(palette)])
                trace = dict(
                    x=df_state['Hora'],
                    y=df_state[y_col],
                    name=trace_name,
                    mode='lines+markers',
                    line=dict(color=color, width=3.2, shape='hv'),
                    marker=dict(size=5, color=color),
                    hovertemplate=(
                        f'<b>%{{x|{hover_time_format}}}</b><br>%{{customdata[0]}}<br>{hover_value_line}'
                        + ('<br>%{customdata[2]}' if show_ideal_lines else '')
                        + '<br>%{customdata[1]}<extra></extra>'
                    ),
                    customdata=df_state[customdata_columns],
                    legendgroup=str(var_name),
                    legendrank=order * 10 + 1
                )
                if not cortina_legend_title_added:
                    trace['legendgrouptitle_text'] = 'Frentes y puertas'
                    cortina_legend_title_added = True
                cortina_traces.append((var_name, trace, color))

                if show_ideal_lines and motor_reference.get('ideal_max_area') is not None:
                    serie_area_ideal = pd.to_numeric(df_state['Apertura_ideal_m2'], errors='coerce').dropna()
                    if not serie_area_ideal.empty:
                        cortina_axis_max = max(cortina_axis_max, float(serie_area_ideal.max()))

                    trace_ideal = dict(
                        x=df_state['Hora'],
                        y=df_state['Apertura_ideal_m2'],
                        name=f'{var_name} ideal',
                        mode='lines',
                        line=dict(color=color, width=2.2, shape='hv', dash='dot'),
                        opacity=0.68,
                        hoverinfo='skip',
                        legendgroup=str(var_name),
                        legendrank=order * 10 + 2,
                        showlegend=False
                    )
                    cortina_traces.append((f'{var_name}_ideal', trace_ideal, color))
                break

    if not selected_sensors and selected_cortinas and not cortina_traces:
        st.warning('No hay información de motores para el rango seleccionado.')
        return

    if not sensor_traces and not cortina_traces:
        if selected_cortinas and not selected_sensors:
            st.warning('No hay información de motores para el periodo seleccionado. Elige otra fecha o activa alguna variable ambiental.')
        else:
            st.warning('No hay datos disponibles para las variables seleccionadas.')
        return

    axis_configs = {}
    num_axes = len(sensor_traces)
    has_cortina_axis = bool(cortina_traces)

    if has_cortina_axis:
        if num_axes >= 4:
            x_domain_end = 0.76
            axis_start = 0.80
            axis_end = 0.92
            cortina_axis_position = 0.965
            right_margin = 250
        elif num_axes == 3:
            x_domain_end = 0.80
            axis_start = 0.84
            axis_end = 0.93
            cortina_axis_position = 0.97
            right_margin = 220
        else:
            x_domain_end = 0.84
            axis_start = 0.87
            axis_end = 0.94
            cortina_axis_position = 0.98
            right_margin = 190
    else:
        if num_axes >= 4:
            x_domain_end = 0.79
            axis_start = 0.84
            axis_end = 0.98
            right_margin = 255
        elif num_axes == 3:
            x_domain_end = 0.86
            axis_start = 0.90
            axis_end = 0.96
            right_margin = 190
        elif num_axes == 2:
            x_domain_end = 0.90
            axis_start = 0.93
            axis_end = 0.97
            right_margin = 160
        else:
            x_domain_end = 0.93
            axis_start = 0.95
            axis_end = 0.98
            right_margin = 130
        cortina_axis_position = None

    right_positions = [axis_start + i * ((axis_end - axis_start) / max(1, num_axes - 1)) for i in range(num_axes)]
    sensor_axis_names = ['y', 'y3', 'y4', 'y5']
    sensor_axis_map = {}

    sensor_traces = sorted(sensor_traces, key=lambda item: item[3])

    for idx, (var_name, trace, color, _) in enumerate(sensor_traces):
        axis_name = sensor_axis_names[idx] if idx < len(sensor_axis_names) else f'y{idx + 2}'
        sensor_axis_map[var_name] = axis_name
        trace['yaxis'] = None if axis_name == 'y' else axis_name
        fig_corr.add_trace(go.Scatter(**trace))

        axis_var_name = var_name.replace('_almacen', '')
        series_for_axis = []
        serie = df_plot[[axis_var_name]].dropna(subset=[axis_var_name]).copy()
        if not serie.empty:
            series_for_axis.append(serie[axis_var_name])
        if axis_var_name in compare_sensor_vars and not df_plot_almacen.empty and axis_var_name in df_plot_almacen.columns:
            serie_almacen_axis = df_plot_almacen[[axis_var_name]].dropna(subset=[axis_var_name]).copy()
            if not serie_almacen_axis.empty:
                series_for_axis.append(serie_almacen_axis[axis_var_name])
        serie_combinada = pd.concat(series_for_axis, ignore_index=True) if series_for_axis else pd.Series(dtype=float)
        if serie_combinada.empty:
            continue
        min_val = float(serie_combinada.min())
        max_val = float(serie_combinada.max())
        padding = 2 if axis_var_name == 'Temperatura' else 5 if axis_var_name == 'Humedad Relativa' else max(100, (max_val - min_val) * 0.08) if axis_var_name == 'Radiación PAR' else 2
        range_min = min_val - padding
        if min_val >= 0:
            range_min = max(0, range_min)
        if 'PAR' in axis_var_name and min_val >= 0:
            range_min = -max(35, padding * 0.35)
        range_max = max_val + padding
        axis_range = [range_min, range_max]

        side = 'right'
        position = right_positions[min(idx, len(right_positions) - 1)]

        axis_kwargs = dict(
            title=dict(
                text=CORR_AXIS_TITLES.get(axis_var_name, axis_var_name),
                font=dict(color=color, size=11, family='Manrope, sans-serif')
            ),
            tickfont=dict(color=color, size=10, family='Manrope, sans-serif'),
            tickcolor=color,
            range=axis_range,
            autorange=False,
            side=side,
            showgrid=False,
            showline=True,
            linecolor=color,
            linewidth=1,
            ticks='',
            zeroline=False,
            tickmode='auto',
            automargin=True,
            title_standoff=16
        )

        if axis_name == 'y':
            axis_kwargs.update({
                'anchor': 'x',
                'position': position
            })
        else:
            axis_kwargs.update({
                'overlaying': 'y',
                'anchor': 'free',
                'position': position,
                'showgrid': False,
                'showline': True
            })

        axis_configs[axis_name] = axis_kwargs

    for var_name, trace, _, _ in compare_sensor_traces:
        base_var_name = var_name.replace('_almacen', '')
        axis_name = sensor_axis_map.get(base_var_name, 'y')
        trace['yaxis'] = None if axis_name == 'y' else axis_name
        fig_corr.add_trace(go.Scatter(**trace))

    if cortina_traces:
        for var_name, trace, color in cortina_traces:
            trace['yaxis'] = 'y2'
            fig_corr.add_trace(go.Scatter(**trace))

        cortina_color = BRAND_COLORS['hero']
        if use_cortina_area:
            axis_range_max = max(10.0, cortina_axis_max * 1.08 if cortina_axis_max > 0 else 10.0)
            axis_range_min = -max(10.0, axis_range_max * 0.05)
            cortina_dtick = max(50.0, round((axis_range_max / 8) / 50.0) * 50.0)
            axis_configs['y2'] = dict(
                title=dict(
                    text='Frentes / Puertas (m2)',
                    font=dict(color=cortina_color, size=11, family='Manrope, sans-serif')
                ),
                tickfont=dict(color=cortina_color, size=10, family='Manrope, sans-serif'),
                tickcolor=cortina_color,
                range=[axis_range_min, axis_range_max],
                autorange=False,
                side='right',
                overlaying='y',
                anchor='free',
                position=cortina_axis_position,
                showgrid=False,
                showline=True,
                linewidth=1,
                ticks='',
                zeroline=False,
                tickmode='linear',
                tick0=0,
                dtick=cortina_dtick,
                automargin=True,
                title_standoff=18
            )
        else:
            axis_configs['y2'] = dict(
                title=dict(
                    text=CORR_AXIS_TITLES['% Apertura Cortinas'],
                    font=dict(color=cortina_color, size=11, family='Manrope, sans-serif')
                ),
                tickfont=dict(color=cortina_color, size=10, family='Manrope, sans-serif'),
                tickcolor=cortina_color,
                range=[-4, 100],
                autorange=False,
                side='right',
                overlaying='y',
                anchor='free',
                position=cortina_axis_position,
                showgrid=False,
                showline=True,
                linewidth=1,
                ticks='',
                zeroline=False,
                tickmode='array',
                tickvals=[0, 25, 50, 75, 100],
                ticksuffix='%',
                automargin=True,
                title_standoff=18
            )

    fig_corr.update_layout(
        title=dict(
            text='Correlación entre Variables y Cortinas',
            x=0,
            xanchor='left',
            y=0.98,
            yanchor='top',
            pad=dict(b=20),
            font=dict(size=22, color=BRAND_COLORS['graphite'], family='Manrope, sans-serif')
        ),
        xaxis=dict(
            title=dict(
                text=xaxis_title_text,
                font=dict(size=14, family='Manrope, sans-serif', color=BRAND_COLORS['graphite'])
            ),
            tickformat=xaxis_tickformat,
            tickfont=dict(size=11, family='Manrope, sans-serif', color=BRAND_COLORS['graphite']),
            domain=[0, x_domain_end],
            showgrid=True,
            gridcolor='rgba(76, 70, 120, 0.07)',
            zeroline=False
        ),
        hovermode='x unified',
        template='plotly_white',
        font=dict(family='Manrope, sans-serif', color=BRAND_COLORS['graphite']),
        paper_bgcolor='rgba(255,255,255,0)',
        plot_bgcolor='rgba(250,248,243,0.65)',
        hoverlabel=dict(
            bgcolor='rgba(249, 246, 240, 0.98)',
            bordercolor='rgba(76, 70, 120, 0.16)',
            font=dict(family='Manrope, sans-serif', color=BRAND_COLORS['graphite'], size=12)
        ),
        height=620,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.10,
            xanchor='left',
            x=0,
            traceorder='normal',
            font=dict(size=11, family='Manrope, sans-serif', color=BRAND_COLORS['graphite']),
            grouptitlefont=dict(size=11, family='Manrope, sans-serif', color=BRAND_COLORS['hero']),
            bgcolor='rgba(255,255,255,0.76)',
            bordercolor='rgba(76, 70, 120, 0.08)',
            borderwidth=1
        ),
        margin=dict(l=50, r=right_margin, t=142, b=55),
        **{f'yaxis{axis_name[1:]}': config for axis_name, config in axis_configs.items()}
    )

    st.plotly_chart(fig_corr, width='stretch')

    if selected_cortinas and not cortina_traces and selected_sensors:
        st.info('No hay información de motores para el periodo seleccionado. Se muestran únicamente las variables ambientales.')

# 4. Datos cargados en memoria para evitar recálculos repetidos
def _sort_block_names(block_names):
    def sort_key(value):
        block_identifier = _extract_block_identifier(value)
        is_numeric_block = bool(block_identifier and str(block_identifier).isdigit())
        return (
            0 if is_numeric_block else 1,
            int(block_identifier) if is_numeric_block else 9999,
            _format_block_display_name(value)
        )

    return sorted(
        block_names,
        key=sort_key
    )


def _get_block_analysis_color(block_name):
    block_identifier = _extract_block_identifier(block_name)
    return BLOCK_ANALYSIS_COLORS.get(block_identifier, BRAND_COLORS['hero'])


def _format_block_display_name(block_name):
    block_identifier = _extract_block_identifier(block_name)
    if block_identifier in SPECIAL_BLOCK_LABELS:
        return SPECIAL_BLOCK_LABELS[block_identifier]
    if block_identifier and str(block_identifier).isdigit():
        return f'Bloque {block_identifier}'
    return str(block_name)


def _build_hourly_block_analysis(df_variables, variable_name):
    required_cols = {'DateTime', 'Bloque', variable_name}
    if df_variables.empty or not required_cols.issubset(df_variables.columns):
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    data = df_variables[['DateTime', 'Bloque', variable_name]].dropna(subset=['DateTime', 'Bloque', variable_name]).copy()
    if data.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # Normaliza pequeñas desviaciones del Excel como 01:31 o 01:32
    # para consolidar la lectura en franjas limpias de 30 minutos.
    data['FranjaDateTime'] = data['DateTime'].dt.round('30min')
    data['FranjaMinutos'] = data['FranjaDateTime'].dt.hour * 60 + data['FranjaDateTime'].dt.minute
    data['Franja'] = data['FranjaDateTime'].dt.strftime('%H:%M')

    grouped = (
        data.groupby(['FranjaMinutos', 'Franja', 'Bloque'], as_index=False)
        .agg(
            Promedio=(variable_name, 'mean'),
            Varianza=(variable_name, lambda serie: serie.var(ddof=1) if len(serie) > 1 else 0.0),
            Registros=(variable_name, 'count')
        )
        .sort_values(['FranjaMinutos', 'Bloque'])
        .reset_index(drop=True)
    )
    grouped['Varianza'] = grouped['Varianza'].fillna(0.0)

    ordered_blocks = _sort_block_names(grouped['Bloque'].dropna().unique().tolist())
    base_columns = ['FranjaMinutos', 'Franja']

    pivot_promedio = (
        grouped.pivot(index=base_columns, columns='Bloque', values='Promedio')
        .reset_index()
        .sort_values('FranjaMinutos')
        .reindex(columns=base_columns + ordered_blocks)
    )
    pivot_varianza = (
        grouped.pivot(index=base_columns, columns='Bloque', values='Varianza')
        .reset_index()
        .sort_values('FranjaMinutos')
        .reindex(columns=base_columns + ordered_blocks)
    )

    return grouped, pivot_promedio, pivot_varianza


def _prepare_hourly_pivot_display(pivot_df):
    if pivot_df.empty:
        return pivot_df

    display_df = pivot_df.copy()
    display_df = display_df.rename(columns={'Franja': 'Franja horaria'})
    display_df = display_df.drop(columns=['FranjaMinutos'], errors='ignore')

    rename_map = {
        column: _format_block_display_name(column)
        for column in display_df.columns
        if column != 'Franja horaria'
    }
    display_df = display_df.rename(columns=rename_map)
    display_df.columns.name = None
    return display_df.round(2)


def _render_hourly_metric_chart(grouped_df, variable_name, metric_column):
    if grouped_df.empty:
        return

    ordered_blocks = _sort_block_names(grouped_df['Bloque'].dropna().unique().tolist())
    ordered_slots = (
        grouped_df[['FranjaMinutos', 'Franja']]
        .drop_duplicates()
        .sort_values('FranjaMinutos')
        .reset_index(drop=True)
    )
    if ordered_slots.empty:
        return

    slot_minutes = ordered_slots['FranjaMinutos'].dropna().astype(int).tolist()
    use_half_hour_axis = bool(slot_minutes) and all(minute % 30 == 0 for minute in slot_minutes)
    if use_half_hour_axis:
        display_slots = [
            f'{hour:02d}:{minute:02d}'
            for hour in range(24)
            for minute in (0, 30)
        ]
    else:
        display_slots = ordered_slots['Franja'].tolist()
    metric_title = 'Promedio por franja horaria' if metric_column == 'Promedio' else 'Varianza por franja horaria'

    metric_label = VARIABLE_LABELS.get(variable_name, variable_name)
    fig = go.Figure()
    for block_name in ordered_blocks:
        serie = grouped_df[grouped_df['Bloque'] == block_name].sort_values('FranjaMinutos')
        if serie.empty:
            continue

        block_label = _format_block_display_name(block_name)
        color = _get_block_analysis_color(block_name)
        fig.add_trace(go.Scatter(
            x=serie['Franja'],
            y=serie[metric_column],
            mode='lines+markers',
            name=block_label,
            line=dict(color=color, width=3.2, shape='spline', smoothing=0.38),
            marker=dict(size=6, color=color, line=dict(color='rgba(255,255,255,0.82)', width=1)),
            hovertemplate=(
                '<b>%{x}</b><br>' +
                f'{block_label}<br>{metric_column}: ' +
                '%{y:.2f}<extra></extra>'
            ),
            hoverlabel=dict(namelength=-1)
        ))

    fig.update_layout(
        height=500,
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(250,248,243,0.68)',
        margin=dict(l=34, r=22, t=108, b=96),
        title=dict(
            text=f'{metric_title} - {metric_label}',
            x=0.01,
            xanchor='left',
            y=0.97,
            font=dict(family='Manrope', size=20, color=BRAND_COLORS['ink'])
        ),
        hovermode='x unified',
        template='plotly_white',
        font=dict(family='Manrope, sans-serif', color=BRAND_COLORS['graphite']),
        hoverlabel=dict(
            bgcolor='rgba(249, 246, 240, 0.98)',
            bordercolor='rgba(76, 70, 120, 0.16)',
            font=dict(family='Manrope, sans-serif', color=BRAND_COLORS['graphite'], size=12)
        ),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.06,
            xanchor='left',
            x=0,
            traceorder='normal',
            font=dict(size=11, family='Manrope, sans-serif', color=BRAND_COLORS['graphite']),
            bgcolor='rgba(255,255,255,0.74)',
            bordercolor='rgba(76, 70, 120, 0.08)',
            borderwidth=1
        ),
        xaxis=dict(
            title='<b>Franja horaria</b>',
            type='category',
            categoryorder='array',
            categoryarray=display_slots,
            tickmode='array',
            tickvals=display_slots,
            ticktext=display_slots,
            tickangle=-90,
            tickfont=dict(size=10, family='Manrope, sans-serif', color=BRAND_COLORS['graphite']),
            gridcolor='rgba(76, 70, 120, 0.07)',
            linecolor='rgba(45, 48, 64, 0.18)',
            zeroline=False,
            automargin=True
        ),
        yaxis=dict(
            title=f'<b>{metric_column}</b>',
            tickfont=dict(size=11, family='Manrope, sans-serif', color=BRAND_COLORS['graphite']),
            gridcolor='rgba(76, 70, 120, 0.07)',
            linecolor='rgba(45, 48, 64, 0.18)',
            zerolinecolor='rgba(45, 48, 64, 0.10)'
        )
    )

    st.plotly_chart(
        fig,
        width='stretch',
        config={
            'displaylogo': False,
            'responsive': True,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d']
        }
    )


def _render_hourly_analysis_view(df_variables, fecha_variables, selected_blocks):
    if df_variables.empty:
        fecha_inicio, fecha_fin = fecha_variables
        fecha_label = (
            fecha_inicio.strftime('%Y-%m-%d')
            if fecha_inicio == fecha_fin else
            f"{fecha_inicio.strftime('%Y-%m-%d')} a {fecha_fin.strftime('%Y-%m-%d')}"
        )
        st.warning(f'No se encontraron datos de variables para el rango seleccionado: {fecha_label}.')
        return

    fecha_inicio, fecha_fin = fecha_variables
    blocks_in_data = _sort_block_names(df_variables['Bloque'].dropna().unique().tolist())

    period_text = (
        fecha_inicio.strftime("%Y-%m-%d")
        if fecha_inicio == fecha_fin else
        f'{fecha_inicio.strftime("%Y-%m-%d")} a {fecha_fin.strftime("%Y-%m-%d")}'
    )
    block_labels = [_format_block_display_name(block) for block in blocks_in_data]

    single_day_analysis = fecha_inicio == fecha_fin

    # Selector para Promedio y Varianza
    metric_tabs = st.tabs(["Promedio", "Varianza"])
    
    for tab_idx, tab in enumerate(metric_tabs):
        tab_label = "Promedio" if tab_idx == 0 else "Varianza"
        with tab:
            # Calcular métricas generales para todas las variables
            metrics_data = {}
            for variable_name in SENSOR_VARIABLES:
                required_cols = {'DateTime', 'Bloque', variable_name}
                if not required_cols.issubset(df_variables.columns):
                    continue
                
                data = df_variables[['DateTime', 'Bloque', variable_name]].dropna(subset=['DateTime', 'Bloque', variable_name]).copy()
                if data.empty:
                    continue

                series = data[variable_name]
                stats_payload = {
                    'principal': series.mean() if tab_label == "Promedio" else (series.var(ddof=1) if len(series) > 1 else 0.0),
                    'minimo': series.min(),
                    'maximo': series.max()
                }
                metrics_data[variable_name] = stats_payload
            
            # Mostrar tarjetas de métricas
            metric_cols = st.columns(4)
            for idx, variable_name in enumerate(SENSOR_VARIABLES):
                if idx < len(metric_cols):
                    with metric_cols[idx]:
                        if variable_name in metrics_data:
                            stats_payload = metrics_data[variable_name]
                            value = stats_payload['principal']
                            color = VARIABLE_COLORS.get(variable_name, BRAND_COLORS['graphite'])
                            unit = VARIABLE_UNITS.get(variable_name, '')
                            min_value = stats_payload['minimo']
                            max_value = stats_payload['maximo']
                            
                            # Decidir formato según si es promedio o varianza
                            if tab_label == "Promedio":
                                display_value = f"{value:.1f}"
                                if single_day_analysis:
                                    descriptor = "Promedio general de todas las mediciones del día seleccionado."
                                    footer_label = "Promedio general del día"
                                else:
                                    descriptor = "Promedio general de todas las mediciones del rango seleccionado."
                                    footer_label = "Promedio general del periodo"
                            else:
                                display_value = f"{value:.2f}"
                                descriptor = "Varianza general calculada con todas las mediciones del rango seleccionado."
                                footer_label = "Varianza general del periodo"
                                if single_day_analysis:
                                    display_value = "0.00"
                                    descriptor = "En un solo día la varianza se reporta en 0 por consistencia analítica."
                                    footer_label = "Varianza en un día"
                            
                            metric_card_html = f'''
                            <div style="
                                background: linear-gradient(135deg, rgba(255,255,255,0.95) 0%, rgba(255,255,255,0.85) 100%);
                                border-left: 4px solid {color};
                                padding: 20px;
                                border-radius: 8px;
                                box-shadow: 0 2px 8px rgba(0,0,0,0.08);
                                overflow: hidden;
                            ">
                                <p style="
                                    font-family: 'Manrope', sans-serif;
                                    font-size: 13px;
                                    color: {color};
                                    font-weight: 500;
                                    margin: 0 0 12px 0;
                                    text-transform: uppercase;
                                    letter-spacing: 0.5px;
                                ">{variable_name}</p>
                                <div style="display: flex; align-items: baseline; gap: 4px; flex-wrap: wrap;">
                                    <p style="
                                        font-family: 'Manrope', sans-serif;
                                        font-size: 32px;
                                        font-weight: 700;
                                        color: {BRAND_COLORS['ink']};
                                        margin: 0;
                                        line-height: 1;
                                    ">{display_value}</p>
                                    <p style="
                                        font-family: 'Manrope', sans-serif;
                                        font-size: 12px;
                                        color: {BRAND_COLORS['graphite']};
                                        margin: 0;
                                        font-weight: 500;
                                        word-break: break-word;
                                        line-height: 1.3;
                                    ">{unit}</p>
                                </div>
                                <p style="
                                    font-family: 'Manrope', sans-serif;
                                    font-size: 11px;
                                    color: {BRAND_COLORS['graphite']};
                                    margin: 10px 0 0 0;
                                    line-height: 1.45;
                                ">{descriptor}</p>
                                <div style="
                                    display: flex;
                                    justify-content: space-between;
                                    gap: 8px;
                                    margin-top: 12px;
                                    padding-top: 10px;
                                    border-top: 1px solid rgba(76, 70, 120, 0.10);
                                ">
                                    <div>
                                        <p style="
                                            font-family: 'Manrope', sans-serif;
                                            font-size: 10px;
                                            color: {BRAND_COLORS['graphite']};
                                            margin: 0 0 4px 0;
                                            text-transform: uppercase;
                                        ">Mínimo</p>
                                        <p style="
                                            font-family: 'Manrope', sans-serif;
                                            font-size: 14px;
                                            font-weight: 700;
                                            color: {BRAND_COLORS['ink']};
                                            margin: 0;
                                        ">{min_value:.2f}</p>
                                    </div>
                                    <div style="text-align: right;">
                                        <p style="
                                            font-family: 'Manrope', sans-serif;
                                            font-size: 10px;
                                            color: {BRAND_COLORS['graphite']};
                                            margin: 0 0 4px 0;
                                            text-transform: uppercase;
                                        ">Máximo</p>
                                        <p style="
                                            font-family: 'Manrope', sans-serif;
                                            font-size: 14px;
                                            font-weight: 700;
                                            color: {BRAND_COLORS['ink']};
                                            margin: 0;
                                        ">{max_value:.2f}</p>
                                    </div>
                                </div>
                                <p style="
                                    font-family: 'Manrope', sans-serif;
                                    font-size: 11px;
                                    color: {color};
                                    margin: 10px 0 0 0;
                                    font-weight: 500;
                                ">{footer_label}</p>
                            </div>
                            '''
                            st.markdown(metric_card_html, unsafe_allow_html=True)

            if len(selected_blocks) == 1 and tab_label == "Promedio":
                st.markdown('<p class="analysis-note">Este resumen muestra el promedio consolidado del bloque seleccionado dentro del periodo filtrado y los extremos observados para cada variable.</p>', unsafe_allow_html=True)
            elif len(selected_blocks) == 1 and tab_label == "Varianza":
                st.markdown('<p class="analysis-note">La varianza resume qué tanto cambian las mediciones dentro del periodo. Con un solo día no hay dispersión temporal suficiente para una varianza útil por franja.</p>', unsafe_allow_html=True)
            else:
                if tab_label == "Promedio":
                    st.markdown('<p class="analysis-note">Explora cada variable para ver el valor promedio por franja horaria y comparar el comportamiento típico de los bloques seleccionados.</p>', unsafe_allow_html=True)
                else:
                    st.markdown('<p class="analysis-note">Explora cada variable para ver qué tanto fluctúa cada bloque por franja horaria. Valores más altos indican mayor variabilidad dentro del periodo analizado.</p>', unsafe_allow_html=True)

            # Mostrar tabs de variables dentro del tab de métrica seleccionado
            variable_tabs = st.tabs([
                VARIABLE_SELECTOR_LABELS.get(variable_name, VARIABLE_LABELS.get(variable_name, variable_name))
                for variable_name in SENSOR_VARIABLES
            ])

            for variable_name, variable_tab in zip(SENSOR_VARIABLES, variable_tabs):
                with variable_tab:
                    grouped_df, pivot_promedio, pivot_varianza = _build_hourly_block_analysis(df_variables, variable_name)
                    if grouped_df.empty:
                        st.info(f'No se encontraron datos para {variable_name} en el rango seleccionado.')
                        continue

                    if tab_label == "Promedio":
                        st.caption('Cada punto resume el promedio de todas las mediciones disponibles en la misma franja horaria para cada bloque. Úsalo para comparar el comportamiento típico entre bloques.')
                        _render_hourly_metric_chart(grouped_df, variable_name, 'Promedio')
                        with st.expander('Ver tabla dinámica de promedio', expanded=False):
                            st.dataframe(_prepare_hourly_pivot_display(pivot_promedio), width='stretch')
                    else:  # Varianza
                        st.caption('La varianza muestra qué tanto fluctúa cada bloque dentro de la misma franja horaria a lo largo del periodo filtrado. Valores cercanos a 0 indican un comportamiento más estable.')
                        if single_day_analysis:
                            st.info(
                                f'Varianza de un solo día para {VARIABLE_SELECTOR_LABELS.get(variable_name, variable_name)}: '
                                'se muestra en 0 porque con un único día no hay suficiente repetición por franja horaria para calcular una dispersión representativa.'
                            )
                        else:
                            _render_hourly_metric_chart(grouped_df, variable_name, 'Varianza')
                            with st.expander('Ver tabla dinámica de varianza', expanded=False):
                                st.dataframe(_prepare_hourly_pivot_display(pivot_varianza), width='stretch')


_df_variables_all = cargar_datos(archivo_variables_bytes) if archivo_variables_bytes else pd.DataFrame()
_df_cortinas_all = cargar_cortinas(archivo_cortinas_bytes) if archivo_cortinas_bytes else pd.DataFrame()

if 'graficar_correlacion' not in st.session_state:
    st.session_state.graficar_correlacion = False
if 'mostrar_aperturas_ideales' not in st.session_state:
    st.session_state.mostrar_aperturas_ideales = False
if 'comparar_con_almacen' not in st.session_state:
    st.session_state.comparar_con_almacen = False

st.sidebar.markdown(
    f"""
    <div class="sidebar-title">
        <span class="sidebar-title-icon">{_sidebar_icon_svg('filter')}</span>
        <span>Filtros</span>
    </div>
    """,
    unsafe_allow_html=True
)

with st.sidebar.expander("Vista", expanded=True):
    _sidebar_field_label("filter", "Seleccionar vista")
    dashboard_mode = st.radio(
        "Seleccionar vista:",
        options=["Correlación", "Varianza Y Promedio"],
        key="modo_dashboard",
        help=FILTER_HELP_TEXTS['modo_dashboard']
    )

if dashboard_mode == "Varianza Y Promedio":
    analysis_block_codes, analysis_variable_map, _ = _get_block_options(_df_variables_all, _df_cortinas_all)
    fecha_analisis = None
    analysis_block_names = []

    with st.sidebar.expander("Periodo", expanded=True):
        if _df_variables_all.empty:
            st.write("No hay datos de variables para habilitar el filtro de fechas.")
        else:
            fechas_disponibles = _get_all_variable_dates(_df_variables_all)
            if not fechas_disponibles:
                st.warning("No hay fechas disponibles en variables para construir el análisis de varianza y promedio.")
            else:
                min_fecha = min(fechas_disponibles)
                max_fecha = max(fechas_disponibles)

                if min_fecha == max_fecha:
                    fecha_unica_default = _coerce_sidebar_date(
                        st.session_state.get("fecha_analisis_unica", max_fecha),
                        max_fecha
                    )
                    _sidebar_field_label("calendar", "Seleccionar fecha")
                    fecha_unica = st.date_input(
                        "Seleccionar fecha para el análisis:",
                        value=fecha_unica_default,
                        key="fecha_analisis_unica",
                        help=FILTER_HELP_TEXTS['fecha']
                    )
                    fecha_analisis = (fecha_unica, fecha_unica)
                else:
                    modo_fechas_analisis = st.radio(
                        "Modo de fechas del análisis:",
                        options=["Un día", "Varios días"],
                        horizontal=True,
                        key="modo_fechas_analisis",
                        help=FILTER_HELP_TEXTS['modo_fechas']
                    )

                    if modo_fechas_analisis == "Un día":
                        fecha_unica_default = _coerce_sidebar_date(
                            st.session_state.get("fecha_analisis_un_dia", max_fecha),
                            max_fecha
                        )
                        _sidebar_field_label("calendar", "Seleccionar fecha")
                        fecha_unica = st.date_input(
                            "Seleccionar fecha para el análisis:",
                            value=fecha_unica_default,
                            key="fecha_analisis_un_dia",
                            help=FILTER_HELP_TEXTS['fecha']
                        )
                        fecha_analisis = (fecha_unica, fecha_unica)
                    else:
                        _sidebar_field_label("calendar", "Fecha inicio")
                        fecha_inicio_analisis = st.date_input(
                            "Fecha inicio del análisis:",
                            value=min_fecha,
                            key="fecha_inicio_analisis",
                            help=FILTER_HELP_TEXTS['fecha']
                        )
                        _sidebar_field_label("calendar", "Fecha fin")
                        fecha_fin_analisis = st.date_input(
                            "Fecha fin del análisis:",
                            value=max_fecha,
                            key="fecha_fin_analisis",
                            help=FILTER_HELP_TEXTS['fecha']
                        )
                        if fecha_fin_analisis < fecha_inicio_analisis:
                            fecha_inicio_analisis, fecha_fin_analisis = fecha_fin_analisis, fecha_inicio_analisis
                        fecha_analisis = (fecha_inicio_analisis, fecha_fin_analisis)

    with st.sidebar.expander("Bloques comparados", expanded=True):
        if _df_variables_all.empty:
            st.write("No se encontraron datos para habilitar la comparación de bloques.")
        elif not analysis_block_codes:
            st.warning("No se detectaron bloques válidos dentro del archivo de variables.")
        else:
            _sidebar_field_label("location", "Bloques incluidos")
            current_analysis_context = tuple(analysis_block_codes)
            previous_analysis_context = st.session_state.get('bloques_analisis_context')
            if previous_analysis_context != current_analysis_context:
                _reset_analysis_block_selector(analysis_block_codes)
                st.session_state['bloques_analisis_context'] = current_analysis_context

            for block_code in analysis_block_codes:
                block_state_key = _analysis_block_state_key(block_code)
                if block_state_key not in st.session_state:
                    st.session_state[block_state_key] = True
                st.checkbox(
                    _format_block_display_name(block_code),
                    key=block_state_key,
                    help=FILTER_HELP_TEXTS['bloques_comparados']
                )

            selected_analysis_codes = _get_selected_analysis_blocks(analysis_block_codes)
            analysis_block_names = [
                analysis_variable_map[block_code]
                for block_code in selected_analysis_codes
                if block_code in analysis_variable_map
            ]

    if _df_variables_all.empty:
        st.warning("No se encontraron datos de variables para construir el análisis de varianza y promedio.")
    elif fecha_analisis is None:
        st.warning("Selecciona el periodo del análisis en la barra lateral.")
    elif not analysis_block_names:
        st.warning("Selecciona al menos un bloque para comparar en la nueva vista.")
    else:
        fecha_inicio_analisis, fecha_fin_analisis = fecha_analisis
        df_variables_analisis = _filter_variables_multi_block_range(
            _df_variables_all,
            fecha_inicio_analisis,
            fecha_fin_analisis,
            analysis_block_names
        )
        _render_hourly_analysis_view(
            df_variables_analisis,
            fecha_analisis,
            analysis_block_names
        )
    st.stop()

block_codes, variable_block_map, cortina_block_map = _get_block_options(_df_variables_all, _df_cortinas_all)
bloque_variables = None
bloque_seleccionado = None
selected_block_code_current = st.session_state.get("bloque_compartido")
if not selected_block_code_current and block_codes:
    selected_block_code_current = block_codes[0]
if selected_block_code_current in variable_block_map:
    bloque_variables = variable_block_map.get(selected_block_code_current)
    bloque_seleccionado = cortina_block_map.get(selected_block_code_current)

with st.sidebar.expander("Periodo", expanded=True):
    fecha_variables = None
    fecha_cortinas = None

    if _df_variables_all.empty:
        st.write("No hay datos de variables para habilitar el filtro de fechas.")
    elif bloque_variables is None:
        st.write("Selecciona primero el bloque.")
    else:
        fechas_disponibles = _get_available_variable_dates(_df_variables_all, bloque_variables)

        if not fechas_disponibles:
            st.warning("No hay fechas disponibles en variables para el bloque seleccionado.")
        else:
            min_fecha = min(fechas_disponibles)
            max_fecha = max(fechas_disponibles)

            if min_fecha == max_fecha:
                st.caption("Solo hay una fecha con datos en variables para este bloque, pero puedes consultar cualquier día desde el calendario.")
                fecha_unica_default = _coerce_sidebar_date(
                    st.session_state.get("fecha_calendario_unica", max_fecha),
                    max_fecha
                )
                _sidebar_field_label("calendar", "Seleccionar fecha")
                fecha_unica = st.date_input(
                    "Seleccionar fecha:",
                    value=fecha_unica_default,
                    key="fecha_calendario_unica",
                    help=FILTER_HELP_TEXTS['fecha']
                )
                fecha_variables = (fecha_unica, fecha_unica)
                fecha_cortinas = (fecha_unica, fecha_unica)
            else:
                modo_fechas = st.radio(
                    "Modo de fechas:",
                    options=["Un día", "Varios días"],
                    horizontal=True,
                    key="modo_fechas_compartidas",
                    help=FILTER_HELP_TEXTS['modo_fechas']
                )

                if modo_fechas == "Un día":
                    fecha_unica_default = _coerce_sidebar_date(
                        st.session_state.get("fecha_calendario_un_dia", max_fecha),
                        max_fecha
                    )
                    _sidebar_field_label("calendar", "Seleccionar fecha")
                    fecha_unica = st.date_input(
                        "Seleccionar fecha:",
                        value=fecha_unica_default,
                        key="fecha_calendario_un_dia",
                        help=FILTER_HELP_TEXTS['fecha']
                    )
                    fecha_variables = (fecha_unica, fecha_unica)
                    fecha_cortinas = (fecha_unica, fecha_unica)
                else:
                    _sidebar_field_label("calendar", "Fecha inicio")
                    fecha_inicio = st.date_input(
                        "Fecha inicio:",
                        value=min_fecha,
                        key="fecha_inicio_compartida",
                        help=FILTER_HELP_TEXTS['fecha']
                    )
                    _sidebar_field_label("calendar", "Fecha fin")
                    fecha_fin = st.date_input(
                        "Fecha fin:",
                        value=max_fecha,
                        key="fecha_fin_compartida",
                        help=FILTER_HELP_TEXTS['fecha']
                    )
                    if fecha_fin < fecha_inicio:
                        fecha_inicio, fecha_fin = fecha_fin, fecha_inicio
                    fecha_variables = (fecha_inicio, fecha_fin)
                    fecha_cortinas = (fecha_inicio, fecha_fin)

with st.sidebar.expander("Bloque", expanded=True):
    if _df_variables_all.empty:
        st.write("No se encontraron datos de variables para habilitar los bloques.")
    elif not block_codes:
        st.warning("No se detectaron bloques válidos dentro del archivo de variables.")
    else:
        _sidebar_field_label("location", "Seleccionar bloque")
        selected_block_code = st.selectbox(
            "Seleccionar bloque:",
            options=block_codes,
            format_func=_format_block_display_name,
            key="bloque_compartido",
            help=FILTER_HELP_TEXTS['bloque']
        )
        bloque_variables = variable_block_map.get(selected_block_code)
        bloque_seleccionado = cortina_block_map.get(selected_block_code)

df_variables_corr = pd.DataFrame()
df_variables_almacen_corr = pd.DataFrame()
datos_cortinas_sel = pd.DataFrame()
available_correlacion_vars = []

if fecha_variables is not None and bloque_variables is not None:
    fecha_inicio, fecha_fin = fecha_variables
    df_variables_corr = _filter_variables_range(
        _df_variables_all,
        bloque_variables,
        fecha_inicio,
        fecha_fin
    )
    bloque_almacen = variable_block_map.get('ALMACEN')
    if bloque_almacen and bloque_almacen != bloque_variables:
        df_variables_almacen_corr = _filter_variables_range(
            _df_variables_all,
            bloque_almacen,
            fecha_inicio,
            fecha_fin
        )

if fecha_cortinas is not None:
    fecha_cortinas_inicio, fecha_cortinas_fin = fecha_cortinas
    datos_cortinas_sel = _filter_cortinas_range(
        _df_cortinas_all,
        bloque_seleccionado,
        fecha_cortinas_inicio,
        fecha_cortinas_fin
    )

available_correlacion_vars = _get_available_correlacion_vars(df_variables_corr, datos_cortinas_sel)

selected_vars_sidebar = []
with st.sidebar.expander("Series visibles", expanded=True):
    if bloque_variables is None or fecha_variables is None:
        st.write("Selecciona bloque y fechas para elegir qué series mostrar.")
    elif not available_correlacion_vars:
        st.write("No se encontraron variables con datos para el rango seleccionado.")
    else:
        current_context = (
            str(bloque_variables),
            str(fecha_variables[0]),
            str(fecha_variables[1]),
            tuple(available_correlacion_vars)
        )
        previous_context = st.session_state.get('variables_correlacion_context')
        if previous_context != current_context:
            _reset_correlacion_selector(available_correlacion_vars)
            st.session_state['variables_correlacion_context'] = current_context

        for option in available_correlacion_vars:
            state_key = _selector_state_key(option)
            if state_key not in st.session_state:
                st.session_state[state_key] = option in available_correlacion_vars
            st.checkbox(
                VARIABLE_SELECTOR_LABELS.get(option, VARIABLE_LABELS.get(option, option)),
                key=state_key,
                help=VARIABLE_FILTER_HELP.get(option, FILTER_HELP_TEXTS['series_visibles'])
            )

        selected_vars_sidebar = _get_selected_correlacion_vars(available_correlacion_vars)
        st.checkbox(
            "Comparar con Estación externa",
            key="comparar_con_almacen",
            disabled=selected_block_code == 'ALMACEN' or df_variables_almacen_corr.empty,
            help=FILTER_HELP_TEXTS['comparar_almacen']
        )
        st.checkbox(
            "Aperturas ideales",
            key="mostrar_aperturas_ideales",
            help=FILTER_HELP_TEXTS['aperturas_ideales']
        )

toggle_chart_label = "Mostrar correlación" if not st.session_state.graficar_correlacion else "Ocultar correlación"
if st.sidebar.button(toggle_chart_label, key="boton_toggle_graficos", use_container_width=True):
    st.session_state.graficar_correlacion = not st.session_state.graficar_correlacion
    st.rerun()

# Vista principal
tab_correlacion = st.container()

with tab_correlacion:
    if _df_variables_all.empty:
        st.warning("No se encontraron datos de variables para visualizar este análisis.")
    elif fecha_variables is None or fecha_cortinas is None or bloque_variables is None:
        st.warning("Selecciona bloque y fechas en los filtros de la barra lateral.")
    else:
        fecha_inicio, fecha_fin = fecha_variables
        rango_multiple = fecha_inicio != fecha_fin
        variables_sensor = _get_available_sensor_vars(df_variables_corr)
        datos_sensores_corr = (
            df_variables_corr[['DateTime'] + variables_sensor].dropna(how='all', subset=variables_sensor)
            if variables_sensor else pd.DataFrame()
        )
        _render_summary_cards_selector(df_variables_corr, fecha_variables)

        block_label = _format_block_display_name(bloque_seleccionado or bloque_variables)
        block_modification = _get_block_modification(block_label)
        culatas_observation = _get_culatas_daily_observation(datos_cortinas_sel, block_label)
        culatas_by_day = _get_culatas_observation_by_day(datos_cortinas_sel, block_label)
        daily_annotations = _get_daily_annotations(datos_cortinas_sel)
        annotations_by_day = _get_annotations_by_day(datos_cortinas_sel)
        if (
            block_label or
            block_modification or
            culatas_observation or
            daily_annotations or
            culatas_by_day or
            annotations_by_day
        ):
            _render_info_panels(
                block_label,
                block_modification,
                culatas_observation,
                daily_annotations,
                rango_multiple,
                annotations_by_day=annotations_by_day,
                culatas_by_day=culatas_by_day
            )

        tab_corr_graf, tab_corr_regs = st.tabs(["Correlación", "Registros"])

        with tab_corr_graf:
            if not st.session_state.graficar_correlacion:
                st.info("Usa el botón lateral para mostrar u ocultar el análisis de correlación.")
            else:
                selected_vars = selected_vars_sidebar or st.session_state.get('variables_correlacion', available_correlacion_vars.copy())

                if df_variables_corr.empty:
                    fecha_label = fecha_inicio.strftime('%Y-%m-%d') if not rango_multiple else f"{fecha_inicio.strftime('%Y-%m-%d')} a {fecha_fin.strftime('%Y-%m-%d')}"
                    st.warning(f"No se encontraron datos de variables para el rango seleccionado: {fecha_label}.")
                elif not available_correlacion_vars:
                    st.warning("No se encontraron variables con datos para graficar en el rango seleccionado.")
                elif datos_cortinas_sel.empty:
                    st.info("No hay información de motores para este periodo. Se mostrarán las variables ambientales disponibles.")

                if df_variables_corr.empty or not available_correlacion_vars:
                    pass
                elif not selected_vars:
                    st.warning('Selecciona al menos una variable para mostrar la correlación.')
                else:
                    _render_correlacion(
                        df_variables_corr,
                        datos_cortinas_sel,
                        fecha_variables,
                        selected_vars,
                        block_label=block_label,
                        show_ideal_aperturas=st.session_state.get('mostrar_aperturas_ideales', False),
                        df_variables_almacen=df_variables_almacen_corr,
                        compare_with_almacen=st.session_state.get('comparar_con_almacen', False)
                    )

        with tab_corr_regs:
            reg_sensores_tab, reg_cortinas_tab = st.tabs(["Registros sensores", "Registros cortinas"])

            with reg_sensores_tab:
                if datos_sensores_corr.empty:
                    st.info("No hay registros de sensores para los filtros seleccionados.")
                else:
                    st.dataframe(datos_sensores_corr, width='stretch')

            with reg_cortinas_tab:
                if datos_cortinas_sel.empty:
                    st.info("No hay registros de cortinas para los filtros seleccionados.")
                else:
                    st.dataframe(datos_cortinas_sel, width='stretch')
