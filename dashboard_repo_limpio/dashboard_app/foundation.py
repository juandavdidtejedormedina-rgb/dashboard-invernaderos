import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import math
import warnings
import re
import html
import base64
import unicodedata
from functools import lru_cache
from contextlib import nullcontext
from pathlib import Path
from datetime import date, datetime, timedelta
from urllib.parse import quote_plus

from data_loaders import (
    load_dashboard_data,
    load_greenhouse_analysis,
    load_marley_data,
    load_ponderosa_ecowitt_data,
)


@lru_cache(maxsize=4096)
def _normalize_text_key_cached(text):
    normalized = unicodedata.normalize('NFKD', text)
    normalized = ''.join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace(chr(181), 'u').replace(chr(176), ' ')
    normalized = normalized.lower()
    normalized = re.sub(r'[^a-z0-9]+', ' ', normalized)
    return re.sub(r'\s+', ' ', normalized).strip()


@lru_cache(maxsize=8)
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

def _google_maps_embed_url(location_query):
    query = str(location_query or "").strip()
    if not query:
        return ""
    return f"https://www.google.com/maps?q={quote_plus(query)}&output=embed"

def _render_autoplay_video(video_url, height=430):
    video_urls = video_url if isinstance(video_url, (list, tuple)) else [video_url]
    safe_urls = [
        html.escape(str(url or "").strip(), quote=True)
        for url in video_urls
        if str(url or "").strip()
    ]
    if not safe_urls:
        return
    first_url = safe_urls[0]
    playlist_js = "[" + ",".join(f'"{url}"' for url in safe_urls) + "]"

    st.html(
        f"""
        <video
            autoplay
            muted
            playsinline
            controls
            preload="auto"
            style="
                width: 100%;
                height: {height}px;
                object-fit: cover;
                display: block;
                border-radius: 8px;
                background: #111;
            "
        >
            <source src="{first_url}" type="video/mp4">
        </video>
        <script>
            const video = document.currentScript.previousElementSibling;
            const playlist = {playlist_js};
            let currentIndex = 0;
            if (video) {{
                video.muted = true;
                video.addEventListener("ended", () => {{
                    currentIndex = (currentIndex + 1) % playlist.length;
                    video.src = playlist[currentIndex];
                    video.load();
                    video.play().catch(() => {{}});
                }});
                video.play().catch(() => {{}});
            }}
        </script>
        """,
        unsafe_allow_javascript=True
    )


def _get_dashboard_media_config(selected_finca):
    return DASHBOARD_MEDIA.get(selected_finca, DASHBOARD_MEDIA['La Ponderosa'])


def _render_dashboard_media(selected_finca, lazy_load=False):
    media_config = _get_dashboard_media_config(selected_finca)
    video_url = media_config.get('video_urls') or media_config.get('video_url', '')
    location_query = str(media_config.get('location_query', '')).strip()

    if video_url:
        with st.expander("Video introductorio", expanded=not lazy_load):
            if not lazy_load or st.checkbox("Cargar video", key="cargar_video_dashboard"):
                youtube_source_url = video_url[0] if isinstance(video_url, (list, tuple)) else video_url
                youtube_embed_url = _youtube_embed_url(youtube_source_url)
                if youtube_embed_url:
                    st.iframe(youtube_embed_url, height=430)
                else:
                    _render_autoplay_video(video_url)
            else:
                st.caption("Carga el video solo cuando lo necesites.")

    if location_query:
        with st.expander("Ubicación", expanded=not lazy_load):
            if not lazy_load or st.checkbox("Cargar mapa", key="cargar_mapa_dashboard"):
                st.iframe(_google_maps_embed_url(location_query), height=430)
            else:
                st.caption("Carga el mapa solo cuando lo necesites.")

SENSOR_VARIABLES = ['Temperatura', 'Humedad Relativa', 'Radiación PAR', 'Gramos de agua']
PPFD_DISPLAY_NAME = 'PPFD (PAR)'
PPFD_HELP_TEXT = ''
PPFD_DISPLAY_LABEL = 'PPFD (PAR, µmol m⁻² s⁻¹)'
PPFD_DISPLAY_LABEL_ASCII = 'PPFD (PAR, µmol m-2 s-1)'
VARIABLE_LABELS = {
    'Temperatura': 'Temperatura (°C)',
    'Humedad Relativa': 'Humedad Relativa (%)',
    'Radiación PAR': PPFD_DISPLAY_LABEL,
    'Gramos de agua': 'Gramos de agua (g)',
    'LUX': 'LUX'
}
VARIABLE_UNITS = {
    'Temperatura': '°C',
    'Humedad Relativa': '%',
    'Radiación PAR': 'PPFD µmol m⁻² s⁻¹',
    'Gramos de agua': 'g',
    'LUX': 'lux'
}
VARIABLE_COLORS = {
    'Temperatura': '#7DB7FF',
    'Humedad Relativa': '#4A4A4A',
    'Radiación PAR': '#6BEA5B',
    'Gramos de agua': '#F2A04B',
    'LUX': '#B9832F'
}
CORTINA_COLORS = {
    'FRENTE 1': '#5E5AAE',
    'FRENTE 2': '#9089D8',
    'PUERTA 1': '#B67895',
    'PUERTA 2': '#D8AFC3'
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
    'Radiación PAR': PPFD_DISPLAY_NAME,
    'Gramos de agua': 'Gramos de agua (g)',
    'LUX': 'LUX',
    'FRENTE 1': 'Frente 1',
    'FRENTE 2': 'Frente 2',
    'PUERTA 1': 'Puerta 1',
    'PUERTA 2': 'Puerta 2'
}
FILTER_HELP_TEXTS = {
    'modo_dashboard': 'Elige la vista principal: WIGA con cortinas, relación WIGA / ECOWITT, APOGEE / MCI / WIGA, APOGEE, varianza, desviacion estandar, promedio o fuentes individuales.',
    'finca': 'Selecciona la finca que quieres explorar en el dashboard. Los bloques y fechas disponibles se ajustan según esa finca.',
    'modo_fechas': 'Define si quieres analizar un solo día o un rango de varios días.',
    'fecha': 'Selecciona la fecha o el rango que se usará para filtrar los registros visibles en la vista actual.',
    'bloque': 'Selecciona el bloque principal que quieres analizar en la correlación.',
    'bloques_comparados': 'Activa o desactiva los bloques que quieres incluir en la comparación de promedio, desviacion estandar y varianza.',
    'series_visibles': 'Activa las variables ambientales y operativas que deseas mostrar en la gráfica.',
    'comparar_almacen': 'Muestra la serie equivalente de la Estación externa para cada variable ambiental seleccionada.',
    'aperturas_ideales': 'Superpone la apertura ideal calculada sobre las series de frentes y puertas cuando exista la referencia del bloque.',
    'graficas_detalladas': 'Carga las gráficas secundarias solo cuando necesites revisar cada variable por separado.',
    'registros': 'Carga las tablas de registros solo cuando necesites inspeccionar los datos crudos.'
}
VARIABLE_FILTER_HELP = {
    'Temperatura': 'Muestra la temperatura del bloque seleccionado.',
    'Humedad Relativa': 'Muestra la humedad relativa del bloque seleccionado.',
    'Radiación PAR': 'Muestra el PPFD del bloque seleccionado: fotones de luz PAR útiles para fotosíntesis por metro cuadrado por segundo.',
    'Gramos de agua': 'Muestra los gramos de agua del bloque seleccionado.',
    'FRENTE 1': 'Muestra la apertura del Frente 1.',
    'FRENTE 2': 'Muestra la apertura del Frente 2.',
    'PUERTA 1': 'Muestra la apertura de la Puerta 1.',
    'PUERTA 2': 'Muestra la apertura de la Puerta 2.'
}
BRAND_COLORS = {
    'hero': '#545386',
    'sky': '#C2DFEA',
    'rose': '#F4C7CE',
    'beige': '#D8D2C4',
    'graphite': '#383A35',
    'ink': '#2C2E2A',
    'paper': '#F7F4EE',
    'white': '#FFFFFF'
}
APP_DIR = Path(__file__).resolve().parent.parent
DATA_CACHE_VERSION = "2026-05-12-data-refresh-v1"
LOGO_PATH = APP_DIR / 'logo elite.png'
MARLEY_SENSOR_NAMES = ("WIGA", "ECOWITT")
MARLEY_TIME_BUCKET = "30min"
MARLEY_SERIES_END_OFFSET = pd.Timedelta(hours=23, minutes=30)
MARLEY_AXIS_END_OFFSET = pd.Timedelta(hours=23, minutes=59)
POINT_COMPARISON_TOLERANCE = pd.Timedelta(minutes=15)
COMPARISON_RESOLUTION_OPTIONS = (
    "Promedio cada 30 min",
    "Punto por punto",
    "WIGA 30 min + ECOWITT cercano",
)
SOURCE_RESOLUTION_OPTIONS = (
    "Promedio cada 30 min",
    "Punto por punto",
    "Valor más cercano cada 30 min",
)
PONDEROSA_SENSOR_NAMES = ("WIGA", "ECOWITT")
PONDEROSA_ECOWITT_BLOCK_CODE = "35"
PONDEROSA_ECOWITT_RECORDS_DEFAULT = False
PONDEROSA_ECOWITT_DETAILS_DEFAULT = False
PAR_TO_LUX_FACTOR = 54.0
PONDEROSA_LIGHT_SENSOR_NAMES = ("WIGA", "MCI", "APOGEE")
PONDEROSA_LIGHT_VIEW_NAME = "APOGEE MCI WIGA"
PONDEROSA_BLOCK_INFO_VIEW_NAME = "Ficha tecnica"
PONDEROSA_VIEW_GROUPS = {
    "Comparativas": ["WIGA con cortinas", "WIGA relacion ECOWITT", PONDEROSA_LIGHT_VIEW_NAME],
    "Análisis": ["Varianza", "Desviacion estandar", "Promedio"],
    "Contexto tecnico": [PONDEROSA_BLOCK_INFO_VIEW_NAME],
    "Fuentes individuales": ["WIGA", "ECOWITT", "APOGEE", "Cortinas"],
}
MARLY_VIEW_GROUPS = {
    "Comparativas": ["Comparativa"],
    "Análisis": ["Varianza", "Desviacion estandar", "Promedio"],
    "Fuentes individuales": ["Solo WIGA", "Solo ECOWITT"],
}
VIEW_DISPLAY_LABELS = {
    "WIGA relacion ECOWITT": "WIGA relación ECOWITT",
    PONDEROSA_LIGHT_VIEW_NAME: "APOGEE / MCI / WIGA",
    PONDEROSA_BLOCK_INFO_VIEW_NAME: "Ficha técnica",
    "Comparativa": "WIGA relación ECOWITT",
    "Desviacion estandar": "Desviación estándar",
    "Solo WIGA": "WIGA",
    "Solo ECOWITT": "ECOWITT",
}
MARLEY_SHEETS = {
    "WIGA": ["WIGGA MONTAÑA", "WIGA MARLEY"],
    "ECOWITT": ["ECOWITT MONTAÑA", "ECOWIT MARLEY"],
}
MARLEY_VARIABLES = {
    "Gramos de agua (g)": {
        "title": "Comparativa de gramos de agua",
        "unit": "g",
        "colors": {"WIGA": "#4E8D7C", "ECOWITT": "#5AA6A6"},
        "accent": "#4E8D7C",
    },
    "Humedad Relativa (%)": {
        "title": "Comparativa de humedad relativa",
        "unit": "%",
        "colors": {"WIGA": "#4A4A4A", "ECOWITT": "#7DB7FF"},
        "accent": "#8077AE",
    },
    "Temperatura (°C)": {
        "title": "Comparativa de temperatura",
        "unit": "°C",
        "colors": {"WIGA": "#F2A04B", "ECOWITT": "#C06C84"},
        "accent": "#D39A58",
    },
    "Radiación PAR (µmol m-2 s-1)": {
        "title": "Comparativa de PPFD (PAR)",
        "unit": "PPFD µmol m-2 s-1",
        "colors": {"WIGA": "#6BEA5B", "ECOWITT": "#524B82"},
        "accent": "#6BEA5B",
    },
}
MARLEY_CORRELACION_VARIABLE_MAP = {
    "Temperatura (°C)": "Temperatura",
    "Humedad Relativa (%)": "Humedad Relativa",
    "Radiación PAR (µmol m-2 s-1)": "Radiación PAR",
    "Gramos de agua (g)": "Gramos de agua",
}
PONDEROSA_COMPARISON_VARIABLES = {
    "Temperatura": {
        "title": "Comparativa de temperatura",
        "unit": "°C",
        "colors": {"WIGA": "#F2A04B", "ECOWITT": "#C06C84"},
        "accent": "#D39A58",
    },
    "Humedad Relativa": {
        "title": "Comparativa de humedad relativa",
        "unit": "%",
        "colors": {"WIGA": "#4A4A4A", "ECOWITT": "#7DB7FF"},
        "accent": "#8077AE",
    },
    "Radiación PAR": {
        "title": "Comparativa de PPFD (PAR)",
        "unit": "PPFD µmol m-2 s-1",
        "colors": {"WIGA": "#6BEA5B", "ECOWITT": "#524B82"},
        "accent": "#6BEA5B",
    },
}
PONDEROSA_WIGA_VARIABLES = {
    "Temperatura": {
        "title": "Temperatura",
        "unit": "°C",
        "colors": {"WIGA": VARIABLE_COLORS["Temperatura"]},
        "accent": VARIABLE_COLORS["Temperatura"],
    },
    "Humedad Relativa": {
        "title": "Humedad relativa",
        "unit": "%",
        "colors": {"WIGA": VARIABLE_COLORS["Humedad Relativa"]},
        "accent": VARIABLE_COLORS["Humedad Relativa"],
    },
    "Radiación PAR": {
        "title": "PPFD (PAR)",
        "unit": "PPFD µmol m-2 s-1",
        "colors": {"WIGA": VARIABLE_COLORS["Radiación PAR"]},
        "accent": VARIABLE_COLORS["Radiación PAR"],
    },
    "Gramos de agua": {
        "title": "Gramos de agua",
        "unit": "g",
        "colors": {"WIGA": VARIABLE_COLORS["Gramos de agua"]},
        "accent": VARIABLE_COLORS["Gramos de agua"],
    },
}
PONDEROSA_ECOWITT_VARIABLES = {
    **PONDEROSA_COMPARISON_VARIABLES,
}
PONDEROSA_APOGEE_VARIABLES = {
    "LUX": {
        "title": "Luminosidad LUX",
        "unit": "lux",
        "colors": {"APOGEE": "#B9832F"},
        "accent": "#B9832F",
    },
}
PONDEROSA_ECOWITT_DATA_VARIABLES = {
    **PONDEROSA_ECOWITT_VARIABLES,
    **PONDEROSA_APOGEE_VARIABLES,
}
PONDEROSA_LIGHT_VARIABLES = {
    "LUX": {
        "title": "Comparativa de LUX",
        "unit": "lux",
        "colors": {"WIGA": "#5E5AAE", "MCI": "#00A6A6", "APOGEE": "#E07A2F"},
        "accent": "#5E5AAE",
    },
    "Radiación PAR": {
        "title": "Comparativa de PPFD (PAR)",
        "unit": "PPFD µmol m-2 s-1",
        "colors": {"WIGA": "#5E5AAE", "MCI": "#00A6A6", "APOGEE": "#E07A2F"},
        "accent": "#5E5AAE",
    },
}
LOGO_URL_LARGE = "https://raw.githubusercontent.com/juandavdidtejedormedina-rgb/dashboard-invernaderos/main/logo%20elite.png"
LOGO_URL_SMALL = LOGO_URL_LARGE
DASHBOARD_MEDIA = {
    'La Ponderosa': {
        'video_url': (
            "https://raw.githubusercontent.com/"
            "juandavdidtejedormedina-rgb/dashboard-invernaderos/"
            "59df2b2f7fee2b9632ae4865fedae119e81b3b79/"
            "flor%20video.mp4"
        ),
        'location_query': "La Ponderosa - The Elite Flower SAS CI Madrid Cundinamarca Colombia",
    },
    'Marly': {
        'video_urls': [
            "https://raw.githubusercontent.com/juandavdidtejedormedina-rgb/dashboard-invernaderos/277ebb73478df2c61271154170df491f8375f103/video%201.mp4",
            "https://raw.githubusercontent.com/juandavdidtejedormedina-rgb/dashboard-invernaderos/277ebb73478df2c61271154170df491f8375f103/video%202.mp4",
            "https://raw.githubusercontent.com/juandavdidtejedormedina-rgb/dashboard-invernaderos/277ebb73478df2c61271154170df491f8375f103/video%203.mp4",
            "https://raw.githubusercontent.com/juandavdidtejedormedina-rgb/dashboard-invernaderos/277ebb73478df2c61271154170df491f8375f103/video%204.mp4",
            "https://raw.githubusercontent.com/juandavdidtejedormedina-rgb/dashboard-invernaderos/277ebb73478df2c61271154170df491f8375f103/video%205.mp4",
            "https://raw.githubusercontent.com/juandavdidtejedormedina-rgb/dashboard-invernaderos/277ebb73478df2c61271154170df491f8375f103/video%206.mp4",
        ],
        'location_query': "Finca Marly - The Elite Flower SAS CI Madrid Road Facatativa Cundinamarca Colombia",
    }
}
LAZY_LOAD_MEDIA = True
DETAIL_CHARTS_DEFAULT = False
MARLEY_DETAIL_CHARTS_DEFAULT = False
MARLEY_RECORDS_DEFAULT = False
FINCA_OPTIONS = ['La Ponderosa', 'Marly']
BLOCK_FARMS = {
    '27': 'La Ponderosa',
    '34': 'La Ponderosa',
    '35': 'La Ponderosa',
    '38': 'La Ponderosa',
    'ALMACEN': 'La Ponderosa'
}
STREAMLIT_LOGO_WIDTH = 108
STREAMLIT_LOGO_HEIGHT = 108
STREAMLIT_LOGO_BORDER_RADIUS = 8
TEMP_FOCUS_CHART_ENABLED = True
TEMP_FOCUS_CHART_PLACEMENT = 'below'  # Opciones: 'below', 'left', 'right'
TEMP_FOCUS_CHART_HEIGHT = 330
TEMP_FOCUS_CHART_COLUMN_LAYOUT = (1, 1)
TEMP_FOCUS_CHART_TITLE = 'Temperatura del bloque'
HUMIDITY_FOCUS_CHART_ENABLED = True
HUMIDITY_FOCUS_CHART_TITLE = 'Humedad del bloque'
PAR_FOCUS_CHART_ENABLED = True
PAR_FOCUS_CHART_TITLE = 'PPFD (PAR) del bloque'
WATER_FOCUS_CHART_ENABLED = True
WATER_FOCUS_CHART_TITLE = 'Gramos de agua del bloque'
FOCUS_CHART_CONFIGS = (
    (TEMP_FOCUS_CHART_ENABLED, 'Temperatura', TEMP_FOCUS_CHART_TITLE),
    (HUMIDITY_FOCUS_CHART_ENABLED, 'Humedad Relativa', HUMIDITY_FOCUS_CHART_TITLE),
    (PAR_FOCUS_CHART_ENABLED, 'Radiación PAR', PAR_FOCUS_CHART_TITLE),
    (WATER_FOCUS_CHART_ENABLED, 'Gramos de agua', WATER_FOCUS_CHART_TITLE),
)
FOCUS_CHARTS_INTERNAL_HEADING = 'Variables del bloque seleccionado'
FOCUS_CHARTS_EXTERNAL_HEADING = 'Variables de la estación externa'
MOTOR_FOCUS_CHART_ENABLED = True
MOTOR_FOCUS_CHART_TITLE = 'Motores del bloque'
CORR_AXIS_TITLES = {
    'Temperatura': 'Temp.',
    'Humedad Relativa': 'Humedad',
    'Radiación PAR': 'PPFD',
    'Gramos de agua': 'Gramos',
    'LUX': 'LUX',
    '% Apertura Cortinas': 'Cortinas %'
}
CORTINAS_NUMERIC_COLUMNS = [
    '% Apertura A', '% Cierre A', '% Apertura B', '% Cierre B',
    'Duracion Apertura A', 'Duracion Cierre A', 'Duracion Apertura B', 'Duracion Cierre B', 'Culatas %'
]
CORTINAS_TIME_COLUMNS = ['Hora Apertura A', 'Hora Cierre A', 'Hora Apertura B', 'Hora Cierre B']
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
'27': '#6FA8FF',
'34': '#4F4A85',
'35': '#53C66F',
'38': '#E39A46',
'ALMACEN': '#C86F8F'
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

def render_app_foundation():
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
        if logo_base64 else f'<img src="{LOGO_URL_LARGE}" alt="The Elite Flower" class="hero-logo-image">'
    )

    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800;900&display=swap');

    :root {{
        --elite-hero: {BRAND_COLORS['hero']};
        --elite-sky: {BRAND_COLORS['sky']};
        --elite-rose: {BRAND_COLORS['rose']};
        --elite-beige: {BRAND_COLORS['beige']};
        --elite-graphite: {BRAND_COLORS['graphite']};
        --elite-ink: {BRAND_COLORS['ink']};
        --elite-paper: {BRAND_COLORS['paper']};
        --elite-white: {BRAND_COLORS['white']};
        --elite-surface: rgba(255, 255, 255, 0.91);
        --elite-surface-strong: #FFFFFF;
        --elite-line: rgba(84, 83, 134, 0.14);
        --elite-line-soft: rgba(84, 83, 134, 0.08);
        --elite-shadow: 0 12px 28px rgba(56, 58, 53, 0.08);
        --control-idle: rgba(255, 255, 255, 0.10);
        --control-idle-strong: rgba(255, 255, 255, 0.15);
        --control-active: #545386;
        --control-active-deep: #454575;
        --control-hover: rgba(194, 223, 234, 0.18);
        --font-display: 'Montserrat', sans-serif;
        --font-body: 'Montserrat', sans-serif;
        --font-brand: 'Montserrat', sans-serif;
        --streamlit-logo-width: {STREAMLIT_LOGO_WIDTH}px;
        --streamlit-logo-height: {STREAMLIT_LOGO_HEIGHT}px;
        --streamlit-logo-radius: {STREAMLIT_LOGO_BORDER_RADIUS}px;
    }}

    .stApp {{
        background:
            linear-gradient(90deg, rgba(84, 83, 134, 0.035) 1px, transparent 1px),
            linear-gradient(180deg, rgba(255,255,255,0.94) 0%, rgba(255,255,255,0.76) 24%, rgba(247,244,238,0.96) 100%),
            linear-gradient(180deg, #fbfaf7 0%, #f3eee5 100%);
        background-repeat: repeat, no-repeat, no-repeat;
        background-position: center top, center center, center center;
        background-size: 56px 56px, cover, cover;
        color: var(--elite-ink);
        font-family: var(--font-body);
    }}
    html, body, [data-testid="stAppViewContainer"] {{
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
        min-width: 300px !important;
        max-width: 300px !important;
    }}
    section[data-testid="stSidebar"] > div {{
        width: 300px !important;
    }}
    [data-testid="stSidebar"] .block-container {{
        padding: 5.1rem 0.7rem 1rem 0.7rem;
    }}
    [data-testid="stSidebar"] {{
        background:
            linear-gradient(180deg, rgba(84, 83, 134, 0.99) 0%, rgba(73, 73, 125, 0.99) 52%, rgba(56, 58, 53, 0.99) 100%);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 10px 0 28px rgba(31, 36, 48, 0.14);
    }}
    [data-testid="stSidebar"] * {{
        color: #f7f7fb;
    }}
    [data-testid="stSidebarHeader"] {{
        padding-top: 3rem !important;
        padding-bottom: 1rem !important;
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
        z-index: 30 !important;
    }}
    section[data-testid="stSidebar"][aria-expanded="true"] [data-testid="stSidebarCollapseButton"],
    section[data-testid="stSidebar"][aria-expanded="true"] [data-testid="stSidebarHeader"] button {{
        position: absolute !important;
        top: 2rem !important;
        right: 0.45rem !important;
        left: auto !important;
        z-index: 30 !important;
    }}
    [data-testid="stAppViewContainer"] > section[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarCollapseButton"],
    [data-testid="stAppViewContainer"] > section[data-testid="stSidebar"][aria-expanded="false"] [data-testid="stSidebarHeader"] button {{
        position: fixed !important;
        top: 0.95rem !important;
        left: 4.35rem !important;
        right: auto !important;
        z-index: 40 !important;
    }}
    [data-testid="stSidebarCollapseButton"] > button,
    [data-testid="stSidebarHeader"] button {{
        width: 2.5rem !important;
        height: 2.5rem !important;
        min-width: 2.5rem !important;
        min-height: 2.5rem !important;
        border-radius: 999px !important;
        border: 1px solid rgba(255, 255, 255, 0.28) !important;
        background:
            linear-gradient(180deg, rgba(109, 107, 166, 0.98), rgba(78, 77, 128, 0.98)) !important;
        color: #ffffff !important;
        box-shadow:
            0 14px 28px rgba(28, 30, 52, 0.24),
            inset 0 1px 0 rgba(255, 255, 255, 0.22) !important;
        backdrop-filter: blur(10px);
    }}
    [data-testid="stSidebarCollapseButton"] > button:hover,
    [data-testid="stSidebarHeader"] button:hover {{
        border-color: rgba(255, 255, 255, 0.44) !important;
        background:
            linear-gradient(180deg, rgba(123, 121, 180, 1), rgba(88, 86, 142, 1)) !important;
        box-shadow:
            0 18px 34px rgba(28, 30, 52, 0.30),
            inset 0 1px 0 rgba(255, 255, 255, 0.28) !important;
    }}
    [data-testid="stSidebarCollapseButton"] svg,
    [data-testid="stSidebarHeader"] button svg {{
        width: 1.15rem !important;
        height: 1.15rem !important;
        color: #ffffff !important;
        stroke: #ffffff !important;
    }}
    [data-testid="stSidebarHeader"] a {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin: 2rem auto 1.25rem auto !important;
        padding: 0.42rem;
        border: 1px solid rgba(255, 255, 255, 0.58);
        border-radius: 8px;
        background:
            linear-gradient(180deg, rgba(255, 255, 255, 0.30) 0%, rgba(247, 244, 238, 0.13) 100%);
        box-shadow:
            0 12px 24px rgba(18, 20, 38, 0.22),
            inset 0 1px 0 rgba(255, 255, 255, 0.42);
        backdrop-filter: blur(8px);
        transform: translateY(18px);
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
        margin: 4.1rem 0 1.45rem 0.15rem;
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
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.105), rgba(255, 255, 255, 0.055));
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 10px 22px rgba(0, 0, 0, 0.11);
        margin-bottom: 0.9rem;
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
        padding: 0.38rem 0.56rem;
        border-radius: 8px;
        border: 1px solid var(--control-idle-strong);
        background: linear-gradient(180deg, rgba(255,255,255,0.11), rgba(255,255,255,0.055));
        box-shadow: 0 8px 18px rgba(0, 0, 0, 0.10);
        transition: background 0.2s ease, transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    }}
    [data-testid="stSidebar"] [data-testid="stCheckbox"] label:hover {{
        background: linear-gradient(180deg, var(--control-hover), rgba(255,255,255,0.08));
        border-color: rgba(214, 229, 236, 0.50);
        box-shadow: 0 12px 24px rgba(0, 0, 0, 0.14);
        transform: translateY(-1px);
    }}
    [data-testid="stSidebar"] [data-testid="stCheckbox"] label:has([aria-checked="true"]) {{
        border-color: rgba(194, 223, 234, 0.58);
        background: linear-gradient(135deg, rgba(108, 106, 160, 0.95), rgba(84, 83, 134, 0.98));
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.18), 0 14px 28px rgba(53, 52, 88, 0.26);
    }}
    [data-testid="stSidebar"] [data-testid="stCheckbox"] p {{
        font-size: 0.9rem;
        font-weight: 600;
        letter-spacing: 0.01em;
    }}
    [data-testid="stSidebar"] [data-testid="stCheckbox"] svg {{
        fill: var(--elite-white);
    }}
    [data-testid="stSidebar"] .stCheckbox [role="checkbox"] {{
        border-radius: 8px;
    }}
    [data-testid="stSidebar"] div.stButton > button {{
        width: 100%;
        min-height: 2.95rem;
        border-radius: 8px;
        border: 1px solid rgba(214, 229, 236, 0.26);
        background: linear-gradient(135deg, var(--control-active) 0%, var(--control-active-deep) 100%);
        color: var(--elite-white);
        font-family: var(--font-display);
        font-weight: 800;
        font-size: 0.92rem;
        letter-spacing: 0.02em;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.18), 0 12px 24px rgba(25, 48, 83, 0.22);
    }}
    [data-testid="stSidebar"] div.stButton > button:hover {{
        border-color: rgba(214, 229, 236, 0.42);
        background: linear-gradient(135deg, #64639A 0%, #5C5A8E 100%);
        color: var(--elite-white);
        transform: translateY(-1px);
    }}
    .hero-card {{
        position: relative;
        display: grid;
        grid-template-columns: 168px minmax(0, 1fr);
        gap: 1rem;
        align-items: stretch;
        padding: 1.05rem 1.15rem;
        margin: 0 0 1rem 0;
        border: 1px solid rgba(84, 83, 134, 0.16);
        border-radius: 8px;
        background:
            linear-gradient(90deg, rgba(84, 83, 134, 0.98) 0%, rgba(84, 83, 134, 0.92) 54%, rgba(56, 58, 53, 0.95) 100%);
        box-shadow: var(--elite-shadow);
        overflow: hidden;
    }}
    .hero-card::before {{
        content: '';
        position: absolute;
        inset: 1px;
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        pointer-events: none;
    }}
    .hero-logo-shell {{
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.18);
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(247, 244, 238, 0.95));
        min-height: 116px;
        padding: 0.9rem;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.70), 0 12px 24px rgba(36, 31, 61, 0.14);
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
        font-size: 2rem;
        line-height: 1.08;
        letter-spacing: 0;
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
        border-radius: 8px;
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
        border-radius: 8px;
        border: 1px solid var(--elite-line-soft);
        background: linear-gradient(180deg, var(--elite-surface-strong) 0%, rgba(255,255,255,0.90) 100%);
        box-shadow: var(--elite-shadow);
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
        background: transparent;
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
        border-radius: 8px;
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
        letter-spacing: 0;
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
        background: color-mix(in srgb, var(--summary-accent) 14%, white 86%);
        color: color-mix(in srgb, var(--summary-accent) 72%, #2c2e2a 28%);
        font-size: 0.74rem;
        font-weight: 800;
        letter-spacing: 0.02em;
        border: 1px solid color-mix(in srgb, var(--summary-accent) 18%, white 82%);
    }}
    .summary-card-period {{
        color: #6a6d76;
        font-size: 0.78rem;
        font-weight: 500;
        text-align: right;
    }}
    .summary-card-delta {{
        position: relative;
        z-index: 1;
        display: inline-flex;
        align-items: center;
        align-self: flex-start;
        gap: 0.34rem;
        margin-top: 0.52rem;
        padding: 0.26rem 0.58rem;
        border-radius: 999px;
        background: rgba(84, 83, 134, 0.10);
        color: #545386;
        font-size: 0.7rem;
        font-weight: 750;
        letter-spacing: 0.01em;
        max-width: 100%;
        line-height: 1.15;
    }}
    .summary-card-delta-value {{
        flex: 0 0 auto;
        white-space: nowrap;
        font-weight: 850;
    }}
    .summary-card-delta-label {{
        min-width: 0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .summary-card-delta.is-positive {{
        background: rgba(28, 132, 87, 0.11);
        color: #1C8457;
    }}
    .summary-card-delta.is-negative {{
        background: rgba(181, 86, 97, 0.12);
        color: #A34858;
    }}
    .summary-card-delta.is-neutral {{
        background: rgba(95, 100, 114, 0.12);
        color: #5f6472;
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
        letter-spacing: 0;
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
        border-radius: 8px;
        border: 1px solid var(--elite-line-soft);
        background:
            linear-gradient(180deg, rgba(255,255,255,0.94) 0%, rgba(247,244,238,0.96) 100%);
        box-shadow:
            0 12px 28px rgba(45, 48, 64, 0.07),
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
        background: transparent;
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
        border-radius: 8px;
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
        letter-spacing: 0;
        word-break: keep-all;
        overflow-wrap: normal;
        hyphens: none;
    }}
    .info-panel-tag {{
        display: inline-flex;
        align-items: center;
        padding: 0.28rem 0.64rem;
        border-radius: 999px;
        background: color-mix(in srgb, var(--info-accent) 14%, white 86%);
        color: color-mix(in srgb, var(--info-accent) 76%, #2c2e2a 24%);
        border: 1px solid color-mix(in srgb, var(--info-accent) 20%, white 80%);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.68);
        font-size: 0.68rem;
        font-weight: 900;
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
        letter-spacing: 0;
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
        border-radius: 8px;
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
        background: rgba(84, 83, 134, 0.14);
        color: color-mix(in srgb, var(--elite-hero) 78%, #2c2e2a 22%);
        border: 1px solid rgba(84, 83, 134, 0.16);
        font-size: 0.68rem;
        font-weight: 800;
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
        font-weight: 800;
        letter-spacing: 0.01em;
        border: 1px solid rgba(56, 58, 53, 0.10);
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
        border-radius: 8px;
        border: 1px solid rgba(76, 70, 120, 0.18);
        background: linear-gradient(135deg, #6C6AA0 0%, #545386 100%);
        color: var(--elite-white);
        font-family: var(--font-display);
        font-weight: 800;
        padding: 0.56rem 1.1rem;
        letter-spacing: 0.01em;
        box-shadow: 0 12px 24px rgba(60, 58, 102, 0.18);
    }}
    div.stButton > button:hover {{
        border-color: rgba(76, 70, 120, 0.30);
        color: var(--elite-white);
        background: linear-gradient(135deg, #64639A 0%, #5C5A8E 100%);
        transform: translateY(-1px);
    }}
    div[data-testid="stTabs"] [data-baseweb="tab-list"] {{
        gap: 0.55rem;
    }}
    button[data-baseweb="tab"] {{
        border-radius: 8px;
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
        background: linear-gradient(135deg, #6C6AA0 0%, #545386 100%);
        border-color: rgba(76, 70, 120, 0.18) !important;
        box-shadow: 0 16px 30px rgba(60, 58, 102, 0.18);
    }}
    div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{
        display: none !important;
    }}
    div[data-testid="stTabs"] [data-baseweb="tab-border"] {{
        background: rgba(76, 70, 120, 0.10) !important;
    }}
    div[data-testid="stPlotlyChart"],
    div[data-testid="stDataFrame"] {{
        border-radius: 8px;
        border: 1px solid var(--elite-line-soft);
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(255, 255, 255, 0.86));
        box-shadow: var(--elite-shadow);
        padding: 0.45rem 0.45rem 0.2rem 0.45rem;
        backdrop-filter: blur(12px);
    }}
    [data-testid="stMetric"] {{
        background: rgba(255, 255, 255, 0.82);
        border-radius: 8px;
        border: 1px solid rgba(76, 70, 120, 0.08);
        box-shadow: 0 12px 28px rgba(45, 48, 64, 0.06);
        padding: 0.35rem 0.6rem;
    }}
    [data-testid="stInfo"],
    [data-testid="stWarning"],
    [data-testid="stSuccess"],
    [data-testid="stError"] {{
        border-radius: 8px;
        border-width: 1px;
    }}
    .analysis-hero {{
        position: relative;
        overflow: hidden;
        margin: 0.2rem 0 1rem 0;
        padding: 1.2rem 1.22rem 1.08rem 1.22rem;
        border-radius: 8px;
        border: 1px solid var(--elite-line-soft);
        background:
            linear-gradient(180deg, rgba(255,255,255,0.94), rgba(247,244,238,0.96));
        box-shadow: var(--elite-shadow);
    }}
    .analysis-hero::before {{
        content: '';
        position: absolute;
        inset: 0 0 auto 0;
        height: 5px;
        background: linear-gradient(90deg, var(--elite-hero), rgba(194, 223, 234, 0.82));
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
        border-radius: 8px;
        border: 1px solid var(--elite-line-soft);
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
        letter-spacing: 0;
    }}
    .analysis-stat-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.85rem;
        margin: 0.35rem 0 1rem 0;
    }}
    .analysis-stat-card {{
        position: relative;
        overflow: hidden;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid var(--elite-line-soft);
        background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(247,244,238,0.93));
        box-shadow: 0 18px 36px rgba(45, 48, 64, 0.06);
    }}
    .analysis-stat-card::before {{
        content: '';
        position: absolute;
        inset: 0 0 auto 0;
        height: 5px;
        background: linear-gradient(90deg, var(--analysis-accent), rgba(255,255,255,0.25));
    }}
    .analysis-stat-label {{
        margin: 0 0 0.6rem 0;
        color: var(--analysis-accent);
        font-family: var(--font-display);
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.07em;
        text-transform: uppercase;
    }}
    .analysis-stat-main {{
        display: flex;
        align-items: baseline;
        gap: 0.42rem;
        flex-wrap: wrap;
        margin-bottom: 0.55rem;
    }}
    .analysis-stat-main-value {{
        color: var(--elite-ink);
        font-family: var(--font-display);
        font-size: 2rem;
        font-weight: 800;
        line-height: 1.05;
        font-variant-numeric: tabular-nums;
    }}
    .analysis-stat-unit {{
        color: #606674;
        font-size: 0.78rem;
        font-weight: 700;
    }}
    .analysis-stat-subtitle {{
        margin: 0 0 0.72rem 0;
        color: #69707d;
        font-size: 0.84rem;
        line-height: 1.45;
    }}
    .analysis-stat-mini-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 0.55rem;
        padding-top: 0.7rem;
        border-top: 1px solid rgba(76, 70, 120, 0.10);
    }}
    .analysis-stat-mini {{
        min-width: 0;
    }}
    .analysis-stat-mini span {{
        display: block;
        color: #747987;
        font-size: 0.66rem;
        font-weight: 800;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin-bottom: 0.18rem;
    }}
    .analysis-stat-mini strong {{
        display: block;
        color: var(--elite-graphite);
        font-family: var(--font-display);
        font-size: 0.98rem;
        font-weight: 800;
        font-variant-numeric: tabular-nums;
        overflow-wrap: anywhere;
    }}
    .analysis-note {{
        margin: 0.1rem 0 0.95rem 0;
        color: #6d727f;
        font-size: 0.9rem;
    }}
    .series-control-card {{
        position: relative;
        overflow: hidden;
        margin: 0.2rem 0 0.85rem 0;
        padding: 0.95rem 1rem;
        border-radius: 12px;
        border: 1px solid rgba(84,83,134,0.12);
        background:
            radial-gradient(circle at 8% 0%, rgba(231,200,122,0.18), transparent 30%),
            linear-gradient(135deg, rgba(255,255,255,0.97), rgba(247,244,238,0.90));
        box-shadow: 0 16px 34px rgba(45,48,64,0.07);
    }}
    .series-control-kicker {{
        margin: 0 0 0.22rem 0;
        color: var(--elite-hero);
        font-size: 0.74rem;
        font-weight: 900;
        letter-spacing: 0.10em;
        text-transform: uppercase;
    }}
    .series-control-title {{
        margin: 0;
        color: var(--elite-graphite);
        font-family: var(--font-display);
        font-size: 1.08rem;
        font-weight: 900;
    }}
    .series-control-copy {{
        margin: 0.45rem 0 0 0;
        color: #666c78;
        font-size: 0.9rem;
        line-height: 1.5;
    }}
    .series-side-panel-marker {{
        display: block;
        height: 0;
    }}
    [data-testid="stVerticalBlock"]:has(.series-side-panel-marker) {{
        position: sticky;
        top: 0.85rem;
    }}
    [data-testid="stVerticalBlock"]:has(.series-side-panel-marker) .series-control-card {{
        margin-top: 0;
        margin-bottom: 0.65rem;
        padding: 0.78rem 0.85rem;
        border-radius: 8px;
        border-color: rgba(84,83,134,0.16);
        background:
            linear-gradient(145deg, rgba(255,255,255,0.98), rgba(248,246,241,0.96));
        box-shadow: 0 12px 24px rgba(45,48,64,0.055);
    }}
    [data-testid="stVerticalBlock"]:has(.series-side-panel-marker) .series-control-kicker {{
        font-size: 0.68rem;
    }}
    [data-testid="stVerticalBlock"]:has(.series-side-panel-marker) .series-control-title {{
        font-size: 0.98rem;
        line-height: 1.18;
    }}
    [data-testid="stVerticalBlock"]:has(.series-side-panel-marker) .series-control-copy {{
        display: none;
    }}
    [data-testid="stVerticalBlock"]:has(.series-side-panel-marker) [data-testid="stCheckbox"] {{
        margin-bottom: 0.24rem;
    }}
    [data-testid="stVerticalBlock"]:has(.series-side-panel-marker) [data-testid="stCheckbox"] label {{
        width: 100%;
        min-height: 2.45rem;
        padding: 0.28rem 0.56rem;
        border-radius: 999px;
        border: 1px solid rgba(84,83,134,0.16);
        background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(246,244,239,0.96));
        box-shadow: 0 8px 18px rgba(45,48,64,0.055);
    }}
    [data-testid="stVerticalBlock"]:has(.series-side-panel-marker) [data-testid="stCheckbox"] label:hover {{
        border-color: rgba(84,83,134,0.32);
        background: linear-gradient(180deg, rgba(255,255,255,1), rgba(239,236,229,0.98));
        box-shadow: 0 12px 24px rgba(45,48,64,0.08);
    }}
    [data-testid="stVerticalBlock"]:has(.series-side-panel-marker) [data-testid="stCheckbox"] label p {{
        color: var(--elite-graphite);
        font-size: 0.82rem;
        font-weight: 800;
        line-height: 1.15;
    }}
    [data-testid="stVerticalBlock"]:has(.series-side-panel-marker) [data-testid="stCheckbox"] [role="checkbox"] {{
        width: 1rem;
        height: 1rem;
        border-radius: 6px;
        border-color: rgba(84,83,134,0.24);
    }}
    [data-testid="stVerticalBlock"]:has(.series-side-panel-marker) [data-testid="stCheckbox"]:has([aria-checked="true"]) label {{
        border-color: rgba(84,83,134,0.32);
        background: linear-gradient(180deg, rgba(255,255,255,1), rgba(237,232,247,0.98));
        box-shadow:
            inset 0 1px 0 rgba(255,255,255,0.95),
            0 14px 28px rgba(84,83,134,0.10);
    }}
    .series-toolbar-label {{
        margin: 0.2rem 0 0.55rem 0.12rem;
        color: var(--elite-hero);
        font-size: 0.72rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }}
    .series-toolbar-spacer {{
        height: 0.25rem;
    }}
    .series-chip-note {{
        margin: 0.2rem 0 0.85rem 0;
        color: rgba(56, 58, 53, 0.68);
        font-size: 0.84rem;
    }}
    [data-testid="stExpander"]:has(.series-control-card) {{
        border-radius: 12px;
        border: 1px solid rgba(84,83,134,0.12);
        background: linear-gradient(180deg, rgba(255,255,255,0.70), rgba(255,255,255,0.62));
        box-shadow: 0 14px 30px rgba(45,48,64,0.05);
    }}
    [data-testid="stExpander"]:has(.series-control-card) details {{
        padding: 0.15rem 0.2rem 0.35rem 0.2rem;
    }}
    [data-testid="stExpander"]:has(.series-control-card) details summary {{
        padding-bottom: 0.55rem;
    }}
    [data-testid="stExpander"]:has(.series-control-card) div.stButton > button {{
        height: 3.1rem;
        min-height: 3.1rem;
        padding: 0 1rem;
        border-radius: 8px;
        border: 1px solid rgba(84,83,134,0.18);
        background:
            linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,246,241,0.98));
        color: var(--elite-hero);
        font-size: 0.9rem;
        font-weight: 800;
        line-height: 1.15;
        box-shadow: 0 8px 18px rgba(84,83,134,0.07);
    }}
    [data-testid="stExpander"]:has(.series-control-card) div.stButton > button:hover {{
        border-color: rgba(84,83,134,0.32);
        background:
            linear-gradient(180deg, rgba(255,255,255,1), rgba(239,236,229,1));
        color: var(--elite-hero);
        box-shadow: 0 12px 24px rgba(84,83,134,0.12);
    }}
    [data-testid="stExpander"]:has(.series-control-card) [data-testid="stCheckbox"] {{
        margin-bottom: 0.25rem;
    }}
    [data-testid="stExpander"]:has(.series-control-card) [data-testid="stCheckbox"] label {{
        width: 100%;
        height: 3.1rem;
        min-height: 3.1rem;
        padding: 0 0.78rem;
        border-radius: 8px;
        border: 1px solid rgba(84,83,134,0.14);
        background:
            linear-gradient(180deg, rgba(255,255,255,0.98), rgba(248,246,241,0.96));
        box-shadow: 0 8px 18px rgba(45,48,64,0.055);
    }}
    [data-testid="stExpander"]:has(.series-control-card) [data-testid="stCheckbox"] label:hover {{
        border-color: rgba(84,83,134,0.30);
        background:
            linear-gradient(180deg, rgba(255,255,255,1), rgba(239,236,229,0.98));
        box-shadow: 0 12px 24px rgba(45,48,64,0.08);
    }}
    [data-testid="stExpander"]:has(.series-control-card) [data-testid="stCheckbox"] label p {{
        font-size: 0.9rem;
        font-weight: 800;
        line-height: 1.18;
        color: var(--elite-graphite);
    }}
    [data-testid="stExpander"]:has(.series-control-card) [data-testid="stCheckbox"] [role="checkbox"] {{
        width: 1rem;
        height: 1rem;
        border-radius: 6px;
        border-color: rgba(84,83,134,0.24);
    }}
    [data-testid="stExpander"]:has(.series-control-card) [data-testid="stCheckbox"]:has([aria-checked="true"]) label {{
        border-color: rgba(84,83,134,0.30);
        background:
            linear-gradient(180deg, rgba(255,255,255,1), rgba(237,232,247,0.98));
        box-shadow:
            inset 0 1px 0 rgba(255,255,255,0.95),
            0 14px 28px rgba(84,83,134,0.10);
    }}
    [data-testid="stAppViewContainer"] div.stButton > button {{
        border-radius: 999px;
        min-height: 2.72rem;
    }}
    [data-testid="stAppViewContainer"] [data-testid="stCheckbox"] label {{
        gap: 0.48rem;
        align-items: center;
        min-height: 2.55rem;
        padding: 0.36rem 0.55rem;
        border-radius: 999px;
        border: 1px solid rgba(84,83,134,0.10);
        background: rgba(255,255,255,0.70);
        box-shadow: 0 8px 18px rgba(45,48,64,0.04);
        transition: border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
    }}
    [data-testid="stAppViewContainer"] [data-testid="stCheckbox"] label:hover {{
        border-color: rgba(84,83,134,0.24);
        background: rgba(255,255,255,0.92);
        box-shadow: 0 12px 24px rgba(45,48,64,0.07);
    }}
    [data-testid="stAppViewContainer"] [data-testid="stCheckbox"] label p {{
        font-weight: 700;
        color: var(--elite-graphite);
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
        border-radius: 8px;
    }}
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] {{
        display: grid;
        gap: 0.24rem;
    }}
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label {{
        width: 100%;
        margin: 0;
        padding: 0.42rem 0.56rem;
        border-radius: 8px;
        border: 1px solid var(--control-idle-strong);
        background: linear-gradient(180deg, rgba(255,255,255,0.11), rgba(255,255,255,0.055));
        box-shadow: 0 8px 18px rgba(0, 0, 0, 0.10);
        transition: background 0.2s ease, transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
    }}
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:hover {{
        background: linear-gradient(180deg, var(--control-hover), rgba(255,255,255,0.08));
        border-color: rgba(214, 229, 236, 0.50);
        box-shadow: 0 12px 24px rgba(0, 0, 0, 0.14);
        transform: translateY(-1px);
    }}
    [data-testid="stSidebar"] [data-testid="stRadio"] div[role="radiogroup"] > label:has(input:checked) {{
        border-color: rgba(214, 229, 236, 0.58);
        background: linear-gradient(135deg, rgba(108, 106, 160, 0.95), rgba(84, 83, 134, 0.98));
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.18), 0 14px 28px rgba(53, 52, 88, 0.26);
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
        .stApp {{
            background-size: 48px 48px, cover, cover;
        }}
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
        .analysis-stat-grid {{
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

    selected_finca_media = st.session_state.get('finca_compartida', 'La Ponderosa')
    _render_dashboard_media(selected_finca_media, lazy_load=LAZY_LOAD_MEDIA)


# 3. Funciones de carga de datos con corrección de FECHAS



__all__ = [name for name in globals() if not name.startswith("__")]
