import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import io
import warnings
import requests
import re
import html
import base64
from pathlib import Path
from datetime import datetime, timedelta


def _image_to_base64(image_path):
    try:
        return base64.b64encode(Path(image_path).read_bytes()).decode('utf-8')
    except Exception:
        return None

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
    'Temperatura': '#6FAEF7',
    'Humedad Relativa': '#2F3136',
    'Radiación PAR': '#7ED957',
    'Gramos de agua': '#F5A14B'
}
CORTINA_COLORS = {
    'FRENTE 1': '#545386',
    'FRENTE 2': '#8D86BE',
    'PUERTA 1': '#9F6C76',
    'PUERTA 2': '#F4C7CE'
}
BRAND_COLORS = {
    'hero': '#545386',
    'sky': '#C2DFEA',
    'rose': '#F4C7CE',
    'beige': '#D8D2C4',
    'graphite': '#383A35',
    'ink': '#26282F',
    'paper': '#FAF8F3',
    'white': '#FFFFFF'
}
BRAND_KEYWORDS = ['Bold', 'Caring', 'Creative', 'Inspiring', 'Forward Looking']
APP_DIR = Path(__file__).resolve().parent
LOGO_PATH = APP_DIR / 'logo elite.png'
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
st.set_page_config(page_title="The Elite Flower | Monitor Variables B34", layout="wide")
logo_base64 = _image_to_base64(LOGO_PATH)
logo_html = (
    f'<img src="data:image/png;base64,{logo_base64}" alt="The Elite Flower" class="hero-logo-image">'
    if logo_base64 else '<div class="hero-logo-fallback">THE ELITE FLOWER</div>'
)

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@500;600;700;800&family=Roboto:wght@300;400;500;700&display=swap');

:root {{
    --elite-hero: {BRAND_COLORS['hero']};
    --elite-sky: {BRAND_COLORS['sky']};
    --elite-rose: {BRAND_COLORS['rose']};
    --elite-beige: {BRAND_COLORS['beige']};
    --elite-graphite: {BRAND_COLORS['graphite']};
    --elite-ink: {BRAND_COLORS['ink']};
    --elite-paper: {BRAND_COLORS['paper']};
    --elite-white: {BRAND_COLORS['white']};
}}

.stApp {{
    background:
        radial-gradient(circle at top right, rgba(194, 223, 234, 0.45), transparent 25%),
        linear-gradient(180deg, #fffdf8 0%, var(--elite-paper) 100%);
    color: var(--elite-ink);
    font-family: 'Roboto', sans-serif;
}}
[data-testid="stAppViewContainer"] > .main {{
    padding-top: 1.25rem;
}}
[data-testid="stSidebar"] {{
    background:
        linear-gradient(180deg, rgba(84, 83, 134, 0.97) 0%, rgba(56, 58, 53, 0.98) 100%);
    border-right: 1px solid rgba(255, 255, 255, 0.08);
}}
[data-testid="stSidebar"] * {{
    color: #f7f7fb;
}}
[data-testid="stSidebar"] .stExpander {{
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 18px 40px rgba(0, 0, 0, 0.14);
}}
[data-testid="stSidebar"] .stExpander details summary {{
    background: rgba(255, 255, 255, 0.06);
    padding: 0.35rem 0.65rem;
}}
[data-testid="stSidebar"] .stFileUploader {{
    background: rgba(255, 255, 255, 0.06);
    border-radius: 16px;
    border: 1px dashed rgba(255, 255, 255, 0.18);
    padding: 0.55rem 0.55rem 0.2rem 0.55rem;
}}
[data-testid="stSidebar"] .stFileUploader section,
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {{
    background: rgba(255, 255, 255, 0.96);
    border-radius: 14px;
    border: 1px solid rgba(84, 83, 134, 0.14);
}}
[data-testid="stSidebar"] .stFileUploader section *,
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] * {{
    color: var(--elite-ink) !important;
}}
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] svg {{
    fill: var(--elite-hero);
}}
[data-testid="stSidebar"] [data-testid="stFileUploaderFileName"],
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzoneInstructions"] small {{
    color: var(--elite-ink) !important;
}}
.hero-card {{
    display: grid;
    grid-template-columns: 200px minmax(0, 1fr);
    gap: 1.15rem;
    align-items: stretch;
    padding: 1.2rem;
    margin: 0 0 1.2rem 0;
    border: 1px solid rgba(84, 83, 134, 0.12);
    border-radius: 24px;
    background:
        linear-gradient(135deg, rgba(84, 83, 134, 0.96) 0%, rgba(84, 83, 134, 0.88) 52%, rgba(56, 58, 53, 0.96) 100%);
    box-shadow: 0 24px 60px rgba(56, 58, 53, 0.18);
}}
.hero-logo-shell {{
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 20px;
    background: rgba(255, 255, 255, 0.98);
    min-height: 150px;
    padding: 1rem;
}}
.hero-logo-image {{
    width: 100%;
    max-width: 165px;
    height: auto;
    object-fit: contain;
}}
.hero-logo-fallback {{
    font-family: 'Montserrat', sans-serif;
    font-weight: 800;
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
    color: rgba(255, 255, 255, 0.72);
    font-size: 0.86rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    font-weight: 700;
}}
.hero-copy h1 {{
    margin: 0;
    color: var(--elite-white);
    font-family: 'Montserrat', sans-serif;
    font-weight: 800;
    font-size: 2.15rem;
    line-height: 1.06;
}}
.hero-subtitle {{
    margin: 0.75rem 0 0.85rem 0;
    max-width: 48rem;
    color: rgba(255, 255, 255, 0.86);
    font-size: 1rem;
    line-height: 1.6;
}}
.section-intro {{
    margin: 0.4rem 0 0.85rem 0;
    padding: 1rem 1.05rem;
    border-radius: 20px;
    border: 1px solid rgba(84, 83, 134, 0.12);
    background: linear-gradient(135deg, rgba(255,255,255,0.94), rgba(216,210,196,0.35));
}}
.section-kicker {{
    margin: 0 0 0.35rem 0;
    color: var(--elite-hero);
    font-size: 0.78rem;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    font-weight: 700;
}}
.section-title {{
    margin: 0;
    color: var(--elite-graphite);
    font-family: 'Montserrat', sans-serif;
    font-size: 1.45rem;
    font-weight: 700;
}}
.section-text {{
    margin: 0.45rem 0 0 0;
    color: #55575f;
    font-size: 0.97rem;
    line-height: 1.55;
}}
.block-note {{
    margin: 0.5rem 0 1.1rem 0;
    padding: 1rem 1.05rem;
    border: 1px solid rgba(84, 83, 134, 0.16);
    border-left: 5px solid var(--elite-hero);
    border-radius: 18px;
    background: linear-gradient(135deg, rgba(255,255,255,0.96) 0%, rgba(244,199,206,0.25) 100%);
    box-shadow: 0 12px 30px rgba(84, 83, 134, 0.08);
}}
.block-note-title {{
    margin: 0 0 0.25rem 0;
    color: var(--elite-hero);
    font-size: 0.92rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}}
.block-note-text {{
    margin: 0;
    color: #575962;
    font-size: 0.96rem;
    line-height: 1.45;
}}
.block-note-observation {{
    margin: 0.55rem 0 0 0;
    color: var(--elite-graphite);
    font-size: 0.92rem;
    font-weight: 700;
}}
div.stButton > button {{
    border-radius: 999px;
    border: 1px solid rgba(84, 83, 134, 0.2);
    background: linear-gradient(135deg, var(--elite-hero) 0%, #6967a4 100%);
    color: var(--elite-white);
    font-family: 'Montserrat', sans-serif;
    font-weight: 700;
    padding: 0.52rem 1.05rem;
    box-shadow: 0 14px 28px rgba(84, 83, 134, 0.22);
}}
div.stButton > button:hover {{
    border-color: rgba(84, 83, 134, 0.35);
    color: var(--elite-white);
    background: linear-gradient(135deg, #49487b 0%, var(--elite-hero) 100%);
}}
div[data-testid="stPills"] {{
    margin: 0.5rem 0 1rem 0;
}}
div[data-testid="stPills"] button {{
    border-radius: 999px;
    border: 1px solid rgba(84, 83, 134, 0.18);
    background: rgba(255, 255, 255, 0.92);
    color: var(--elite-graphite);
    font-family: 'Roboto', sans-serif;
    font-weight: 500;
    padding: 0.35rem 0.85rem;
    transition: all 0.2s ease;
    box-shadow: 0 6px 18px rgba(56, 58, 53, 0.05);
}}
div[data-testid="stPills"] button:hover {{
    border-color: rgba(84, 83, 134, 0.32);
    background: rgba(194, 223, 234, 0.32);
    color: var(--elite-hero);
}}
div[data-testid="stPills"] button[aria-pressed="true"] {{
    border-color: rgba(84, 83, 134, 0.4);
    background: linear-gradient(135deg, rgba(84, 83, 134, 0.16), rgba(244, 199, 206, 0.34));
    color: var(--elite-hero);
    font-weight: 700;
}}
button[data-baseweb="tab"] {{
    font-family: 'Montserrat', sans-serif;
    font-weight: 700;
}}
button[data-baseweb="tab"][aria-selected="true"] {{
    color: var(--elite-hero) !important;
}}
div[data-testid="stPlotlyChart"],
div[data-testid="stDataFrame"] {{
    border-radius: 22px;
    border: 1px solid rgba(84, 83, 134, 0.08);
    background: rgba(255, 255, 255, 0.82);
    box-shadow: 0 18px 40px rgba(56, 58, 53, 0.08);
    padding: 0.45rem 0.45rem 0.2rem 0.45rem;
}}
[data-testid="stMetric"] {{
    background: rgba(255, 255, 255, 0.8);
    border-radius: 18px;
    border: 1px solid rgba(84, 83, 134, 0.1);
    box-shadow: 0 12px 28px rgba(84, 83, 134, 0.06);
    padding: 0.35rem 0.6rem;
}}
[data-testid="stInfo"],
[data-testid="stWarning"],
[data-testid="stSuccess"],
[data-testid="stError"] {{
    border-radius: 18px;
    border-width: 1px;
}}
[data-testid="stRadio"] label,
[data-testid="stSelectbox"] label,
[data-testid="stDateInput"] label,
[data-testid="stFileUploader"] label {{
    font-family: 'Roboto', sans-serif;
    font-weight: 500;
}}
[data-testid="stSidebar"] .stRadio > div,
[data-testid="stSidebar"] .stDateInput > div,
[data-testid="stSidebar"] .stSelectbox > div[data-baseweb="select"] {{
    background: rgba(255, 255, 255, 0.08);
    border-radius: 14px;
}}
[data-testid="stSidebar"] .stSelectbox > div[data-baseweb="select"] span,
[data-testid="stSidebar"] .stSelectbox > div[data-baseweb="select"] div,
[data-testid="stSidebar"] .stDateInput input {{
    color: var(--elite-ink) !important;
    -webkit-text-fill-color: var(--elite-ink) !important;
    font-weight: 500;
}}
[data-testid="stSidebar"] .stDateInput input::placeholder {{
    color: rgba(56, 58, 53, 0.70) !important;
    -webkit-text-fill-color: rgba(56, 58, 53, 0.70) !important;
}}
[data-testid="stSidebar"] .stSelectbox svg,
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
            <p class="hero-kicker">THE ELITE FLOWER • MANTENIMIENTO Y AUTOMATIZACIÓN</p>
            <h1>Visualizacion Variables Invernaderos</h1>
            <p class="hero-subtitle">
                Panel ejecutivo para analizar sensores, cortinas y comportamiento operativo
                por bloque.
            </p>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# --- CONFIGURACIÓN DE URLS (Mover aquí para evitar NameError) ---
URL_VARIABLES = "https://raw.githubusercontent.com/juandavidtejodermedina-rgb/dashboard-invernaderos/main/Datos_variables.xlsx"
URL_CORTINAS = "https://raw.githubusercontent.com/juandavidtejodermedina-rgb/dashboard-invernaderos/main/Registro_Cortinas_Final.xlsx"

# Definición de la función de descarga
@st.cache_data(show_spinner="Descargando datos desde el repositorio...")
def descargar_desde_github(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.content
    except Exception as e:
        st.error(f"Error al conectar con GitHub: {e}")
        return None

# 2. Selector de archivos en la barra lateral
st.sidebar.header("Datos fuente")
st.sidebar.caption("Usa los archivos de GitHub o sube unos nuevos.")

archivo_variables = st.sidebar.file_uploader("Sube variables (Opcional)", type=["xlsx"])
archivo_cortinas = st.sidebar.file_uploader("Sube cortinas (Opcional)", type=["xlsx"])

# Lógica de asignación de datos
if archivo_variables:
    archivo_variables_bytes = archivo_variables.read()
else:
    archivo_variables_bytes = descargar_desde_github(URL_VARIABLES)

if archivo_cortinas:
    archivo_cortinas_bytes = archivo_cortinas.read()
else:
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


@st.cache_data
def cargar_datos(ruta_bytes):
    if not ruta_bytes:
        return pd.DataFrame()

    try:
        xls = pd.ExcelFile(io.BytesIO(ruta_bytes), engine="openpyxl")
        registros = []

        for sheet in [s for s in xls.sheet_names if s.lower() != 'plantilla']:
            df_sheet = _leer_excel_desde_bytes(ruta_bytes, sheet_name=sheet)
            df_sheet = _limpiar_columnas(df_sheet)

            if 'DateTime' not in df_sheet.columns and len(df_sheet):
                df_sheet = _leer_excel_desde_bytes(ruta_bytes, sheet_name=sheet, skiprows=1)
                df_sheet = _limpiar_columnas(df_sheet)

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


def _sync_corr_bottom_to_top():
    st.session_state['variables_correlacion'] = st.session_state.get('variables_correlacion_bottom', []).copy()


def _get_block_modification(block_name):
    if not block_name:
        return None
    match = re.search(r'(\d+)', str(block_name))
    if not match:
        return None
    return BLOCK_MODIFICATIONS.get(match.group(1))


def _extract_block_code(block_name):
    if not block_name:
        return None
    match = re.search(r'(\d+)', str(block_name))
    return match.group(1) if match else None


def _get_shared_block_options(df_variables_all, df_cortinas_all):
    variable_map = {}
    cortina_map = {}

    if not df_variables_all.empty and 'Bloque' in df_variables_all.columns:
        for block_name in sorted(df_variables_all['Bloque'].dropna().unique()):
            block_code = _extract_block_code(block_name)
            if block_code:
                variable_map[block_code] = block_name

    if not df_cortinas_all.empty and 'Bloque' in df_cortinas_all.columns:
        for block_name in sorted(df_cortinas_all['Bloque'].dropna().unique()):
            block_code = _extract_block_code(block_name)
            if block_code:
                cortina_map[block_code] = block_name

    shared_codes = sorted(set(variable_map) & set(cortina_map), key=lambda value: int(value))
    return shared_codes, variable_map, cortina_map


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

    datos_elem = df_cortinas[df_cortinas[elemento_col] == elemento].copy()
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


def _get_culatas_daily_observation(datos_cortinas):
    if datos_cortinas.empty or 'Culatas %' not in datos_cortinas.columns:
        return None

    valores_culatas = datos_cortinas['Culatas %'].dropna()
    if valores_culatas.empty:
        return None

    ultimo_valor = _normalize_percent_value(valores_culatas.iloc[-1])
    if ultimo_valor is None:
        return None
    return 'Culatas abiertas' if ultimo_valor > 0 else 'Culatas cerradas'


def _get_available_cortina_vars(datos_cortinas):
    if datos_cortinas.empty:
        return []

    available = []
    for config in SIDE_CONFIGS.values():
        element_col = config['element_col']
        if element_col in datos_cortinas.columns:
            available.extend([str(v).strip() for v in datos_cortinas[element_col].dropna().unique() if str(v).strip()])
    return sorted(set(available))


def _get_shared_available_dates(df_variables_all, df_cortinas_all, bloque_variables, bloque_cortinas):
    if bloque_variables is None or bloque_cortinas is None:
        return []

    fechas_variables = set(
        pd.Series(
            df_variables_all[df_variables_all['Bloque'] == bloque_variables]['Fecha_Filtro'].dropna().unique()
        ).tolist()
    )
    fechas_cortinas = set(
        pd.Series(
            df_cortinas_all[df_cortinas_all['Bloque'] == bloque_cortinas]['Fecha'].dropna().unique()
        ).tolist()
    )

    return sorted(fechas_variables & fechas_cortinas)


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


def _render_correlacion(df_variables_all, df_cortinas_all, fecha_variables, fecha_cortinas, bloque_variables, bloque_seleccionado, variables_seleccionadas=None):
    fecha_inicio, fecha_fin = fecha_variables
    multi_day_view = fecha_inicio != fecha_fin
    hover_time_format = '%d/%m %H:%M' if multi_day_view else '%H:%M'
    xaxis_tickformat = '%H:%M\n%d/%m' if multi_day_view else '%H:%M'
    xaxis_title_text = '<b>Fecha y hora</b>' if multi_day_view else '<b>Hora del Día</b>'
    if isinstance(fecha_cortinas, tuple):
        fecha_cortinas_inicio, fecha_cortinas_fin = fecha_cortinas
    else:
        fecha_cortinas_inicio = fecha_cortinas
        fecha_cortinas_fin = fecha_cortinas
    df_variables = df_variables_all[
        (df_variables_all['Fecha_Filtro'] >= fecha_inicio) &
        (df_variables_all['Fecha_Filtro'] <= fecha_fin) &
        (df_variables_all['Bloque'] == bloque_variables)
    ].copy()
    df_cortinas = df_cortinas_all
    datos_cortinas_sel = df_cortinas[
        (df_cortinas['Bloque'] == bloque_seleccionado) &
        (df_cortinas['Fecha'] >= fecha_cortinas_inicio) &
        (df_cortinas['Fecha'] <= fecha_cortinas_fin)
    ].copy()

    sensor_vars = [v for v in SENSOR_VARIABLES if v in df_variables.columns]
    selected_vars = variables_seleccionadas or []
    if df_variables.empty or datos_cortinas_sel.empty or not sensor_vars:
        st.warning("No hay datos disponibles para la combinación seleccionada o no se detectaron las columnas de sensor.")
        return

    if not selected_vars:
        st.warning("Selecciona al menos una variable para mostrar la correlación.")
        return

    available_cortinas = _get_available_cortina_vars(datos_cortinas_sel)

    selected_sensors = [v for v in selected_vars if v in sensor_vars]
    selected_cortinas = [v for v in selected_vars if v in available_cortinas]

    if not selected_sensors and not selected_cortinas:
        st.warning("No se detectaron variables seleccionadas válidas para graficar.")
        return

    df_plot = df_variables[['DateTime'] + selected_sensors].copy() if selected_sensors else pd.DataFrame()
    if selected_sensors:
        df_plot = df_plot.dropna(how='all', subset=selected_sensors)
        if df_plot.empty:
            st.warning("No hay registros de sensores para las variables seleccionadas.")
            return

    fig_corr = go.Figure()
    palette = ['#d62728', '#9467bd', '#8c564b', '#e377c2']
    sensor_render_priority = {
        'Gramos de agua': 1,
        'Temperatura': 2,
        'Humedad Relativa': 3,
        'Radiación PAR': 4
    }
    sensor_traces = []
    cortina_traces = []

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
                )
            )
            sensor_traces.append((
                var_name,
                trace,
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
                color = CORTINA_COLORS.get(str(var_name).upper(), palette[order % len(palette)])
                trace = dict(
                    x=df_state['Hora'],
                    y=df_state['Apertura'],
                    name=str(var_name),
                    mode='lines+markers',
                    line=dict(color=color, width=3.2, shape='hv'),
                    marker=dict(size=5, color=color),
                    hovertemplate=f'<b>%{{x|{hover_time_format}}}</b><br>%{{customdata[0]}}<br>Apertura: %{{y:.0f}}%<br>%{{customdata[1]}}<extra></extra>',
                    customdata=df_state[['Evento', 'Detalle']]
                )
                cortina_traces.append((var_name, trace, color))
                break

    if not sensor_traces and not cortina_traces:
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
            x_domain_end = 0.82
            axis_start = 0.87
            axis_end = 0.95
            right_margin = 220
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

    sensor_traces = sorted(sensor_traces, key=lambda item: item[3])

    for idx, (var_name, trace, color, _) in enumerate(sensor_traces):
        axis_name = sensor_axis_names[idx] if idx < len(sensor_axis_names) else f'y{idx + 2}'
        trace['yaxis'] = None if axis_name == 'y' else axis_name
        fig_corr.add_trace(go.Scatter(**trace))

        serie = df_plot[['DateTime', var_name]].dropna(subset=[var_name]).copy()
        min_val = float(serie[var_name].min())
        max_val = float(serie[var_name].max())
        padding = 2 if var_name == 'Temperatura' else 5 if var_name == 'Humedad Relativa' else max(100, (max_val - min_val) * 0.08) if var_name == 'Radiación PAR' else 2
        range_min = min_val - padding
        if min_val >= 0:
            range_min = max(0, range_min)
        if 'PAR' in var_name and min_val >= 0:
            range_min = -max(35, padding * 0.35)
        range_max = max_val + padding
        axis_range = [range_min, range_max]

        side = 'right'
        position = right_positions[min(idx, len(right_positions) - 1)]

        axis_kwargs = dict(
            title=dict(
                text=CORR_AXIS_TITLES.get(var_name, var_name),
                font=dict(color=color, size=11, family='Montserrat, sans-serif')
            ),
            tickfont=dict(color=color, size=10, family='Roboto, sans-serif'),
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

    if cortina_traces:
        for var_name, trace, color in cortina_traces:
            trace['yaxis'] = 'y2'
            fig_corr.add_trace(go.Scatter(**trace))

        cortina_color = BRAND_COLORS['hero']
        axis_configs['y2'] = dict(
            title=dict(
                text=CORR_AXIS_TITLES['% Apertura Cortinas'],
                font=dict(color=cortina_color, size=11, family='Montserrat, sans-serif')
            ),
            tickfont=dict(color=cortina_color, size=10, family='Roboto, sans-serif'),
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
            text='Correlación: Sensores y Estado de Cortinas',
            x=0,
            xanchor='left',
            y=0.98,
            yanchor='top',
            pad=dict(b=20),
            font=dict(size=22, color=BRAND_COLORS['graphite'], family='Montserrat, sans-serif')
        ),
        xaxis=dict(
            title=dict(
                text=xaxis_title_text,
                font=dict(size=14, family='Montserrat, sans-serif', color=BRAND_COLORS['graphite'])
            ),
            tickformat=xaxis_tickformat,
            tickfont=dict(size=11, family='Roboto, sans-serif', color=BRAND_COLORS['graphite']),
            domain=[0, x_domain_end],
            showgrid=True,
            gridcolor='rgba(84, 83, 134, 0.08)',
            zeroline=False
        ),
        hovermode='x unified',
        template='plotly_white',
        font=dict(family='Roboto, sans-serif', color=BRAND_COLORS['graphite']),
        paper_bgcolor='rgba(255,255,255,0.78)',
        plot_bgcolor='rgba(255,255,255,0.94)',
        hoverlabel=dict(
            bgcolor='rgba(250, 248, 243, 0.97)',
            bordercolor='rgba(84, 83, 134, 0.22)',
            font=dict(family='Roboto, sans-serif', color=BRAND_COLORS['graphite'], size=12)
        ),
        height=620,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.10,
            xanchor='left',
            x=0,
            traceorder='normal',
            font=dict(size=11, family='Roboto, sans-serif', color=BRAND_COLORS['graphite']),
            bgcolor='rgba(255,255,255,0.68)',
            bordercolor='rgba(84, 83, 134, 0.10)',
            borderwidth=1
        ),
        margin=dict(l=50, r=right_margin, t=142, b=55),
        **{f'yaxis{axis_name[1:]}': config for axis_name, config in axis_configs.items()}
    )

    st.plotly_chart(fig_corr, width='stretch')

# 4. Datos cargados en memoria para evitar recálculos repetidos
_df_variables_all = cargar_datos(archivo_variables_bytes) if archivo_variables_bytes else pd.DataFrame()
_df_cortinas_all = cargar_cortinas(archivo_cortinas_bytes) if archivo_cortinas_bytes else pd.DataFrame()

if 'graficar_correlacion' not in st.session_state:
    st.session_state.graficar_correlacion = False

if st.sidebar.button("Detener / limpiar gráficos", key="boton_detener_graficos"):
    st.session_state.graficar_correlacion = False

st.sidebar.header("Filtros compartidos")

shared_block_codes, variable_block_map, cortina_block_map = _get_shared_block_options(_df_variables_all, _df_cortinas_all)
bloque_variables = None
bloque_seleccionado = None

with st.sidebar.expander("Filtros Bloque", expanded=True):
    if _df_variables_all.empty or _df_cortinas_all.empty:
        st.write("Carga ambos archivos para habilitar el bloque compartido.")
    elif not shared_block_codes:
        st.warning("No hay bloques en común entre variables y cortinas.")
    else:
        selected_block_code = st.selectbox(
            "Seleccionar bloque:",
            options=shared_block_codes,
            format_func=lambda code: f"Bloque {code}",
            key="bloque_compartido"
        )
        bloque_variables = variable_block_map.get(selected_block_code)
        bloque_seleccionado = cortina_block_map.get(selected_block_code)

with st.sidebar.expander("Filtros Fechas", expanded=True):
    fecha_variables = None
    fecha_cortinas = None

    if _df_variables_all.empty or _df_cortinas_all.empty:
        st.write("Carga ambos archivos para habilitar el filtro compartido de fechas.")
    elif bloque_variables is None or bloque_seleccionado is None:
        st.write("Selecciona primero el bloque de variables y el bloque de cortinas.")
    else:
        fechas_compartidas = _get_shared_available_dates(
            _df_variables_all,
            _df_cortinas_all,
            bloque_variables,
            bloque_seleccionado
        )

        if not fechas_compartidas:
            st.warning("No hay fechas comunes entre los bloques seleccionados.")
        else:
            min_fecha = min(fechas_compartidas)
            max_fecha = max(fechas_compartidas)

            if min_fecha == max_fecha:
                st.caption("Solo hay una fecha disponible para esa combinación de bloques.")
                fecha_unica = st.selectbox(
                    "Seleccionar fecha:",
                    options=fechas_compartidas,
                    format_func=lambda d: d.strftime('%Y-%m-%d'),
                    key="fecha_compartida_unica"
                )
                fecha_variables = (fecha_unica, fecha_unica)
                fecha_cortinas = (fecha_unica, fecha_unica)
            else:
                modo_fechas = st.radio(
                    "Modo de fechas:",
                    options=["Un día", "Varios días"],
                    horizontal=True,
                    key="modo_fechas_compartidas"
                )

                if modo_fechas == "Un día":
                    fecha_unica = st.selectbox(
                        "Seleccionar fecha:",
                        options=fechas_compartidas,
                        index=len(fechas_compartidas) - 1,
                        format_func=lambda d: d.strftime('%Y-%m-%d'),
                        key="fecha_compartida_un_dia"
                    )
                    fecha_variables = (fecha_unica, fecha_unica)
                    fecha_cortinas = (fecha_unica, fecha_unica)
                else:
                    fecha_inicio = st.date_input(
                        "Fecha inicio:",
                        value=min_fecha,
                        min_value=min_fecha,
                        max_value=max_fecha,
                        key="fecha_inicio_compartida"
                    )
                    fecha_fin = st.date_input(
                        "Fecha fin:",
                        value=max_fecha,
                        min_value=min_fecha,
                        max_value=max_fecha,
                        key="fecha_fin_compartida"
                    )
                    if fecha_fin < fecha_inicio:
                        fecha_inicio, fecha_fin = fecha_fin, fecha_inicio
                    fecha_variables = (fecha_inicio, fecha_fin)
                    fecha_cortinas = (fecha_inicio, fecha_fin)

# Vista principal
tab_correlacion = st.container()

with tab_correlacion:
    st.markdown(
        """
        <div class="section-intro">
            <p class="section-kicker">Monitoreo Inteligente</p>
            <h2 class="section-title">Correlación operativa de sensores y cortinas</h2>
            <p class="section-text">
                Visual ejecutivo para revisar comportamiento ambiental, apertura de cortinas
                y eventos operativos por bloque, con una lectura clara para seguimiento diario
                o análisis de varios días.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    if _df_variables_all.empty or _df_cortinas_all.empty:
        st.warning("Debes cargar ambos archivos (variables y cortinas) para ver este análisis.")
    elif fecha_variables is None or fecha_cortinas is None or bloque_seleccionado is None or bloque_variables is None:
        st.warning("Selecciona bloque y fechas en los filtros de la barra lateral.")
    else:
        fecha_inicio, fecha_fin = fecha_variables
        fecha_cortinas_inicio, fecha_cortinas_fin = fecha_cortinas
        rango_multiple = fecha_inicio != fecha_fin
        df_variables_corr = _df_variables_all[
            (_df_variables_all['Fecha_Filtro'] >= fecha_inicio) &
            (_df_variables_all['Fecha_Filtro'] <= fecha_fin) &
            (_df_variables_all['Bloque'] == bloque_variables)
        ].copy()
        variables_sensor = [v for v in SENSOR_VARIABLES if v in df_variables_corr.columns]
        datos_sensores_corr = (
            df_variables_corr[['DateTime'] + variables_sensor].dropna(how='all', subset=variables_sensor)
            if variables_sensor else pd.DataFrame()
        )
        datos_cortinas_sel = _df_cortinas_all[
            (_df_cortinas_all['Bloque'] == bloque_seleccionado) &
            (_df_cortinas_all['Fecha'] >= fecha_cortinas_inicio) &
            (_df_cortinas_all['Fecha'] <= fecha_cortinas_fin)
        ].copy()

        block_label = bloque_seleccionado or bloque_variables
        block_modification = _get_block_modification(block_label)
        culatas_observation = _get_culatas_daily_observation(datos_cortinas_sel)
        daily_annotations = _get_daily_annotations(datos_cortinas_sel)
        if block_label and (block_modification or culatas_observation or daily_annotations):
            observation_label = 'Observación del rango' if rango_multiple else 'Observación del día'
            annotations_label = 'Anotaciones del rango' if rango_multiple else 'Anotaciones del día'
            note_parts = [
                f'<p class="block-note-title">Modificación aplicada en {html.escape(str(block_label))}</p>'
            ]
            if block_modification:
                note_parts.append(f'<p class="block-note-text">{html.escape(block_modification)}</p>')
            if culatas_observation:
                note_parts.append(f'<p class="block-note-observation">{observation_label}: {html.escape(culatas_observation)}</p>')
            if daily_annotations:
                formatted_annotations = '<br>'.join(html.escape(text) for text in daily_annotations)
                note_parts.append(
                    f'<p class="block-note-text"><strong>{annotations_label}:</strong><br>{formatted_annotations}</p>'
                )
            st.markdown(
                f"""
                <div class="block-note">
                    {''.join(note_parts)}
                </div>
                """,
                unsafe_allow_html=True
            )

        tab_corr_graf, tab_corr_regs = st.tabs(["Correlación", "Registros"])

        with tab_corr_graf:
            graficar_corr = st.button("Graficar correlación", key="boton_graficar_correlacion")
            if graficar_corr:
                st.session_state.graficar_correlacion = True

            if not st.session_state.graficar_correlacion:
                st.info("Presiona el botón Graficar para generar el análisis de correlación.")
            else:
                available_vars = [v for v in SENSOR_VARIABLES if v in _df_variables_all.columns]
                cortina_vars = _get_available_cortina_vars(datos_cortinas_sel)

                available_vars += cortina_vars
                current_context = (
                    str(bloque_variables),
                    str(bloque_seleccionado),
                    str(fecha_inicio),
                    str(fecha_fin),
                    str(fecha_cortinas),
                    tuple(available_vars)
                )
                previous_context = st.session_state.get('variables_correlacion_context')
                if previous_context != current_context:
                    st.session_state['variables_correlacion'] = available_vars.copy()
                    st.session_state['variables_correlacion_bottom'] = available_vars.copy()
                    st.session_state['variables_correlacion_context'] = current_context

                current_top = [v for v in st.session_state.get('variables_correlacion', available_vars.copy()) if v in available_vars]
                current_bottom = [v for v in st.session_state.get('variables_correlacion_bottom', current_top) if v in available_vars]

                st.session_state['variables_correlacion'] = current_top
                if 'variables_correlacion_bottom' not in st.session_state:
                    st.session_state['variables_correlacion_bottom'] = current_top
                else:
                    st.session_state['variables_correlacion_bottom'] = current_bottom

                st.pills(
                    'Mostrar u ocultar variables:',
                    options=available_vars,
                    default=st.session_state['variables_correlacion_bottom'],
                    selection_mode='multi',
                    format_func=lambda v: VARIABLE_LABELS.get(v, v),
                    key='variables_correlacion_bottom',
                    on_change=_sync_corr_bottom_to_top
                )
                selected_vars = st.session_state['variables_correlacion_bottom']
                if not selected_vars:
                    st.warning('Selecciona al menos una variable para mostrar la correlación.')
                else:
                    _render_correlacion(
                        _df_variables_all,
                        _df_cortinas_all,
                        fecha_variables,
                        fecha_cortinas,
                        bloque_variables,
                        bloque_seleccionado,
                        selected_vars
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
