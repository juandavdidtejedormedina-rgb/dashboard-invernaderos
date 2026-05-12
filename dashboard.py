import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import warnings
import requests
import re
import html
import base64
import unicodedata
import shutil
from contextlib import nullcontext
from pathlib import Path
from datetime import date, datetime, timedelta
from urllib.parse import quote_plus
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
APP_DIR = Path(__file__).resolve().parent
DATA_CACHE_VERSION = "2026-05-04-ponderosa-ecowitt-v1"
LOGO_PATH = APP_DIR / 'logo elite.png'
MARLEY_LOCAL_EXCEL_PATHS = [
    APP_DIR / 'Datos Final marley.xlsx',
    APP_DIR / 'Datos Final marley (2).xlsx'
]
MARLEY_REMOTE_EXCEL_URLS = [
    (
        "https://raw.githubusercontent.com/"
        "juandavdidtejedormedina-rgb/dashboard-invernaderos/"
        "89ab929cbeba025053c07941988fc5366e9727bd/"
        "Datos%20Final%20marley.xlsx"
    )
]
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
PONDEROSA_ECOWITT_LOCAL_EXCEL_PATHS = [
    APP_DIR / 'ECOWITT Ponderosa.xlsx'
]
GREENHOUSE_ANALYSIS_LOCAL_EXCEL_PATHS = [
    APP_DIR / 'Analisis invernaderos.xlsx',
    Path.home() / 'OneDrive - Elite Flower' / 'Escritorio' / 'Analisis invernaderos.xlsx',
]
PONDEROSA_ECOWITT_REMOTE_EXCEL_URLS = [
    (
        "https://raw.githubusercontent.com/"
        "juandavdidtejedormedina-rgb/dashboard-invernaderos/"
        "2a0c6005a0ce0e60ae0ab3af99dfc117cf746576/"
        "ECOWITT%20Ponderosa.xlsx"
    )
]
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
PPFD_HELP_TEXT = (
    "PPFD significa Photosynthetic Photon Flux Density: mide el flujo de fotones de luz PAR "
    "útiles para fotosíntesis que llegan a un metro cuadrado cada segundo. En el dashboard se "
    "muestra como PPFD (PAR, µmol m-2 s-1)."
)
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
MARLEY_CANONICAL_COLUMNS = {
    "fecha": "Fecha",
    "hora": "Hora",
    "fecha hora": "FechaHora",
    "fechahora": "FechaHora",
    "tiempo de lectura": "FechaHora",
    "gramos de agua g": "Gramos de agua (g)",
    "gramos de agua": "Gramos de agua (g)",
    "humedad relativa": "Humedad Relativa (%)",
    "humedad relativa %": "Humedad Relativa (%)",
    "humedad relativa (%)": "Humedad Relativa (%)",
    "temperatura c": "Temperatura (°C)",
    "temperatura": "Temperatura (°C)",
    "temperatura montana c": "Temperatura (°C)",
    "radiacion par mol m 2 s 1": "Radiación PAR (µmol m-2 s-1)",
    "radiacion par umol m 2 s 1": "Radiación PAR (µmol m-2 s-1)",
    "radiacion par": "Radiación PAR (µmol m-2 s-1)",
}
PONDEROSA_ECOWITT_CANONICAL_COLUMNS = {
    "timestamp recepcion": "FechaHora",
    "fecha hora": "FechaHora",
    "fechahora": "FechaHora",
    "temperatura c": "Temperatura",
    "temperatura": "Temperatura",
    "humedad relativa": "Humedad Relativa",
    "humedad relativa %": "Humedad Relativa",
    "radiacion par umol m 2 s 1": "Radiación PAR",
    "radiacion par mol m 2 s 1": "Radiación PAR",
    "radiacion par": "Radiación PAR",
    "luz lux": "LUX",
    "lux": "LUX",
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
TEMP_FOCUS_CHART_HEIGHT = 260
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
    position: absolute !important;
    top: 2rem !important;
    right: 0.45rem !important;
    left: auto !important;
    z-index: 20 !important;
}}
[data-testid="stSidebarHeader"] button {{
    position: absolute !important;
    top: 2rem !important;
    right: 0.45rem !important;
    left: auto !important;
    z-index: 20 !important;
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
    grid-template-columns: repeat(3, minmax(0, 1fr));
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

# --- Configuracion de URLs (Mover aqui para evitar NameError) ---
URL_VARIABLES = "https://raw.githubusercontent.com/juandavdidtejedormedina-rgb/dashboard-invernaderos/main/Datos_Variables.xlsx"
URL_VARIABLES_FALLBACKS = (
    URL_VARIABLES,
    "https://raw.githubusercontent.com/juandavdidtejedormedina-rgb/dashboard-invernaderos/8ad936f88e1d3bb9363c8223ec6deeb8222f238c/Datos_Variables.xlsx",
)
URL_CORTINAS = "https://raw.githubusercontent.com/juandavdidtejedormedina-rgb/dashboard-invernaderos/main/Registro_Cortinas_Final.xlsx"
URL_ANALYSIS_FALLBACKS = (
    "https://raw.githubusercontent.com/juandavdidtejedormedina-rgb/dashboard-invernaderos/main/Analisis%20invernaderos.xlsx",
    "https://raw.githubusercontent.com/juandavdidtejedormedina-rgb/dashboard-invernaderos/ef0c3dbe72a317574b9c656386a74a34582aabdf/Analisis%20invernaderos.xlsx",
)
LOCAL_VARIABLES_PATHS = (
    APP_DIR / "Datos_Variables.xlsx",
    APP_DIR / "Datos_variables.xlsx",
)
LOCAL_CORTINAS_PATHS = (
    APP_DIR / "Registro_Cortinas_Final.xlsx",
)

# Definición de la función de descarga
@st.cache_data(show_spinner="Descargando datos desde el repositorio...")
def descargar_desde_github(urls):
    candidate_urls = (urls,) if isinstance(urls, str) else tuple(urls)
    errors = []

    for url in candidate_urls:
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.content
        except requests.RequestException as error:
            errors.append(f"{url} ({error})")

    if errors:
        st.warning(
            "No fue posible descargar un archivo desde GitHub. "
            "Se intentará usar el respaldo local si existe."
        )
    return None


def _read_local_file_bytes(path):
    path = Path(path)
    if not path.exists():
        return None
    try:
        return path.read_bytes()
    except OSError as error:
        temp_copy_path = APP_DIR / f"_tmp_{path.name}"
        try:
            shutil.copy2(path, temp_copy_path)
            file_bytes = temp_copy_path.read_bytes()
            temp_copy_path.unlink(missing_ok=True)
            return file_bytes
        except OSError:
            st.warning(f"No fue posible leer el respaldo local {path.name}: {error}")
            return None


def _read_first_local_file_bytes(paths):
    for path in paths:
        file_bytes = _read_local_file_bytes(path)
        if file_bytes:
            return file_bytes
    return None

# 3. Funciones de carga de datos con corrección de FECHAS

def _limpiar_columnas(df):
    df = df.copy()
    df.columns = (
        df.columns.str.strip()
            .str.replace(r'\s*B\d+\s*$', '', regex=True)
            .str.replace(r'\s+', ' ', regex=True)
    )
    return df


def _build_normalized_text_key(value):
    normalized = unicodedata.normalize('NFKD', str(value))
    normalized = ''.join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace('µ', 'u').replace('°', ' ')
    normalized = normalized.lower()
    normalized = re.sub(r'[^a-z0-9]+', ' ', normalized)
    return re.sub(r'\s+', ' ', normalized).strip()


def _parse_date_series(date_series):
    if pd.api.types.is_datetime64_any_dtype(date_series):
        return pd.to_datetime(date_series, errors='coerce')

    text_values = date_series.astype(str).str.strip()
    text_values = text_values.replace({'': None, 'nan': None, 'NaT': None, 'None': None})
    parsed_dates = pd.Series(pd.NaT, index=text_values.index, dtype='datetime64[ns]')

    iso_mask = text_values.notna() & text_values.str.match(r'^\d{4}-\d{2}-\d{2}$')
    if iso_mask.any():
        parsed_dates.loc[iso_mask] = pd.to_datetime(
            text_values.loc[iso_mask],
            format='%Y-%m-%d',
            errors='coerce'
        )

    remaining_mask = text_values.notna() & parsed_dates.isna()
    if remaining_mask.any():
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            parsed_dates.loc[remaining_mask] = pd.to_datetime(
                text_values.loc[remaining_mask],
                errors='coerce',
                dayfirst=True
            )

    return parsed_dates


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
    fecha_series = _parse_date_series(df['Fecha'])
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
def cargar_datos(ruta_bytes, cache_version=DATA_CACHE_VERSION):
    _ = cache_version
    if not ruta_bytes:
        return pd.DataFrame()

    try:
        xls = pd.ExcelFile(io.BytesIO(ruta_bytes), engine="openpyxl")
        registros = []

        for sheet in [s for s in xls.sheet_names if s.lower() != 'plantilla']:
            df_sheet = pd.DataFrame()

            for read_kwargs in ({}, {'skiprows': 1}):
                candidate = xls.parse(sheet_name=sheet, **read_kwargs)
                candidate = _prepare_variables_sheet(candidate)
                candidate = _limpiar_columnas(candidate)
                if 'DateTime' in candidate.columns:
                    df_sheet = candidate
                    break

            if 'DateTime' not in df_sheet.columns:
                continue

            df_sheet['DateTime'] = _parse_date_series(df_sheet['DateTime'])
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


def _clamp_sidebar_date(value, min_date, max_date):
    if value < min_date:
        return min_date
    if value > max_date:
        return max_date
    return value


def _get_nearest_available_date(value, available_dates):
    if not available_dates:
        return value

    ordered_dates = sorted(available_dates)
    value = _coerce_sidebar_date(value, ordered_dates[-1])
    if value in ordered_dates:
        return value

    previous_dates = [available_date for available_date in ordered_dates if available_date <= value]
    if previous_dates:
        return previous_dates[-1]
    return ordered_dates[0]


def _date_input_with_state(label, default_value, key, min_value, max_value, help_text=None):
    kwargs = {
        'key': key,
        'min_value': min_value,
        'max_value': max_value,
        'help': help_text,
    }
    if key not in st.session_state:
        kwargs['value'] = default_value
    return st.date_input(label, **kwargs)


def _loading_context(enabled, message):
    return st.spinner(message, show_time=True) if enabled else nullcontext()


def _get_sidebar_default_range_end(fecha_inicio, max_date, default_days=7):
    default_span_days = max(1, int(default_days))
    return min(fecha_inicio + timedelta(days=default_span_days - 1), max_date)


def _normalize_sidebar_date_range(fecha_inicio, fecha_fin, min_date, max_date):
    fecha_inicio = _clamp_sidebar_date(fecha_inicio, min_date, max_date)
    fecha_fin = _clamp_sidebar_date(fecha_fin, min_date, max_date)

    if fecha_fin < fecha_inicio:
        fecha_inicio, fecha_fin = fecha_fin, fecha_inicio

    return fecha_inicio, fecha_fin


def _format_selected_period_label(fecha_inicio, fecha_fin):
    if fecha_inicio is None or fecha_fin is None:
        return "Sin periodo seleccionado"
    if fecha_inicio == fecha_fin:
        return fecha_inicio.strftime('%d/%m/%Y')
    return f"{fecha_inicio.strftime('%d/%m/%Y')} a {fecha_fin.strftime('%d/%m/%Y')}"


def _shift_selected_period_day(navigation_state_key, current_date, delta_days, min_fecha, max_fecha, available_dates=None):
    if available_dates:
        ordered_dates = sorted({_coerce_sidebar_date(value, value) for value in available_dates})
        if ordered_dates:
            if current_date in ordered_dates:
                current_index = ordered_dates.index(current_date)
            else:
                candidates = [
                    index
                    for index, available_date in enumerate(ordered_dates)
                    if available_date <= current_date
                ]
                current_index = candidates[-1] if candidates else 0
            target_index = max(0, min(current_index + delta_days, len(ordered_dates) - 1))
            st.session_state[navigation_state_key] = ordered_dates[target_index]
            return

    shifted_date = current_date + timedelta(days=delta_days)
    st.session_state[navigation_state_key] = _clamp_sidebar_date(shifted_date, min_fecha, max_fecha)


def _render_selected_period_banner(
    fecha_periodo,
    min_fecha=None,
    max_fecha=None,
    navigation_state_key=None,
    title_text='Periodo visible',
    available_dates=None
):
    if not fecha_periodo:
        return

    fecha_inicio, fecha_fin = fecha_periodo
    single_day = fecha_inicio == fecha_fin
    period_label = _format_selected_period_label(fecha_inicio, fecha_fin)
    helper_text = (
        'Estás viendo un solo día del historial.'
        if single_day else
        'Estás viendo un rango completo de días.'
    )

    col_info, col_prev, col_next = st.columns([8.5, 1.1, 1.1])
    with col_info:
        st.markdown(
            f"""
            <div style="
                margin: 0.2rem 0 1rem 0;
                padding: 0.95rem 1rem;
                border-radius: 8px;
                background: linear-gradient(135deg, rgba(194,223,234,0.18) 0%, rgba(244,199,206,0.14) 100%);
                border: 1px solid rgba(84, 83, 134, 0.08);
            ">
                <div style="
                    font-family: 'Montserrat', sans-serif;
                    font-size: 0.78rem;
                    font-weight: 800;
                    letter-spacing: 0.04em;
                    text-transform: uppercase;
                    color: {BRAND_COLORS['hero']};
                    margin-bottom: 0.35rem;
                ">
                    {html.escape(title_text)}
                </div>
                <div style="
                    font-family: 'Montserrat', sans-serif;
                    font-size: 1.3rem;
                    font-weight: 800;
                    color: {BRAND_COLORS['graphite']};
                    margin-bottom: 0.2rem;
                ">
                    {html.escape(period_label)}
                </div>
                <div style="
                    font-family: 'Montserrat', sans-serif;
                    font-size: 0.92rem;
                    line-height: 1.5;
                    color: rgba(56, 58, 53, 0.78);
                ">
                    {html.escape(helper_text)}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    can_navigate = bool(
        single_day and
        navigation_state_key and
        min_fecha is not None and
        max_fecha is not None
    )
    ordered_available_dates = sorted(available_dates) if available_dates else None
    prev_limit = ordered_available_dates[0] if ordered_available_dates else min_fecha
    next_limit = ordered_available_dates[-1] if ordered_available_dates else max_fecha
    prev_disabled = (not can_navigate) or fecha_inicio <= prev_limit
    next_disabled = (not can_navigate) or fecha_inicio >= next_limit

    with col_prev:
        st.button(
            "◀",
            key=f"{navigation_state_key}_prev" if navigation_state_key else "period_prev_disabled",
            disabled=prev_disabled,
            width="stretch",
        on_click=_shift_selected_period_day if can_navigate else None,
        args=(navigation_state_key, fecha_inicio, -1, min_fecha, max_fecha, ordered_available_dates) if can_navigate else None
    )

    with col_next:
        st.button(
            "▶",
            key=f"{navigation_state_key}_next" if navigation_state_key else "period_next_disabled",
            disabled=next_disabled,
            width="stretch",
        on_click=_shift_selected_period_day if can_navigate else None,
        args=(navigation_state_key, fecha_inicio, 1, min_fecha, max_fecha, ordered_available_dates) if can_navigate else None
    )


def _render_chart_explanation(title, description, accent=None, kicker='Guía de lectura'):
    if not description:
        return

    accent_color = accent or BRAND_COLORS['hero']
    st.markdown(
        f"""
        <div style="
            position: relative;
            overflow: hidden;
            margin: 0.35rem 0 0.8rem 0;
            padding: 0.86rem 1rem 0.84rem 1.05rem;
            border-radius: 8px;
            border: 1px solid rgba(84, 83, 134, 0.09);
            border-left: 4px solid {accent_color};
            background:
                linear-gradient(135deg, rgba(255,255,255,0.94) 0%, rgba(247,244,238,0.90) 100%);
            box-shadow: 0 14px 32px rgba(45, 48, 64, 0.055);
        ">
            <div style="
                font-family: 'Montserrat', sans-serif;
                font-size: 0.70rem;
                font-weight: 800;
                letter-spacing: 0.10em;
                text-transform: uppercase;
                color: {accent_color};
                margin-bottom: 0.26rem;
            ">
                {html.escape(kicker)}
            </div>
            <div style="
                font-family: 'Montserrat', sans-serif;
                font-size: 1rem;
                font-weight: 800;
                color: {BRAND_COLORS['ink']};
                margin-bottom: 0.22rem;
            ">
                {html.escape(title)}
            </div>
            <div style="
                font-family: 'Montserrat', sans-serif;
                font-size: 0.91rem;
                line-height: 1.55;
                color: rgba(56, 58, 53, 0.82);
            ">
                {html.escape(description)}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


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


def _plotly_chart(fig, **kwargs):
    if fig is not None:
        try:
            fig.update_layout(
                font=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['graphite']),
                paper_bgcolor='rgba(255,255,255,0)',
                plot_bgcolor='rgba(255,255,255,0.66)',
                hoverlabel=dict(
                    bgcolor='rgba(255,255,255,0.96)',
                    bordercolor='rgba(84,83,134,0.18)',
                    font=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['ink'])
                )
            )
            fig.update_xaxes(
                gridcolor='rgba(84,83,134,0.08)',
                zerolinecolor='rgba(84,83,134,0.18)',
                linecolor='rgba(84,83,134,0.16)',
                tickfont=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['graphite'])
            )
            fig.update_yaxes(
                gridcolor='rgba(84,83,134,0.08)',
                zerolinecolor='rgba(84,83,134,0.18)',
                linecolor='rgba(84,83,134,0.16)',
                tickfont=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['graphite'])
            )
        except Exception:
            pass
    st.plotly_chart(fig, width='stretch', **kwargs)


def _dataframe(data, **kwargs):
    st.dataframe(data, width='stretch', **kwargs)


def _format_dashboard_view_option(view_name):
    return VIEW_DISPLAY_LABELS.get(view_name, view_name)


def _get_view_group_for_mode(view_groups, mode):
    for group_name, group_options in view_groups.items():
        if mode in group_options:
            return group_name
    return next(iter(view_groups))


def _format_variable_display_title(title):
    clean_title = str(title or "").replace("Comparativa de ", "").strip()
    if 'ppfd' in _build_normalized_text_key(clean_title):
        return PPFD_DISPLAY_NAME
    return clean_title[:1].upper() + clean_title[1:] if clean_title else clean_title


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


def _resolve_correlacion_axis_layout(num_sensor_axes, has_cortina_axis):
    total_right_axes = max(1, num_sensor_axes + (1 if has_cortina_axis else 0))
    right_axis_step = 0.041
    axis_end = 0.997
    axis_start = axis_end - right_axis_step * (total_right_axes - 1)
    x_domain_end = max(0.76, axis_start - 0.014)
    right_margin = 58 + total_right_axes * 18

    return {
        'x_domain_end': x_domain_end,
        'sensor_positions': [
            axis_start + right_axis_step * index
            for index in range(num_sensor_axes)
        ],
        'cortina_position': axis_end if has_cortina_axis else None,
        'right_margin': right_margin,
    }


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
            'delta_unit_html': '&deg;C',
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
            'delta_unit_html': '%',
            'decimals': 1,
            'icon_svg': (
                '<svg viewBox="0 0 24 24" aria-hidden="true">'
                '<path d="M12 3C9.2 7.1 6.5 9.8 6.5 13a5.5 5.5 0 0 0 11 0C17.5 9.8 14.8 7.1 12 3Z"></path>'
                '</svg>'
            )
        }
    if normalized_key.startswith('radiacion par'):
        return {
            'label': 'PPFD (PAR)',
            'unit_html': 'PPFD &micro;mol m<sup>-2</sup> s<sup>-1</sup>',
            'delta_unit_html': 'PPFD umol/m2/s',
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
            'delta_unit_html': 'g',
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
        'delta_unit_html': '',
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


def _calculate_summary_value(df_variables, var_name, summary_mode_config):
    if df_variables.empty or var_name not in df_variables.columns:
        return None

    serie = pd.to_numeric(df_variables[var_name], errors='coerce').dropna()
    if serie.empty:
        return None

    return summary_mode_config['calculator'](serie)


def _build_summary_delta_html(df_variables, df_reference, var_name, config, summary_mode_config, reference_label):
    summary_value = _calculate_summary_value(df_variables, var_name, summary_mode_config)
    reference_value = _calculate_summary_value(df_reference, var_name, summary_mode_config)

    if summary_value is None or reference_value is None:
        return ''

    delta_value = float(summary_value) - float(reference_value)
    delta_text = _format_summary_number(abs(delta_value), config['decimals'])
    sign = '+' if delta_value > 0 else '-' if delta_value < 0 else ''
    delta_class = 'is-positive' if delta_value > 0 else 'is-negative' if delta_value < 0 else 'is-neutral'

    return (
        f'<span class="summary-card-delta {delta_class}">'
        f'<span class="summary-card-delta-value">{sign}{delta_text} {config.get("delta_unit_html", config["unit_html"])}</span>'
        f'<span class="summary-card-delta-label">vs {html.escape(reference_label)}</span>'
        '</span>'
    )


def _build_summary_cards_html(df_variables, fecha_variables, summary_mode='Promedio', df_reference=None, reference_label='Estación externa'):
    if fecha_variables is None:
        return ''

    fecha_inicio, fecha_fin = fecha_variables
    single_day = fecha_inicio == fecha_fin
    summary_mode_config = _get_summary_mode_config(summary_mode, single_day)
    df_reference = df_reference if isinstance(df_reference, pd.DataFrame) else pd.DataFrame()
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
        delta_markup = _build_summary_delta_html(
            df_variables,
            df_reference,
            var_name,
            config,
            summary_mode_config,
            reference_label
        ) if single_day else ''

        if not df_variables.empty and var_name in df_variables.columns:
            if single_day:
                summary_value = _calculate_summary_value(df_variables, var_name, summary_mode_config)
                if summary_value is not None:
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
                f'{delta_markup}'
                '<div class="summary-card-footer">'
                f'<span class="summary-card-chip">{html.escape(period_chip)}</span>'
                f'<span class="summary-card-period">{html.escape(period_text)}</span>'
                '</div>'
                '</div>'
            )
        )

    return f'<div class="summary-grid">{"".join(cards_html)}</div>'


def _render_summary_cards(df_variables, fecha_variables, summary_mode='Promedio', df_reference=None, reference_label='Estación externa'):
    cards_html = _build_summary_cards_html(
        df_variables,
        fecha_variables,
        summary_mode=summary_mode,
        df_reference=df_reference,
        reference_label=reference_label
    )
    if cards_html:
        st.markdown(cards_html, unsafe_allow_html=True)


def _render_reference_summary_cards(df_reference, fecha_variables, summary_mode, reference_label, df_base=None, base_label='Bloque seleccionado'):
    if not isinstance(df_reference, pd.DataFrame) or df_reference.empty:
        return

    st.markdown(
        f'<p class="analysis-note"><strong>{html.escape(reference_label)}</strong></p>',
        unsafe_allow_html=True
    )
    _render_summary_cards(
        df_reference,
        fecha_variables,
        summary_mode=summary_mode,
        df_reference=df_base,
        reference_label=base_label
    )


def _render_summary_cards_selector(df_variables, fecha_variables, df_reference=None, reference_label='Estación externa', base_label='Bloque seleccionado'):
    _render_chart_explanation(
        'Resumen rápido del periodo',
        'Estas tarjetas condensan las variables ambientales del periodo filtrado. Cambia entre promedio, máximo y mínimo para entender el comportamiento general antes de revisar las gráficas.',
        accent=BRAND_COLORS['hero'],
        kicker='Resumen del análisis'
    )
    summary_modes = ["Promedio", "Máximo", "Mínimo"]
    if st.session_state.get("resumen_metric_option") not in summary_modes:
        st.session_state["resumen_metric_option"] = summary_modes[0]
    summary_mode = st.segmented_control(
        "Métrica del resumen",
        options=summary_modes,
        key="resumen_metric_option",
        help="Calcula solo el resumen visible para mantener la carga más liviana.",
        width="stretch"
    )
    _render_summary_cards(
        df_variables,
        fecha_variables,
        summary_mode=summary_mode,
        df_reference=df_reference,
        reference_label=reference_label
    )
    _render_reference_summary_cards(
        df_reference,
        fecha_variables,
        summary_mode,
        reference_label,
        df_base=df_variables,
        base_label=base_label
    )


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


def _render_correlacion_series_panel(available_vars, selected_block_code, df_variables_almacen):
    if not available_vars:
        st.info("No hay series disponibles para el rango seleccionado.")
        return []

    with st.expander("Configurar series visibles", expanded=True):
        action_col, clear_col, external_col, ideal_col = st.columns([0.14, 0.14, 0.36, 0.36])
        with action_col:
            if st.button("Todas", key="correlacion_select_all", width="stretch"):
                _reset_correlacion_selector(available_vars)
        with clear_col:
            if st.button("Limpiar", key="correlacion_clear_all", width="stretch"):
                for option in available_vars:
                    st.session_state[_selector_state_key(option)] = False
                st.session_state['variables_correlacion'] = []
        with external_col:
            st.checkbox(
                "Comparar con Estación externa",
                key="comparar_con_almacen",
                disabled=selected_block_code == 'ALMACEN' or df_variables_almacen.empty,
                help=FILTER_HELP_TEXTS['comparar_almacen']
            )
        with ideal_col:
            st.checkbox(
                "Aperturas ideales",
                key="mostrar_aperturas_ideales",
                help=FILTER_HELP_TEXTS['aperturas_ideales']
            )

        option_columns = st.columns(min(4, max(1, len(available_vars))))
        for idx, option in enumerate(available_vars):
            state_key = _selector_state_key(option)
            if state_key not in st.session_state:
                st.session_state[state_key] = True
            with option_columns[idx % len(option_columns)]:
                st.checkbox(
                    VARIABLE_SELECTOR_LABELS.get(option, VARIABLE_LABELS.get(option, option)),
                    key=state_key,
                    help=VARIABLE_FILTER_HELP.get(option, FILTER_HELP_TEXTS['series_visibles'])
                )

    return _get_selected_correlacion_vars(available_vars)


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


def _get_finca_for_block(block_name):
    normalized_key = _build_normalized_text_key(block_name)
    if 'marley' in normalized_key or 'marly' in normalized_key:
        return 'Marly'

    block_identifier = _extract_block_identifier(block_name)
    if block_identifier and block_identifier in BLOCK_FARMS:
        return BLOCK_FARMS[block_identifier]

    return 'La Ponderosa'


def _get_block_options(df_variables_all, df_cortinas_all, selected_finca=None):
    variable_map = {}
    cortina_map = {}

    if not df_variables_all.empty and 'Bloque' in df_variables_all.columns:
        for block_name in sorted(df_variables_all['Bloque'].dropna().unique()):
            if selected_finca and _get_finca_for_block(block_name) != selected_finca:
                continue
            block_identifier = _extract_block_identifier(block_name)
            if block_identifier:
                variable_map[block_identifier] = block_name

    if not df_cortinas_all.empty and 'Bloque' in df_cortinas_all.columns:
        for block_name in sorted(df_cortinas_all['Bloque'].dropna().unique()):
            if selected_finca and _get_finca_for_block(block_name) != selected_finca:
                continue
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
                    'Detalle': f"Objetivo: {target_open_level:.0f}% abierto | Duración apertura: {duracion_ap:.0f} min"
                })
                profile.append({
                    'Hora': fin_apertura,
                    'Apertura': target_open_level,
                    'Evento': 'Fin Apertura',
                    'Detalle': f"Nivel alcanzado: {target_open_level:.0f}% abierto | Inicio: {inicio_apertura.strftime('%H:%M')} | Fin: {fin_apertura.strftime('%H:%M')}"
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
                    'Detalle': f"Cierre: {cierre_pct:.0f}% | Duración cierre: {duracion_ci:.0f} min"
                    if cierre_pct is not None else f"Duración cierre: {duracion_ci:.0f} min"
                })
                profile.append({
                    'Hora': fin_cierre,
                    'Apertura': target_close_level,
                    'Evento': 'Fin Cierre',
                    'Detalle': f"Nivel final: {target_close_level:.0f}% abierto | Inicio: {inicio_cierre.strftime('%H:%M')} | Fin: {fin_cierre.strftime('%H:%M')}"
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


def _format_cortina_time(value):
    if pd.isna(value):
        return 'Sin dato'
    if hasattr(value, 'strftime'):
        return value.strftime('%H:%M')
    timestamp = pd.to_datetime(value, errors='coerce')
    if pd.isna(timestamp):
        return str(value)
    return timestamp.strftime('%H:%M')


def _format_cortina_duration(value):
    numeric_value = pd.to_numeric(pd.Series([value]), errors='coerce').iloc[0]
    if pd.isna(numeric_value):
        return 'Sin dato'
    return f"{float(numeric_value):.0f} min"


def _format_cortina_pct(value):
    pct_value = _normalize_percent_value(value)
    if pct_value is None:
        return 'Sin dato'
    return f"{pct_value:.0f}%"


def _build_cortina_operation_rows(datos_cortinas, selected_motors=None):
    if datos_cortinas.empty:
        return pd.DataFrame()

    selected_set = set(selected_motors or [])
    rows = []
    for _, record in datos_cortinas.sort_values('Fecha').iterrows():
        fecha = record.get('Fecha')
        fecha_label = _format_info_day_label(fecha)
        for side_label, config in SIDE_CONFIGS.items():
            motor_name = _normalize_cortina_name(record.get(config['element_col']))
            if not motor_name or (selected_set and motor_name not in selected_set):
                continue

            note_value = record.get(config['note_col'])
            note_text = '' if pd.isna(note_value) else str(note_value).strip()
            if note_text.lower() in {'nan', 'none'}:
                note_text = ''

            rows.append({
                'Fecha': fecha_label,
                'Cortina': VARIABLE_SELECTOR_LABELS.get(motor_name, motor_name),
                'Lado': side_label,
                'Inicio apertura': _format_cortina_time(record.get(config['open_time_col'])),
                'Duración apertura': _format_cortina_duration(record.get(config['open_duration_col'])),
                'Apertura objetivo': _format_cortina_pct(record.get(config['open_pct_col'])),
                'Inicio cierre': _format_cortina_time(record.get(config['close_time_col'])),
                'Duración cierre': _format_cortina_duration(record.get(config['close_duration_col'])),
                'Cierre registrado': _format_cortina_pct(record.get(config['close_pct_col'])),
                'Comentario': note_text or 'Sin comentario'
            })

    return pd.DataFrame(rows)


def _render_cortina_operation_summary(datos_cortinas, selected_motors):
    operation_rows = _build_cortina_operation_rows(datos_cortinas, selected_motors)
    if operation_rows.empty:
        st.info("No hay eventos operativos de apertura o cierre para las cortinas seleccionadas.")
        return

    st.markdown("### Detalle operativo de cortinas")
    _render_chart_explanation(
        "Aperturas y cierres registrados",
        "Esta tabla resume cuándo empezó a abrir o cerrar cada frente o puerta, cuánto duró el movimiento, el porcentaje objetivo y los comentarios registrados en el Excel.",
        accent=BRAND_COLORS['hero']
    )
    _dataframe(operation_rows, hide_index=True)


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

    sensor_candidates = list(dict.fromkeys([*SENSOR_VARIABLES, 'LUX']))
    return [
        var_name for var_name in sensor_candidates
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

    fechas_variables = df_variables_all.loc[
        df_variables_all['Bloque'].eq(bloque_variables),
        'Fecha_Filtro'
    ].dropna().unique().tolist()
    return sorted(fechas_variables)


def _get_all_variable_dates_for_blocks(df_variables_all, block_names=None):
    if (
        df_variables_all.empty or
        'Fecha_Filtro' not in df_variables_all.columns or
        'Bloque' not in df_variables_all.columns
    ):
        return []

    filtered_df = df_variables_all
    if block_names:
        filtered_df = filtered_df[filtered_df['Bloque'].isin(block_names)]

    fechas_variables = pd.Series(filtered_df['Fecha_Filtro'].dropna().unique()).tolist()
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


def _resolve_marley_sheet_name(sheet_names, aliases, source_name):
    for alias in aliases:
        if alias in sheet_names:
            return alias

    normalized_lookup = {_build_normalized_text_key(name): name for name in sheet_names}
    for alias in aliases:
        match = normalized_lookup.get(_build_normalized_text_key(alias))
        if match:
            return match

    raise ValueError(
        f"No se encontró una hoja válida para {source_name}. "
        f"Hojas disponibles: {', '.join(sheet_names)}"
    )


def _standardize_marley_columns(df):
    renamed = {}
    for column in df.columns:
        normalized = _build_normalized_text_key(column)
        if normalized in MARLEY_CANONICAL_COLUMNS:
            renamed[column] = MARLEY_CANONICAL_COLUMNS[normalized]
    return df.rename(columns=renamed)


def _ensure_marley_expected_columns(df):
    for column in ["Fecha", "Hora", *MARLEY_VARIABLES.keys()]:
        if column not in df.columns:
            df[column] = pd.NA
    return df


def _coerce_marley_measurement_columns(df):
    for column in MARLEY_VARIABLES:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors='coerce')
    return df


def _load_marley_wiga_sheet(workbook, sheet_name):
    df = workbook.parse(sheet_name=sheet_name)
    df = _standardize_marley_columns(df)
    df = _ensure_marley_expected_columns(df)
    df = _coerce_marley_measurement_columns(df)
    return df


def _load_marley_ecowitt_sheet(workbook, sheet_name):
    df = workbook.parse(sheet_name=sheet_name)
    df = _standardize_marley_columns(df)

    if 'FechaHora' not in df.columns:
        raw = workbook.parse(sheet_name=sheet_name, header=None)
        raw = raw.iloc[:, :5].copy()
        if raw.shape[1] >= 5:
            raw.columns = [
                'FechaHora',
                'Gramos de agua (g)',
                'Humedad Relativa (%)',
                'Radiación PAR (µmol m-2 s-1)',
                'Temperatura (°C)',
            ]
        else:
            raw = raw.iloc[:, :4].copy()
            raw.columns = [
                'FechaHora',
                'Humedad Relativa (%)',
                'Radiación PAR (µmol m-2 s-1)',
                'Temperatura (°C)',
            ]
        df = raw

    df['FechaHora'] = pd.to_datetime(df['FechaHora'], errors='coerce', dayfirst=True)
    df = _ensure_marley_expected_columns(df)
    df = _coerce_marley_measurement_columns(df)
    df = df.dropna(subset=['FechaHora'])
    df['Fecha'] = df['FechaHora'].dt.strftime('%Y-%m-%d')
    df['Hora'] = df['FechaHora'].dt.strftime('%H:%M:%S')
    return df[['Fecha', 'Hora', *MARLEY_VARIABLES.keys()]]


def _resolve_marley_excel_sources():
    sources = []
    for candidate in MARLEY_LOCAL_EXCEL_PATHS:
        if candidate.exists():
            sources.append(candidate)
    sources.extend(MARLEY_REMOTE_EXCEL_URLS)
    return sources


def _build_marley_source_signature(excel_source):
    if isinstance(excel_source, Path):
        stat = excel_source.stat()
        return f"{excel_source}|{stat.st_mtime_ns}|{stat.st_size}"
    return str(excel_source)


def _open_marley_workbook(excel_source):
    if isinstance(excel_source, Path):
        return pd.ExcelFile(excel_source)

    response = requests.get(excel_source, timeout=45)
    response.raise_for_status()
    return pd.ExcelFile(io.BytesIO(response.content))


@st.cache_data(show_spinner="Cargando datos de Marly...")
def _load_marley_data_from_source(excel_source, source_signature):
    _ = source_signature
    workbook = _open_marley_workbook(excel_source)
    source_frames = {}

    for source_name, aliases in MARLEY_SHEETS.items():
        sheet_name = _resolve_marley_sheet_name(workbook.sheet_names, aliases, source_name)
        if source_name == 'WIGA':
            df = _load_marley_wiga_sheet(workbook, sheet_name)
        else:
            df = _load_marley_ecowitt_sheet(workbook, sheet_name)

        df['FechaHora'] = pd.to_datetime(
            df['Fecha'].astype(str) + ' ' + df['Hora'].astype(str),
            errors='coerce'
        )
        df = df.dropna(subset=['FechaHora']).sort_values('FechaHora')
        df['Fecha_Filtro'] = df['FechaHora'].dt.date
        df = df[['FechaHora', 'Fecha_Filtro', *MARLEY_VARIABLES.keys()]].copy()

        for variable in MARLEY_VARIABLES:
            df.rename(columns={variable: f"{variable} - {source_name}"}, inplace=True)
        source_frames[source_name] = df

    merged = None
    for frame in source_frames.values():
        merge_frame = frame.drop(columns=['Fecha_Filtro'], errors='ignore')
        merged = merge_frame if merged is None else merged.merge(merge_frame, on='FechaHora', how='outer')

    if merged is None:
        raise ValueError("No fue posible construir la tabla consolidada de Marly.")

    merged = merged.sort_values('FechaHora').reset_index(drop=True)
    merged['Fecha_Filtro'] = merged['FechaHora'].dt.date
    return merged, source_frames


def _load_marley_data():
    errors = []
    for excel_source in _resolve_marley_excel_sources():
        try:
            return _load_marley_data_from_source(excel_source, _build_marley_source_signature(excel_source))
        except Exception as error:
            errors.append(f"{excel_source}: {error}")

    raise ValueError("No fue posible cargar los datos de Marly.\n" + "\n".join(errors))


def _build_marley_full_time_index(selected_range):
    start_date, end_date = selected_range
    return pd.date_range(
        start=pd.Timestamp(start_date),
        end=pd.Timestamp(end_date) + MARLEY_SERIES_END_OFFSET,
        freq=MARLEY_TIME_BUCKET,
    )


def _build_marley_hourly_series(df, column_name, selected_range):
    source_df = df[['FechaHora', column_name]].dropna(subset=[column_name]).copy()
    if source_df.empty:
        return source_df

    source_df['FechaHora'] = source_df['FechaHora'].dt.floor(MARLEY_TIME_BUCKET)
    source_df = source_df.groupby('FechaHora', as_index=False)[column_name].mean()
    full_index = _build_marley_full_time_index(selected_range)
    source_df = source_df.set_index('FechaHora').reindex(full_index).rename_axis('FechaHora').reset_index()
    return source_df


def _build_marley_hourly_comparison(df, variable, selected_range):
    wiga_col = f"{variable} - WIGA"
    ecowitt_col = f"{variable} - ECOWITT"

    hourly_wiga = _build_marley_hourly_series(df, wiga_col, selected_range).rename(columns={wiga_col: 'WIGA'})
    hourly_eco = _build_marley_hourly_series(df, ecowitt_col, selected_range).rename(columns={ecowitt_col: 'ECOWITT'})
    comparison = hourly_wiga.merge(hourly_eco, on='FechaHora', how='outer')
    comparison['DiffPct'] = pd.NA
    comparison['DiffValue'] = pd.NA
    comparison['SignedDiff'] = pd.NA

    valid_mask = comparison['WIGA'].notna() & comparison['ECOWITT'].notna()
    comparison.loc[valid_mask, 'SignedDiff'] = comparison.loc[valid_mask, 'WIGA'] - comparison.loc[valid_mask, 'ECOWITT']
    comparison.loc[valid_mask, 'DiffValue'] = comparison.loc[valid_mask, 'SignedDiff'].abs()

    pct_base = (comparison.loc[valid_mask, 'WIGA'].abs() + comparison.loc[valid_mask, 'ECOWITT'].abs()) / 2
    valid_pct_index = pct_base[pct_base != 0].index
    comparison.loc[valid_pct_index, 'DiffPct'] = (
        comparison.loc[valid_pct_index, 'DiffValue'] / pct_base.loc[valid_pct_index] * 100
    )
    comparison['SignedDiffLabel'] = comparison['SignedDiff'].apply(
        lambda value: "No disponible" if pd.isna(value) else f"{value:+.2f}"
    )
    comparison['DiffValueLabel'] = comparison['DiffValue'].apply(
        lambda value: "No disponible" if pd.isna(value) else f"{value:.2f}"
    )
    comparison['DiffPctLabel'] = comparison['DiffPct'].apply(
        lambda value: "No disponible" if pd.isna(value) else f"{value:.2f}%"
    )
    return comparison


def _finalize_sensor_comparison(comparison, sensor_names):
    comparison = comparison.copy()
    for source_name in sensor_names:
        if source_name not in comparison.columns:
            comparison[source_name] = pd.NA
        comparison[source_name] = pd.to_numeric(comparison[source_name], errors='coerce')

    comparison['DiffPct'] = pd.NA
    comparison['DiffValue'] = pd.NA
    comparison['SignedDiff'] = pd.NA

    if len(sensor_names) >= 2:
        first_source, second_source = sensor_names[:2]
        valid_mask = comparison[first_source].notna() & comparison[second_source].notna()
        comparison.loc[valid_mask, 'SignedDiff'] = (
            comparison.loc[valid_mask, first_source] -
            comparison.loc[valid_mask, second_source]
        )
        comparison.loc[valid_mask, 'DiffValue'] = comparison.loc[valid_mask, 'SignedDiff'].abs()
        pct_base = (
            comparison.loc[valid_mask, first_source].abs() +
            comparison.loc[valid_mask, second_source].abs()
        ) / 2
        valid_pct_index = pct_base[pct_base != 0].index
        comparison.loc[valid_pct_index, 'DiffPct'] = (
            comparison.loc[valid_pct_index, 'DiffValue'] / pct_base.loc[valid_pct_index] * 100
        )

    comparison['SignedDiffLabel'] = comparison['SignedDiff'].apply(
        lambda value: "No disponible" if pd.isna(value) else f"{value:+.2f}"
    )
    comparison['DiffValueLabel'] = comparison['DiffValue'].apply(
        lambda value: "No disponible" if pd.isna(value) else f"{value:.2f}"
    )
    comparison['DiffPctLabel'] = comparison['DiffPct'].apply(
        lambda value: "No disponible" if pd.isna(value) else f"{value:.2f}%"
    )
    return comparison.sort_values('FechaHora').reset_index(drop=True)


def _build_point_comparison(df, variable, sensor_names, tolerance=POINT_COMPARISON_TOLERANCE):
    source_frames = {}
    for source_name in sensor_names:
        column_name = f"{variable} - {source_name}"
        if column_name not in df.columns:
            source_frames[source_name] = pd.DataFrame(columns=['FechaHora', source_name])
            continue

        source_df = df[['FechaHora', column_name]].dropna(subset=[column_name]).copy()
        if source_df.empty:
            source_frames[source_name] = pd.DataFrame(columns=['FechaHora', source_name])
            continue

        source_df['FechaHora'] = pd.to_datetime(source_df['FechaHora'], errors='coerce')
        source_df = source_df.dropna(subset=['FechaHora'])
        source_df[column_name] = pd.to_numeric(source_df[column_name], errors='coerce')
        source_df = (
            source_df
            .dropna(subset=[column_name])
            .groupby('FechaHora', as_index=False)[column_name]
            .mean()
            .sort_values('FechaHora')
            .rename(columns={column_name: source_name})
        )
        source_frames[source_name] = source_df

    if len(sensor_names) >= 2:
        first_source, second_source = sensor_names[:2]
        first_df = source_frames[first_source]
        second_df = source_frames[second_source]
        if not first_df.empty and not second_df.empty:
            comparison = pd.merge_asof(
                first_df,
                second_df,
                on='FechaHora',
                direction='nearest',
                tolerance=tolerance
            )
            return _finalize_sensor_comparison(comparison, sensor_names)

    comparison = None
    for source_name in sensor_names:
        source_df = source_frames[source_name]
        if source_df.empty:
            continue
        comparison = source_df if comparison is None else comparison.merge(source_df, on='FechaHora', how='outer')

    if comparison is None:
        return pd.DataFrame(columns=['FechaHora', *sensor_names, 'DiffPct', 'DiffValue', 'SignedDiff'])

    return _finalize_sensor_comparison(comparison, sensor_names)


def _build_wiga_anchor_nearest_comparison(
    df,
    variable,
    sensor_names,
    selected_range,
    hourly_builder,
    tolerance=POINT_COMPARISON_TOLERANCE
):
    if len(sensor_names) < 2:
        return pd.DataFrame(columns=['FechaHora', *sensor_names, 'DiffPct', 'DiffValue', 'SignedDiff'])

    first_source, second_source = sensor_names[:2]
    first_col = f"{variable} - {first_source}"
    second_col = f"{variable} - {second_source}"
    if df.empty or first_col not in df.columns or second_col not in df.columns:
        return pd.DataFrame(columns=['FechaHora', *sensor_names, 'DiffPct', 'DiffValue', 'SignedDiff'])

    first_df = hourly_builder(df, first_col, selected_range)
    if first_df.empty or first_col not in first_df.columns:
        return pd.DataFrame(columns=['FechaHora', *sensor_names, 'DiffPct', 'DiffValue', 'SignedDiff'])

    first_df = (
        first_df[['FechaHora', first_col]]
        .dropna(subset=[first_col])
        .sort_values('FechaHora')
        .rename(columns={first_col: first_source})
    )
    if first_df.empty:
        return pd.DataFrame(columns=['FechaHora', *sensor_names, 'DiffPct', 'DiffValue', 'SignedDiff'])

    second_df = df[['FechaHora', second_col]].dropna(subset=[second_col]).copy()
    if second_df.empty:
        comparison = first_df.copy()
        comparison[second_source] = pd.NA
        return _finalize_sensor_comparison(comparison, sensor_names)

    second_df['FechaHora'] = pd.to_datetime(second_df['FechaHora'], errors='coerce')
    second_df[second_col] = pd.to_numeric(second_df[second_col], errors='coerce')
    second_df = (
        second_df
        .dropna(subset=['FechaHora', second_col])
        .groupby('FechaHora', as_index=False)[second_col]
        .mean()
        .sort_values('FechaHora')
        .rename(columns={second_col: second_source})
    )
    if second_df.empty:
        comparison = first_df.copy()
        comparison[second_source] = pd.NA
        return _finalize_sensor_comparison(comparison, sensor_names)

    comparison = pd.merge_asof(
        first_df,
        second_df,
        on='FechaHora',
        direction='nearest',
        tolerance=tolerance
    )
    return _finalize_sensor_comparison(comparison, sensor_names)


def _build_nearest_series_to_time_grid(
    df,
    column_name,
    selected_range,
    tolerance=POINT_COMPARISON_TOLERANCE
):
    if df.empty or column_name not in df.columns:
        return pd.DataFrame(columns=['FechaHora', column_name])

    source_df = df[['FechaHora', column_name]].dropna(subset=[column_name]).copy()
    if source_df.empty:
        return pd.DataFrame(columns=['FechaHora', column_name])

    source_df['FechaHora'] = pd.to_datetime(source_df['FechaHora'], errors='coerce')
    source_df[column_name] = pd.to_numeric(source_df[column_name], errors='coerce')
    source_df = (
        source_df
        .dropna(subset=['FechaHora', column_name])
        .groupby('FechaHora', as_index=False)[column_name]
        .mean()
        .sort_values('FechaHora')
    )
    if source_df.empty:
        return pd.DataFrame(columns=['FechaHora', column_name])

    anchors = pd.DataFrame({'FechaHora': _build_ponderosa_full_time_index(selected_range)})
    nearest_df = pd.merge_asof(
        anchors.sort_values('FechaHora'),
        source_df.sort_values('FechaHora'),
        on='FechaHora',
        direction='nearest',
        tolerance=tolerance
    )
    return nearest_df


def _build_difference_table_30min(
    df,
    variables,
    sensor_names,
    selected_range,
    resolution_label,
    hourly_comparison_builder,
    hourly_series_builder,
    variable_configs
):
    if df.empty or len(sensor_names) < 2:
        return pd.DataFrame(), ""

    first_source, second_source = sensor_names[:2]
    use_nearest = resolution_label != COMPARISON_RESOLUTION_OPTIONS[0]
    table_mode = (
        "WIGA 30 min + ECOWITT cercano"
        if use_nearest else
        "Promedio cada 30 min"
    )
    rows = []

    for variable in variables:
        comparison = (
            _build_wiga_anchor_nearest_comparison(
                df,
                variable,
                sensor_names,
                selected_range,
                hourly_series_builder
            )
            if use_nearest else
            hourly_comparison_builder(df, variable, selected_range)
        )
        if comparison.empty:
            continue

        comparison = comparison.copy()
        comparison = comparison.dropna(how='all', subset=list(sensor_names))
        if comparison.empty:
            continue

        config = variable_configs.get(variable, {})
        unit = config.get('unit', VARIABLE_UNITS.get(variable, ''))
        variable_label = _format_variable_display_title(
            config.get('title', VARIABLE_SELECTOR_LABELS.get(variable, variable))
        )

        for _, row in comparison.iterrows():
            timestamp = pd.to_datetime(row.get('FechaHora'), errors='coerce')
            if pd.isna(timestamp):
                continue
            wiga_value = pd.to_numeric(pd.Series([row.get(first_source)]), errors='coerce').iloc[0]
            ecowitt_value = pd.to_numeric(pd.Series([row.get(second_source)]), errors='coerce').iloc[0]
            if pd.isna(wiga_value) and pd.isna(ecowitt_value):
                continue

            signed_diff = (
                wiga_value - ecowitt_value
                if pd.notna(wiga_value) and pd.notna(ecowitt_value) else
                pd.NA
            )
            abs_diff = abs(signed_diff) if pd.notna(signed_diff) else pd.NA
            pct_base = (
                (abs(wiga_value) + abs(ecowitt_value)) / 2
                if pd.notna(wiga_value) and pd.notna(ecowitt_value) else
                pd.NA
            )
            diff_pct = (
                abs_diff / pct_base * 100
                if pd.notna(abs_diff) and pd.notna(pct_base) and pct_base != 0 else
                pd.NA
            )

            rows.append({
                'Fecha': timestamp.strftime('%Y-%m-%d'),
                'Hora': timestamp.strftime('%H:%M'),
                'Variable': variable_label,
                'Unidad': unit,
                first_source: round(float(wiga_value), 2) if pd.notna(wiga_value) else pd.NA,
                second_source: round(float(ecowitt_value), 2) if pd.notna(ecowitt_value) else pd.NA,
                'Diferencia WIGA - ECOWITT': round(float(signed_diff), 2) if pd.notna(signed_diff) else pd.NA,
                'Diferencia absoluta': round(float(abs_diff), 2) if pd.notna(abs_diff) else pd.NA,
                'Diferencia %': round(float(diff_pct), 2) if pd.notna(diff_pct) else pd.NA,
            })

    if not rows:
        return pd.DataFrame(), table_mode

    table = pd.DataFrame(rows)
    return table.sort_values(['Fecha', 'Hora', 'Variable']).reset_index(drop=True), table_mode


def _render_difference_table_30min(
    df,
    variables,
    sensor_names,
    selected_range,
    resolution_label,
    hourly_comparison_builder,
    hourly_series_builder,
    variable_configs,
    state_key
):
    show_table = st.checkbox(
        "Mostrar tabla de diferencias cada 30 min",
        value=True,
        key=state_key,
        help="Genera una tabla con WIGA, ECOWITT y la diferencia para temperatura, humedad y PPFD (PAR) en cada franja de 30 minutos."
    )
    if not show_table:
        return

    table, table_mode = _build_difference_table_30min(
        df,
        variables,
        sensor_names,
        selected_range,
        resolution_label,
        hourly_comparison_builder,
        hourly_series_builder,
        variable_configs
    )
    if table.empty:
        st.info("No hay datos suficientes para construir la tabla de diferencias en el periodo seleccionado.")
        return

    st.caption(f"Tabla calculada con: {table_mode}. La diferencia se calcula como WIGA - ECOWITT.")
    _render_comparison_table_summary(table, title="Resumen ejecutivo de diferencias")
    _render_variable_split_tables(
        table,
        default_expanded=True,
        download_label="Descargar reporte WIGA vs ECOWITT",
        download_file_name=f"reporte_wiga_ecowitt_{_build_normalized_text_key(table_mode).replace(' ', '_')}.xlsx",
        download_key=f"{state_key}_download"
    )


def _sanitize_excel_sheet_name(name, existing_names=None):
    existing_names = set(existing_names or [])
    clean = re.sub(r'[\[\]\:\*\?\/\\]', ' ', str(name or 'Hoja')).strip()
    clean = re.sub(r'\s+', ' ', clean) or 'Hoja'
    clean = clean[:31]
    candidate = clean
    suffix = 2
    while candidate in existing_names:
        suffix_text = f" {suffix}"
        candidate = f"{clean[:31 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    return candidate


def _build_report_slug(*parts):
    text = " ".join(str(part) for part in parts if part not in (None, ""))
    slug = _build_normalized_text_key(text).replace(' ', '_')
    return slug or "reporte"


def _build_variable_split_excel_bytes(table, variable_column='Variable'):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        sheets_written = []
        if variable_column in table.columns:
            for variable_name in table[variable_column].dropna().unique().tolist():
                variable_table = (
                    table[table[variable_column] == variable_name]
                    .drop(columns=[variable_column], errors='ignore')
                    .reset_index(drop=True)
                )
                if variable_table.empty:
                    continue
                sheet_name = _sanitize_excel_sheet_name(variable_name, sheets_written)
                variable_table.to_excel(writer, index=False, sheet_name=sheet_name)
                sheets_written.append(sheet_name)

        consolidated_name = _sanitize_excel_sheet_name('Consolidado', sheets_written)
        table.to_excel(writer, index=False, sheet_name=consolidated_name)
        sheets_written.append(consolidated_name)

        workbook = writer.book
        for worksheet in workbook.worksheets:
            worksheet.freeze_panes = 'A2'
            worksheet.auto_filter.ref = worksheet.dimensions
            for column_cells in worksheet.columns:
                max_length = 0
                column_letter = column_cells[0].column_letter
                for cell in column_cells:
                    value = cell.value
                    if value is None:
                        continue
                    max_length = max(max_length, len(str(value)))
                worksheet.column_dimensions[column_letter].width = min(max(max_length + 2, 11), 34)

    output.seek(0)
    return output.getvalue()


def _render_table_download_button(table, label, file_name, key, variable_column='Variable', help_text=None):
    if table.empty:
        return

    try:
        report_bytes = _build_variable_split_excel_bytes(table, variable_column=variable_column)
    except Exception as error:
        st.info(f"No fue posible preparar el Excel descargable. Detalle: {error}")
        return

    st.download_button(
        label,
        data=report_bytes,
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=key,
        help=help_text or "Descarga un Excel con una hoja por variable y una hoja consolidada."
    )


def _render_comparison_table_summary(table, title="Resumen ejecutivo"):
    if table.empty or 'Variable' not in table.columns:
        return

    summary_rows = []
    for variable_name, variable_table in table.groupby('Variable', sort=False):
        unit = ''
        if 'Unidad' in variable_table.columns:
            units = variable_table['Unidad'].dropna().astype(str)
            unit = units.iloc[0] if not units.empty else ''

        if 'Diferencia absoluta' in variable_table.columns:
            abs_diff = pd.to_numeric(variable_table['Diferencia absoluta'], errors='coerce')
            signed_diff = pd.to_numeric(variable_table.get('Diferencia WIGA - ECOWITT'), errors='coerce')
            valid_abs = abs_diff.dropna()
            if valid_abs.empty:
                continue
            max_idx = valid_abs.idxmax()
            max_row = variable_table.loc[max_idx]
            mean_signed = signed_diff.mean()
            tendency = (
                "WIGA mayor"
                if pd.notna(mean_signed) and mean_signed > 0 else
                "ECOWITT mayor"
                if pd.notna(mean_signed) and mean_signed < 0 else
                "Alineados"
            )
            summary_rows.append({
                'Variable': variable_name,
                'Registros comparados': int(valid_abs.count()),
                'Diferencia media abs.': round(float(valid_abs.mean()), 2),
                'Diferencia media': round(float(mean_signed), 2) if pd.notna(mean_signed) else pd.NA,
                'Mayor diferencia': round(float(valid_abs.max()), 2),
                'Momento mayor diferencia': f"{max_row.get('Fecha', '')} {max_row.get('Hora', '')}".strip(),
                'Lectura general': tendency,
                'Unidad': unit,
            })
            continue

        diff_columns = [
            column
            for column in variable_table.columns
            if ' - ' in str(column) and column not in ('Fecha', 'Hora')
        ]
        if not diff_columns:
            continue

        diff_frame = variable_table[diff_columns].apply(pd.to_numeric, errors='coerce')
        if diff_frame.dropna(how='all').empty:
            continue
        abs_frame = diff_frame.abs()
        max_column = abs_frame.max().idxmax()
        max_idx = abs_frame[max_column].idxmax()
        max_row = variable_table.loc[max_idx]
        summary_rows.append({
            'Variable': variable_name,
            'Registros comparados': int(abs_frame.dropna(how='all').shape[0]),
            'Diferencia media abs.': round(float(abs_frame.stack().mean()), 2),
            'Diferencia media': round(float(diff_frame[max_column].mean()), 2) if diff_frame[max_column].notna().any() else pd.NA,
            'Mayor diferencia': round(float(abs_frame.loc[max_idx, max_column]), 2),
            'Momento mayor diferencia': f"{max_row.get('Fecha', '')} {max_row.get('Hora', '')}".strip(),
            'Lectura general': max_column,
            'Unidad': unit,
        })

    if not summary_rows:
        return

    st.markdown(f"### {title}")
    summary_df = pd.DataFrame(summary_rows)
    cols = st.columns(min(3, len(summary_rows)))
    for idx, row in enumerate(summary_rows):
        with cols[idx % len(cols)]:
            unit_label = f" {row['Unidad']}" if row.get('Unidad') else ""
            st.markdown(
                f"""
                <div style="
                    background: rgba(255,255,255,0.94);
                    border: 1px solid rgba(84, 83, 134, 0.10);
                    border-left: 4px solid {BRAND_COLORS['hero']};
                    border-radius: 8px;
                    padding: 0.9rem 1rem;
                    margin-bottom: 0.8rem;
                    box-shadow: 0 12px 28px rgba(44,46,42,0.06);
                    min-height: 150px;
                ">
                    <div style="font-size:0.78rem;font-weight:800;letter-spacing:0.04em;text-transform:uppercase;color:{BRAND_COLORS['hero']};">
                        {html.escape(str(row['Variable']))}
                    </div>
                    <div style="font-size:1.75rem;font-weight:800;line-height:1.05;margin:0.35rem 0;color:{BRAND_COLORS['graphite']};">
                        {html.escape(str(row['Mayor diferencia']))}{html.escape(unit_label)}
                    </div>
                    <div style="font-size:0.9rem;line-height:1.45;color:rgba(56,58,53,0.82);">
                        Mayor diferencia en {html.escape(str(row['Momento mayor diferencia']))}.<br>
                        Media absoluta: {html.escape(str(row['Diferencia media abs.']))}{html.escape(unit_label)}.<br>
                        Lectura: {html.escape(str(row['Lectura general']))}.
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    with st.expander("Ver resumen ejecutivo en tabla", expanded=False):
        _dataframe(summary_df, hide_index=True)


def _render_variable_split_tables(
    table,
    variable_column='Variable',
    default_expanded=True,
    download_label=None,
    download_file_name=None,
    download_key=None,
):
    if table.empty:
        return

    if download_label and download_file_name and download_key:
        _render_table_download_button(table, download_label, download_file_name, download_key, variable_column)

    if variable_column not in table.columns:
        _dataframe(table, hide_index=True)
        return

    variable_names = [name for name in table[variable_column].dropna().unique().tolist()]
    if not variable_names:
        _dataframe(table, hide_index=True)
        return

    for variable_name in variable_names:
        variable_table = (
            table[table[variable_column] == variable_name]
            .drop(columns=[variable_column], errors='ignore')
            .reset_index(drop=True)
        )
        if variable_table.empty:
            continue
        with st.expander(f"Tabla de {variable_name}", expanded=default_expanded):
            _dataframe(variable_table, hide_index=True)


def _get_marley_time_axis_config(df):
    min_time = df['FechaHora'].min()
    max_time = df['FechaHora'].max()
    span = max_time - min_time
    total_days = max(span.total_seconds() / 86400, 0)

    if total_days <= 1.1:
        return {'tickformat': '%H:%M', 'dtick': 30 * 60 * 1000, 'title': 'Hora del día', 'tickmode': 'linear'}
    if total_days <= 3:
        return {'tickformat': '%d/%m\n%H:%M', 'dtick': 6 * 60 * 60 * 1000, 'title': 'Fecha y hora', 'tickmode': 'linear'}
    if total_days <= 10:
        return {'tickformat': '%d/%m\n%H:%M', 'dtick': 12 * 60 * 60 * 1000, 'title': 'Fecha y hora', 'tickmode': 'linear'}
    return {'tickformat': '%d/%m/%Y', 'dtick': 24 * 60 * 60 * 1000, 'title': 'Fecha', 'tickmode': 'linear'}


def _get_marley_y_axis_config(df, variable):
    series = []
    for source_name in MARLEY_SENSOR_NAMES:
        column_name = f"{variable} - {source_name}"
        if column_name in df.columns:
            clean = pd.to_numeric(df[column_name], errors='coerce').dropna()
            if not clean.empty:
                series.append(clean)

    if not series:
        return {'title': MARLEY_VARIABLES[variable]['unit']}

    values = pd.concat(series, ignore_index=True)
    vmin = float(values.min())
    vmax = float(values.max())

    if variable == 'Gramos de agua (g)':
        axis_min = round(max(0, vmin - 0.5), 2)
        axis_max = round(vmax + 0.5, 2)
        spread = max(axis_max - axis_min, 0.1)
        dtick = 0.2 if spread <= 2 else 0.5 if spread <= 5 else 1
        return {'title': 'Gramos de agua (g)', 'range': [axis_min, axis_max], 'dtick': dtick}

    if variable == 'Humedad Relativa (%)':
        axis_min = max(0, min(100, (int(vmin // 5) * 5) - 5))
        axis_max = min(100, (int(vmax // 5) * 5) + 5)
        if axis_max <= axis_min:
            axis_max = min(100, axis_min + 5)
        return {'title': 'Humedad relativa (%)', 'range': [axis_min, axis_max], 'dtick': 5, 'ticksuffix': '%'}

    if variable == 'Temperatura (°C)':
        return {'title': 'Temperatura (°C)', 'range': [round(vmin - 1.5, 1), round(vmax + 1.5, 1)], 'dtick': 2}

    axis_max = int(vmax * 1.05) if vmax > 0 else 10
    spread = max(axis_max, 1)
    dtick = 10 if spread <= 100 else 25 if spread <= 300 else 50 if spread <= 800 else 100
    return {'title': PPFD_DISPLAY_LABEL_ASCII, 'range': [-25, axis_max], 'dtick': dtick}


def _tighten_comparison_y_axis(comparison, sensor_names, y_axis, variable_name):
    values = []
    for source_name in sensor_names:
        if source_name not in comparison.columns:
            continue
        clean = pd.to_numeric(comparison[source_name], errors='coerce').dropna()
        if not clean.empty:
            values.append(clean)

    if not values:
        return y_axis

    combined = pd.concat(values, ignore_index=True)
    vmin = float(combined.min())
    vmax = float(combined.max())
    spread = max(vmax - vmin, 0.01)
    normalized_variable = _build_normalized_text_key(variable_name)

    if 'humedad' in normalized_variable:
        padding = max(0.6, spread * 0.035)
        axis_min = max(0, vmin - padding)
        axis_max = min(100, vmax + padding)
        axis_span = axis_max - axis_min
        dtick = 0.5 if axis_span <= 8 else 1 if axis_span <= 18 else 2 if axis_span <= 35 else 5
        y_axis.update({'range': [round(axis_min, 1), round(axis_max, 1)], 'dtick': dtick, 'ticksuffix': '%', 'tickformat': '.1f'})
        return y_axis

    if 'temperatura' in normalized_variable:
        padding = max(0.15, spread * 0.035)
        axis_min = vmin - padding
        axis_max = vmax + padding
        axis_span = axis_max - axis_min
        dtick = 0.2 if axis_span <= 3 else 0.5 if axis_span <= 7 else 1 if axis_span <= 15 else 2
        y_axis.update({'range': [round(axis_min, 2), round(axis_max, 2)], 'dtick': dtick, 'tickformat': '.2f'})
        return y_axis

    if 'gramos' in normalized_variable:
        padding = max(0.08, spread * 0.035)
        axis_min = max(0, vmin - padding)
        axis_max = vmax + padding
        axis_span = axis_max - axis_min
        dtick = 0.1 if axis_span <= 1.2 else 0.2 if axis_span <= 2.5 else 0.5 if axis_span <= 6 else 1
        y_axis.update({'range': [round(axis_min, 2), round(axis_max, 2)], 'dtick': dtick, 'tickformat': '.2f'})
        return y_axis

    if 'radiacion par' in normalized_variable:
        padding = max(5, spread * 0.035)
        axis_min = max(0, vmin - padding)
        axis_max = vmax + padding
        axis_span = max(axis_max - axis_min, 1)
        dtick = 5 if axis_span <= 80 else 10 if axis_span <= 180 else 25 if axis_span <= 450 else 50 if axis_span <= 900 else 100
        y_axis.update({'range': [round(axis_min, 1), round(axis_max, 1)], 'dtick': dtick, 'tickformat': '.1f'})
        return y_axis

    padding = max(spread * 0.035, 0.25)
    y_axis.update({'range': [round(vmin - padding, 2), round(vmax + padding, 2)], 'tickformat': '.2f'})
    return y_axis


def _make_marley_comparison_chart(comparison, variable, selected_range, resolution_label=COMPARISON_RESOLUTION_OPTIONS[0]):
    config = MARLEY_VARIABLES[variable]
    fig = go.Figure()
    time_axis = _get_marley_time_axis_config(comparison)
    y_axis = _get_marley_y_axis_config(
        comparison.rename(columns={name: f"{variable} - {name}" for name in MARLEY_SENSOR_NAMES}),
        variable
    )
    y_axis = _tighten_comparison_y_axis(comparison, MARLEY_SENSOR_NAMES, y_axis, variable)
    start_date, end_date = selected_range
    multi_day_view = start_date != end_date
    point_mode = resolution_label == COMPARISON_RESOLUTION_OPTIONS[1]
    nearest_wiga_mode = resolution_label == COMPARISON_RESOLUTION_OPTIONS[2]
    if point_mode:
        chart_title = f"{config['title']} - punto por punto"
    elif nearest_wiga_mode:
        chart_title = f"{config['title']} - WIGA 30 min / ECOWITT cercano"
    else:
        chart_title = config['title']

    for source_name in MARLEY_SENSOR_NAMES:
        source_df = comparison[['FechaHora', source_name, 'SignedDiffLabel', 'DiffValueLabel', 'DiffPctLabel']].copy()
        if source_df[source_name].dropna().empty:
            continue

        trace_type = go.Scattergl if point_mode and len(source_df) > 250 else go.Scatter
        fig.add_trace(
            trace_type(
                x=source_df['FechaHora'],
                y=source_df[source_name],
                name=source_name,
                mode='lines+markers' if point_mode or not multi_day_view else 'lines',
                line=dict(color=config['colors'][source_name], width=2.2 if point_mode else 3),
                marker=dict(size=4 if point_mode else 6),
                opacity=0.86 if point_mode else 1,
                connectgaps=False,
                customdata=source_df[['SignedDiffLabel', 'DiffValueLabel', 'DiffPctLabel']],
                hovertemplate=(
                    "<b>%{x|%Y-%m-%d %H:%M}</b><br>"
                    + f"{source_name}: "
                    + "%{y:.2f} "
                    + config['unit']
                    + "<br>Diferencia WIGA - ECOWITT: %{customdata[0]} "
                    + config['unit']
                    + "<br>Diferencia absoluta: %{customdata[1]} "
                    + config['unit']
                    + "<br>Diferencia % sobre promedio: %{customdata[2]}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title=dict(text=chart_title, x=0, xanchor='left'),
        height=470,
        margin=dict(l=28, r=28, t=74, b=28),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(250,248,243,0.72)",
        hovermode='x unified',
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
        xaxis=dict(
            title=time_axis['title'],
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
            tickformat=time_axis['tickformat'],
            tickmode=time_axis.get('tickmode', 'linear'),
            dtick=time_axis['dtick'],
            ticklabelmode='period',
            range=[
                pd.Timestamp(start_date),
                pd.Timestamp(end_date) + MARLEY_AXIS_END_OFFSET
            ],
        ),
        yaxis=dict(
            title=y_axis['title'],
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
            range=y_axis.get('range'),
            dtick=y_axis.get('dtick'),
            ticksuffix=y_axis.get('ticksuffix', ''),
            tickformat=y_axis.get('tickformat'),
        ),
    )
    return fig


def _make_marley_difference_chart(comparison, variable, selected_range, resolution_label=COMPARISON_RESOLUTION_OPTIONS[0]):
    diff_df = comparison[['FechaHora', 'SignedDiff']].dropna().copy()
    if diff_df.empty:
        return None

    config = MARLEY_VARIABLES[variable]
    time_axis = _get_marley_time_axis_config(comparison)
    start_date, end_date = selected_range
    multi_day_view = start_date != end_date
    point_mode = resolution_label == COMPARISON_RESOLUTION_OPTIONS[1]
    nearest_wiga_mode = resolution_label == COMPARISON_RESOLUTION_OPTIONS[2]
    max_abs_diff = float(diff_df['SignedDiff'].abs().max())
    axis_limit = max(round(max_abs_diff * 1.15, 2), 0.5)

    fig = go.Figure()
    fig.add_trace(
        (go.Scattergl if multi_day_view else go.Scatter)(
            x=diff_df['FechaHora'],
            y=diff_df['SignedDiff'],
            name='WIGA - ECOWITT',
            mode='lines+markers',
            line=dict(color=config['accent'], width=3),
            marker=dict(size=6),
            hovertemplate="<b>%{x|%Y-%m-%d %H:%M}</b><br>Diferencia: %{y:+.2f} " + config['unit'] + "<extra></extra>",
        )
    )
    fig.add_hline(y=0, line_width=1.4, line_dash='solid', line_color="rgba(45, 48, 64, 0.45)")
    fig.update_layout(
        title=dict(
            text=(
                "Diferencia entre sensores punto por punto"
                if point_mode else
                "Diferencia con ECOWITT cercano a WIGA"
                if nearest_wiga_mode else
                "Diferencia entre sensores por bloque de 30 minutos"
            ),
            x=0,
            xanchor='left'
        ),
        height=340,
        margin=dict(l=28, r=28, t=72, b=28),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(250,248,243,0.72)",
        template='plotly_white',
        xaxis=dict(
            title=time_axis['title'],
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
            tickformat=time_axis['tickformat'],
            tickmode=time_axis.get('tickmode', 'linear'),
            dtick=time_axis['dtick'],
            range=[pd.Timestamp(start_date), pd.Timestamp(end_date) + MARLEY_AXIS_END_OFFSET],
        ),
        yaxis=dict(
            title=f"Diferencia ({config['unit']})",
            range=[-axis_limit, axis_limit],
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
        ),
    )
    return fig


def _make_marley_scatter_chart(comparison, variable):
    hourly = comparison.dropna(subset=list(MARLEY_SENSOR_NAMES)).copy()
    if hourly.empty:
        return None

    config = MARLEY_VARIABLES[variable]
    axis_min = float(min(hourly['WIGA'].min(), hourly['ECOWITT'].min()))
    axis_max = float(max(hourly['WIGA'].max(), hourly['ECOWITT'].max()))
    padding = max((axis_max - axis_min) * 0.08, 0.5)
    axis_min -= padding
    axis_max += padding

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=hourly['WIGA'],
            y=hourly['ECOWITT'],
            mode='markers',
            name='Lecturas simultáneas',
            marker=dict(size=8, color=config['accent'], opacity=0.72),
            text=hourly['FechaHora'].dt.strftime('%Y-%m-%d %H:%M'),
            hovertemplate="<b>%{text}</b><br>WIGA: %{x:.2f} " + config['unit'] + "<br>ECOWITT: %{y:.2f} " + config['unit'] + "<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[axis_min, axis_max],
            y=[axis_min, axis_max],
            mode='lines',
            name='Referencia y = x',
        line=dict(color="#D39A58", width=2),
            hoverinfo='skip',
        )
    )
    fig.update_layout(
        title=dict(text="Dispersión entre sensores", x=0, xanchor='left'),
        height=420,
        margin=dict(l=28, r=28, t=72, b=28),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(250,248,243,0.72)",
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
        xaxis=dict(title=f"WIGA ({config['unit']})", range=[axis_min, axis_max], showgrid=True, zeroline=False),
        yaxis=dict(title=f"ECOWITT ({config['unit']})", range=[axis_min, axis_max], showgrid=True, zeroline=False, scaleanchor='x', scaleratio=1),
    )
    return fig


def _build_marley_hourly_metric(df, variable, metric_column):
    value_columns = {
        source_name: f"{variable} - {source_name}"
        for source_name in MARLEY_SENSOR_NAMES
    }
    available_columns = [
        column_name
        for column_name in value_columns.values()
        if column_name in df.columns
    ]
    if df.empty or 'FechaHora' not in df.columns or not available_columns:
        return pd.DataFrame()

    records = []
    for source_name, column_name in value_columns.items():
        if column_name not in df.columns:
            continue
        source_df = df[['FechaHora', column_name]].dropna(subset=[column_name]).copy()
        if source_df.empty:
            continue
        source_df['FranjaDateTime'] = source_df['FechaHora'].dt.floor(MARLEY_TIME_BUCKET)
        source_df['FranjaMinutos'] = source_df['FranjaDateTime'].dt.hour * 60 + source_df['FranjaDateTime'].dt.minute
        source_df['Franja'] = source_df['FranjaDateTime'].dt.strftime('%H:%M')

        if metric_column == 'Promedio':
            aggregation = 'mean'
        elif metric_column == 'Desviacion estandar':
            aggregation = lambda serie: serie.std(ddof=1) if len(serie) > 1 else 0.0
        else:
            aggregation = lambda serie: serie.var(ddof=1) if len(serie) > 1 else 0.0
        grouped = (
            source_df.groupby(['FranjaMinutos', 'Franja'], as_index=False)
            .agg(Valor=(column_name, aggregation), Registros=(column_name, 'count'))
        )
        grouped['Sensor'] = source_name
        records.append(grouped)

    if not records:
        return pd.DataFrame()

    return (
        pd.concat(records, ignore_index=True)
        .sort_values(['FranjaMinutos', 'Sensor'])
        .reset_index(drop=True)
    )


def _make_marley_hourly_metric_chart(grouped_df, variable, metric_column):
    config = MARLEY_VARIABLES[variable]
    fig = go.Figure()
    display_slots = [
        f'{hour:02d}:{minute:02d}'
        for hour in range(24)
        for minute in (0, 30)
    ]

    for source_name in MARLEY_SENSOR_NAMES:
        source_df = grouped_df[grouped_df['Sensor'] == source_name].copy()
        if source_df.empty:
            continue
        source_df = (
            source_df.set_index('Franja')
            .reindex(display_slots)
            .rename_axis('Franja')
            .reset_index()
        )
        source_df['Sensor'] = source_name

        fig.add_trace(
            go.Scatter(
                x=source_df['Franja'],
                y=source_df['Valor'],
                name=source_name,
                mode='lines+markers',
                line=dict(color=config['colors'][source_name], width=3),
                marker=dict(size=6),
                connectgaps=False,
                customdata=source_df[['Registros']],
                hovertemplate=(
                    '<b>%{x}</b><br>'
                    + f'{source_name} - {metric_column}: '
                    + '%{y:.2f} '
                    + config['unit']
                    + '<br>Registros: %{customdata[0]}<extra></extra>'
                ),
            )
        )

    if metric_column == 'Promedio':
        yaxis_title = config['unit']
    elif metric_column == 'Desviacion estandar':
        yaxis_title = f"Desviacion estandar ({config['unit']})"
    else:
        yaxis_title = f"Varianza ({config['unit']})"
    fig.update_layout(
        title=dict(text=f"{metric_column} por franja horaria - {_format_variable_display_title(config['title'])}", x=0, xanchor='left'),
        height=470,
        margin=dict(l=28, r=28, t=74, b=75),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(250,248,243,0.72)",
        hovermode='x unified',
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
        xaxis=dict(
            title='Franja horaria',
            type='category',
            categoryorder='array',
            categoryarray=display_slots,
            tickangle=-90,
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
        ),
        yaxis=dict(
            title=yaxis_title,
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
        ),
    )
    return fig


def _prepare_marley_hourly_metric_table(grouped_df):
    if grouped_df.empty:
        return grouped_df
    table = grouped_df.pivot(index=['FranjaMinutos', 'Franja'], columns='Sensor', values='Valor')
    table = table.reset_index().sort_values('FranjaMinutos').drop(columns=['FranjaMinutos'])
    table = table.rename(columns={'Franja': 'Franja horaria'})
    table.columns.name = None
    return table.round(2)


def _build_marley_individual_series(df, variable, source_name, selected_range, resolution_label=COMPARISON_RESOLUTION_OPTIONS[0]):
    column_name = f"{variable} - {source_name}"
    if df.empty or column_name not in df.columns:
        return pd.DataFrame()

    if resolution_label == COMPARISON_RESOLUTION_OPTIONS[1]:
        series_df = df[['FechaHora', column_name]].dropna(subset=[column_name]).copy()
        series_df['FechaHora'] = pd.to_datetime(series_df['FechaHora'], errors='coerce')
        series_df[column_name] = pd.to_numeric(series_df[column_name], errors='coerce')
        series_df = (
            series_df
            .dropna(subset=['FechaHora', column_name])
            .sort_values('FechaHora')
            .reset_index(drop=True)
        )
    elif resolution_label == SOURCE_RESOLUTION_OPTIONS[2]:
        series_df = _build_nearest_series_to_time_grid(df, column_name, selected_range)
    else:
        series_df = _build_marley_hourly_series(df, column_name, selected_range)

    if series_df.empty or series_df[column_name].dropna().empty:
        return pd.DataFrame()

    return series_df.rename(columns={column_name: 'Valor'})


def _make_marley_individual_variable_chart(df, variable, source_name, selected_range, resolution_label=COMPARISON_RESOLUTION_OPTIONS[0]):
    series_df = _build_marley_individual_series(df, variable, source_name, selected_range, resolution_label)
    if series_df.empty:
        return None

    config = MARLEY_VARIABLES[variable]
    time_axis = _get_marley_time_axis_config(series_df)
    start_date, end_date = selected_range
    variable_title = _format_variable_display_title(config['title'])
    point_mode = resolution_label == COMPARISON_RESOLUTION_OPTIONS[1]
    nearest_mode = resolution_label == SOURCE_RESOLUTION_OPTIONS[2]
    trace_type = go.Scattergl if point_mode and len(series_df) > 250 else go.Scatter

    fig = go.Figure()
    fig.add_trace(
        trace_type(
            x=series_df['FechaHora'],
            y=series_df['Valor'],
            name=f"{variable_title} - {source_name}",
            mode='lines+markers',
            line=dict(color=config['colors'][source_name], width=2.1 if point_mode else 2.7),
            marker=dict(size=3.5 if point_mode else 5),
            opacity=0.86 if point_mode else 1,
            connectgaps=False,
            hovertemplate=(
                "<b>%{x|%Y-%m-%d %H:%M}</b><br>"
                + f"{variable_title} {source_name}: "
                + "%{y:.2f} "
                + config['unit']
                + "<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title=dict(
            text=(
                f"{variable_title} - {source_name} - punto por punto"
                if point_mode else
                f"{variable_title} - {source_name} - valor más cercano cada 30 min"
                if nearest_mode else
                f"{variable_title} - {source_name}"
            ),
            x=0,
            xanchor='left'
        ),
        height=285,
        margin=dict(l=24, r=18, t=54, b=42),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(250,248,243,0.72)",
        hovermode='x unified',
        template='plotly_white',
        showlegend=False,
        xaxis=dict(
            title=time_axis['title'],
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
            tickformat=time_axis['tickformat'],
            tickmode=time_axis.get('tickmode', 'linear'),
            dtick=time_axis['dtick'],
            range=[
                pd.Timestamp(start_date),
                pd.Timestamp(end_date) + MARLEY_AXIS_END_OFFSET
            ],
        ),
        yaxis=dict(
            title=config['unit'],
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
        ),
    )
    return fig


def _make_source_all_variables_chart(
    filtered_df,
    selected_range,
    variables,
    variable_configs,
    source_name,
    series_builder,
    title,
    resolution_label=COMPARISON_RESOLUTION_OPTIONS[0],
):
    rendered_series = []
    for variable in variables:
        series_df = series_builder(filtered_df, variable, source_name, selected_range, resolution_label)
        if series_df.empty or series_df['Valor'].dropna().empty:
            continue
        rendered_series.append((variable, series_df))

    if not rendered_series:
        return None

    fig = make_subplots(
        rows=len(rendered_series),
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.045,
        subplot_titles=[
            _format_variable_display_title(variable_configs[variable]['title'])
            for variable, _ in rendered_series
        ],
    )
    start_date, end_date = selected_range
    point_mode = resolution_label == COMPARISON_RESOLUTION_OPTIONS[1]
    nearest_mode = resolution_label == SOURCE_RESOLUTION_OPTIONS[2]

    for row_index, (variable, series_df) in enumerate(rendered_series, start=1):
        config = variable_configs[variable]
        variable_title = _format_variable_display_title(config['title'])
        color = config['colors'].get(source_name, config.get('accent', BRAND_COLORS['hero']))
        trace_type = go.Scattergl if point_mode and len(series_df) > 250 else go.Scatter
        fig.add_trace(
            trace_type(
                x=series_df['FechaHora'],
                y=series_df['Valor'],
                name=variable_title,
                mode='lines+markers',
                line=dict(color=color, width=1.9 if point_mode else 2.35),
                marker=dict(size=3 if point_mode else 4),
                opacity=0.86 if point_mode else 1,
                connectgaps=False,
                hovertemplate=(
                    "<b>%{x|%Y-%m-%d %H:%M}</b><br>"
                    + f"{variable_title}: "
                    + "%{y:.2f} "
                    + config['unit']
                    + "<extra></extra>"
                ),
            ),
            row=row_index,
            col=1,
        )
        fig.update_yaxes(
            title_text=config['unit'],
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
            row=row_index,
            col=1,
        )

    time_axis = _get_marley_time_axis_config(rendered_series[0][1])
    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(76, 70, 120, 0.07)",
        zeroline=False,
        tickformat=time_axis['tickformat'],
        tickmode=time_axis.get('tickmode', 'linear'),
        dtick=time_axis['dtick'],
        range=[pd.Timestamp(start_date), pd.Timestamp(end_date) + MARLEY_AXIS_END_OFFSET],
    )
    fig.update_xaxes(title_text=time_axis['title'], row=len(rendered_series), col=1)
    fig.update_layout(
        title=dict(
            text=(
                title + " - punto por punto"
                if point_mode else
                title + " - valor más cercano cada 30 min"
                if nearest_mode else
                title
            ),
            x=0,
            xanchor='left'
        ),
        height=max(540, 235 * len(rendered_series)),
        margin=dict(l=36, r=28, t=82, b=48),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(250,248,243,0.72)",
        hovermode='x unified',
        template='plotly_white',
        showlegend=False,
        font=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['graphite']),
    )
    return fig


def _build_single_source_correlacion_frame(
    filtered_df,
    selected_range,
    variables,
    source_name,
    series_builder,
    resolution_label=COMPARISON_RESOLUTION_OPTIONS[0],
):
    merged = None
    for variable in variables:
        series_df = series_builder(filtered_df, variable, source_name, selected_range, resolution_label)
        if series_df.empty or series_df['Valor'].dropna().empty:
            continue

        variable_frame = (
            series_df[['FechaHora', 'Valor']]
            .rename(columns={'FechaHora': 'DateTime', 'Valor': variable})
            .dropna(subset=['DateTime'])
            .copy()
        )
        merged = variable_frame if merged is None else merged.merge(variable_frame, on='DateTime', how='outer')

    if merged is None or merged.empty:
        return pd.DataFrame()

    merged = merged.sort_values('DateTime').reset_index(drop=True)
    merged['Fecha_Filtro'] = pd.to_datetime(merged['DateTime'], errors='coerce').dt.date
    return merged


def _get_table_variable_label(variable, variable_configs=None):
    normalized_variable = _build_normalized_text_key(variable)
    if 'radiacion par' in normalized_variable or 'ppfd' in normalized_variable:
        return PPFD_DISPLAY_LABEL_ASCII

    if variable in VARIABLE_LABELS:
        return VARIABLE_LABELS[variable]

    config = (variable_configs or {}).get(variable, {})
    if config:
        title = _format_variable_display_title(config.get('title', variable))
        unit = str(config.get('unit', '')).strip()
        if unit and unit not in title:
            return f"{title} ({unit})"
        return title

    return str(variable)


def _prepare_graphed_series_table(correlation_df, variables, variable_configs=None):
    if correlation_df.empty or 'DateTime' not in correlation_df.columns:
        return pd.DataFrame()

    value_columns = [variable for variable in variables if variable in correlation_df.columns]
    if not value_columns:
        return pd.DataFrame()

    table = correlation_df[['DateTime', *value_columns]].copy()
    table['DateTime'] = pd.to_datetime(table['DateTime'], errors='coerce')
    table = table.dropna(subset=['DateTime']).sort_values('DateTime').reset_index(drop=True)
    table.insert(0, 'Fecha', table['DateTime'].dt.strftime('%Y-%m-%d'))
    table.insert(1, 'Hora', table['DateTime'].dt.strftime('%H:%M'))
    table = table.drop(columns=['DateTime'])
    table = table.rename(
        columns={
            variable: _get_table_variable_label(variable, variable_configs)
            for variable in value_columns
        }
    )
    numeric_columns = table.select_dtypes(include='number').columns
    if len(numeric_columns):
        table[numeric_columns] = table[numeric_columns].round(2)
    return table.dropna(how='all', subset=[column for column in table.columns if column not in ('Fecha', 'Hora')])


def _render_graphed_series_table(
    correlation_df,
    variables,
    variable_configs,
    title,
    resolution_label,
    source_label=None,
    expanded=False,
):
    table = _prepare_graphed_series_table(correlation_df, variables, variable_configs)
    if table.empty:
        return

    with st.expander(title, expanded=expanded):
        caption_source = f" para {source_label}" if source_label else ""
        st.caption(
            f"Datos usados por la gráfica{caption_source}. Resolución: {resolution_label}. "
            "La tabla queda ordenada por fecha y hora para facilitar revisión o reporte."
        )
        download_slug = _build_report_slug(title, source_label, resolution_label)
        _render_table_download_button(
            table,
            "Descargar datos graficados",
            f"datos_graficados_{download_slug}.xlsx",
            f"descargar_datos_graficados_{download_slug}",
            help_text="Descarga un Excel con los mismos datos que alimentan esta gráfica."
        )
        _dataframe(table, hide_index=True)


def _render_marley_individual_variable_charts(
    filtered_df,
    selected_range,
    source_names=MARLEY_SENSOR_NAMES,
    heading="Variables individuales Marly",
    resolution_label=COMPARISON_RESOLUTION_OPTIONS[0],
):
    rendered_charts = []
    for variable in MARLEY_VARIABLES:
        for source_name in source_names:
            chart = _make_marley_individual_variable_chart(
                filtered_df,
                variable,
                source_name,
                selected_range,
                resolution_label
            )
            if chart is not None:
                rendered_charts.append(chart)

    if not rendered_charts:
        return

    st.markdown(f"### {heading}")
    _render_chart_explanation(
        'Lectura individual por sensor',
        'Cada gráfica muestra una sola variable de un solo equipo. Sirve para revisar patrones puntuales de WIGA y ECOWITT sin mezclar las líneas en una misma visual.',
        accent=BRAND_COLORS['hero']
    )

    for start in range(0, len(rendered_charts), 2):
        cols = st.columns(2)
        for offset, chart in enumerate(rendered_charts[start:start + 2]):
            with cols[offset]:
                _plotly_chart(chart)


def _render_marley_dashboard(dashboard_mode):
    try:
        marley_df, marley_source_data = _load_marley_data()
    except Exception as error:
        st.error(f"No fue posible cargar los datos de Marly. Detalle: {error}")
        st.stop()

    if marley_df.empty or 'FechaHora' not in marley_df.columns:
        st.warning("No hay datos disponibles para Marly.")
        st.stop()

    date_source_df = marley_df
    if dashboard_mode in ("Solo WIGA", "Solo ECOWITT"):
        date_source_name = "WIGA" if dashboard_mode == "Solo WIGA" else "ECOWITT"
        date_source_df = marley_source_data.get(date_source_name, marley_df)
        if date_source_df.empty:
            st.warning(f"No hay datos disponibles para {date_source_name} en Marly.")
            st.stop()

    min_date = date_source_df['FechaHora'].min().date()
    max_date = date_source_df['FechaHora'].max().date()
    marley_navigation_state_key = None

    with st.sidebar.expander("Periodo", expanded=True):
        if min_date == max_date:
            fecha_unica = st.date_input(
                "Seleccionar fecha:",
                value=max_date,
                key="marley_fecha_unica",
                min_value=min_date,
                max_value=max_date,
                help=FILTER_HELP_TEXTS['fecha']
            )
            selected_range = (fecha_unica, fecha_unica)
            marley_navigation_state_key = "marley_fecha_unica"
        else:
            if dashboard_mode in ("Varianza", "Desviacion estandar"):
                modo_fechas = "Varios días"
                st.session_state["marley_modo_fechas"] = modo_fechas
                st.caption(f"{dashboard_mode} se calcula automáticamente con varios días.")
            else:
                modo_fechas = st.radio(
                    "Modo de fechas:",
                    options=["Un día", "Varios días"],
                    horizontal=True,
                    key="marley_modo_fechas",
                    help=FILTER_HELP_TEXTS['modo_fechas']
                )
            if modo_fechas == "Un día":
                fecha_unica_default = _clamp_sidebar_date(
                    _coerce_sidebar_date(st.session_state.get("marley_fecha_un_dia", max_date), max_date),
                    min_date,
                    max_date
                )
                _sidebar_field_label("calendar", "Seleccionar fecha")
                fecha_unica = st.date_input(
                    "Seleccionar fecha:",
                    value=fecha_unica_default,
                    key="marley_fecha_un_dia",
                    min_value=min_date,
                    max_value=max_date,
                    help=FILTER_HELP_TEXTS['fecha']
                )
                selected_range = (fecha_unica, fecha_unica)
                marley_navigation_state_key = "marley_fecha_un_dia"
            else:
                default_range_end = _get_sidebar_default_range_end(min_date, max_date, default_days=7)
                _sidebar_field_label("calendar", "Fecha inicio")
                fecha_inicio = st.date_input(
                    "Fecha inicio:",
                    value=min_date,
                    key="marley_fecha_inicio",
                    min_value=min_date,
                    max_value=max_date,
                    help=FILTER_HELP_TEXTS['fecha']
                )
                _sidebar_field_label("calendar", "Fecha fin")
                fecha_fin = st.date_input(
                    "Fecha fin:",
                    value=default_range_end,
                    key="marley_fecha_fin",
                    min_value=min_date,
                    max_value=max_date,
                    help=FILTER_HELP_TEXTS['fecha']
                )
                fecha_inicio, fecha_fin = _normalize_sidebar_date_range(
                    fecha_inicio,
                    fecha_fin,
                    min_date,
                    max_date
                )
                selected_range = (fecha_inicio, fecha_fin)

    filtered_df = marley_df[marley_df['Fecha_Filtro'].between(*selected_range)].copy()
    if filtered_df.empty:
        st.warning("No hay datos disponibles para Marly en el rango seleccionado.")
        st.stop()

    _render_selected_period_banner(
        selected_range,
        min_fecha=min_date,
        max_fecha=max_date,
        navigation_state_key=marley_navigation_state_key,
        title_text='Periodo Marly'
    )

    if dashboard_mode in ("Solo WIGA", "Solo ECOWITT"):
        source_name = "WIGA" if dashboard_mode == "Solo WIGA" else "ECOWITT"
        st.markdown(f"## Marly - {source_name}")
        st.caption(f"Lectura de todas las variables medidas por {source_name}, sin superponer el otro sensor.")
        _render_chart_explanation(
            f'Variables {source_name}',
            f'Primero se muestran todas las variables de {source_name} en una sola visual apilada para comparar tendencias en el mismo periodo. Luego se muestran las gráficas individuales para revisar cada variable con más detalle.',
            accent=BRAND_COLORS['hero'],
            kicker='Orientación'
        )
        source_resolution = st.radio(
            f"Resolución de las gráficas {source_name}:",
            options=SOURCE_RESOLUTION_OPTIONS,
            horizontal=True,
            key=f"marley_{source_name.lower()}_source_resolution",
            help="Usa promedio para agrupar por media hora, punto por punto para ver las lecturas crudas, o valor más cercano para tomar el registro más próximo a cada marca exacta de 30 minutos."
        )

        combined_chart = _make_source_all_variables_chart(
            filtered_df,
            selected_range,
            list(MARLEY_VARIABLES.keys()),
            MARLEY_VARIABLES,
            source_name,
            _build_marley_individual_series,
            f"Variables {source_name} - Marly",
            source_resolution,
        )
        if combined_chart is None:
            st.warning(f"No hay datos suficientes para graficar las variables de {source_name} en el periodo seleccionado.")
            st.stop()
        graphed_frame = _build_single_source_correlacion_frame(
            filtered_df,
            selected_range,
            list(MARLEY_VARIABLES.keys()),
            source_name,
            _build_marley_individual_series,
            source_resolution,
        )

        tab_general, tab_stats, tab_detail, tab_records = st.tabs(["Gráfica", "Resumen estadístico", "Detalle individual", "Registros"])
        with tab_general:
            _plotly_chart(combined_chart)

        with tab_stats:
            stats_table = _build_variable_distribution_table(graphed_frame, list(MARLEY_VARIABLES.keys()))
            _render_variable_distribution_cards(
                stats_table,
                MARLEY_VARIABLES,
                title=f"Resumen estadístico {source_name} - Marly"
            )
            if not stats_table.empty:
                with st.expander("Ver resumen estadístico en tabla", expanded=False):
                    _dataframe(stats_table.round(2), hide_index=True)

        with tab_detail:
            _render_marley_individual_variable_charts(
                filtered_df,
                selected_range,
                source_names=(source_name,),
                heading=f"Variables individuales {source_name} - Marly",
                resolution_label=source_resolution
            )

        with tab_records:
            _render_graphed_series_table(
                graphed_frame,
                list(MARLEY_VARIABLES.keys()),
                MARLEY_VARIABLES,
                f"Tabla de datos graficados - {source_name}",
                source_resolution,
                source_label=f"{source_name} Marly",
                expanded=True,
            )
            if st.checkbox(
                f"Cargar registros crudos de Marly - {source_name}",
                key=f"mostrar_marley_{source_name.lower()}_registros",
                help=FILTER_HELP_TEXTS['registros']
            ):
                source_columns = [
                    column
                    for column in filtered_df.columns
                    if column == 'FechaHora' or column.endswith(f" - {source_name}")
                ]
                _dataframe(filtered_df[source_columns].dropna(how='all', subset=source_columns[1:]), hide_index=True)
        st.stop()

    st.markdown(f"## Marly - {dashboard_mode}")
    st.caption("Lectura comparativa entre los sensores WIGA y ECOWITT, con opción de promedio por franja o lectura punto por punto.")
    _render_chart_explanation(
        'Cómo usar el análisis Marly',
        f'Elige una variable para comparar ambos sensores. Las tarjetas explican la diferencia general y las gráficas muestran cuándo se parecen, cuándo se separan y qué sensor mide más alto. {PPFD_HELP_TEXT}',
        accent=BRAND_COLORS['hero'],
        kicker='Orientación'
    )

    show_marley_details = st.checkbox(
        "Cargar variables individuales",
        key="mostrar_marley_detalles",
        help=FILTER_HELP_TEXTS['graficas_detalladas']
    )

    if dashboard_mode in ("Varianza", "Desviacion estandar", "Promedio"):
        selected_variable = st.segmented_control(
            "Variable Marly",
            options=list(MARLEY_VARIABLES.keys()),
            format_func=lambda value: _format_variable_display_title(MARLEY_VARIABLES[value]['title']),
            default=list(MARLEY_VARIABLES.keys())[0],
            key="marley_variable",
        )
        if dashboard_mode in ("Varianza", "Desviacion estandar") and selected_range[0] == selected_range[1]:
            st.warning(f"Para ver {dashboard_mode.lower()} en Marly selecciona un rango de al menos 2 días.")
            st.stop()

        grouped_metric = _build_marley_hourly_metric(filtered_df, selected_variable, dashboard_mode)
        if grouped_metric.empty:
            st.warning("No hay datos suficientes para construir esta vista de Marly en el periodo seleccionado.")
            st.stop()

        _render_marley_metric_analysis_tabs(
            filtered_df,
            selected_range,
            selected_variable,
            dashboard_mode,
            grouped_metric,
            show_marley_details
        )
        st.stop()

        _render_chart_explanation(
            f'{dashboard_mode} por franja horaria',
            (
                'Esta gráfica muestra qué tanto se alejan las lecturas de cada sensor respecto a su valor central dentro de una misma hora del día durante el rango seleccionado. Valores bajos indican mayor estabilidad; valores altos indican una dispersión más amplia.'
                if dashboard_mode == "Desviacion estandar" else
                'Esta gráfica muestra qué tanto cambió cada sensor dentro de una misma hora del día durante el rango seleccionado. Valores bajos indican lecturas más estables; valores altos indican mayor fluctuación.'
                if dashboard_mode == "Varianza" else
                'Esta gráfica resume el valor promedio de cada sensor por franja de 30 minutos para comparar el comportamiento típico dentro del periodo seleccionado.'
            ),
            accent=MARLEY_VARIABLES[selected_variable]['accent']
        )
        _plotly_chart(_make_marley_hourly_metric_chart(grouped_metric, selected_variable, dashboard_mode))
        metric_table = _prepare_marley_hourly_metric_table(grouped_metric)
        with st.expander(f"Ver tabla ordenada de {dashboard_mode.lower()}", expanded=True):
            st.caption("Tabla calculada con los mismos valores de la gráfica, ordenada por franja horaria.")
            report_slug = _build_report_slug("marly", dashboard_mode, selected_variable)
            _render_table_download_button(
                metric_table,
                f"Descargar tabla de {dashboard_mode.lower()}",
                f"marly_{dashboard_mode.lower()}_{report_slug}.xlsx",
                f"descargar_marley_{dashboard_mode.lower()}_{report_slug}",
                help_text="Descarga un Excel con la tabla calculada a partir de la gráfica visible."
            )
            _dataframe(metric_table, hide_index=True)
        if show_marley_details:
            detail_resolution = st.radio(
                "Resolución de las gráficas individuales:",
                options=SOURCE_RESOLUTION_OPTIONS,
                horizontal=True,
                key=f"marley_{dashboard_mode.lower()}_detail_resolution",
                help=f"El análisis de {dashboard_mode.lower()} se mantiene por franja horaria; este control aplica solo a las gráficas individuales con promedio, punto por punto o valor más cercano cada 30 minutos."
            )
            _render_marley_individual_variable_charts(
                filtered_df,
                selected_range,
                resolution_label=detail_resolution
            )
        st.stop()

    comparison_resolution = st.radio(
        "Resolución de la gráfica WIGA vs ECOWITT:",
        options=COMPARISON_RESOLUTION_OPTIONS,
        horizontal=True,
        key="marley_comparison_resolution",
        help="Promedio agrupa ambos sensores cada 30 minutos; punto por punto usa lecturas crudas; WIGA 30 min mantiene WIGA como base y toma el ECOWITT más cercano a cada hora WIGA."
    )
    point_mode = comparison_resolution == COMPARISON_RESOLUTION_OPTIONS[1]
    nearest_wiga_mode = comparison_resolution == COMPARISON_RESOLUTION_OPTIONS[2]
    compared_variables = [
        "Temperatura (°C)",
        "Humedad Relativa (%)",
        "Radiación PAR (µmol m-2 s-1)",
    ]
    _render_chart_explanation(
        'Comparación directa WIGA vs ECOWITT',
        (
            'Se muestran todas las variables compartidas, una debajo de otra. Cada gráfica superpone WIGA y ECOWITT con la resolución seleccionada para revisar diferencias sin cambiar de pestaña.'
        ),
        accent=BRAND_COLORS['hero']
    )
    for variable_name in compared_variables:
        comparison = (
            _build_point_comparison(filtered_df, variable_name, MARLEY_SENSOR_NAMES)
            if point_mode else
            _build_wiga_anchor_nearest_comparison(
                filtered_df,
                variable_name,
                MARLEY_SENSOR_NAMES,
                selected_range,
                _build_marley_hourly_series
            )
            if nearest_wiga_mode else
            _build_marley_hourly_comparison(filtered_df, variable_name, selected_range)
        )
        if comparison.empty or comparison.dropna(how='all', subset=list(MARLEY_SENSOR_NAMES)).empty:
            st.info(f"No hay datos suficientes para graficar {_format_variable_display_title(MARLEY_VARIABLES[variable_name]['title'])}.")
            continue
        _plotly_chart(_make_marley_comparison_chart(comparison, variable_name, selected_range, comparison_resolution))
        difference_chart = _make_marley_difference_chart(comparison, variable_name, selected_range, comparison_resolution)
        if difference_chart is not None:
            _plotly_chart(difference_chart)

    _render_difference_table_30min(
        filtered_df,
        compared_variables,
        MARLEY_SENSOR_NAMES,
        selected_range,
        comparison_resolution,
        _build_marley_hourly_comparison,
        _build_marley_hourly_series,
        MARLEY_VARIABLES,
        "mostrar_marley_tabla_diferencias_30min"
    )

    if show_marley_details:
        _render_marley_individual_variable_charts(
            filtered_df,
            selected_range,
            resolution_label=comparison_resolution
        )

    if st.checkbox(
        "Cargar registros consolidados de Marly",
        key="mostrar_marley_registros",
        help=FILTER_HELP_TEXTS['registros']
    ):
        _dataframe(filtered_df.drop(columns=['Fecha_Filtro'], errors='ignore'), hide_index=True)
        summary_rows = []
        for source_name, source_df in marley_source_data.items():
            current = source_df[source_df['Fecha_Filtro'].between(*selected_range)]
            summary_rows.append({
                'Equipo': source_name,
                'Registros': len(current),
                'Inicio': current['FechaHora'].min().strftime('%Y-%m-%d %H:%M') if not current.empty else '-',
                'Fin': current['FechaHora'].max().strftime('%Y-%m-%d %H:%M') if not current.empty else '-',
            })
        _dataframe(pd.DataFrame(summary_rows), hide_index=True)

    st.stop()
    point_mode = comparison_resolution == COMPARISON_RESOLUTION_OPTIONS[1]
    nearest_wiga_mode = comparison_resolution == COMPARISON_RESOLUTION_OPTIONS[2]
    comparison = (
        _build_point_comparison(filtered_df, selected_variable, MARLEY_SENSOR_NAMES)
        if point_mode else
        _build_wiga_anchor_nearest_comparison(
            filtered_df,
            selected_variable,
            MARLEY_SENSOR_NAMES,
            selected_range,
            _build_marley_hourly_series
        )
        if nearest_wiga_mode else
        _build_marley_hourly_comparison(filtered_df, selected_variable, selected_range)
    )
    overlap = comparison.dropna(subset=list(MARLEY_SENSOR_NAMES)).copy()

    _render_chart_explanation(
        'Comparación directa WIGA vs ECOWITT',
        (
            'Aquí se superponen las lecturas punto por punto. Cada punto WIGA se compara con la lectura ECOWITT más cercana en el tiempo para ver mejor la relación real entre sensores.'
            if point_mode else
            'Aquí WIGA mantiene la lectura por franjas de 30 minutos y ECOWITT toma el registro más cercano a cada hora WIGA. Sirve para comparar contra el reloj de WIGA sin promediar ECOWITT.'
            if nearest_wiga_mode else
            'Aquí se superponen ambos sensores para la variable elegida. Si las líneas viajan cerca, las lecturas son similares; si se separan, hay diferencia entre equipos en esa franja de 30 minutos.'
        ),
        accent=MARLEY_VARIABLES[selected_variable]['accent']
    )
    _plotly_chart(_make_marley_comparison_chart(comparison, selected_variable, selected_range, comparison_resolution))
    _render_difference_table_30min(
        filtered_df,
        [
            "Temperatura (°C)",
            "Humedad Relativa (%)",
            "Radiación PAR (µmol m-2 s-1)",
        ],
        MARLEY_SENSOR_NAMES,
        selected_range,
        comparison_resolution,
        _build_marley_hourly_comparison,
        _build_marley_hourly_series,
        MARLEY_VARIABLES,
        "mostrar_marley_tabla_diferencias_30min"
    )

    avg_abs_diff = overlap['DiffValue'].mean() if not overlap.empty else None
    avg_signed_diff = overlap['SignedDiff'].mean() if not overlap.empty else None
    std_diff = overlap['SignedDiff'].std() if not overlap.empty else None
    unit = MARLEY_VARIABLES[selected_variable]['unit']

    if pd.isna(avg_signed_diff):
        signed_interpretation = "No hay suficientes lecturas simultáneas para identificar cuál sensor quedó por encima."
    elif avg_signed_diff > 0:
        signed_interpretation = "En promedio, WIGA estuvo por encima de ECOWITT en esta variable."
    elif avg_signed_diff < 0:
        signed_interpretation = "En promedio, ECOWITT estuvo por encima de WIGA en esta variable."
    else:
        signed_interpretation = "En promedio, ambos sensores quedaron prácticamente alineados."

    if pd.isna(std_diff):
        std_interpretation = "No hay suficientes lecturas comparables para evaluar estabilidad."
    elif std_diff <= 0.3:
        std_interpretation = "La diferencia entre sensores fue bastante estable a lo largo del tiempo."
    elif std_diff <= 0.8:
        std_interpretation = "La diferencia entre sensores tuvo una variación moderada entre franjas."
    else:
        std_interpretation = "La diferencia entre sensores cambió bastante entre bloques de 30 minutos."

    marley_metric_cards = [
        {
            'title': 'Diferencia absoluta media',
            'value': f"{avg_abs_diff:.2f} {unit}" if pd.notna(avg_abs_diff) else "Sin datos",
            'accent': MARLEY_VARIABLES[selected_variable]['colors']['WIGA'],
            'description': "Mide qué tan separados estuvieron WIGA y ECOWITT en promedio, sin importar cuál quedó por encima.",
            'insight': (
                "Mientras más bajo sea este valor, más parecidas fueron las lecturas entre ambos sensores."
                if pd.notna(avg_abs_diff) else
                "Necesitamos más datos simultáneos para medir qué tan separados estuvieron ambos sensores."
            ),
        },
        {
            'title': 'Diferencia media WIGA - ECOWITT',
            'value': f"{avg_signed_diff:+.2f} {unit}" if pd.notna(avg_signed_diff) else "Sin datos",
            'accent': MARLEY_VARIABLES[selected_variable]['colors']['ECOWITT'],
            'description': "Conserva el signo de la diferencia. Nos dice si uno de los sensores tiende a leer más alto que el otro.",
            'insight': signed_interpretation,
        },
        {
            'title': 'Desviación estándar',
            'value': f"{std_diff:.2f} {unit}" if pd.notna(std_diff) else "Sin datos",
            'accent': MARLEY_VARIABLES[selected_variable]['accent'],
            'description': "Muestra qué tan estable fue la diferencia entre ambos sensores a lo largo del tiempo.",
            'insight': std_interpretation,
        },
    ]

    metric_cols = st.columns(3)
    for idx, metric in enumerate(marley_metric_cards):
        with metric_cols[idx]:
            st.markdown(
                f"""
                <div style="
                    background: linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(247,244,238,0.96) 100%);
                    border: 1px solid rgba(84, 83, 134, 0.10);
                    border-top: 4px solid {metric['accent']};
                    border-radius: 8px;
                    padding: 1.15rem 1.1rem 1rem 1.1rem;
                    box-shadow: 0 18px 36px rgba(44, 46, 42, 0.08);
                    min-height: 255px;
                ">
                    <div style="
                        font-family: 'Montserrat', sans-serif;
                        font-size: 0.82rem;
                        font-weight: 800;
                        letter-spacing: 0.03em;
                        text-transform: uppercase;
                        color: {metric['accent']};
                        margin-bottom: 0.7rem;
                    ">
                        {html.escape(metric['title'])}
                    </div>
                    <div style="
                        font-family: 'Montserrat', sans-serif;
                        font-size: 2.6rem;
                        line-height: 1;
                        font-weight: 800;
                        color: {BRAND_COLORS['graphite']};
                        margin-bottom: 0.95rem;
                    ">
                        {html.escape(metric['value'])}
                    </div>
                    <div style="
                        font-family: 'Montserrat', sans-serif;
                        font-size: 0.94rem;
                        line-height: 1.55;
                        color: rgba(56, 58, 53, 0.82);
                        margin-bottom: 0.85rem;
                    ">
                        {html.escape(metric['description'])}
                    </div>
                    <div style="
                        background: rgba(84, 83, 134, 0.05);
                        border: 1px solid rgba(84, 83, 134, 0.08);
                        border-radius: 8px;
                        padding: 0.8rem 0.85rem;
                    ">
                        <div style="
                            font-family: 'Montserrat', sans-serif;
                            font-size: 0.76rem;
                            font-weight: 800;
                            letter-spacing: 0.04em;
                            text-transform: uppercase;
                            color: {BRAND_COLORS['hero']};
                            margin-bottom: 0.35rem;
                        ">
                            Cómo leerlo
                        </div>
                        <div style="
                            font-family: 'Montserrat', sans-serif;
                            font-size: 0.9rem;
                            line-height: 1.55;
                            color: {BRAND_COLORS['ink']};
                        ">
                            {html.escape(metric['insight'])}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

    st.markdown(
        """
        <div style="
            margin: 0.95rem 0 0.65rem 0;
            padding: 0.95rem 1rem;
            border-radius: 8px;
            background: linear-gradient(135deg, rgba(194,223,234,0.20) 0%, rgba(244,199,206,0.12) 100%);
            border: 1px solid rgba(84, 83, 134, 0.08);
            color: rgba(56, 58, 53, 0.88);
            font-family: 'Montserrat', sans-serif;
            font-size: 0.94rem;
            line-height: 1.6;
        ">
            <strong>Lectura rápida:</strong> estos indicadores ayudan a ver si ambos sensores se parecen,
            si alguno suele medir más alto y si esa diferencia se mantiene estable o cambia mucho durante el día.
        </div>
        """,
        unsafe_allow_html=True
    )

    difference_chart = _make_marley_difference_chart(comparison, selected_variable, selected_range, comparison_resolution)
    if difference_chart is not None:
        _render_chart_explanation(
            'Diferencia WIGA - ECOWITT',
            'Esta gráfica convierte la comparación en una sola línea. Valores sobre cero significan que WIGA midió más alto; valores bajo cero significan que ECOWITT midió más alto.',
            accent=MARLEY_VARIABLES[selected_variable]['colors']['ECOWITT']
        )
        _plotly_chart(difference_chart)

    scatter_chart = _make_marley_scatter_chart(comparison, selected_variable)
    if scatter_chart is not None:
        _render_chart_explanation(
            'Dispersión entre sensores',
            'Cada punto cruza una lectura simultánea de WIGA y ECOWITT. Mientras más cerca esté de la línea diagonal, más parecidos fueron ambos sensores en ese momento.',
            accent=MARLEY_VARIABLES[selected_variable]['colors']['WIGA']
        )
        _plotly_chart(scatter_chart)
    else:
        st.info("No hay suficientes datos simultáneos entre WIGA y ECOWITT para construir la dispersión.")

    if show_marley_details:
        _render_marley_individual_variable_charts(
            filtered_df,
            selected_range,
            resolution_label=comparison_resolution
        )

    if st.checkbox(
        "Cargar registros consolidados de Marly",
        key="mostrar_marley_registros",
        help=FILTER_HELP_TEXTS['registros']
    ):
        _dataframe(filtered_df.drop(columns=['Fecha_Filtro'], errors='ignore'), hide_index=True)
        summary_rows = []
        for source_name, source_df in marley_source_data.items():
            current = source_df[source_df['Fecha_Filtro'].between(*selected_range)]
            summary_rows.append({
                'Equipo': source_name,
                'Registros': len(current),
                'Inicio': current['FechaHora'].min().strftime('%Y-%m-%d %H:%M') if not current.empty else '-',
                'Fin': current['FechaHora'].max().strftime('%Y-%m-%d %H:%M') if not current.empty else '-',
            })
        _dataframe(pd.DataFrame(summary_rows), hide_index=True)

    st.stop()


def _resolve_ponderosa_ecowitt_sources():
    sources = []
    for candidate in PONDEROSA_ECOWITT_LOCAL_EXCEL_PATHS:
        if candidate.exists():
            sources.append(candidate)
    sources.extend(PONDEROSA_ECOWITT_REMOTE_EXCEL_URLS)
    return sources


def _build_ponderosa_ecowitt_source_signature(excel_source):
    if isinstance(excel_source, Path):
        stat = excel_source.stat()
        return f"{excel_source}|{stat.st_mtime_ns}|{stat.st_size}|{DATA_CACHE_VERSION}"
    return f"{excel_source}|{DATA_CACHE_VERSION}"


def _open_ponderosa_ecowitt_workbook(excel_source):
    if isinstance(excel_source, Path):
        return pd.ExcelFile(excel_source)

    response = requests.get(excel_source, timeout=45)
    response.raise_for_status()
    return pd.ExcelFile(io.BytesIO(response.content))


def _standardize_ponderosa_ecowitt_columns(df):
    renamed = {}
    for column in df.columns:
        normalized = _build_normalized_text_key(column)
        if normalized in PONDEROSA_ECOWITT_CANONICAL_COLUMNS:
            renamed[column] = PONDEROSA_ECOWITT_CANONICAL_COLUMNS[normalized]
    return df.rename(columns=renamed)


@st.cache_data(show_spinner="Cargando ECOWITT Ponderosa...")
def _load_ponderosa_ecowitt_data_from_source(excel_source, source_signature):
    _ = source_signature
    workbook = _open_ponderosa_ecowitt_workbook(excel_source)
    sheet_name = workbook.sheet_names[0]
    df = workbook.parse(sheet_name=sheet_name)
    df = _standardize_ponderosa_ecowitt_columns(df)

    if 'FechaHora' not in df.columns:
        raise ValueError("El archivo ECOWITT Ponderosa no tiene una columna de fecha/hora reconocible.")

    df['FechaHora'] = pd.to_datetime(df['FechaHora'], errors='coerce')
    df = df.dropna(subset=['FechaHora']).sort_values('FechaHora')
    df['Fecha_Filtro'] = df['FechaHora'].dt.date

    for variable in PONDEROSA_ECOWITT_DATA_VARIABLES:
        if variable not in df.columns:
            df[variable] = pd.NA
        df[variable] = pd.to_numeric(df[variable], errors='coerce')

    return df[['FechaHora', 'Fecha_Filtro', *PONDEROSA_ECOWITT_DATA_VARIABLES.keys()]].copy()


def _load_ponderosa_ecowitt_data():
    errors = []
    for excel_source in _resolve_ponderosa_ecowitt_sources():
        try:
            return _load_ponderosa_ecowitt_data_from_source(
                excel_source,
                _build_ponderosa_ecowitt_source_signature(excel_source)
            )
        except Exception as error:
            errors.append(f"{excel_source}: {error}")

    raise ValueError("No fue posible cargar ECOWITT Ponderosa.\n" + "\n".join(errors))


def _build_ponderosa_wiga_source(df_variables_all, bloque_variables):
    if df_variables_all.empty or not bloque_variables:
        return pd.DataFrame()

    required_columns = ['DateTime', 'Fecha_Filtro', *SENSOR_VARIABLES]
    available_columns = [column for column in required_columns if column in df_variables_all.columns]
    if 'DateTime' not in available_columns:
        return pd.DataFrame()

    df = df_variables_all[df_variables_all['Bloque'] == bloque_variables][available_columns].copy()
    if df.empty:
        return df

    df['FechaHora'] = pd.to_datetime(df['DateTime'], errors='coerce')
    df = df.dropna(subset=['FechaHora']).sort_values('FechaHora')
    if 'Fecha_Filtro' not in df.columns:
        df['Fecha_Filtro'] = df['FechaHora'].dt.date

    for variable in SENSOR_VARIABLES:
        if variable not in df.columns:
            df[variable] = pd.NA
        df[variable] = pd.to_numeric(df[variable], errors='coerce')

    df = df[['FechaHora', 'Fecha_Filtro', *SENSOR_VARIABLES]].copy()
    for variable in SENSOR_VARIABLES:
        df.rename(columns={variable: f"{variable} - WIGA"}, inplace=True)
    return df


def _build_ponderosa_ecowitt_source(ecowitt_df):
    if ecowitt_df.empty:
        return pd.DataFrame()

    df = ecowitt_df[['FechaHora', 'Fecha_Filtro', *PONDEROSA_ECOWITT_VARIABLES.keys()]].copy()
    for variable in PONDEROSA_ECOWITT_VARIABLES:
        df.rename(columns={variable: f"{variable} - ECOWITT"}, inplace=True)
    return df


def _build_ponderosa_apogee_source(ecowitt_df):
    if ecowitt_df.empty:
        return pd.DataFrame()

    df = ecowitt_df[['FechaHora', 'Fecha_Filtro', *PONDEROSA_APOGEE_VARIABLES.keys()]].copy()
    for variable in PONDEROSA_APOGEE_VARIABLES:
        df.rename(columns={variable: f"{variable} - APOGEE"}, inplace=True)
    return df


def _build_ponderosa_comparison_dataset(df_variables_all, ecowitt_df, bloque_variables):
    wiga_source = _build_ponderosa_wiga_source(df_variables_all, bloque_variables)
    ecowitt_source = _build_ponderosa_ecowitt_source(ecowitt_df)
    if wiga_source.empty and ecowitt_source.empty:
        return pd.DataFrame(), {'WIGA': wiga_source, 'ECOWITT': ecowitt_source}

    merge_frames = []
    if not wiga_source.empty:
        merge_frames.append(wiga_source.drop(columns=['Fecha_Filtro'], errors='ignore'))
    if not ecowitt_source.empty:
        merge_frames.append(ecowitt_source.drop(columns=['Fecha_Filtro'], errors='ignore'))

    merged = merge_frames[0]
    for frame in merge_frames[1:]:
        merged = merged.merge(frame, on='FechaHora', how='outer')

    merged = merged.sort_values('FechaHora').reset_index(drop=True)
    merged['Fecha_Filtro'] = merged['FechaHora'].dt.date
    return merged, {'WIGA': wiga_source, 'ECOWITT': ecowitt_source}


def _build_ponderosa_light_sensor_dataset(df_variables_all, ecowitt_df, bloque_variables):
    wiga_source_raw = _build_ponderosa_wiga_source(df_variables_all, bloque_variables)
    light_columns = [
        'FechaHora',
        'Fecha_Filtro',
        *[
            f"{variable} - {sensor_name}"
            for variable in PONDEROSA_LIGHT_VARIABLES
            for sensor_name in PONDEROSA_LIGHT_SENSOR_NAMES
        ],
    ]

    wiga_source = pd.DataFrame()
    if not wiga_source_raw.empty and 'Radiación PAR - WIGA' in wiga_source_raw.columns:
        wiga_source = wiga_source_raw[['FechaHora', 'Fecha_Filtro', 'Radiación PAR - WIGA']].copy()
        wiga_source['Radiación PAR - WIGA'] = pd.to_numeric(wiga_source['Radiación PAR - WIGA'], errors='coerce')
        wiga_source['LUX - WIGA'] = wiga_source['Radiación PAR - WIGA'] * PAR_TO_LUX_FACTOR

    mci_source = pd.DataFrame()
    apogee_source = pd.DataFrame()
    if not ecowitt_df.empty:
        base_ecowitt = ecowitt_df[['FechaHora', 'Fecha_Filtro', 'Radiación PAR', 'LUX']].copy()
        base_ecowitt['Radiación PAR'] = pd.to_numeric(base_ecowitt['Radiación PAR'], errors='coerce')
        base_ecowitt['LUX'] = pd.to_numeric(base_ecowitt['LUX'], errors='coerce')

        mci_source = base_ecowitt[['FechaHora', 'Fecha_Filtro', 'Radiación PAR']].copy()
        mci_source.rename(columns={'Radiación PAR': 'Radiación PAR - MCI'}, inplace=True)
        mci_source['LUX - MCI'] = mci_source['Radiación PAR - MCI'] * PAR_TO_LUX_FACTOR

        apogee_source = base_ecowitt[['FechaHora', 'Fecha_Filtro', 'LUX']].copy()
        apogee_source.rename(columns={'LUX': 'LUX - APOGEE'}, inplace=True)
        apogee_source['Radiación PAR - APOGEE'] = apogee_source['LUX - APOGEE'] / PAR_TO_LUX_FACTOR

    merge_frames = [
        frame.drop(columns=['Fecha_Filtro'], errors='ignore')
        for frame in (wiga_source, mci_source, apogee_source)
        if not frame.empty
    ]
    if not merge_frames:
        return pd.DataFrame(columns=light_columns), {
            'WIGA': wiga_source,
            'MCI': mci_source,
            'APOGEE': apogee_source,
        }

    merged = merge_frames[0]
    for frame in merge_frames[1:]:
        merged = merged.merge(frame, on='FechaHora', how='outer')

    merged = merged.sort_values('FechaHora').reset_index(drop=True)
    merged['Fecha_Filtro'] = pd.to_datetime(merged['FechaHora'], errors='coerce').dt.date
    for column in light_columns:
        if column not in merged.columns:
            merged[column] = pd.NA
    return merged[light_columns].copy(), {
        'WIGA': wiga_source,
        'MCI': mci_source,
        'APOGEE': apogee_source,
    }


def _build_multi_sensor_average_comparison(df, variable, sensor_names, selected_range, hourly_builder):
    comparison = None
    for sensor_name in sensor_names:
        column_name = f"{variable} - {sensor_name}"
        if df.empty or column_name not in df.columns:
            continue
        series_df = hourly_builder(df, column_name, selected_range)
        if series_df.empty or column_name not in series_df.columns:
            continue
        series_df = series_df.rename(columns={column_name: sensor_name})
        comparison = series_df if comparison is None else comparison.merge(series_df, on='FechaHora', how='outer')

    if comparison is None:
        return pd.DataFrame(columns=['FechaHora', *sensor_names])

    for sensor_name in sensor_names:
        if sensor_name not in comparison.columns:
            comparison[sensor_name] = pd.NA
        comparison[sensor_name] = pd.to_numeric(comparison[sensor_name], errors='coerce')
    return comparison.sort_values('FechaHora').reset_index(drop=True)


def _build_multi_sensor_raw_frames(df, variable, sensor_names):
    source_frames = {}
    for sensor_name in sensor_names:
        column_name = f"{variable} - {sensor_name}"
        if df.empty or column_name not in df.columns:
            source_frames[sensor_name] = pd.DataFrame(columns=['FechaHora', sensor_name])
            continue

        source_df = df[['FechaHora', column_name]].dropna(subset=[column_name]).copy()
        source_df['FechaHora'] = pd.to_datetime(source_df['FechaHora'], errors='coerce')
        source_df[column_name] = pd.to_numeric(source_df[column_name], errors='coerce')
        source_df = (
            source_df
            .dropna(subset=['FechaHora', column_name])
            .groupby('FechaHora', as_index=False)[column_name]
            .mean()
            .sort_values('FechaHora')
            .rename(columns={column_name: sensor_name})
        )
        source_frames[sensor_name] = source_df
    return source_frames


def _finalize_multi_sensor_comparison(comparison, sensor_names):
    if comparison is None or comparison.empty:
        return pd.DataFrame(columns=['FechaHora', *sensor_names])

    comparison = comparison.copy()
    for sensor_name in sensor_names:
        if sensor_name not in comparison.columns:
            comparison[sensor_name] = pd.NA
        comparison[sensor_name] = pd.to_numeric(comparison[sensor_name], errors='coerce')
    return comparison.sort_values('FechaHora').reset_index(drop=True)


def _build_multi_sensor_point_comparison(df, variable, sensor_names, tolerance=POINT_COMPARISON_TOLERANCE):
    if not sensor_names:
        return pd.DataFrame(columns=['FechaHora'])

    source_frames = _build_multi_sensor_raw_frames(df, variable, sensor_names)
    anchor_sensor = sensor_names[0]
    comparison = source_frames.get(anchor_sensor, pd.DataFrame()).copy()
    if comparison.empty:
        return pd.DataFrame(columns=['FechaHora', *sensor_names])

    for sensor_name in sensor_names[1:]:
        sensor_df = source_frames.get(sensor_name, pd.DataFrame())
        if sensor_df.empty:
            comparison[sensor_name] = pd.NA
            continue
        comparison = pd.merge_asof(
            comparison.sort_values('FechaHora'),
            sensor_df.sort_values('FechaHora'),
            on='FechaHora',
            direction='nearest',
            tolerance=tolerance
        )
    return _finalize_multi_sensor_comparison(comparison, sensor_names)


def _build_multi_sensor_anchor_nearest_comparison(
    df,
    variable,
    sensor_names,
    selected_range,
    hourly_builder,
    tolerance=POINT_COMPARISON_TOLERANCE
):
    if not sensor_names:
        return pd.DataFrame(columns=['FechaHora'])

    anchor_sensor = sensor_names[0]
    anchor_column = f"{variable} - {anchor_sensor}"
    if df.empty or anchor_column not in df.columns:
        return pd.DataFrame(columns=['FechaHora', *sensor_names])

    anchor_df = hourly_builder(df, anchor_column, selected_range)
    if anchor_df.empty or anchor_column not in anchor_df.columns:
        return pd.DataFrame(columns=['FechaHora', *sensor_names])

    comparison = (
        anchor_df[['FechaHora', anchor_column]]
        .dropna(subset=[anchor_column])
        .sort_values('FechaHora')
        .rename(columns={anchor_column: anchor_sensor})
    )
    if comparison.empty:
        return pd.DataFrame(columns=['FechaHora', *sensor_names])

    source_frames = _build_multi_sensor_raw_frames(df, variable, sensor_names[1:])
    for sensor_name in sensor_names[1:]:
        sensor_df = source_frames.get(sensor_name, pd.DataFrame())
        if sensor_df.empty:
            comparison[sensor_name] = pd.NA
            continue
        comparison = pd.merge_asof(
            comparison.sort_values('FechaHora'),
            sensor_df.sort_values('FechaHora'),
            on='FechaHora',
            direction='nearest',
            tolerance=tolerance
        )
    return _finalize_multi_sensor_comparison(comparison, sensor_names)


def _build_ponderosa_light_comparison(df, variable, selected_range, resolution_label):
    if resolution_label == COMPARISON_RESOLUTION_OPTIONS[1]:
        return _build_multi_sensor_point_comparison(
            df,
            variable,
            PONDEROSA_LIGHT_SENSOR_NAMES
        )
    if resolution_label == COMPARISON_RESOLUTION_OPTIONS[2]:
        return _build_multi_sensor_anchor_nearest_comparison(
            df,
            variable,
            PONDEROSA_LIGHT_SENSOR_NAMES,
            selected_range,
            _build_ponderosa_hourly_series
        )
    return _build_multi_sensor_average_comparison(
        df,
        variable,
        PONDEROSA_LIGHT_SENSOR_NAMES,
        selected_range,
        _build_ponderosa_hourly_series
    )


def _build_ponderosa_full_time_index(selected_range):
    start_date, end_date = selected_range
    return pd.date_range(
        start=pd.Timestamp(start_date),
        end=pd.Timestamp(end_date) + MARLEY_SERIES_END_OFFSET,
        freq=MARLEY_TIME_BUCKET,
    )


def _build_ponderosa_hourly_series(df, column_name, selected_range):
    full_index = _build_ponderosa_full_time_index(selected_range)
    if 'FechaHora' not in df.columns or column_name not in df.columns:
        return pd.DataFrame({
            'FechaHora': full_index,
            column_name: [pd.NA] * len(full_index)
        })

    source_df = df[['FechaHora', column_name]].dropna(subset=[column_name]).copy()
    if source_df.empty:
        return pd.DataFrame({
            'FechaHora': full_index,
            column_name: [pd.NA] * len(full_index)
        })

    source_df['FechaHora'] = source_df['FechaHora'].dt.floor(MARLEY_TIME_BUCKET)
    source_df = source_df.groupby('FechaHora', as_index=False)[column_name].mean()
    source_df = source_df.set_index('FechaHora').reindex(full_index).rename_axis('FechaHora').reset_index()
    return source_df


def _build_ponderosa_hourly_comparison(df, variable, selected_range):
    wiga_col = f"{variable} - WIGA"
    ecowitt_col = f"{variable} - ECOWITT"

    hourly_wiga = _build_ponderosa_hourly_series(df, wiga_col, selected_range).rename(columns={wiga_col: 'WIGA'})
    hourly_eco = _build_ponderosa_hourly_series(df, ecowitt_col, selected_range).rename(columns={ecowitt_col: 'ECOWITT'})
    comparison = hourly_wiga.merge(hourly_eco, on='FechaHora', how='outer')
    comparison['DiffPct'] = pd.NA
    comparison['DiffValue'] = pd.NA
    comparison['SignedDiff'] = pd.NA

    valid_mask = comparison['WIGA'].notna() & comparison['ECOWITT'].notna()
    comparison.loc[valid_mask, 'SignedDiff'] = comparison.loc[valid_mask, 'WIGA'] - comparison.loc[valid_mask, 'ECOWITT']
    comparison.loc[valid_mask, 'DiffValue'] = comparison.loc[valid_mask, 'SignedDiff'].abs()
    pct_base = (comparison.loc[valid_mask, 'WIGA'].abs() + comparison.loc[valid_mask, 'ECOWITT'].abs()) / 2
    valid_pct_index = pct_base[pct_base != 0].index
    comparison.loc[valid_pct_index, 'DiffPct'] = (
        comparison.loc[valid_pct_index, 'DiffValue'] / pct_base.loc[valid_pct_index] * 100
    )
    comparison['SignedDiffLabel'] = comparison['SignedDiff'].apply(
        lambda value: "No disponible" if pd.isna(value) else f"{value:+.2f}"
    )
    comparison['DiffValueLabel'] = comparison['DiffValue'].apply(
        lambda value: "No disponible" if pd.isna(value) else f"{value:.2f}"
    )
    comparison['DiffPctLabel'] = comparison['DiffPct'].apply(
        lambda value: "No disponible" if pd.isna(value) else f"{value:.2f}%"
    )
    return comparison


def _get_ponderosa_y_axis_config(df, variable):
    config = (
        PONDEROSA_WIGA_VARIABLES.get(variable) or
        PONDEROSA_COMPARISON_VARIABLES.get(variable) or
        PONDEROSA_ECOWITT_VARIABLES.get(variable) or
        PONDEROSA_APOGEE_VARIABLES.get(variable, {})
    )
    series = []
    for source_name in (*PONDEROSA_SENSOR_NAMES, "APOGEE"):
        column_name = f"{variable} - {source_name}"
        if column_name in df.columns:
            clean = pd.to_numeric(df[column_name], errors='coerce').dropna()
            if not clean.empty:
                series.append(clean)

    if not series:
        return {'title': config['unit']}

    values = pd.concat(series, ignore_index=True)
    vmin = float(values.min())
    vmax = float(values.max())

    if variable == 'Humedad Relativa':
        axis_min = max(0, min(100, (int(vmin // 5) * 5) - 5))
        axis_max = min(100, (int(vmax // 5) * 5) + 5)
        if axis_max <= axis_min:
            axis_max = min(100, axis_min + 5)
        return {'title': 'Humedad relativa (%)', 'range': [axis_min, axis_max], 'dtick': 5, 'ticksuffix': '%'}

    if variable == 'Temperatura':
        return {'title': 'Temperatura (°C)', 'range': [round(vmin - 1.5, 1), round(vmax + 1.5, 1)], 'dtick': 2}

    if variable == 'Gramos de agua':
        return {'title': 'Gramos de agua (g)', 'range': [round(vmin - 0.8, 1), round(vmax + 0.8, 1)], 'dtick': 1}

    if variable == 'LUX':
        axis_max = int(vmax * 1.08) if vmax > 0 else 100
        return {'title': 'LUX', 'range': [0, axis_max], 'dtick': 10000 if axis_max > 50000 else 5000}

    if variable != 'Radiación PAR':
        return {'title': config.get('unit', VARIABLE_UNITS.get(variable, ''))}

    axis_max = int(vmax * 1.05) if vmax > 0 else 10
    spread = max(axis_max, 1)
    dtick = 10 if spread <= 100 else 25 if spread <= 300 else 50 if spread <= 800 else 100
    return {'title': PPFD_DISPLAY_LABEL_ASCII, 'range': [-25, axis_max], 'dtick': dtick}


def _make_ponderosa_comparison_chart(comparison, variable, selected_range, resolution_label=COMPARISON_RESOLUTION_OPTIONS[0]):
    config = PONDEROSA_COMPARISON_VARIABLES[variable]
    fig = go.Figure()
    time_axis = _get_marley_time_axis_config(comparison)
    y_axis = _get_ponderosa_y_axis_config(
        comparison.rename(columns={name: f"{variable} - {name}" for name in PONDEROSA_SENSOR_NAMES}),
        variable
    )
    y_axis = _tighten_comparison_y_axis(comparison, PONDEROSA_SENSOR_NAMES, y_axis, variable)
    start_date, end_date = selected_range
    multi_day_view = start_date != end_date
    point_mode = resolution_label == COMPARISON_RESOLUTION_OPTIONS[1]
    nearest_wiga_mode = resolution_label == COMPARISON_RESOLUTION_OPTIONS[2]
    if point_mode:
        chart_title = f"{config['title']} - punto por punto"
    elif nearest_wiga_mode:
        chart_title = f"{config['title']} - WIGA 30 min / ECOWITT cercano"
    else:
        chart_title = config['title']

    for source_name in PONDEROSA_SENSOR_NAMES:
        source_df = comparison[['FechaHora', source_name, 'SignedDiffLabel', 'DiffValueLabel', 'DiffPctLabel']].copy()
        if source_df[source_name].dropna().empty:
            continue

        trace_type = go.Scattergl if point_mode and len(source_df) > 250 else go.Scatter
        fig.add_trace(
            trace_type(
                x=source_df['FechaHora'],
                y=source_df[source_name],
                name=source_name,
                mode='lines+markers' if point_mode or not multi_day_view else 'lines',
                line=dict(color=config['colors'][source_name], width=2.2 if point_mode else 3),
                marker=dict(size=4 if point_mode else 6),
                opacity=0.86 if point_mode else 1,
                connectgaps=False,
                customdata=source_df[['SignedDiffLabel', 'DiffValueLabel', 'DiffPctLabel']],
                hovertemplate=(
                    "<b>%{x|%Y-%m-%d %H:%M}</b><br>"
                    + f"{source_name}: "
                    + "%{y:.2f} "
                    + config['unit']
                    + "<br>Diferencia WIGA - ECOWITT: %{customdata[0]} "
                    + config['unit']
                    + "<br>Diferencia absoluta: %{customdata[1]} "
                    + config['unit']
                    + "<br>Diferencia % sobre promedio: %{customdata[2]}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        title=dict(text=chart_title, x=0, xanchor='left'),
        height=470,
        margin=dict(l=28, r=28, t=74, b=28),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(250,248,243,0.72)",
        hovermode='x unified',
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
        xaxis=dict(
            title=time_axis['title'],
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
            tickformat=time_axis['tickformat'],
            tickmode=time_axis.get('tickmode', 'linear'),
            dtick=time_axis['dtick'],
            ticklabelmode='period',
            range=[pd.Timestamp(start_date), pd.Timestamp(end_date) + MARLEY_AXIS_END_OFFSET],
        ),
        yaxis=dict(
            title=y_axis['title'],
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
            range=y_axis.get('range'),
            dtick=y_axis.get('dtick'),
            ticksuffix=y_axis.get('ticksuffix', ''),
            tickformat=y_axis.get('tickformat'),
        ),
    )
    return fig


def _make_ponderosa_difference_chart(comparison, variable, selected_range, resolution_label=COMPARISON_RESOLUTION_OPTIONS[0]):
    diff_df = comparison[['FechaHora', 'SignedDiff']].dropna().copy()
    if diff_df.empty:
        return None

    config = PONDEROSA_COMPARISON_VARIABLES[variable]
    time_axis = _get_marley_time_axis_config(comparison)
    start_date, end_date = selected_range
    multi_day_view = start_date != end_date
    point_mode = resolution_label == COMPARISON_RESOLUTION_OPTIONS[1]
    nearest_wiga_mode = resolution_label == COMPARISON_RESOLUTION_OPTIONS[2]
    max_abs_diff = float(diff_df['SignedDiff'].abs().max())
    axis_limit = max(round(max_abs_diff * 1.15, 2), 0.5)

    fig = go.Figure()
    fig.add_trace(
        (go.Scattergl if multi_day_view else go.Scatter)(
            x=diff_df['FechaHora'],
            y=diff_df['SignedDiff'],
            name='WIGA - ECOWITT',
            mode='lines+markers',
            line=dict(color=config['accent'], width=3),
            marker=dict(size=6),
            hovertemplate="<b>%{x|%Y-%m-%d %H:%M}</b><br>Diferencia: %{y:+.2f} " + config['unit'] + "<extra></extra>",
        )
    )
    fig.add_hline(y=0, line_width=1.4, line_dash='solid', line_color="rgba(45, 48, 64, 0.45)")
    fig.update_layout(
        title=dict(
            text=(
                "Diferencia entre sensores punto por punto"
                if point_mode else
                "Diferencia con ECOWITT cercano a WIGA"
                if nearest_wiga_mode else
                "Diferencia entre sensores por bloque de 30 minutos"
            ),
            x=0,
            xanchor='left'
        ),
        height=340,
        margin=dict(l=28, r=28, t=72, b=28),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(250,248,243,0.72)",
        template='plotly_white',
        xaxis=dict(
            title=time_axis['title'],
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
            tickformat=time_axis['tickformat'],
            tickmode=time_axis.get('tickmode', 'linear'),
            dtick=time_axis['dtick'],
            range=[pd.Timestamp(start_date), pd.Timestamp(end_date) + MARLEY_AXIS_END_OFFSET],
        ),
        yaxis=dict(
            title=f"Diferencia ({config['unit']})",
            range=[-axis_limit, axis_limit],
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
        ),
    )
    return fig


def _make_ponderosa_scatter_chart(comparison, variable):
    hourly = comparison.dropna(subset=list(PONDEROSA_SENSOR_NAMES)).copy()
    if hourly.empty:
        return None

    config = PONDEROSA_COMPARISON_VARIABLES[variable]
    axis_min = float(min(hourly['WIGA'].min(), hourly['ECOWITT'].min()))
    axis_max = float(max(hourly['WIGA'].max(), hourly['ECOWITT'].max()))
    padding = max((axis_max - axis_min) * 0.08, 0.5)
    axis_min -= padding
    axis_max += padding

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=hourly['WIGA'],
            y=hourly['ECOWITT'],
            mode='markers',
            name='Lecturas simultáneas',
            marker=dict(size=8, color=config['accent'], opacity=0.72),
            text=hourly['FechaHora'].dt.strftime('%Y-%m-%d %H:%M'),
            hovertemplate="<b>%{text}</b><br>WIGA: %{x:.2f} " + config['unit'] + "<br>ECOWITT: %{y:.2f} " + config['unit'] + "<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[axis_min, axis_max],
            y=[axis_min, axis_max],
            mode='lines',
            name='Referencia y = x',
        line=dict(color="#D39A58", width=2),
            hoverinfo='skip',
        )
    )
    fig.update_layout(
        title=dict(text="Dispersión entre sensores", x=0, xanchor='left'),
        height=420,
        margin=dict(l=28, r=28, t=72, b=28),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(250,248,243,0.72)",
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
        xaxis=dict(title=f"WIGA ({config['unit']})", range=[axis_min, axis_max], showgrid=True, zeroline=False),
        yaxis=dict(title=f"ECOWITT ({config['unit']})", range=[axis_min, axis_max], showgrid=True, zeroline=False, scaleanchor='x', scaleratio=1),
    )
    return fig


def _get_ponderosa_source_variable_configs(source_name):
    if source_name == "WIGA":
        return PONDEROSA_WIGA_VARIABLES
    if source_name == "ECOWITT":
        return PONDEROSA_ECOWITT_VARIABLES
    if source_name == "APOGEE":
        return PONDEROSA_APOGEE_VARIABLES
    return {**PONDEROSA_WIGA_VARIABLES, **PONDEROSA_ECOWITT_VARIABLES, **PONDEROSA_APOGEE_VARIABLES}


def _build_ponderosa_source_individual_series(df, variable, source_name, selected_range, resolution_label=COMPARISON_RESOLUTION_OPTIONS[0]):
    column_name = f"{variable} - {source_name}"
    if df.empty or column_name not in df.columns:
        return pd.DataFrame()

    if resolution_label == COMPARISON_RESOLUTION_OPTIONS[1]:
        series_df = df[['FechaHora', column_name]].dropna(subset=[column_name]).copy()
        series_df['FechaHora'] = pd.to_datetime(series_df['FechaHora'], errors='coerce')
        series_df[column_name] = pd.to_numeric(series_df[column_name], errors='coerce')
        series_df = (
            series_df
            .dropna(subset=['FechaHora', column_name])
            .sort_values('FechaHora')
            .reset_index(drop=True)
        )
    elif resolution_label == SOURCE_RESOLUTION_OPTIONS[2]:
        series_df = _build_nearest_series_to_time_grid(df, column_name, selected_range)
    else:
        series_df = _build_ponderosa_hourly_series(df, column_name, selected_range)

    if series_df.empty or series_df[column_name].dropna().empty:
        return pd.DataFrame()
    return series_df.rename(columns={column_name: 'Valor'})


def _build_ponderosa_ecowitt_individual_series(df, variable, selected_range, resolution_label=COMPARISON_RESOLUTION_OPTIONS[0]):
    return _build_ponderosa_source_individual_series(df, variable, "ECOWITT", selected_range, resolution_label)


def _build_ponderosa_apogee_individual_series(df, variable, selected_range, resolution_label=COMPARISON_RESOLUTION_OPTIONS[0]):
    return _build_ponderosa_source_individual_series(df, variable, "APOGEE", selected_range, resolution_label)


def _make_ponderosa_source_individual_chart(df, variable, source_name, selected_range, resolution_label=COMPARISON_RESOLUTION_OPTIONS[0]):
    series_df = _build_ponderosa_source_individual_series(df, variable, source_name, selected_range, resolution_label)
    if series_df.empty:
        return None

    variable_configs = _get_ponderosa_source_variable_configs(source_name)
    config = variable_configs[variable]
    time_axis = _get_marley_time_axis_config(series_df)
    start_date, end_date = selected_range
    point_mode = resolution_label == COMPARISON_RESOLUTION_OPTIONS[1]
    nearest_mode = resolution_label == SOURCE_RESOLUTION_OPTIONS[2]
    trace_type = go.Scattergl if point_mode and len(series_df) > 250 else go.Scatter
    y_axis = _get_ponderosa_y_axis_config(
        series_df.rename(columns={'Valor': f"{variable} - {source_name}"}),
        variable
    )

    fig = go.Figure()
    fig.add_trace(
        trace_type(
            x=series_df['FechaHora'],
            y=series_df['Valor'],
            name=config['title'],
            mode='lines+markers',
            line=dict(color=config['colors'].get(source_name, config['accent']), width=2.1 if point_mode else 2.7),
            marker=dict(size=3.5 if point_mode else 5),
            opacity=0.86 if point_mode else 1,
            connectgaps=False,
            hovertemplate=(
                "<b>%{x|%Y-%m-%d %H:%M}</b><br>"
                + config['title']
                + ": %{y:.2f} "
                + config['unit']
                + "<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title=dict(
            text=(
                f"{config['title']} - {source_name} - punto por punto"
                if point_mode else
                f"{config['title']} - {source_name} - valor más cercano cada 30 min"
                if nearest_mode else
                f"{config['title']} - {source_name}"
            ),
            x=0,
            xanchor='left'
        ),
        height=305,
        margin=dict(l=24, r=18, t=54, b=42),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(250,248,243,0.72)",
        hovermode='x unified',
        template='plotly_white',
        showlegend=False,
        xaxis=dict(
            title=time_axis['title'],
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
            tickformat=time_axis['tickformat'],
            tickmode=time_axis.get('tickmode', 'linear'),
            dtick=time_axis['dtick'],
            range=[pd.Timestamp(start_date), pd.Timestamp(end_date) + MARLEY_AXIS_END_OFFSET],
        ),
        yaxis=dict(
            title=y_axis['title'],
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
            range=y_axis.get('range'),
            dtick=y_axis.get('dtick'),
            ticksuffix=y_axis.get('ticksuffix', ''),
        ),
    )
    return fig


def _make_ponderosa_ecowitt_individual_chart(df, variable, selected_range, resolution_label=COMPARISON_RESOLUTION_OPTIONS[0]):
    return _make_ponderosa_source_individual_chart(df, variable, "ECOWITT", selected_range, resolution_label)


def _render_ponderosa_source_individual_charts(
    filtered_df,
    selected_range,
    variables,
    source_names,
    heading,
    description,
    resolution_label=COMPARISON_RESOLUTION_OPTIONS[0]
):
    rendered_charts = []
    for source_name in source_names:
        for variable in variables:
            chart = _make_ponderosa_source_individual_chart(
                filtered_df,
                variable,
                source_name,
                selected_range,
                resolution_label
            )
            if chart is not None:
                rendered_charts.append(chart)

    if not rendered_charts:
        return

    st.markdown(f"### {heading}")
    _render_chart_explanation(
        'Lectura individual',
        description,
        accent=BRAND_COLORS['hero']
    )

    for start in range(0, len(rendered_charts), 2):
        cols = st.columns(2)
        for offset, chart in enumerate(rendered_charts[start:start + 2]):
            with cols[offset]:
                _plotly_chart(chart)


def _render_ponderosa_ecowitt_individual_charts(filtered_df, selected_range, resolution_label=COMPARISON_RESOLUTION_OPTIONS[0]):
    _render_ponderosa_source_individual_charts(
        filtered_df,
        selected_range,
        list(PONDEROSA_ECOWITT_VARIABLES.keys()),
        ("ECOWITT",),
        "Variables individuales ECOWITT Ponderosa",
        "Estas gráficas muestran temperatura, humedad y PPFD (PAR) de ECOWITT/MCI, sin mezclar la luminosidad de APOGEE.",
        resolution_label
    )


def _render_ponderosa_apogee_individual_charts(filtered_df, selected_range, resolution_label=COMPARISON_RESOLUTION_OPTIONS[0]):
    _render_ponderosa_source_individual_charts(
        filtered_df,
        selected_range,
        list(PONDEROSA_APOGEE_VARIABLES.keys()),
        ("APOGEE",),
        "Variables individuales APOGEE Ponderosa",
        "Estas gráficas muestran la luminosidad LUX medida por APOGEE desde la columna luz_lux.",
        resolution_label
    )


def _get_ponderosa_light_y_axis_config(comparison, variable):
    config = PONDEROSA_LIGHT_VARIABLES[variable]
    values = []
    for sensor_name in PONDEROSA_LIGHT_SENSOR_NAMES:
        if sensor_name in comparison.columns:
            clean = pd.to_numeric(comparison[sensor_name], errors='coerce').dropna()
            if not clean.empty:
                values.append(clean)

    if not values:
        return {'title': config['unit']}

    all_values = pd.concat(values, ignore_index=True)
    vmin = float(all_values.min())
    vmax = float(all_values.max())
    span = max(vmax - vmin, 1)

    if variable == "LUX":
        axis_max = vmax + max(span * 0.035, 300)
        zero_padding = max(axis_max * 0.018, 250)
        axis_min = -zero_padding if vmin >= 0 else vmin - span * 0.08
        dtick = 500 if axis_max <= 8000 else 1000 if axis_max <= 15000 else 2500 if axis_max <= 45000 else 5000
        return {
            'title': 'LUX',
            'range': [axis_min, axis_max],
            'dtick': dtick,
            'tickformat': ',.0f',
        }

    axis_max = vmax + max(span * 0.035, 8)
    zero_padding = max(axis_max * 0.018, 3)
    axis_min = -zero_padding if vmin >= 0 else vmin - span * 0.08
    dtick = 5 if axis_max <= 80 else 10 if axis_max <= 180 else 25 if axis_max <= 450 else 50 if axis_max <= 1200 else 100
    return {
        'title': PPFD_DISPLAY_LABEL_ASCII,
        'range': [axis_min, axis_max],
        'dtick': dtick,
        'tickformat': ',.0f',
    }


def _make_ponderosa_light_comparison_chart(comparison, variable, selected_range, resolution_label):
    if comparison.empty:
        return None

    config = PONDEROSA_LIGHT_VARIABLES[variable]
    time_axis = _get_marley_time_axis_config(comparison)
    y_axis = _get_ponderosa_light_y_axis_config(comparison, variable)
    start_date, end_date = selected_range
    multi_day_view = start_date != end_date
    point_mode = resolution_label == COMPARISON_RESOLUTION_OPTIONS[1]
    nearest_mode = resolution_label == COMPARISON_RESOLUTION_OPTIONS[2]
    chart_suffix = (
        " - punto por punto"
        if point_mode else
        " - WIGA 30 min / sensores cercanos"
        if nearest_mode else
        ""
    )

    fig = go.Figure()
    for sensor_name in PONDEROSA_LIGHT_SENSOR_NAMES:
        if sensor_name not in comparison.columns or comparison[sensor_name].dropna().empty:
            continue
        source_df = comparison[['FechaHora', sensor_name]].dropna(subset=[sensor_name]).copy()
        trace_type = go.Scattergl if point_mode and len(source_df) > 250 else go.Scatter
        fig.add_trace(
            trace_type(
                x=source_df['FechaHora'],
                y=source_df[sensor_name],
                name=sensor_name,
                mode='lines+markers' if point_mode or not multi_day_view else 'lines',
                line=dict(
                    color=config['colors'][sensor_name],
                    width=2.2 if point_mode else 3
                ),
                marker=dict(size=4 if point_mode else 6),
                opacity=0.86 if point_mode else 1,
                connectgaps=False,
                hovertemplate=(
                    "<b>%{x|%Y-%m-%d %H:%M}</b><br>"
                    + f"{sensor_name}: "
                    + "%{y:.2f} "
                    + config['unit']
                    + "<extra></extra>"
                ),
            )
        )

    if not fig.data:
        return None

    fig.update_layout(
        title=dict(text=f"{config['title']}{chart_suffix}", x=0, xanchor='left'),
        height=460,
        margin=dict(l=30, r=30, t=76, b=32),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(250,248,243,0.72)",
        hovermode='x unified',
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
        xaxis=dict(
            title=time_axis['title'],
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
            tickformat=time_axis['tickformat'],
            tickmode=time_axis.get('tickmode', 'linear'),
            dtick=time_axis['dtick'],
            range=[pd.Timestamp(start_date), pd.Timestamp(end_date) + MARLEY_AXIS_END_OFFSET],
        ),
        yaxis=dict(
            title=y_axis['title'],
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=True,
            zerolinecolor="rgba(45, 48, 64, 0.45)",
            zerolinewidth=1.2,
            range=y_axis.get('range'),
            dtick=y_axis.get('dtick'),
            tickformat=y_axis.get('tickformat'),
        ),
    )
    return fig


def _make_ponderosa_light_difference_chart(comparison, variable, selected_range, resolution_label):
    if comparison.empty or 'WIGA' not in comparison.columns:
        return None

    config = PONDEROSA_LIGHT_VARIABLES[variable]
    diff_df = comparison[['FechaHora', 'WIGA', 'MCI', 'APOGEE']].copy()
    diff_df['MCI - WIGA'] = pd.to_numeric(diff_df['MCI'], errors='coerce') - pd.to_numeric(diff_df['WIGA'], errors='coerce')
    diff_df['APOGEE - WIGA'] = pd.to_numeric(diff_df['APOGEE'], errors='coerce') - pd.to_numeric(diff_df['WIGA'], errors='coerce')
    diff_df = diff_df.dropna(how='all', subset=['MCI - WIGA', 'APOGEE - WIGA'])
    if diff_df.empty:
        return None

    time_axis = _get_marley_time_axis_config(diff_df)
    start_date, end_date = selected_range
    point_mode = resolution_label == COMPARISON_RESOLUTION_OPTIONS[1]
    nearest_mode = resolution_label == COMPARISON_RESOLUTION_OPTIONS[2]
    max_abs = float(pd.concat([
        diff_df['MCI - WIGA'].abs().dropna(),
        diff_df['APOGEE - WIGA'].abs().dropna(),
    ], ignore_index=True).max())
    axis_limit = max(max_abs * 1.12, 1)
    if variable == 'LUX':
        dtick = 250 if axis_limit <= 1500 else 500 if axis_limit <= 4000 else 1000 if axis_limit <= 12000 else 2500
    else:
        dtick = 5 if axis_limit <= 60 else 10 if axis_limit <= 150 else 25 if axis_limit <= 400 else 50

    fig = go.Figure()
    for diff_name, sensor_name in (('MCI - WIGA', 'MCI'), ('APOGEE - WIGA', 'APOGEE')):
        fig.add_trace(
            (go.Scattergl if point_mode and len(diff_df) > 250 else go.Scatter)(
                x=diff_df['FechaHora'],
                y=diff_df[diff_name],
                name=diff_name,
                mode='lines+markers',
                line=dict(color=config['colors'][sensor_name], width=2.8),
                marker=dict(size=5.5),
                connectgaps=False,
                hovertemplate=(
                    "<b>%{x|%Y-%m-%d %H:%M}</b><br>"
                    + f"{diff_name}: "
                    + "%{y:+.2f} "
                    + config['unit']
                    + "<extra></extra>"
                ),
            )
        )

    fig.add_hline(y=0, line_width=1.4, line_dash='solid', line_color="rgba(45, 48, 64, 0.45)")
    fig.update_layout(
        title=dict(
            text=(
                f"Diferencia de {config['title'].replace('Comparativa de ', '')} contra WIGA"
                + (" - punto por punto" if point_mode else " - sensores cercanos" if nearest_mode else " - 30 min")
            ),
            x=0,
            xanchor='left'
        ),
        height=330,
        margin=dict(l=30, r=30, t=70, b=32),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(250,248,243,0.72)",
        hovermode='x unified',
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
        xaxis=dict(
            title=time_axis['title'],
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
            tickformat=time_axis['tickformat'],
            tickmode=time_axis.get('tickmode', 'linear'),
            dtick=time_axis['dtick'],
            range=[pd.Timestamp(start_date), pd.Timestamp(end_date) + MARLEY_AXIS_END_OFFSET],
        ),
        yaxis=dict(
            title=f"Diferencia ({config['unit']})",
            range=[-axis_limit, axis_limit],
            dtick=dtick,
            tickformat=',.0f' if variable == 'LUX' else ',.1f',
            zeroline=True,
            zerolinecolor="rgba(45, 48, 64, 0.45)",
            zerolinewidth=1.2,
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
        ),
    )
    return fig


def _make_ponderosa_light_individual_chart(comparison, variable, sensor_name, selected_range, resolution_label):
    if comparison.empty or sensor_name not in comparison.columns or comparison[sensor_name].dropna().empty:
        return None

    config = PONDEROSA_LIGHT_VARIABLES[variable]
    series_df = comparison[['FechaHora', sensor_name]].dropna(subset=[sensor_name]).copy()
    time_axis = _get_marley_time_axis_config(series_df)
    y_axis = _get_ponderosa_light_y_axis_config(series_df.rename(columns={sensor_name: sensor_name}), variable)
    start_date, end_date = selected_range
    point_mode = resolution_label == COMPARISON_RESOLUTION_OPTIONS[1]
    trace_type = go.Scattergl if point_mode and len(series_df) > 250 else go.Scatter

    fig = go.Figure()
    fig.add_trace(
        trace_type(
            x=series_df['FechaHora'],
            y=series_df[sensor_name],
            name=sensor_name,
            mode='lines+markers',
            line=dict(color=config['colors'][sensor_name], width=2.1 if point_mode else 2.7),
            marker=dict(size=3.5 if point_mode else 5),
            opacity=0.86 if point_mode else 1,
            connectgaps=False,
            hovertemplate=(
                "<b>%{x|%Y-%m-%d %H:%M}</b><br>"
                + f"{sensor_name}: "
                + "%{y:.2f} "
                + config['unit']
                + "<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title=dict(text=f"{_format_variable_display_title(config['title'])} - {sensor_name}", x=0, xanchor='left'),
        height=300,
        margin=dict(l=24, r=18, t=54, b=42),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(250,248,243,0.72)",
        hovermode='x unified',
        template='plotly_white',
        showlegend=False,
        xaxis=dict(
            title=time_axis['title'],
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
            tickformat=time_axis['tickformat'],
            tickmode=time_axis.get('tickmode', 'linear'),
            dtick=time_axis['dtick'],
            range=[pd.Timestamp(start_date), pd.Timestamp(end_date) + MARLEY_AXIS_END_OFFSET],
        ),
        yaxis=dict(
            title=y_axis['title'],
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
            range=y_axis.get('range'),
            dtick=y_axis.get('dtick'),
            tickformat=y_axis.get('tickformat'),
        ),
    )
    return fig


def _build_ponderosa_light_comparison_table(filtered_df, selected_range, resolution_label):
    rows = []
    for variable, config in PONDEROSA_LIGHT_VARIABLES.items():
        comparison = _build_ponderosa_light_comparison(filtered_df, variable, selected_range, resolution_label)
        if comparison.empty:
            continue

        comparison = comparison.dropna(how='all', subset=list(PONDEROSA_LIGHT_SENSOR_NAMES))
        for _, row in comparison.iterrows():
            timestamp = pd.to_datetime(row.get('FechaHora'), errors='coerce')
            if pd.isna(timestamp):
                continue

            values = {
                sensor_name: pd.to_numeric(pd.Series([row.get(sensor_name)]), errors='coerce').iloc[0]
                for sensor_name in PONDEROSA_LIGHT_SENSOR_NAMES
            }
            if all(pd.isna(value) for value in values.values()):
                continue

            wiga_value = values.get('WIGA')
            mci_value = values.get('MCI')
            apogee_value = values.get('APOGEE')
            rows.append({
                'Fecha': timestamp.strftime('%Y-%m-%d'),
                'Hora': timestamp.strftime('%H:%M'),
                'Variable': _format_variable_display_title(config['title']),
                'Unidad': config['unit'],
                'WIGA': round(float(wiga_value), 2) if pd.notna(wiga_value) else pd.NA,
                'MCI': round(float(mci_value), 2) if pd.notna(mci_value) else pd.NA,
                'APOGEE': round(float(apogee_value), 2) if pd.notna(apogee_value) else pd.NA,
                'MCI - WIGA': round(float(mci_value - wiga_value), 2) if pd.notna(mci_value) and pd.notna(wiga_value) else pd.NA,
                'APOGEE - WIGA': round(float(apogee_value - wiga_value), 2) if pd.notna(apogee_value) and pd.notna(wiga_value) else pd.NA,
                'APOGEE - MCI': round(float(apogee_value - mci_value), 2) if pd.notna(apogee_value) and pd.notna(mci_value) else pd.NA,
            })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(['Fecha', 'Hora', 'Variable']).reset_index(drop=True)


def _render_ponderosa_light_individual_charts(comparisons, selected_range, resolution_label):
    rendered_charts = []
    for variable, comparison in comparisons.items():
        for sensor_name in PONDEROSA_LIGHT_SENSOR_NAMES:
            chart = _make_ponderosa_light_individual_chart(
                comparison,
                variable,
                sensor_name,
                selected_range,
                resolution_label
            )
            if chart is not None:
                rendered_charts.append(chart)

    if not rendered_charts:
        return

    st.markdown("### Lecturas individuales APOGEE / MCI / WIGA")
    _render_chart_explanation(
        'Detalle individual',
        'Cada tarjeta separa una variable por sensor usando la misma resolución seleccionada arriba.',
        accent=BRAND_COLORS['hero']
    )
    for start in range(0, len(rendered_charts), 2):
        cols = st.columns(2)
        for offset, chart in enumerate(rendered_charts[start:start + 2]):
            with cols[offset]:
                _plotly_chart(chart)


def _get_available_cortina_dates(df_cortinas_all, bloque_cortinas=None):
    if df_cortinas_all.empty or 'Fecha' not in df_cortinas_all.columns:
        return []

    filtered_df = df_cortinas_all
    if bloque_cortinas and 'Bloque' in filtered_df.columns:
        filtered_df = filtered_df[filtered_df['Bloque'].eq(bloque_cortinas)]

    return sorted(filtered_df['Fecha'].dropna().unique().tolist())


def _build_cortinas_only_chart(datos_cortinas_sel, fecha_periodo, selected_motors, block_label=None):
    if datos_cortinas_sel.empty or not selected_motors:
        return None

    fecha_inicio, fecha_fin = fecha_periodo
    multi_day_view = fecha_inicio != fecha_fin
    hover_time_format = '%d/%m %H:%M' if multi_day_view else '%H:%M'
    xaxis_tickformat = '%d/%m' if multi_day_view else '%H:%M'
    xaxis_title = 'Fecha' if multi_day_view else 'Hora del día'
    profile_times = []

    fig = go.Figure()
    for motor_name in selected_motors:
        df_state = pd.DataFrame()
        for config in SIDE_CONFIGS.values():
            if config['element_col'] not in datos_cortinas_sel.columns:
                continue
            df_state = _build_cortina_apertura_profile(datos_cortinas_sel, motor_name, config)
            if not df_state.empty:
                break

        if df_state.empty:
            continue

        profile_times.extend(pd.to_datetime(df_state['Hora'], errors='coerce').dropna().tolist())
        color = CORTINA_COLORS.get(motor_name, BRAND_COLORS['hero'])
        fig.add_trace(go.Scatter(
            x=df_state['Hora'],
            y=df_state['Apertura'],
            name=VARIABLE_SELECTOR_LABELS.get(motor_name, motor_name),
            mode='lines+markers',
            line=dict(color=color, width=3, shape='hv'),
            marker=dict(size=5, color=color),
            customdata=df_state[['Evento', 'Detalle', 'Apertura']],
            hovertemplate=(
                f'<b>%{{x|{hover_time_format}}}</b><br>'
                f'{VARIABLE_SELECTOR_LABELS.get(motor_name, motor_name)}: %{{customdata[2]:.0f}}% abierto'
                '<br>%{customdata[0]}'
                '<br>%{customdata[1]}'
                '<extra></extra>'
            )
        ))

    if not fig.data:
        return None

    xaxis_range = None
    if not multi_day_view and profile_times:
        min_time = pd.Timestamp(min(profile_times)).floor('30min').to_pydatetime()
        max_time = pd.Timestamp(max(profile_times)).ceil('30min').to_pydatetime()
        xaxis_range = [min_time, max_time]

    title_suffix = f" - {block_label}" if block_label else ""
    fig.update_layout(
        title=dict(text=f"Comportamiento de bloques{title_suffix}", x=0, xanchor='left'),
        height=520,
        margin=dict(l=42, r=24, t=76, b=52),
        paper_bgcolor="rgba(255,255,255,0)",
        plot_bgcolor="rgba(250,248,243,0.72)",
        hovermode='x unified',
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
        xaxis=dict(
            title=xaxis_title,
            tickformat=xaxis_tickformat,
            tickmode='linear' if not multi_day_view else 'auto',
            dtick=60 * 60 * 1000 if not multi_day_view else None,
            range=xaxis_range,
            tickangle=-45 if not multi_day_view else 0,
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=False,
        ),
        yaxis=dict(
            title='Apertura (%)',
            range=[-3, 105],
            showgrid=True,
            gridcolor="rgba(76, 70, 120, 0.07)",
            zeroline=True,
            zerolinecolor='rgba(84, 83, 134, 0.35)',
        tickmode='array',
        tickvals=[0, 25, 50, 75, 100],
        ticksuffix='%',
    ),
    )
    return fig


def _render_ponderosa_wiga_values_dashboard(df_variables_all, df_cortinas_all, selected_finca):
    block_codes, variable_block_map, _ = _get_block_options(
        df_variables_all,
        df_cortinas_all,
        selected_finca=selected_finca
    )
    if df_variables_all.empty or not block_codes:
        st.warning("No hay datos WIGA disponibles para La Ponderosa.")
        st.stop()

    with st.sidebar.expander("Bloque", expanded=True):
        _sidebar_field_label("location", "Seleccionar bloque")
        selected_block_code = st.selectbox(
            "Seleccionar bloque WIGA:",
            options=block_codes,
            format_func=_format_block_display_name,
            key="ponderosa_wiga_only_bloque",
            help=FILTER_HELP_TEXTS['bloque']
        )

    bloque_variables = variable_block_map.get(selected_block_code)
    available_dates = _get_available_variable_dates(df_variables_all, bloque_variables)
    if not available_dates:
        st.warning("No hay fechas disponibles para el bloque WIGA seleccionado.")
        st.stop()

    min_date = available_dates[0]
    max_date = available_dates[-1]
    navigation_state_key = None
    date_state_keys = (
        "ponderosa_wiga_only_fecha_unica",
        "ponderosa_wiga_only_fecha_un_dia",
        "ponderosa_wiga_only_fecha_inicio",
        "ponderosa_wiga_only_fecha_fin",
    )
    for state_key in date_state_keys:
        if state_key in st.session_state and st.session_state[state_key] not in available_dates:
            del st.session_state[state_key]

    with st.sidebar.expander("Periodo", expanded=True):
        if min_date == max_date:
            fecha_unica = _date_input_with_state(
                "Seleccionar fecha:",
                default_value=max_date,
                key="ponderosa_wiga_only_fecha_unica",
                min_value=min_date,
                max_value=max_date,
                help_text=FILTER_HELP_TEXTS['fecha']
            )
            fecha_unica = _get_nearest_available_date(fecha_unica, available_dates)
            selected_range = (fecha_unica, fecha_unica)
            navigation_state_key = "ponderosa_wiga_only_fecha_unica"
        else:
            modo_fechas = st.radio(
                "Modo de fechas:",
                options=["Un día", "Varios días"],
                horizontal=True,
                key="ponderosa_wiga_only_modo_fechas",
                help=FILTER_HELP_TEXTS['modo_fechas']
            )
            if modo_fechas == "Un día":
                fecha_unica_default = _get_nearest_available_date(
                    st.session_state.get("ponderosa_wiga_only_fecha_un_dia", max_date),
                    available_dates
                )
                _sidebar_field_label("calendar", "Seleccionar fecha")
                fecha_unica = _date_input_with_state(
                    "Seleccionar fecha:",
                    default_value=fecha_unica_default,
                    key="ponderosa_wiga_only_fecha_un_dia",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                fecha_unica = _get_nearest_available_date(fecha_unica, available_dates)
                selected_range = (fecha_unica, fecha_unica)
                navigation_state_key = "ponderosa_wiga_only_fecha_un_dia"
            else:
                default_range_end = _get_sidebar_default_range_end(min_date, max_date, default_days=5)
                fecha_inicio_default = _get_nearest_available_date(
                    st.session_state.get("ponderosa_wiga_only_fecha_inicio", min_date),
                    available_dates
                )
                fecha_fin_default = _get_nearest_available_date(
                    st.session_state.get("ponderosa_wiga_only_fecha_fin", default_range_end),
                    available_dates
                )
                _sidebar_field_label("calendar", "Fecha inicio")
                fecha_inicio = _date_input_with_state(
                    "Fecha inicio:",
                    default_value=fecha_inicio_default,
                    key="ponderosa_wiga_only_fecha_inicio",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                _sidebar_field_label("calendar", "Fecha fin")
                fecha_fin = _date_input_with_state(
                    "Fecha fin:",
                    default_value=fecha_fin_default,
                    key="ponderosa_wiga_only_fecha_fin",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                fecha_inicio = _get_nearest_available_date(fecha_inicio, available_dates)
                fecha_fin = _get_nearest_available_date(fecha_fin, available_dates)
                selected_range = _normalize_sidebar_date_range(fecha_inicio, fecha_fin, min_date, max_date)

    source_df = _build_ponderosa_wiga_source(df_variables_all, bloque_variables)
    filtered_df = source_df[source_df['Fecha_Filtro'].between(*selected_range)].copy()
    if filtered_df.empty:
        st.warning("No hay datos WIGA en el periodo seleccionado.")
        st.stop()

    _render_selected_period_banner(
        selected_range,
        min_fecha=min_date,
        max_fecha=max_date,
        navigation_state_key=navigation_state_key,
        title_text='Periodo WIGA Ponderosa',
        available_dates=available_dates
    )

    block_label = _format_block_display_name(selected_block_code)
    st.markdown(f"## La Ponderosa - Solo WIGA | {block_label}")
    st.caption("Lectura de las cuatro variables de Datos_Variables para el bloque seleccionado.")
    wiga_resolution = st.radio(
        "Resolución de las gráficas WIGA:",
    options=SOURCE_RESOLUTION_OPTIONS,
        horizontal=True,
        key="ponderosa_wiga_only_resolution",
        help="Usa promedio para agrupar por media hora, punto por punto para ver las lecturas crudas, o valor más cercano para tomar el registro más próximo a cada marca exacta de 30 minutos."
    )

    wiga_variables = list(PONDEROSA_WIGA_VARIABLES.keys())
    correlation_df = _build_single_source_correlacion_frame(
        filtered_df,
        selected_range,
        wiga_variables,
        "WIGA",
        _build_ponderosa_source_individual_series,
        wiga_resolution,
    )
    if correlation_df.empty:
        st.warning("No hay datos suficientes para graficar las variables WIGA.")
        st.stop()

    tab_chart, tab_stats, tab_detail, tab_records = st.tabs(["Gráfica", "Resumen estadístico", "Detalle individual", "Registros"])
    with tab_chart:
        _render_correlacion(
            correlation_df,
            pd.DataFrame(),
            selected_range,
            variables_seleccionadas=wiga_variables,
            block_label=block_label,
            chart_title='Variables WIGA - La Ponderosa',
            explanation_title='Variables WIGA',
            explanation_text=f'Esta gráfica reúne las cuatro variables WIGA del bloque seleccionado sobre la misma línea de tiempo. Cada color conserva su propia escala a la derecha para comparar comportamiento sin separar la lectura. {PPFD_HELP_TEXT}'
        )

    with tab_stats:
        stats_table = _build_variable_distribution_table(correlation_df, wiga_variables)
        _render_variable_distribution_cards(
            stats_table,
            PONDEROSA_WIGA_VARIABLES,
            title=f"Resumen estadístico WIGA - {block_label}"
        )
        if not stats_table.empty:
            with st.expander("Ver resumen estadístico en tabla", expanded=False):
                _dataframe(stats_table.round(2), hide_index=True)

    with tab_detail:
        if st.checkbox(
            "Cargar detalle individual WIGA",
            key="mostrar_ponderosa_wiga_only_detalle",
            help=FILTER_HELP_TEXTS['graficas_detalladas']
        ):
            _render_ponderosa_source_individual_charts(
                filtered_df,
                selected_range,
                wiga_variables,
                ("WIGA",),
                "Variables individuales WIGA Ponderosa",
                "Cada gráfica muestra una variable WIGA de Datos_Variables con su propia escala.",
                wiga_resolution
            )

    with tab_records:
        _render_graphed_series_table(
            correlation_df,
            wiga_variables,
            PONDEROSA_WIGA_VARIABLES,
            "Tabla de datos graficados - WIGA",
            wiga_resolution,
            source_label=f"WIGA {block_label}",
            expanded=True,
        )
        if st.checkbox(
            "Cargar registros WIGA Ponderosa",
            key="mostrar_ponderosa_wiga_only_registros",
            help=FILTER_HELP_TEXTS['registros']
        ):
            _dataframe(filtered_df.drop(columns=['Fecha_Filtro'], errors='ignore'), hide_index=True)

    st.stop()

    _render_correlacion(
        correlation_df,
        pd.DataFrame(),
        selected_range,
        variables_seleccionadas=wiga_variables,
        block_label=block_label,
        chart_title='Variables WIGA - La Ponderosa',
        explanation_title='Variables WIGA',
        explanation_text=f'Esta gráfica reúne las cuatro variables WIGA del bloque seleccionado sobre la misma línea de tiempo. Cada color conserva su propia escala a la derecha para comparar comportamiento sin separar la lectura. {PPFD_HELP_TEXT}'
    )
    _render_graphed_series_table(
        correlation_df,
        wiga_variables,
        PONDEROSA_WIGA_VARIABLES,
        "Tabla de datos graficados - WIGA",
        wiga_resolution,
        source_label=f"WIGA {block_label}",
    )

    if st.checkbox(
        "Cargar detalle individual WIGA",
        key="mostrar_ponderosa_wiga_only_detalle",
        help=FILTER_HELP_TEXTS['graficas_detalladas']
    ):
        _render_ponderosa_source_individual_charts(
            filtered_df,
            selected_range,
            wiga_variables,
            ("WIGA",),
            "Variables individuales WIGA Ponderosa",
            "Cada gráfica muestra una variable WIGA de Datos_Variables con su propia escala.",
            wiga_resolution
        )

    if st.checkbox(
        "Cargar registros WIGA Ponderosa",
        key="mostrar_ponderosa_wiga_only_registros",
        help=FILTER_HELP_TEXTS['registros']
    ):
        _dataframe(filtered_df.drop(columns=['Fecha_Filtro'], errors='ignore'), hide_index=True)

    st.stop()


def _render_ponderosa_cortinas_dashboard(df_cortinas_all, selected_finca):
    _, _, cortina_block_map = _get_block_options(
        pd.DataFrame(),
        df_cortinas_all,
        selected_finca=selected_finca
    )
    block_codes = _sort_block_names(list(cortina_block_map.keys()))
    if df_cortinas_all.empty or not block_codes:
        st.warning("No hay registros de cortinas disponibles para La Ponderosa.")
        st.stop()

    with st.sidebar.expander("Bloque", expanded=True):
        _sidebar_field_label("location", "Seleccionar bloque")
        selected_block_code = st.selectbox(
            "Seleccionar bloque:",
            options=block_codes,
            format_func=_format_block_display_name,
            key="ponderosa_cortinas_bloque",
            help="Selecciona el bloque para revisar solo el comportamiento de cortinas."
        )

    bloque_cortinas = cortina_block_map.get(selected_block_code)
    available_dates = _get_available_cortina_dates(df_cortinas_all, bloque_cortinas)
    if not available_dates:
        st.warning("No hay fechas disponibles en registros de cortinas para el bloque seleccionado.")
        st.stop()

    min_date = available_dates[0]
    max_date = available_dates[-1]
    navigation_state_key = None
    date_state_keys = (
        "ponderosa_cortinas_fecha_unica",
        "ponderosa_cortinas_fecha_un_dia",
        "ponderosa_cortinas_fecha_inicio",
        "ponderosa_cortinas_fecha_fin",
    )
    for state_key in date_state_keys:
        if state_key in st.session_state and st.session_state[state_key] not in available_dates:
            del st.session_state[state_key]

    with st.sidebar.expander("Periodo", expanded=True):
        if min_date == max_date:
            fecha_unica = _date_input_with_state(
                "Seleccionar fecha:",
                default_value=max_date,
                key="ponderosa_cortinas_fecha_unica",
                min_value=min_date,
                max_value=max_date,
                help_text=FILTER_HELP_TEXTS['fecha']
            )
            fecha_unica = _get_nearest_available_date(fecha_unica, available_dates)
            selected_range = (fecha_unica, fecha_unica)
            navigation_state_key = "ponderosa_cortinas_fecha_unica"
        else:
            modo_fechas = st.radio(
                "Modo de fechas:",
                options=["Un día", "Varios días"],
                horizontal=True,
                key="ponderosa_cortinas_modo_fechas",
                help=FILTER_HELP_TEXTS['modo_fechas']
            )
            if modo_fechas == "Un día":
                fecha_unica_default = _get_nearest_available_date(
                    st.session_state.get("ponderosa_cortinas_fecha_un_dia", max_date),
                    available_dates
                )
                _sidebar_field_label("calendar", "Seleccionar fecha")
                fecha_unica = _date_input_with_state(
                    "Seleccionar fecha:",
                    default_value=fecha_unica_default,
                    key="ponderosa_cortinas_fecha_un_dia",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                fecha_unica = _get_nearest_available_date(fecha_unica, available_dates)
                selected_range = (fecha_unica, fecha_unica)
                navigation_state_key = "ponderosa_cortinas_fecha_un_dia"
            else:
                default_range_end = _get_sidebar_default_range_end(min_date, max_date, default_days=5)
                fecha_inicio_default = _get_nearest_available_date(
                    st.session_state.get("ponderosa_cortinas_fecha_inicio", min_date),
                    available_dates
                )
                fecha_fin_default = _get_nearest_available_date(
                    st.session_state.get("ponderosa_cortinas_fecha_fin", default_range_end),
                    available_dates
                )
                _sidebar_field_label("calendar", "Fecha inicio")
                fecha_inicio = _date_input_with_state(
                    "Fecha inicio:",
                    default_value=fecha_inicio_default,
                    key="ponderosa_cortinas_fecha_inicio",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                _sidebar_field_label("calendar", "Fecha fin")
                fecha_fin = _date_input_with_state(
                    "Fecha fin:",
                    default_value=fecha_fin_default,
                    key="ponderosa_cortinas_fecha_fin",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                fecha_inicio = _get_nearest_available_date(fecha_inicio, available_dates)
                fecha_fin = _get_nearest_available_date(fecha_fin, available_dates)
                selected_range = _normalize_sidebar_date_range(fecha_inicio, fecha_fin, min_date, max_date)

    fecha_inicio, fecha_fin = selected_range
    filtered_df = _filter_cortinas_range(df_cortinas_all, bloque_cortinas, fecha_inicio, fecha_fin)
    if filtered_df.empty:
        st.warning("No hay registros de cortinas en el periodo seleccionado.")
        st.stop()

    available_motors = _get_available_cortina_vars(filtered_df)
    with st.sidebar.expander("Cortinas visibles", expanded=True):
        if not available_motors:
            st.write("No hay frentes o puertas disponibles en este periodo.")
        else:
            for motor_name in available_motors:
                key = f"ponderosa_cortina_visible_{_build_normalized_text_key(motor_name).replace(' ', '_')}"
                if key not in st.session_state:
                    st.session_state[key] = True
                st.checkbox(
                    VARIABLE_SELECTOR_LABELS.get(motor_name, motor_name),
                    key=key,
                    help=VARIABLE_FILTER_HELP.get(motor_name, FILTER_HELP_TEXTS['series_visibles'])
                )

    selected_motors = [
        motor_name
        for motor_name in available_motors
        if st.session_state.get(f"ponderosa_cortina_visible_{_build_normalized_text_key(motor_name).replace(' ', '_')}", True)
    ]
    block_label = _format_block_display_name(selected_block_code)
    rango_multiple = fecha_inicio != fecha_fin
    block_modification = _get_block_modification(block_label)
    culatas_observation = _get_culatas_daily_observation(filtered_df, block_label)
    culatas_by_day = _get_culatas_observation_by_day(filtered_df, block_label)
    daily_annotations = _get_daily_annotations(filtered_df)
    annotations_by_day = _get_annotations_by_day(filtered_df)
    _render_selected_period_banner(
        selected_range,
        min_fecha=min_date,
        max_fecha=max_date,
        navigation_state_key=navigation_state_key,
        title_text='Periodo de bloques',
        available_dates=available_dates
    )

    st.markdown(f"## La Ponderosa - Solo bloques | {block_label}")
    st.caption("Vista dedicada al comportamiento de frentes y puertas registrado en Registro_Cortinas.")
    tab_chart, tab_summary, tab_records = st.tabs(["Gráfica", "Resumen operativo", "Registros"])
    with tab_chart:
        if not selected_motors:
            st.warning("Selecciona al menos una cortina para graficar.")
        else:
            chart = _build_cortinas_only_chart(filtered_df, selected_range, selected_motors, block_label=block_label)
            if chart is None:
                st.warning("No hay información de apertura para las cortinas seleccionadas.")
            else:
                _plotly_chart(chart)
                _render_chart_explanation(
                    "Comportamiento de cortinas",
                    "Las cortinas cerradas se muestran en 0% como en el registro original. El eje de tiempo se resume por horas para leer mejor el día completo; pasa el cursor por cada punto para ver inicio de apertura, duración y cierre cuando esa información exista en el registro.",
                    accent=BRAND_COLORS['hero']
                )

    with tab_summary:
        _render_info_panels(
            block_label,
            block_modification,
            culatas_observation,
            daily_annotations,
            rango_multiple,
            annotations_by_day=annotations_by_day,
            culatas_by_day=culatas_by_day
        )
        _render_cortina_operation_summary(filtered_df, selected_motors)

    with tab_records:
        if st.checkbox(
            "Cargar registros completos de cortinas",
            key="mostrar_ponderosa_cortinas_registros",
            help=FILTER_HELP_TEXTS['registros']
        ):
            _dataframe(filtered_df, hide_index=True)

    st.stop()

    if not selected_motors:
        st.warning("Selecciona al menos una cortina para graficar.")
    else:
        chart = _build_cortinas_only_chart(filtered_df, selected_range, selected_motors, block_label=block_label)
        if chart is None:
            st.warning("No hay información de apertura para las cortinas seleccionadas.")
        else:
            _plotly_chart(chart)
            _render_chart_explanation(
                "Comportamiento de cortinas",
                "Las cortinas cerradas se muestran en 0% como en el registro original. El eje de tiempo se resume por horas para leer mejor el día completo; pasa el cursor por cada punto para ver inicio de apertura, duración y cierre cuando esa información exista en el registro.",
                accent=BRAND_COLORS['hero']
            )

    _render_info_panels(
        block_label,
        block_modification,
        culatas_observation,
        daily_annotations,
        rango_multiple,
        annotations_by_day=annotations_by_day,
        culatas_by_day=culatas_by_day
    )
    _render_cortina_operation_summary(filtered_df, selected_motors)

    if st.checkbox(
        "Cargar registros completos de cortinas",
        key="mostrar_ponderosa_cortinas_registros",
        help=FILTER_HELP_TEXTS['registros']
    ):
        _dataframe(filtered_df, hide_index=True)

    st.stop()


def _render_ponderosa_ecowitt_values_dashboard():
    try:
        ecowitt_df = _load_ponderosa_ecowitt_data()
    except Exception as error:
        st.error(f"No fue posible cargar ECOWITT Ponderosa. Detalle: {error}")
        st.stop()

    if ecowitt_df.empty:
        st.warning("No hay datos disponibles para ECOWITT Ponderosa.")
        st.stop()

    source_df = _build_ponderosa_ecowitt_source(ecowitt_df)
    available_dates = sorted(source_df['Fecha_Filtro'].dropna().unique())
    if not available_dates:
        st.warning("No hay fechas disponibles para ECOWITT Ponderosa.")
        st.stop()

    min_date = available_dates[0]
    max_date = available_dates[-1]
    navigation_state_key = None
    date_state_keys = (
        "ponderosa_ecowitt_only_fecha_unica",
        "ponderosa_ecowitt_only_fecha_un_dia",
        "ponderosa_ecowitt_only_fecha_inicio",
        "ponderosa_ecowitt_only_fecha_fin",
    )
    for state_key in date_state_keys:
        if state_key in st.session_state and st.session_state[state_key] not in available_dates:
            del st.session_state[state_key]

    with st.sidebar.expander("Periodo", expanded=True):
        if min_date == max_date:
            fecha_unica = _date_input_with_state(
                "Seleccionar fecha:",
                default_value=max_date,
                key="ponderosa_ecowitt_only_fecha_unica",
                min_value=min_date,
                max_value=max_date,
                help_text=FILTER_HELP_TEXTS['fecha']
            )
            fecha_unica = _get_nearest_available_date(fecha_unica, available_dates)
            selected_range = (fecha_unica, fecha_unica)
            navigation_state_key = "ponderosa_ecowitt_only_fecha_unica"
        else:
            modo_fechas = st.radio(
                "Modo de fechas:",
                options=["Un día", "Varios días"],
                horizontal=True,
                key="ponderosa_ecowitt_only_modo_fechas",
                help=FILTER_HELP_TEXTS['modo_fechas']
            )
            if modo_fechas == "Un día":
                fecha_unica_default = _get_nearest_available_date(
                    st.session_state.get("ponderosa_ecowitt_only_fecha_un_dia", max_date),
                    available_dates
                )
                _sidebar_field_label("calendar", "Seleccionar fecha")
                fecha_unica = _date_input_with_state(
                    "Seleccionar fecha:",
                    default_value=fecha_unica_default,
                    key="ponderosa_ecowitt_only_fecha_un_dia",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                fecha_unica = _get_nearest_available_date(fecha_unica, available_dates)
                selected_range = (fecha_unica, fecha_unica)
                navigation_state_key = "ponderosa_ecowitt_only_fecha_un_dia"
            else:
                default_range_end = _get_sidebar_default_range_end(min_date, max_date, default_days=5)
                fecha_inicio_default = _get_nearest_available_date(
                    st.session_state.get("ponderosa_ecowitt_only_fecha_inicio", min_date),
                    available_dates
                )
                fecha_fin_default = _get_nearest_available_date(
                    st.session_state.get("ponderosa_ecowitt_only_fecha_fin", default_range_end),
                    available_dates
                )
                _sidebar_field_label("calendar", "Fecha inicio")
                fecha_inicio = _date_input_with_state(
                    "Fecha inicio:",
                    default_value=fecha_inicio_default,
                    key="ponderosa_ecowitt_only_fecha_inicio",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                _sidebar_field_label("calendar", "Fecha fin")
                fecha_fin = _date_input_with_state(
                    "Fecha fin:",
                    default_value=fecha_fin_default,
                    key="ponderosa_ecowitt_only_fecha_fin",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                fecha_inicio = _get_nearest_available_date(fecha_inicio, available_dates)
                fecha_fin = _get_nearest_available_date(fecha_fin, available_dates)
                selected_range = _normalize_sidebar_date_range(fecha_inicio, fecha_fin, min_date, max_date)

    filtered_df = source_df[source_df['Fecha_Filtro'].between(*selected_range)].copy()
    if filtered_df.empty:
        st.warning("No hay datos ECOWITT Ponderosa en el periodo seleccionado.")
        st.stop()

    _render_selected_period_banner(
        selected_range,
        min_fecha=min_date,
        max_fecha=max_date,
        navigation_state_key=navigation_state_key,
        title_text='Periodo ECOWITT Ponderosa',
        available_dates=available_dates
    )

    st.markdown("## La Ponderosa - ECOWITT")
    st.caption("Lectura de temperatura, humedad y PPFD (PAR, µmol m-2 s-1) de ECOWITT/MCI. La luminosidad LUX se muestra aparte en la vista APOGEE.")
    ecowitt_resolution = st.radio(
        "Resolución de las gráficas ECOWITT:",
        options=SOURCE_RESOLUTION_OPTIONS,
        horizontal=True,
        key="ponderosa_ecowitt_only_resolution",
        help="Usa promedio para agrupar por media hora, punto por punto para ver las lecturas crudas, o valor más cercano para tomar el registro más próximo a cada marca exacta de 30 minutos."
    )

    ecowitt_variables = list(PONDEROSA_ECOWITT_VARIABLES.keys())
    correlation_df = _build_single_source_correlacion_frame(
        filtered_df,
        selected_range,
        ecowitt_variables,
        "ECOWITT",
        lambda df, variable, source_name, current_range, resolution: _build_ponderosa_ecowitt_individual_series(
            df,
            variable,
            current_range,
            resolution
        ),
        ecowitt_resolution,
    )
    if correlation_df.empty:
        st.warning("No hay datos suficientes para graficar las variables de ECOWITT Ponderosa.")
        st.stop()

    tab_chart, tab_stats, tab_detail, tab_records = st.tabs(["Gráfica", "Resumen estadístico", "Detalle individual", "Registros"])
    with tab_chart:
        _render_correlacion(
            correlation_df,
            pd.DataFrame(),
            selected_range,
            variables_seleccionadas=ecowitt_variables,
            block_label=f"ECOWITT Bloque {PONDEROSA_ECOWITT_BLOCK_CODE}",
            chart_title='Variables ECOWITT - La Ponderosa',
            explanation_title='Variables ECOWITT',
            explanation_text=f'Esta gráfica reúne temperatura, humedad y PPFD (PAR, µmol m-2 s-1) de ECOWITT/MCI sobre la misma línea de tiempo. La luminosidad LUX pertenece a APOGEE y se consulta en su propia vista. {PPFD_HELP_TEXT}'
        )

    with tab_stats:
        stats_table = _build_variable_distribution_table(correlation_df, ecowitt_variables)
        _render_variable_distribution_cards(
            stats_table,
            PONDEROSA_ECOWITT_VARIABLES,
            title=f"Resumen estadístico ECOWITT - Bloque {PONDEROSA_ECOWITT_BLOCK_CODE}"
        )
        if not stats_table.empty:
            with st.expander("Ver resumen estadístico en tabla", expanded=False):
                _dataframe(stats_table.round(2), hide_index=True)

    with tab_detail:
        if st.checkbox(
            "Cargar detalle individual ECOWITT",
            key="mostrar_ponderosa_ecowitt_only_detalle",
            help=FILTER_HELP_TEXTS['graficas_detalladas']
        ):
            _render_ponderosa_ecowitt_individual_charts(filtered_df, selected_range, ecowitt_resolution)

    with tab_records:
        _render_graphed_series_table(
            correlation_df,
            ecowitt_variables,
            PONDEROSA_ECOWITT_VARIABLES,
            "Tabla de datos graficados - ECOWITT",
            ecowitt_resolution,
            source_label=f"ECOWITT Bloque {PONDEROSA_ECOWITT_BLOCK_CODE}",
            expanded=True,
        )
        if st.checkbox(
            "Cargar registros ECOWITT Ponderosa",
            key="mostrar_ponderosa_ecowitt_only_registros",
            help=FILTER_HELP_TEXTS['registros']
        ):
            _dataframe(filtered_df.drop(columns=['Fecha_Filtro'], errors='ignore'), hide_index=True)

    st.stop()

    _render_correlacion(
        correlation_df,
        pd.DataFrame(),
        selected_range,
        variables_seleccionadas=ecowitt_variables,
        block_label=f"ECOWITT Bloque {PONDEROSA_ECOWITT_BLOCK_CODE}",
        chart_title='Variables ECOWITT - La Ponderosa',
        explanation_title='Variables ECOWITT',
        explanation_text=f'Esta gráfica reúne temperatura, humedad y PPFD (PAR, µmol m-2 s-1) de ECOWITT/MCI sobre la misma línea de tiempo. La luminosidad LUX pertenece a APOGEE y se consulta en su propia vista. {PPFD_HELP_TEXT}'
    )
    _render_graphed_series_table(
        correlation_df,
        ecowitt_variables,
        PONDEROSA_ECOWITT_VARIABLES,
        "Tabla de datos graficados - ECOWITT",
        ecowitt_resolution,
        source_label=f"ECOWITT Bloque {PONDEROSA_ECOWITT_BLOCK_CODE}",
    )

    if st.checkbox(
        "Cargar detalle individual ECOWITT",
        key="mostrar_ponderosa_ecowitt_only_detalle",
        help=FILTER_HELP_TEXTS['graficas_detalladas']
    ):
        _render_ponderosa_ecowitt_individual_charts(filtered_df, selected_range, ecowitt_resolution)

    if st.checkbox(
        "Cargar registros ECOWITT Ponderosa",
        key="mostrar_ponderosa_ecowitt_only_registros",
        help=FILTER_HELP_TEXTS['registros']
    ):
        _dataframe(filtered_df.drop(columns=['Fecha_Filtro'], errors='ignore'), hide_index=True)

    st.stop()


def _render_ponderosa_apogee_values_dashboard():
    try:
        ecowitt_df = _load_ponderosa_ecowitt_data()
    except Exception as error:
        st.error(f"No fue posible cargar los datos de APOGEE desde ECOWITT Ponderosa. Detalle: {error}")
        st.stop()

    if ecowitt_df.empty:
        st.warning("No hay datos disponibles para APOGEE.")
        st.stop()

    source_df = _build_ponderosa_apogee_source(ecowitt_df)
    available_dates = sorted(source_df['Fecha_Filtro'].dropna().unique())
    if not available_dates:
        st.warning("No hay fechas disponibles para APOGEE.")
        st.stop()

    min_date = available_dates[0]
    max_date = available_dates[-1]
    navigation_state_key = None
    date_state_keys = (
        "ponderosa_apogee_fecha_unica",
        "ponderosa_apogee_fecha_un_dia",
        "ponderosa_apogee_fecha_inicio",
        "ponderosa_apogee_fecha_fin",
    )
    for state_key in date_state_keys:
        if state_key in st.session_state and st.session_state[state_key] not in available_dates:
            del st.session_state[state_key]

    with st.sidebar.expander("Periodo", expanded=True):
        if min_date == max_date:
            fecha_unica = _date_input_with_state(
                "Seleccionar fecha:",
                default_value=max_date,
                key="ponderosa_apogee_fecha_unica",
                min_value=min_date,
                max_value=max_date,
                help_text=FILTER_HELP_TEXTS['fecha']
            )
            fecha_unica = _get_nearest_available_date(fecha_unica, available_dates)
            selected_range = (fecha_unica, fecha_unica)
            navigation_state_key = "ponderosa_apogee_fecha_unica"
        else:
            modo_fechas = st.radio(
                "Modo de fechas:",
                options=["Un día", "Varios días"],
                horizontal=True,
                key="ponderosa_apogee_modo_fechas",
                help=FILTER_HELP_TEXTS['modo_fechas']
            )
            if modo_fechas == "Un día":
                fecha_unica_default = _get_nearest_available_date(
                    st.session_state.get("ponderosa_apogee_fecha_un_dia", max_date),
                    available_dates
                )
                _sidebar_field_label("calendar", "Seleccionar fecha")
                fecha_unica = _date_input_with_state(
                    "Seleccionar fecha:",
                    default_value=fecha_unica_default,
                    key="ponderosa_apogee_fecha_un_dia",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                fecha_unica = _get_nearest_available_date(fecha_unica, available_dates)
                selected_range = (fecha_unica, fecha_unica)
                navigation_state_key = "ponderosa_apogee_fecha_un_dia"
            else:
                default_range_end = _get_sidebar_default_range_end(min_date, max_date, default_days=5)
                fecha_inicio_default = _get_nearest_available_date(
                    st.session_state.get("ponderosa_apogee_fecha_inicio", min_date),
                    available_dates
                )
                fecha_fin_default = _get_nearest_available_date(
                    st.session_state.get("ponderosa_apogee_fecha_fin", default_range_end),
                    available_dates
                )
                _sidebar_field_label("calendar", "Fecha inicio")
                fecha_inicio = _date_input_with_state(
                    "Fecha inicio:",
                    default_value=fecha_inicio_default,
                    key="ponderosa_apogee_fecha_inicio",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                _sidebar_field_label("calendar", "Fecha fin")
                fecha_fin = _date_input_with_state(
                    "Fecha fin:",
                    default_value=fecha_fin_default,
                    key="ponderosa_apogee_fecha_fin",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                fecha_inicio = _get_nearest_available_date(fecha_inicio, available_dates)
                fecha_fin = _get_nearest_available_date(fecha_fin, available_dates)
                selected_range = _normalize_sidebar_date_range(fecha_inicio, fecha_fin, min_date, max_date)

    filtered_df = source_df[source_df['Fecha_Filtro'].between(*selected_range)].copy()
    if filtered_df.empty:
        st.warning("No hay datos APOGEE en el periodo seleccionado.")
        st.stop()

    _render_selected_period_banner(
        selected_range,
        min_fecha=min_date,
        max_fecha=max_date,
        navigation_state_key=navigation_state_key,
        title_text='Periodo APOGEE Ponderosa',
        available_dates=available_dates
    )

    st.markdown("## La Ponderosa - APOGEE")
    st.caption("Lectura de luminosidad LUX medida por APOGEE desde la columna luz_lux del archivo ECOWITT Ponderosa.")
    apogee_resolution = st.radio(
        "Resolución de las gráficas APOGEE:",
        options=SOURCE_RESOLUTION_OPTIONS,
        horizontal=True,
        key="ponderosa_apogee_resolution",
        help="Usa promedio para agrupar por media hora, punto por punto para ver las lecturas crudas, o valor más cercano para tomar el registro más próximo a cada marca exacta de 30 minutos."
    )

    apogee_variables = list(PONDEROSA_APOGEE_VARIABLES.keys())
    correlation_df = _build_single_source_correlacion_frame(
        filtered_df,
        selected_range,
        apogee_variables,
        "APOGEE",
        lambda df, variable, source_name, current_range, resolution: _build_ponderosa_apogee_individual_series(
            df,
            variable,
            current_range,
            resolution
        ),
        apogee_resolution,
    )
    if correlation_df.empty:
        st.warning("No hay datos suficientes para graficar la luminosidad de APOGEE.")
        st.stop()

    tab_chart, tab_stats, tab_detail, tab_records = st.tabs(["Gráfica", "Resumen estadístico", "Detalle individual", "Registros"])
    with tab_chart:
        _render_correlacion(
            correlation_df,
            pd.DataFrame(),
            selected_range,
            variables_seleccionadas=apogee_variables,
            block_label="APOGEE",
            chart_title='Luminosidad APOGEE - La Ponderosa',
            explanation_title='Luminosidad APOGEE',
            explanation_text='Esta gráfica muestra únicamente la luminosidad LUX medida por APOGEE. Esta serie no pertenece a ECOWITT/MCI; solo comparte el archivo de origen.'
        )

    with tab_stats:
        stats_table = _build_variable_distribution_table(correlation_df, apogee_variables)
        _render_variable_distribution_cards(
            stats_table,
            PONDEROSA_APOGEE_VARIABLES,
            title="Resumen estadístico APOGEE"
        )
        if not stats_table.empty:
            with st.expander("Ver resumen estadístico en tabla", expanded=False):
                _dataframe(stats_table.round(2), hide_index=True)

    with tab_detail:
        if st.checkbox(
            "Cargar detalle individual APOGEE",
            key="mostrar_ponderosa_apogee_detalle",
            help=FILTER_HELP_TEXTS['graficas_detalladas']
        ):
            _render_ponderosa_apogee_individual_charts(filtered_df, selected_range, apogee_resolution)

    with tab_records:
        _render_graphed_series_table(
            correlation_df,
            apogee_variables,
            PONDEROSA_APOGEE_VARIABLES,
            "Tabla de datos graficados - APOGEE",
            apogee_resolution,
            source_label="APOGEE",
            expanded=True,
        )
        if st.checkbox(
            "Cargar registros APOGEE Ponderosa",
            key="mostrar_ponderosa_apogee_registros",
            help=FILTER_HELP_TEXTS['registros']
        ):
            _dataframe(filtered_df.drop(columns=['Fecha_Filtro'], errors='ignore'), hide_index=True)

    st.stop()

    _render_correlacion(
        correlation_df,
        pd.DataFrame(),
        selected_range,
        variables_seleccionadas=apogee_variables,
        block_label="APOGEE",
        chart_title='Luminosidad APOGEE - La Ponderosa',
        explanation_title='Luminosidad APOGEE',
        explanation_text='Esta gráfica muestra únicamente la luminosidad LUX medida por APOGEE. Esta serie no pertenece a ECOWITT/MCI; solo comparte el archivo de origen.'
    )
    _render_graphed_series_table(
        correlation_df,
        apogee_variables,
        PONDEROSA_APOGEE_VARIABLES,
        "Tabla de datos graficados - APOGEE",
        apogee_resolution,
        source_label="APOGEE",
    )

    if st.checkbox(
        "Cargar detalle individual APOGEE",
        key="mostrar_ponderosa_apogee_detalle",
        help=FILTER_HELP_TEXTS['graficas_detalladas']
    ):
        _render_ponderosa_apogee_individual_charts(filtered_df, selected_range, apogee_resolution)

    if st.checkbox(
        "Cargar registros APOGEE Ponderosa",
        key="mostrar_ponderosa_apogee_registros",
        help=FILTER_HELP_TEXTS['registros']
    ):
        _dataframe(filtered_df.drop(columns=['Fecha_Filtro'], errors='ignore'), hide_index=True)

    st.stop()


def _render_ponderosa_apogee_mci_wiga_dashboard(df_variables_all, df_cortinas_all, selected_finca):
    try:
        ecowitt_df = _load_ponderosa_ecowitt_data()
    except Exception as error:
        st.error(f"No fue posible cargar ECOWITT Ponderosa. Detalle: {error}")
        st.stop()

    block_codes, variable_block_map, _ = _get_block_options(
        df_variables_all,
        df_cortinas_all,
        selected_finca=selected_finca
    )
    if PONDEROSA_ECOWITT_BLOCK_CODE not in block_codes:
        st.warning("No hay datos WIGA del Bloque 35 disponibles para comparar APOGEE / MCI / WIGA.")
        st.stop()

    selected_source_code = PONDEROSA_ECOWITT_BLOCK_CODE
    bloque_variables = variable_block_map.get(selected_source_code)
    comparison_df, source_frames = _build_ponderosa_light_sensor_dataset(
        df_variables_all,
        ecowitt_df,
        bloque_variables
    )
    if comparison_df.empty:
        st.warning("No fue posible construir la comparación APOGEE / MCI / WIGA.")
        st.stop()

    date_sets = []
    for source_name in PONDEROSA_LIGHT_SENSOR_NAMES:
        source_df = source_frames.get(source_name, pd.DataFrame())
        if source_df.empty or 'Fecha_Filtro' not in source_df.columns:
            date_sets.append(set())
        else:
            date_sets.append(set(source_df['Fecha_Filtro'].dropna().unique()))
    available_dates = sorted(set.intersection(*date_sets)) if date_sets and all(date_sets) else []
    if not available_dates:
        st.warning("No hay fechas comunes entre APOGEE, MCI y WIGA para esta comparación.")
        st.stop()

    min_date = available_dates[0]
    max_date = available_dates[-1]
    navigation_state_key = None
    date_state_keys = (
        "ponderosa_light_fecha_unica",
        "ponderosa_light_fecha_un_dia",
        "ponderosa_light_fecha_inicio",
        "ponderosa_light_fecha_fin",
    )
    for state_key in date_state_keys:
        if state_key in st.session_state and st.session_state[state_key] not in available_dates:
            del st.session_state[state_key]

    with st.sidebar.expander("Fuente WIGA", expanded=True):
        _sidebar_field_label("location", "Fuente comparada")
        st.markdown(
            f"""
            <div class="sidebar-helper-text">
                La comparación usa WIGA del {_format_block_display_name(selected_source_code)}.
                MCI y APOGEE salen de ECOWITT Ponderosa para cruzar los tres sensores sobre el mismo periodo.
            </div>
            """,
            unsafe_allow_html=True
        )

    with st.sidebar.expander("Periodo", expanded=True):
        if min_date == max_date:
            fecha_unica = _date_input_with_state(
                "Seleccionar fecha:",
                default_value=max_date,
                key="ponderosa_light_fecha_unica",
                min_value=min_date,
                max_value=max_date,
                help_text=FILTER_HELP_TEXTS['fecha']
            )
            fecha_unica = _get_nearest_available_date(fecha_unica, available_dates)
            selected_range = (fecha_unica, fecha_unica)
            navigation_state_key = "ponderosa_light_fecha_unica"
        else:
            modo_fechas = st.radio(
                "Modo de fechas:",
                options=["Un día", "Varios días"],
                horizontal=True,
                key="ponderosa_light_modo_fechas",
                help=FILTER_HELP_TEXTS['modo_fechas']
            )
            if modo_fechas == "Un día":
                fecha_unica_default = _get_nearest_available_date(
                    st.session_state.get("ponderosa_light_fecha_un_dia", max_date),
                    available_dates
                )
                _sidebar_field_label("calendar", "Seleccionar fecha")
                fecha_unica = _date_input_with_state(
                    "Seleccionar fecha:",
                    default_value=fecha_unica_default,
                    key="ponderosa_light_fecha_un_dia",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                fecha_unica = _get_nearest_available_date(fecha_unica, available_dates)
                selected_range = (fecha_unica, fecha_unica)
                navigation_state_key = "ponderosa_light_fecha_un_dia"
            else:
                default_range_end = _get_sidebar_default_range_end(min_date, max_date, default_days=5)
                fecha_inicio_default = _get_nearest_available_date(
                    st.session_state.get("ponderosa_light_fecha_inicio", min_date),
                    available_dates
                )
                fecha_fin_default = _get_nearest_available_date(
                    st.session_state.get("ponderosa_light_fecha_fin", default_range_end),
                    available_dates
                )
                _sidebar_field_label("calendar", "Fecha inicio")
                fecha_inicio = _date_input_with_state(
                    "Fecha inicio:",
                    default_value=fecha_inicio_default,
                    key="ponderosa_light_fecha_inicio",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                _sidebar_field_label("calendar", "Fecha fin")
                fecha_fin = _date_input_with_state(
                    "Fecha fin:",
                    default_value=fecha_fin_default,
                    key="ponderosa_light_fecha_fin",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                fecha_inicio = _get_nearest_available_date(fecha_inicio, available_dates)
                fecha_fin = _get_nearest_available_date(fecha_fin, available_dates)
                selected_range = _normalize_sidebar_date_range(fecha_inicio, fecha_fin, min_date, max_date)

    filtered_df = comparison_df[comparison_df['Fecha_Filtro'].between(*selected_range)].copy()
    if filtered_df.empty:
        st.warning("No hay datos APOGEE / MCI / WIGA en el periodo seleccionado.")
        st.stop()

    _render_selected_period_banner(
        selected_range,
        min_fecha=min_date,
        max_fecha=max_date,
        navigation_state_key=navigation_state_key,
        title_text='Periodo APOGEE / MCI / WIGA',
        available_dates=available_dates
    )

    block_label = _format_block_display_name(selected_source_code)
    st.markdown("## La Ponderosa - APOGEE / MCI / WIGA")
    st.caption(f"Comparación de LUX y PPFD (PAR, µmol m-2 s-1) para {block_label}. WIGA usa Datos_Variables; MCI y APOGEE usan ECOWITT Ponderosa.")
    _render_chart_explanation(
        'Origen de los valores',
        (
            f"WIGA toma el PPFD (PAR, µmol m-2 s-1) real del Bloque 35 y calcula LUX estimado con PPFD x {PAR_TO_LUX_FACTOR:.0f}. "
            f"MCI toma el PPFD (PAR) del archivo ECOWITT Ponderosa y calcula LUX con el mismo factor. "
            f"APOGEE toma la columna luz_lux y calcula PPFD (PAR) estimado dividiendo entre {PAR_TO_LUX_FACTOR:.0f}. "
            f"{PPFD_HELP_TEXT}"
        ),
        accent=BRAND_COLORS['hero'],
        kicker='Cálculo'
    )

    comparison_resolution = st.radio(
        "Resolución de APOGEE / MCI / WIGA:",
        options=COMPARISON_RESOLUTION_OPTIONS,
        horizontal=True,
        key="ponderosa_light_resolution",
        help="Promedio agrupa todos los sensores cada 30 minutos; punto por punto usa WIGA como ancla cruda y toma el registro más cercano de MCI/APOGEE; WIGA 30 min toma WIGA por media hora y busca los registros cercanos de MCI/APOGEE."
    )
    comparisons = {}
    for variable in PONDEROSA_LIGHT_VARIABLES:
        comparison = _build_ponderosa_light_comparison(filtered_df, variable, selected_range, comparison_resolution)
        comparison = comparison.dropna(how='all', subset=list(PONDEROSA_LIGHT_SENSOR_NAMES)) if not comparison.empty else comparison
        comparisons[variable] = comparison

    tab_compare, tab_table, tab_detail, tab_records = st.tabs(["Gráfica", "Tabla y resumen", "Detalle individual", "Registros"])
    with tab_compare:
        for variable, comparison in comparisons.items():
            chart = _make_ponderosa_light_comparison_chart(comparison, variable, selected_range, comparison_resolution)
            if chart is None:
                st.info(f"No hay suficientes datos para graficar {PONDEROSA_LIGHT_VARIABLES[variable]['title'].lower()}.")
                continue
            _plotly_chart(chart)
            difference_chart = _make_ponderosa_light_difference_chart(
                comparison,
                variable,
                selected_range,
                comparison_resolution
            )
            if difference_chart is not None:
                _render_chart_explanation(
                    f'Diferencia de {PONDEROSA_LIGHT_VARIABLES[variable]["title"].replace("Comparativa de ", "")}',
                    'Esta gráfica no muestra el valor absoluto, sino cuánto se separan MCI y APOGEE respecto a WIGA. La línea cero significa que el sensor está igual a WIGA; arriba mide más alto y abajo mide más bajo.',
                    accent=PONDEROSA_LIGHT_VARIABLES[variable]['accent']
                )
                _plotly_chart(difference_chart)

    with tab_table:
        table_mode = (
            "Promedio de cada sensor en bloques de 30 minutos"
            if comparison_resolution == COMPARISON_RESOLUTION_OPTIONS[0] else
            "WIGA crudo con MCI/APOGEE más cercanos"
            if comparison_resolution == COMPARISON_RESOLUTION_OPTIONS[1] else
            "WIGA 30 min con MCI/APOGEE más cercanos"
        )
        table = _build_ponderosa_light_comparison_table(filtered_df, selected_range, comparison_resolution)
        if table.empty:
            st.info("No hay datos suficientes para construir la tabla comparativa.")
        else:
            st.caption(f"Tabla calculada con: {table_mode}. Las diferencias se leen como sensor comparado menos WIGA o APOGEE menos MCI.")
            _render_comparison_table_summary(table, title="Resumen ejecutivo APOGEE / MCI / WIGA")
            _render_variable_split_tables(
                table,
                default_expanded=True,
                download_label="Descargar reporte APOGEE / MCI / WIGA",
                download_file_name=f"reporte_apogee_mci_wiga_{_build_normalized_text_key(comparison_resolution).replace(' ', '_')}.xlsx",
                download_key="descargar_ponderosa_light_reporte"
            )

    with tab_detail:
        if st.checkbox(
            "Mostrar gráficas individuales APOGEE / MCI / WIGA",
            key="mostrar_ponderosa_light_detalles",
            help="Activa esta sección para ver cada variable por separado debajo de la comparativa principal."
        ):
            _render_ponderosa_light_individual_charts(comparisons, selected_range, comparison_resolution)

    with tab_records:
        if st.checkbox(
            "Cargar registros base APOGEE / MCI / WIGA",
            key="mostrar_ponderosa_light_registros",
            help=FILTER_HELP_TEXTS['registros']
        ):
            _dataframe(filtered_df.drop(columns=['Fecha_Filtro'], errors='ignore'), hide_index=True)

    st.stop()

    for variable in PONDEROSA_LIGHT_VARIABLES:
        comparison = _build_ponderosa_light_comparison(filtered_df, variable, selected_range, comparison_resolution)
        comparison = comparison.dropna(how='all', subset=list(PONDEROSA_LIGHT_SENSOR_NAMES)) if not comparison.empty else comparison
        comparisons[variable] = comparison
        chart = _make_ponderosa_light_comparison_chart(comparison, variable, selected_range, comparison_resolution)
        if chart is None:
            st.info(f"No hay suficientes datos para graficar {PONDEROSA_LIGHT_VARIABLES[variable]['title'].lower()}.")
            continue
        _plotly_chart(chart)
        difference_chart = _make_ponderosa_light_difference_chart(
            comparison,
            variable,
            selected_range,
            comparison_resolution
        )
        if difference_chart is not None:
            _render_chart_explanation(
                f'Diferencia de {PONDEROSA_LIGHT_VARIABLES[variable]["title"].replace("Comparativa de ", "")}',
                'Esta gráfica no muestra el valor absoluto, sino cuánto se separan MCI y APOGEE respecto a WIGA. La línea cero significa que el sensor está igual a WIGA; arriba mide más alto y abajo mide más bajo.',
                accent=PONDEROSA_LIGHT_VARIABLES[variable]['accent']
            )
            _plotly_chart(difference_chart)

    table_mode = (
        "Promedio de cada sensor en bloques de 30 minutos"
        if comparison_resolution == COMPARISON_RESOLUTION_OPTIONS[0] else
        "WIGA crudo con MCI/APOGEE más cercanos"
        if comparison_resolution == COMPARISON_RESOLUTION_OPTIONS[1] else
        "WIGA 30 min con MCI/APOGEE más cercanos"
    )
    if st.checkbox(
        "Mostrar tabla comparativa de registros",
        value=True,
        key="mostrar_ponderosa_light_tabla",
        help="Muestra fecha, hora, valores de los tres sensores y diferencias por variable."
    ):
        table = _build_ponderosa_light_comparison_table(filtered_df, selected_range, comparison_resolution)
        if table.empty:
            st.info("No hay datos suficientes para construir la tabla comparativa.")
        else:
            st.caption(f"Tabla calculada con: {table_mode}. Las diferencias se leen como sensor comparado menos WIGA o APOGEE menos MCI.")
            _render_comparison_table_summary(table, title="Resumen ejecutivo APOGEE / MCI / WIGA")
            _render_variable_split_tables(
                table,
                default_expanded=True,
                download_label="Descargar reporte APOGEE / MCI / WIGA",
                download_file_name=f"reporte_apogee_mci_wiga_{_build_normalized_text_key(comparison_resolution).replace(' ', '_')}.xlsx",
                download_key="descargar_ponderosa_light_reporte"
            )

    show_details = st.checkbox(
        "Mostrar gráficas individuales APOGEE / MCI / WIGA",
        key="mostrar_ponderosa_light_detalles",
        help="Activa esta sección para ver cada variable por separado debajo de la comparativa principal."
    )
    if show_details:
        _render_ponderosa_light_individual_charts(comparisons, selected_range, comparison_resolution)

    if st.checkbox(
        "Cargar registros base APOGEE / MCI / WIGA",
        key="mostrar_ponderosa_light_registros",
        help=FILTER_HELP_TEXTS['registros']
    ):
        _dataframe(filtered_df.drop(columns=['Fecha_Filtro'], errors='ignore'), hide_index=True)

    st.stop()


def _render_ponderosa_comparison_metric_cards(overlap, selected_variable):
    config = PONDEROSA_COMPARISON_VARIABLES[selected_variable]
    avg_abs_diff = overlap['DiffValue'].mean() if not overlap.empty else None
    avg_signed_diff = overlap['SignedDiff'].mean() if not overlap.empty else None
    std_diff = overlap['SignedDiff'].std() if not overlap.empty else None
    unit = config['unit']
    card_unit = unit.replace("µmol m-2 s-1", "µmol/m²/s")

    if pd.isna(avg_signed_diff):
        signed_interpretation = "No hay suficientes lecturas simultáneas para identificar cuál sensor quedó por encima."
    elif avg_signed_diff > 0:
        signed_interpretation = "En promedio, WIGA estuvo por encima de ECOWITT en esta variable."
    elif avg_signed_diff < 0:
        signed_interpretation = "En promedio, ECOWITT estuvo por encima de WIGA en esta variable."
    else:
        signed_interpretation = "En promedio, ambos sensores quedaron prácticamente alineados."

    if pd.isna(std_diff):
        std_interpretation = "No hay suficientes lecturas comparables para evaluar estabilidad."
    elif std_diff <= 0.3:
        std_interpretation = "La diferencia entre sensores fue bastante estable a lo largo del tiempo."
    elif std_diff <= 0.8:
        std_interpretation = "La diferencia entre sensores tuvo una variación moderada entre franjas."
    else:
        std_interpretation = "La diferencia entre sensores cambió bastante entre bloques de 30 minutos."

    metric_cards = [
        {
            'title': 'Diferencia absoluta media',
            'value': f"{avg_abs_diff:.2f}" if pd.notna(avg_abs_diff) else "Sin datos",
            'unit': card_unit if pd.notna(avg_abs_diff) else "",
            'accent': config['colors']['WIGA'],
            'description': "Mide qué tan separados estuvieron WIGA y ECOWITT en promedio, sin importar cuál quedó por encima.",
            'insight': (
                "Mientras más bajo sea este valor, más parecidas fueron las lecturas entre ambos sensores."
                if pd.notna(avg_abs_diff) else
                "Necesitamos más datos simultáneos para medir qué tan separados estuvieron ambos sensores."
            ),
        },
        {
            'title': 'Diferencia media WIGA - ECOWITT',
            'value': f"{avg_signed_diff:+.2f}" if pd.notna(avg_signed_diff) else "Sin datos",
            'unit': card_unit if pd.notna(avg_signed_diff) else "",
            'accent': config['colors']['ECOWITT'],
            'description': "Conserva el signo de la diferencia. Nos dice si uno de los sensores tiende a leer más alto que el otro.",
            'insight': signed_interpretation,
        },
        {
            'title': 'Desviación estándar',
            'value': f"{std_diff:.2f}" if pd.notna(std_diff) else "Sin datos",
            'unit': card_unit if pd.notna(std_diff) else "",
            'accent': config['accent'],
            'description': "Muestra qué tan estable fue la diferencia entre ambos sensores a lo largo del tiempo.",
            'insight': std_interpretation,
        },
    ]

    metric_cols = st.columns(3)
    for idx, metric in enumerate(metric_cards):
        with metric_cols[idx]:
            st.markdown(
                f"""
                <div style="
                    background: linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(247,244,238,0.96) 100%);
                    border: 1px solid rgba(84, 83, 134, 0.10);
                    border-top: 4px solid {metric['accent']};
                    border-radius: 8px;
                    padding: 1.15rem 1.1rem 1rem 1.1rem;
                    box-shadow: 0 18px 36px rgba(44, 46, 42, 0.08);
                    min-height: 235px;
                ">
                    <div style="
                        font-family: 'Montserrat', sans-serif;
                        font-size: 0.82rem;
                        font-weight: 800;
                        letter-spacing: 0.03em;
                        text-transform: uppercase;
                        color: {metric['accent']};
                        margin-bottom: 0.7rem;
                    ">
                        {html.escape(metric['title'])}
                    </div>
                    <div style="
                        display: flex;
                        align-items: baseline;
                        gap: 0.45rem;
                        flex-wrap: wrap;
                        margin-bottom: 0.95rem;
                    ">
                        <span style="
                            font-family: 'Montserrat', sans-serif;
                            font-size: 2rem;
                            line-height: 1.08;
                            font-weight: 800;
                            color: {BRAND_COLORS['graphite']};
                        ">
                            {html.escape(metric['value'])}
                        </span>
                        <span style="
                            font-family: 'Montserrat', sans-serif;
                            font-size: 1.02rem;
                            line-height: 1.15;
                            font-weight: 800;
                            color: rgba(56, 58, 53, 0.86);
                            max-width: 8.8rem;
                        ">
                            {html.escape(metric['unit'])}
                        </span>
                    </div>
                    <div style="
                        font-family: 'Montserrat', sans-serif;
                        font-size: 0.94rem;
                        line-height: 1.55;
                        color: rgba(56, 58, 53, 0.82);
                        margin-bottom: 0.85rem;
                    ">
                        {html.escape(metric['description'])}
                    </div>
                    <div style="
                        background: rgba(84, 83, 134, 0.05);
                        border: 1px solid rgba(84, 83, 134, 0.08);
                        border-radius: 8px;
                        padding: 0.8rem 0.85rem;
                    ">
                        <div style="
                            font-family: 'Montserrat', sans-serif;
                            font-size: 0.76rem;
                            font-weight: 800;
                            letter-spacing: 0.04em;
                            text-transform: uppercase;
                            color: {BRAND_COLORS['hero']};
                            margin-bottom: 0.35rem;
                        ">
                            Cómo leerlo
                        </div>
                        <div style="
                            font-family: 'Montserrat', sans-serif;
                            font-size: 0.9rem;
                            line-height: 1.55;
                            color: {BRAND_COLORS['ink']};
                        ">
                            {html.escape(metric['insight'])}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )


def _render_ponderosa_ecowitt_dashboard(df_variables_all, df_cortinas_all, selected_finca):
    try:
        ecowitt_df = _load_ponderosa_ecowitt_data()
    except Exception as error:
        st.error(f"No fue posible cargar ECOWITT Ponderosa. Detalle: {error}")
        st.stop()

    if ecowitt_df.empty:
        st.warning("No hay datos disponibles para ECOWITT Ponderosa.")
        st.stop()

    block_codes, variable_block_map, _ = _get_block_options(
        df_variables_all,
        df_cortinas_all,
        selected_finca=selected_finca
    )
    if PONDEROSA_ECOWITT_BLOCK_CODE not in block_codes:
        st.warning("No hay datos WIGA del Bloque 35 disponibles para comparar con ECOWITT Ponderosa.")
        st.stop()

    with st.sidebar.expander("Fuente WIGA", expanded=True):
        _sidebar_field_label("location", "Fuente comparada")
        st.markdown(
            f"""
            <div class="sidebar-helper-text">
                ECOWITT Ponderosa corresponde al {_format_block_display_name(PONDEROSA_ECOWITT_BLOCK_CODE)}.
                La comparación se fija contra ese mismo bloque en Datos_Variables.
            </div>
            """,
            unsafe_allow_html=True
        )
        selected_source_code = PONDEROSA_ECOWITT_BLOCK_CODE

    bloque_variables = variable_block_map.get(selected_source_code)
    comparison_df, source_frames = _build_ponderosa_comparison_dataset(
        df_variables_all,
        ecowitt_df,
        bloque_variables
    )
    if comparison_df.empty:
        st.warning("No fue posible construir la comparación entre WIGA y ECOWITT Ponderosa.")
        st.stop()

    wiga_dates = set(source_frames['WIGA']['Fecha_Filtro'].dropna().unique()) if not source_frames['WIGA'].empty else set()
    eco_dates = set(source_frames['ECOWITT']['Fecha_Filtro'].dropna().unique()) if not source_frames['ECOWITT'].empty else set()
    available_dates = sorted(wiga_dates & eco_dates)
    if not available_dates:
        st.warning("No hay fechas comunes entre la fuente WIGA seleccionada y ECOWITT Ponderosa.")
        st.stop()

    min_date = available_dates[0]
    max_date = available_dates[-1]
    navigation_state_key = None
    date_state_defaults = {
        "ponderosa_ecowitt_fecha_unica": max_date,
        "ponderosa_ecowitt_fecha_un_dia": max_date,
        "ponderosa_ecowitt_fecha_inicio": min_date,
        "ponderosa_ecowitt_fecha_fin": max_date,
    }
    for state_key in date_state_defaults:
        if state_key in st.session_state and st.session_state[state_key] not in available_dates:
            del st.session_state[state_key]

    with st.sidebar.expander("Periodo", expanded=True):
        if min_date == max_date:
            fecha_unica = _date_input_with_state(
                "Seleccionar fecha:",
                default_value=max_date,
                key="ponderosa_ecowitt_fecha_unica",
                min_value=min_date,
                max_value=max_date,
                help_text=FILTER_HELP_TEXTS['fecha']
            )
            fecha_unica = _get_nearest_available_date(fecha_unica, available_dates)
            selected_range = (fecha_unica, fecha_unica)
            navigation_state_key = "ponderosa_ecowitt_fecha_unica"
        else:
            modo_fechas = st.radio(
                "Modo de fechas:",
                options=["Un día", "Varios días"],
                horizontal=True,
                key="ponderosa_ecowitt_modo_fechas",
                help=FILTER_HELP_TEXTS['modo_fechas']
            )
            if modo_fechas == "Un día":
                fecha_unica_default = _coerce_sidebar_date(
                    st.session_state.get("ponderosa_ecowitt_fecha_un_dia", max_date),
                    max_date
                )
                fecha_unica_default = _get_nearest_available_date(fecha_unica_default, available_dates)
                _sidebar_field_label("calendar", "Seleccionar fecha")
                fecha_unica = _date_input_with_state(
                    "Seleccionar fecha:",
                    default_value=fecha_unica_default,
                    key="ponderosa_ecowitt_fecha_un_dia",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                fecha_unica = _get_nearest_available_date(fecha_unica, available_dates)
                selected_range = (fecha_unica, fecha_unica)
                navigation_state_key = "ponderosa_ecowitt_fecha_un_dia"
            else:
                default_range_end = _get_sidebar_default_range_end(min_date, max_date, default_days=5)
                fecha_inicio_default = _coerce_sidebar_date(
                    st.session_state.get("ponderosa_ecowitt_fecha_inicio", min_date),
                    min_date
                )
                fecha_fin_default = _coerce_sidebar_date(
                    st.session_state.get("ponderosa_ecowitt_fecha_fin", default_range_end),
                    default_range_end
                )
                fecha_inicio_default = _get_nearest_available_date(fecha_inicio_default, available_dates)
                fecha_fin_default = _get_nearest_available_date(fecha_fin_default, available_dates)
                _sidebar_field_label("calendar", "Fecha inicio")
                fecha_inicio = _date_input_with_state(
                    "Fecha inicio:",
                    default_value=fecha_inicio_default,
                    key="ponderosa_ecowitt_fecha_inicio",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                _sidebar_field_label("calendar", "Fecha fin")
                fecha_fin = _date_input_with_state(
                    "Fecha fin:",
                    default_value=fecha_fin_default,
                    key="ponderosa_ecowitt_fecha_fin",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                fecha_inicio = _get_nearest_available_date(fecha_inicio, available_dates)
                fecha_fin = _get_nearest_available_date(fecha_fin, available_dates)
                selected_range = _normalize_sidebar_date_range(fecha_inicio, fecha_fin, min_date, max_date)

    filtered_df = comparison_df[comparison_df['Fecha_Filtro'].between(*selected_range)].copy()
    if filtered_df.empty:
        st.warning("No hay datos disponibles en el periodo seleccionado.")
        st.stop()

    _render_selected_period_banner(
        selected_range,
        min_fecha=min_date,
        max_fecha=max_date,
        navigation_state_key=navigation_state_key,
        title_text='Periodo Ponderosa WIGA / ECOWITT',
        available_dates=available_dates
    )

    block_label = _format_block_display_name(selected_source_code)
    st.markdown("## La Ponderosa - Comparativa WIGA / ECOWITT")
    st.caption(f"Comparación entre {block_label} en Datos_Variables y la estación ECOWITT Ponderosa.")
    _render_chart_explanation(
        'Cómo usar esta comparación',
        'Se muestran todas las variables compartidas entre WIGA y ECOWITT, una debajo de otra. Las lecturas se agrupan o se alinean según la resolución seleccionada para que ambos equipos queden sobre la misma línea de tiempo.',
        accent=BRAND_COLORS['hero'],
        kicker='Orientación'
    )

    comparison_resolution = st.radio(
        "Resolución de la gráfica WIGA vs ECOWITT:",
        options=COMPARISON_RESOLUTION_OPTIONS,
        horizontal=True,
        key="ponderosa_ecowitt_comparison_resolution",
        help="Promedio agrupa ambos sensores cada 30 minutos; punto por punto usa lecturas crudas; WIGA 30 min mantiene WIGA como base y toma el ECOWITT más cercano a cada hora WIGA."
    )
    point_mode = comparison_resolution == COMPARISON_RESOLUTION_OPTIONS[1]
    nearest_wiga_mode = comparison_resolution == COMPARISON_RESOLUTION_OPTIONS[2]
    compared_variables = list(PONDEROSA_COMPARISON_VARIABLES.keys())
    tab_compare, tab_stats, tab_tables, tab_detail = st.tabs(["Gráfica", "Resumen estadístico", "Tabla", "Detalle y registros"])

    with tab_compare:
        for variable_name in compared_variables:
            comparison = (
                _build_point_comparison(filtered_df, variable_name, PONDEROSA_SENSOR_NAMES)
                if point_mode else
                _build_wiga_anchor_nearest_comparison(
                    filtered_df,
                    variable_name,
                    PONDEROSA_SENSOR_NAMES,
                    selected_range,
                    _build_ponderosa_hourly_series
                )
                if nearest_wiga_mode else
                _build_ponderosa_hourly_comparison(filtered_df, variable_name, selected_range)
            )
            if comparison.empty or comparison.dropna(how='all', subset=list(PONDEROSA_SENSOR_NAMES)).empty:
                st.info(f"No hay datos suficientes para graficar {_format_variable_display_title(PONDEROSA_COMPARISON_VARIABLES[variable_name]['title'])}.")
                continue
            _plotly_chart(_make_ponderosa_comparison_chart(comparison, variable_name, selected_range, comparison_resolution))
            difference_chart = _make_ponderosa_difference_chart(comparison, variable_name, selected_range, comparison_resolution)
            if difference_chart is not None:
                _plotly_chart(difference_chart)

    with tab_stats:
        selected_variable_stats = st.segmented_control(
            "Variable para resumen:",
            options=compared_variables,
            format_func=lambda value: _format_variable_display_title(PONDEROSA_COMPARISON_VARIABLES[value]['title']),
            key="ponderosa_ecowitt_stats_variable",
            width="stretch"
        )
        comparison_stats = (
            _build_point_comparison(filtered_df, selected_variable_stats, PONDEROSA_SENSOR_NAMES)
            if point_mode else
            _build_wiga_anchor_nearest_comparison(
                filtered_df,
                selected_variable_stats,
                PONDEROSA_SENSOR_NAMES,
                selected_range,
                _build_ponderosa_hourly_series
            )
            if nearest_wiga_mode else
            _build_ponderosa_hourly_comparison(filtered_df, selected_variable_stats, selected_range)
        )
        overlap = comparison_stats.dropna(subset=list(PONDEROSA_SENSOR_NAMES)).copy()
        _render_ponderosa_comparison_metric_cards(overlap, selected_variable_stats)
        scatter_chart = _make_ponderosa_scatter_chart(comparison_stats, selected_variable_stats)
        if scatter_chart is not None:
            _render_chart_explanation(
                'Dispersión entre sensores',
                'Cada punto cruza una lectura simultánea de WIGA y ECOWITT. Mientras más cerca esté de la línea diagonal, más parecidos fueron ambos sensores.',
                accent=PONDEROSA_COMPARISON_VARIABLES[selected_variable_stats]['colors']['WIGA']
            )
            _plotly_chart(scatter_chart)

    with tab_tables:
        _render_difference_table_30min(
            filtered_df,
            compared_variables,
            PONDEROSA_SENSOR_NAMES,
            selected_range,
            comparison_resolution,
            _build_ponderosa_hourly_comparison,
            _build_ponderosa_hourly_series,
            PONDEROSA_COMPARISON_VARIABLES,
            "mostrar_ponderosa_tabla_diferencias_30min"
        )

    with tab_detail:
        if st.checkbox(
            "Mostrar gráficas individuales WIGA / ECOWITT",
            key="mostrar_ponderosa_ecowitt_detalles",
            help="Activa esta sección para ver cada variable por separado debajo de la comparativa principal."
        ):
            _render_ponderosa_source_individual_charts(
                filtered_df,
                selected_range,
                compared_variables,
                PONDEROSA_SENSOR_NAMES,
                "Variables individuales WIGA / ECOWITT Ponderosa",
                "Estas gráficas separan cada variable compartida por sensor para revisar la forma de cada lectura sin la superposición de la comparativa.",
                comparison_resolution
            )

        if st.checkbox(
            "Cargar registros consolidados de Ponderosa",
            key="mostrar_ponderosa_ecowitt_registros",
            help=FILTER_HELP_TEXTS['registros']
        ):
            _dataframe(filtered_df.drop(columns=['Fecha_Filtro'], errors='ignore'), hide_index=True)
            summary_rows = []
            for source_name, source_df in source_frames.items():
                current = source_df[source_df['Fecha_Filtro'].between(*selected_range)] if not source_df.empty else pd.DataFrame()
                summary_rows.append({
                    'Equipo': source_name,
                    'Registros': len(current),
                    'Inicio': current['FechaHora'].min().strftime('%Y-%m-%d %H:%M') if not current.empty else '-',
                    'Fin': current['FechaHora'].max().strftime('%Y-%m-%d %H:%M') if not current.empty else '-',
                })
            _dataframe(pd.DataFrame(summary_rows), hide_index=True)

    st.stop()

    for variable_name in compared_variables:
        comparison = (
            _build_point_comparison(filtered_df, variable_name, PONDEROSA_SENSOR_NAMES)
            if point_mode else
            _build_wiga_anchor_nearest_comparison(
                filtered_df,
                variable_name,
                PONDEROSA_SENSOR_NAMES,
                selected_range,
                _build_ponderosa_hourly_series
            )
            if nearest_wiga_mode else
            _build_ponderosa_hourly_comparison(filtered_df, variable_name, selected_range)
        )
        if comparison.empty or comparison.dropna(how='all', subset=list(PONDEROSA_SENSOR_NAMES)).empty:
            st.info(f"No hay datos suficientes para graficar {_format_variable_display_title(PONDEROSA_COMPARISON_VARIABLES[variable_name]['title'])}.")
            continue
        _plotly_chart(_make_ponderosa_comparison_chart(comparison, variable_name, selected_range, comparison_resolution))
        difference_chart = _make_ponderosa_difference_chart(comparison, variable_name, selected_range, comparison_resolution)
        if difference_chart is not None:
            _plotly_chart(difference_chart)

    _render_difference_table_30min(
        filtered_df,
        compared_variables,
        PONDEROSA_SENSOR_NAMES,
        selected_range,
        comparison_resolution,
        _build_ponderosa_hourly_comparison,
        _build_ponderosa_hourly_series,
        PONDEROSA_COMPARISON_VARIABLES,
        "mostrar_ponderosa_tabla_diferencias_30min"
    )

    show_details = st.checkbox(
        "Mostrar gráficas individuales WIGA / ECOWITT",
        key="mostrar_ponderosa_ecowitt_detalles",
        help="Activa esta sección para ver cada variable por separado debajo de la comparativa principal."
    )
    if show_details:
        _render_ponderosa_source_individual_charts(
            filtered_df,
            selected_range,
            compared_variables,
            PONDEROSA_SENSOR_NAMES,
            "Variables individuales WIGA / ECOWITT Ponderosa",
            "Estas gráficas separan cada variable compartida por sensor para revisar la forma de cada lectura sin la superposición de la comparativa.",
            comparison_resolution
        )

    if st.checkbox(
        "Cargar registros consolidados de Ponderosa",
        key="mostrar_ponderosa_ecowitt_registros",
        help=FILTER_HELP_TEXTS['registros']
    ):
        _dataframe(filtered_df.drop(columns=['Fecha_Filtro'], errors='ignore'), hide_index=True)
        summary_rows = []
        for source_name, source_df in source_frames.items():
            current = source_df[source_df['Fecha_Filtro'].between(*selected_range)] if not source_df.empty else pd.DataFrame()
            summary_rows.append({
                'Equipo': source_name,
                'Registros': len(current),
                'Inicio': current['FechaHora'].min().strftime('%Y-%m-%d %H:%M') if not current.empty else '-',
                'Fin': current['FechaHora'].max().strftime('%Y-%m-%d %H:%M') if not current.empty else '-',
            })
        _dataframe(pd.DataFrame(summary_rows), hide_index=True)

    st.stop()
    point_mode = comparison_resolution == COMPARISON_RESOLUTION_OPTIONS[1]
    nearest_wiga_mode = comparison_resolution == COMPARISON_RESOLUTION_OPTIONS[2]
    comparison = (
        _build_point_comparison(filtered_df, selected_variable, PONDEROSA_SENSOR_NAMES)
        if point_mode else
        _build_wiga_anchor_nearest_comparison(
            filtered_df,
            selected_variable,
            PONDEROSA_SENSOR_NAMES,
            selected_range,
            _build_ponderosa_hourly_series
        )
        if nearest_wiga_mode else
        _build_ponderosa_hourly_comparison(filtered_df, selected_variable, selected_range)
    )
    overlap = comparison.dropna(subset=list(PONDEROSA_SENSOR_NAMES)).copy()

    _render_chart_explanation(
        'Comparación directa WIGA vs ECOWITT',
        (
            'Aquí se superponen las lecturas punto por punto. Cada punto WIGA se compara con la lectura ECOWITT más cercana en el tiempo para revisar la relación real entre sensores.'
            if point_mode else
            'Aquí WIGA conserva sus franjas de 30 minutos y ECOWITT toma el registro más cercano a cada hora WIGA. Es útil cuando quieres que el eje del día siga el reloj de WIGA sin promediar ECOWITT.'
            if nearest_wiga_mode else
            'Aquí se superponen ambos sensores para la variable elegida. Si las líneas viajan cerca, las lecturas son similares; si se separan, hay diferencia entre equipos en esa franja.'
        ),
        accent=PONDEROSA_COMPARISON_VARIABLES[selected_variable]['accent']
    )
    _plotly_chart(_make_ponderosa_comparison_chart(comparison, selected_variable, selected_range, comparison_resolution))
    _render_ponderosa_comparison_metric_cards(overlap, selected_variable)
    _render_difference_table_30min(
        filtered_df,
        list(PONDEROSA_COMPARISON_VARIABLES.keys()),
        PONDEROSA_SENSOR_NAMES,
        selected_range,
        comparison_resolution,
        _build_ponderosa_hourly_comparison,
        _build_ponderosa_hourly_series,
        PONDEROSA_COMPARISON_VARIABLES,
        "mostrar_ponderosa_tabla_diferencias_30min"
    )

    difference_chart = _make_ponderosa_difference_chart(comparison, selected_variable, selected_range, comparison_resolution)
    if difference_chart is not None:
        _render_chart_explanation(
            'Diferencia WIGA - ECOWITT',
            'Valores sobre cero significan que WIGA midió más alto; valores bajo cero significan que ECOWITT midió más alto.',
            accent=PONDEROSA_COMPARISON_VARIABLES[selected_variable]['colors']['ECOWITT']
        )
        _plotly_chart(difference_chart)

    scatter_chart = _make_ponderosa_scatter_chart(comparison, selected_variable)
    if scatter_chart is not None:
        _render_chart_explanation(
            'Dispersión entre sensores',
            'Cada punto cruza una lectura simultánea de WIGA y ECOWITT. Mientras más cerca esté de la línea diagonal, más parecidos fueron ambos sensores.',
            accent=PONDEROSA_COMPARISON_VARIABLES[selected_variable]['colors']['WIGA']
        )
        _plotly_chart(scatter_chart)
    else:
        st.info("No hay suficientes datos simultáneos entre WIGA y ECOWITT para construir la dispersión.")

    if show_details:
        _render_ponderosa_source_individual_charts(
            filtered_df,
            selected_range,
            list(PONDEROSA_COMPARISON_VARIABLES.keys()),
            PONDEROSA_SENSOR_NAMES,
            "Variables individuales WIGA / ECOWITT Ponderosa",
            "Estas gráficas separan cada variable compartida por sensor para revisar la forma de cada lectura sin la superposición de la comparativa.",
            comparison_resolution
        )

    if st.checkbox(
        "Cargar registros consolidados de Ponderosa",
        key="mostrar_ponderosa_ecowitt_registros",
        help=FILTER_HELP_TEXTS['registros']
    ):
        _dataframe(filtered_df.drop(columns=['Fecha_Filtro'], errors='ignore'), hide_index=True)
        summary_rows = []
        for source_name, source_df in source_frames.items():
            current = source_df[source_df['Fecha_Filtro'].between(*selected_range)] if not source_df.empty else pd.DataFrame()
            summary_rows.append({
                'Equipo': source_name,
                'Registros': len(current),
                'Inicio': current['FechaHora'].min().strftime('%Y-%m-%d %H:%M') if not current.empty else '-',
                'Fin': current['FechaHora'].max().strftime('%Y-%m-%d %H:%M') if not current.empty else '-',
            })
        _dataframe(pd.DataFrame(summary_rows), hide_index=True)

    st.stop()


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


def _resolve_plot_resample_rule(total_days, total_points):
    if total_points <= 1200 and total_days <= 3:
        return None
    if total_points <= 2500 and total_days <= 7:
        return None
    if total_days <= 7:
        return '30min'
    if total_days <= 21:
        return '1h'
    if total_days <= 60:
        return '3h'
    return '6h'


def _prepare_sensor_series_for_plot(serie, value_col, multi_day_view=False):
    if serie.empty or 'DateTime' not in serie.columns or value_col not in serie.columns:
        return serie, None

    working = (
        serie[['DateTime', value_col]]
        .dropna(subset=['DateTime', value_col])
        .sort_values('DateTime')
        .copy()
    )
    if working.empty:
        return working, None

    if not multi_day_view:
        return working, None

    total_points = len(working)
    min_dt = pd.Timestamp(working['DateTime'].min())
    max_dt = pd.Timestamp(working['DateTime'].max())
    total_days = max(((max_dt - min_dt).total_seconds() / 86400.0) + 1, 1)
    resample_rule = _resolve_plot_resample_rule(total_days, total_points)

    if not resample_rule:
        return _add_day_breaks_to_series(working, value_col), None

    try:
        resampled = (
            working.set_index('DateTime')[[value_col]]
            .resample(resample_rule)
            .mean()
            .dropna()
            .reset_index()
        )
    except ValueError:
        return _add_day_breaks_to_series(working, value_col), None
    if resampled.empty:
        return _add_day_breaks_to_series(working, value_col), None

    return _add_day_breaks_to_series(resampled, value_col), {
        'rule': resample_rule,
        'original_points': total_points,
        'display_points': len(resampled)
    }


@st.cache_data
def cargar_cortinas(ruta_bytes, cache_version=DATA_CACHE_VERSION):
    _ = cache_version
    if not ruta_bytes:
        return pd.DataFrame()

    try:
        xls = pd.ExcelFile(io.BytesIO(ruta_bytes), engine="openpyxl")
        registros = []

        for sheet in [s for s in xls.sheet_names if s.lower() != 'plantilla']:
            raw = xls.parse(sheet_name=sheet, header=None)
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
            data['Fecha'] = _parse_date_series(data['Fecha']).dt.date
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


@st.cache_data(show_spinner="Cargando dashboard y preparando datos...")
def cargar_dashboard_completo(cache_version=DATA_CACHE_VERSION):
    _ = cache_version
    archivo_variables_bytes = descargar_desde_github(URL_VARIABLES_FALLBACKS)
    archivo_cortinas_bytes = descargar_desde_github(URL_CORTINAS)

    if archivo_variables_bytes is None:
        archivo_variables_bytes = _read_first_local_file_bytes(LOCAL_VARIABLES_PATHS)
    if archivo_cortinas_bytes is None:
        archivo_cortinas_bytes = _read_first_local_file_bytes(LOCAL_CORTINAS_PATHS)

    df_variables = (
        cargar_datos(archivo_variables_bytes, cache_version=cache_version)
        if archivo_variables_bytes else
        pd.DataFrame()
    )
    df_cortinas = (
        cargar_cortinas(archivo_cortinas_bytes, cache_version=cache_version)
        if archivo_cortinas_bytes else
        pd.DataFrame()
    )
    return df_variables, df_cortinas


def _find_excel_row_by_first_value(raw_df, expected_value, start_idx=0):
    expected_text = str(expected_value).strip()
    expected_key = _build_normalized_text_key(expected_text)
    for row_idx in range(start_idx, len(raw_df)):
        first_value = raw_df.iloc[row_idx, 0] if raw_df.shape[1] else None
        first_text = str(first_value).strip()
        if first_text == expected_text or _build_normalized_text_key(first_text) == expected_key:
            return row_idx
    return None


def _extract_excel_table(raw_df, header_row_idx):
    if header_row_idx is None:
        return pd.DataFrame()

    headers = []
    for col_idx, value in enumerate(raw_df.iloc[header_row_idx].tolist()):
        text = str(value).strip() if pd.notna(value) else ""
        headers.append(text if text else f"column_{col_idx}")

    records = []
    for row_idx in range(header_row_idx + 1, len(raw_df)):
        row_values = raw_df.iloc[row_idx].tolist()
        if pd.isna(pd.Series(row_values)).all():
            break
        first_value = row_values[0] if row_values else None
        if str(first_value).strip() == "":
            break
        records.append(row_values)

    if not records:
        return pd.DataFrame(columns=headers)

    table = pd.DataFrame(records, columns=headers)
    keep_columns = [
        column_name
        for column_name in table.columns
        if not (
            str(column_name).startswith("column_")
            and table[column_name].isna().all()
        )
    ]
    return table[keep_columns].reset_index(drop=True)


def _build_greenhouse_interpretation_table(raw_df, start_row_idx):
    if start_row_idx is None:
        return pd.DataFrame(columns=["Indicador", "Interpretacion"])

    records = []
    has_started = False
    for row_idx in range(start_row_idx + 1, len(raw_df)):
        row_values = raw_df.iloc[row_idx].tolist()
        if pd.isna(pd.Series(row_values)).all():
            if has_started:
                break
            continue
        indicator = str(row_values[0]).strip() if row_values else ""
        interpretation = str(row_values[1]).strip() if len(row_values) > 1 and pd.notna(row_values[1]) else ""
        if not indicator:
            continue
        has_started = True
        records.append({
            "Indicador": indicator,
            "Interpretacion": interpretation
        })

    return pd.DataFrame(records)


def _build_greenhouse_guide_table(raw_df, start_row_idx):
    if start_row_idx is None:
        return pd.DataFrame(columns=["Concepto", "Descripcion"])

    records = []
    for row_idx in range(start_row_idx + 1, len(raw_df)):
        row_values = raw_df.iloc[row_idx].tolist()
        if pd.isna(pd.Series(row_values)).all():
            break
        concept = str(row_values[0]).strip() if row_values else ""
        description = str(row_values[1]).strip() if len(row_values) > 1 and pd.notna(row_values[1]) else ""
        if not concept:
            continue
        records.append({
            "Concepto": concept,
            "Descripcion": description
        })
    return pd.DataFrame(records)


def _extract_sparse_excel_table(raw_df, header_row_idx):
    if header_row_idx is None:
        return pd.DataFrame()

    header_row = raw_df.iloc[header_row_idx].tolist()
    header_positions = [
        (col_idx, str(value).strip())
        for col_idx, value in enumerate(header_row)
        if pd.notna(value) and str(value).strip()
    ]
    if not header_positions:
        return pd.DataFrame()

    records = []
    for row_idx in range(header_row_idx + 1, len(raw_df)):
        row_values = raw_df.iloc[row_idx].tolist()
        if pd.isna(pd.Series(row_values)).all():
            break
        first_value = row_values[header_positions[0][0]]
        if pd.isna(first_value) or str(first_value).strip() == "":
            break
        records.append({
            header_name: row_values[col_idx]
            for col_idx, header_name in header_positions
        })

    return pd.DataFrame(records)


def _find_sparse_header_row(raw_df, start_row_idx, required_text):
    if start_row_idx is None:
        return None

    required_key = _build_normalized_text_key(required_text)
    for row_idx in range(start_row_idx + 1, len(raw_df)):
        row_values = raw_df.iloc[row_idx].tolist()
        if pd.isna(pd.Series(row_values)).all():
            continue
        row_key = " ".join(
            _build_normalized_text_key(value)
            for value in row_values
            if pd.notna(value)
        )
        if str(row_values[0]).strip() == "Bloque" and required_key in row_key:
            return row_idx
    return None


def _format_analysis_block_table(df):
    if df.empty:
        return df

    formatted = df.copy()
    percent_columns = [
        column_name
        for column_name in formatted.columns
        if "%" in str(column_name)
    ]
    for column_name in percent_columns:
        formatted[column_name] = formatted[column_name].apply(
            lambda value: f"{float(value):.1%}" if pd.notna(value) else "—"
        )
    return formatted


def _format_single_block_detail_table(df):
    if df.empty:
        return pd.DataFrame(columns=["Campo", "Valor"])

    row = df.iloc[0]
    detail_rows = []
    for column_name, value in row.items():
        if pd.isna(value):
            continue
        numeric_value = _safe_float(value) if not isinstance(value, str) else None
        if numeric_value is not None:
            value_text = f"{numeric_value:,.2f}".rstrip("0").rstrip(".")
        else:
            value_text = str(value)
        detail_rows.append({
            "Campo": column_name,
            "Valor": value_text
        })
    return pd.DataFrame(detail_rows)


GREENHOUSE_COLORS = {
    "real": "#3DBB76",
    "gap": "#E7C87A",
    "theoretical": "#6FA8FF",
    "allowed": "#F2A04B",
    "frontal": "#545386",
    "lateral": "#6FBFD6",
    "culatas": "#D77A94",
    "muted": "#D8D2C4",
}


def _safe_float(value):
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_greenhouse_value(value, decimals=1, suffix=""):
    numeric_value = _safe_float(value)
    if numeric_value is None:
        return "Sin datos"
    if decimals == 0:
        formatted_value = f"{numeric_value:,.0f}"
    else:
        formatted_value = f"{numeric_value:,.{decimals}f}"
    return f"{formatted_value}{suffix}"


def _format_greenhouse_percent(value):
    numeric_value = _safe_float(value)
    return f"{numeric_value:.1%}" if numeric_value is not None else "Sin datos"


def _clean_greenhouse_text(value, fallback=""):
    if value is None or pd.isna(value):
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _render_greenhouse_styles():
    st.markdown(
        """
        <style>
        .greenhouse-hero {
            position: relative;
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 1rem;
            align-items: center;
            margin: 0.1rem 0 1.15rem 0;
            padding: 1.18rem 1.25rem;
            border-radius: 8px;
            border: 1px solid rgba(84, 83, 134, 0.18);
            background:
                linear-gradient(120deg, rgba(84,83,134,0.98) 0%, rgba(62,68,98,0.96) 58%, rgba(61,187,118,0.88) 100%);
            box-shadow: 0 18px 42px rgba(38, 43, 59, 0.16);
            overflow: hidden;
        }
        .greenhouse-hero::after {
            content: '';
            position: absolute;
            inset: auto -42px -68px auto;
            width: 210px;
            height: 210px;
            border-radius: 50%;
            border: 34px solid rgba(255,255,255,0.10);
            pointer-events: none;
        }
        .greenhouse-kicker {
            margin: 0 0 0.35rem 0;
            color: rgba(255,255,255,0.72);
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }
        .greenhouse-hero .greenhouse-title {
            margin: 0;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            font-size: 1.72rem;
            line-height: 1.1;
            font-weight: 900;
            letter-spacing: 0;
            text-shadow: 0 2px 12px rgba(0,0,0,0.28);
        }
        .greenhouse-subtitle {
            max-width: 48rem;
            margin: 0.58rem 0 0 0;
            color: rgba(255,255,255,0.82);
            font-size: 0.96rem;
            line-height: 1.55;
        }
        .greenhouse-hero-badge {
            position: relative;
            z-index: 1;
            min-width: 138px;
            padding: 0.86rem 0.95rem;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.22);
            background: rgba(255,255,255,0.13);
            text-align: center;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.18);
        }
        .greenhouse-hero-badge-label {
            display: block;
            color: rgba(255,255,255,0.72);
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.10em;
            text-transform: uppercase;
        }
        .greenhouse-hero-badge-value {
            display: block;
            margin-top: 0.24rem;
            color: #ffffff;
            font-size: 1.38rem;
            font-weight: 900;
            line-height: 1;
        }
        .greenhouse-section-title {
            margin: 1.05rem 0 0.55rem 0;
            color: var(--elite-graphite);
            font-size: 1.02rem;
            font-weight: 900;
            letter-spacing: 0;
        }
        .greenhouse-flow-grid {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 0.72rem;
            margin: 0.62rem 0 1.05rem 0;
        }
        .greenhouse-flow-card {
            position: relative;
            min-height: 138px;
            padding: 0.92rem 0.86rem 0.84rem 0.9rem;
            border-radius: 8px;
            border: 1px solid rgba(84,83,134,0.12);
            background:
                radial-gradient(circle at 92% 10%, rgba(255,255,255,0.95), transparent 32%),
                linear-gradient(180deg, rgba(255,255,255,0.96), rgba(247,244,238,0.88));
            box-shadow: 0 12px 26px rgba(56,58,53,0.075);
            overflow: hidden;
        }
        .greenhouse-flow-card::before {
            content: '';
            position: absolute;
            inset: 0 0 auto 0;
            height: 5px;
            background: var(--greenhouse-accent);
        }
        .greenhouse-flow-step {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.86rem;
            height: 1.86rem;
            border-radius: 8px;
            background: color-mix(in srgb, var(--greenhouse-accent) 18%, #ffffff 82%);
            color: var(--elite-graphite);
            font-size: 0.74rem;
            font-weight: 900;
            letter-spacing: 0.04em;
        }
        .greenhouse-flow-title {
            display: block;
            margin-top: 0.58rem;
            color: var(--elite-graphite);
            font-size: 0.86rem;
            font-weight: 900;
            line-height: 1.18;
            text-transform: uppercase;
            letter-spacing: 0.035em;
        }
        .greenhouse-flow-copy {
            display: block;
            margin-top: 0.42rem;
            color: rgba(56,58,53,0.72);
            font-size: 0.79rem;
            line-height: 1.42;
        }
        .greenhouse-divider-note {
            margin: 0.2rem 0 0.9rem 0;
            padding: 0.78rem 0.92rem;
            border-radius: 8px;
            border: 1px dashed rgba(84,83,134,0.22);
            background: rgba(255,255,255,0.64);
            color: rgba(56,58,53,0.74);
            font-size: 0.86rem;
            line-height: 1.48;
        }
        .greenhouse-metric-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.72rem;
            margin: 0.4rem 0 0.85rem 0;
        }
        .greenhouse-metric-card {
            position: relative;
            min-height: 112px;
            padding: 0.92rem 0.92rem 0.82rem 0.92rem;
            border-radius: 8px;
            border: 1px solid rgba(84, 83, 134, 0.12);
            background: linear-gradient(180deg, #ffffff 0%, rgba(255,255,255,0.88) 100%);
            box-shadow: 0 12px 28px rgba(56,58,53,0.08);
            overflow: hidden;
        }
        .greenhouse-metric-card::before {
            content: '';
            position: absolute;
            inset: 0 0 auto 0;
            height: 5px;
            background: var(--greenhouse-accent);
        }
        .greenhouse-metric-card-label {
            display: block;
            color: rgba(56,58,53,0.66);
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }
        .greenhouse-metric-card-value {
            display: block;
            margin-top: 0.48rem;
            color: var(--elite-graphite);
            font-size: 1.42rem;
            font-weight: 900;
            line-height: 1.05;
            overflow-wrap: anywhere;
        }
        .greenhouse-metric-card-note {
            display: block;
            margin-top: 0.42rem;
            color: rgba(56,58,53,0.62);
            font-size: 0.78rem;
            line-height: 1.35;
        }
        .greenhouse-insight-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.7rem;
            margin: 0.4rem 0 1rem 0;
        }
        .greenhouse-insight-card {
            padding: 0.9rem 0.95rem;
            border-radius: 8px;
            border: 1px solid rgba(84,83,134,0.12);
            background: linear-gradient(180deg, rgba(255,255,255,0.94), rgba(247,244,238,0.82));
            box-shadow: 0 10px 24px rgba(56,58,53,0.07);
            color: var(--elite-ink);
            font-size: 0.9rem;
            line-height: 1.48;
        }
        .greenhouse-insight-card strong {
            color: var(--elite-hero);
        }
        .greenhouse-reading-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.85rem;
            margin: 0.45rem 0 1rem 0;
        }
        .greenhouse-reading-card {
            position: relative;
            min-height: 118px;
            padding: 1rem 1rem 0.95rem 1.05rem;
            border-radius: 8px;
            border: 1px solid rgba(84,83,134,0.12);
            background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(247,244,238,0.86));
            box-shadow: 0 12px 28px rgba(56,58,53,0.08);
            overflow: hidden;
        }
        .greenhouse-reading-card::before {
            content: '';
            position: absolute;
            inset: 0 auto 0 0;
            width: 5px;
            background: linear-gradient(180deg, var(--elite-hero), rgba(61,187,118,0.78));
        }
        .greenhouse-reading-card-title {
            display: block;
            color: var(--elite-hero);
            font-size: 0.82rem;
            font-weight: 900;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }
        .greenhouse-reading-card-body {
            display: block;
            margin-top: 0.48rem;
            color: var(--elite-ink);
            font-size: 0.92rem;
            line-height: 1.48;
        }
        .greenhouse-dictionary-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.82rem;
            margin: 0.65rem 0 1rem 0;
        }
        .greenhouse-dictionary-card {
            padding: 0.95rem 1rem;
            border-radius: 8px;
            border: 1px solid rgba(84,83,134,0.12);
            background: rgba(255,255,255,0.94);
            box-shadow: 0 10px 22px rgba(56,58,53,0.07);
        }
        .greenhouse-dictionary-card-top {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 0.75rem;
            margin-bottom: 0.52rem;
        }
        .greenhouse-dictionary-term {
            color: var(--elite-graphite);
            font-size: 0.96rem;
            font-weight: 900;
            line-height: 1.22;
        }
        .greenhouse-dictionary-unit {
            flex: 0 0 auto;
            padding: 0.2rem 0.46rem;
            border-radius: 8px;
            background: rgba(84,83,134,0.10);
            color: var(--elite-hero);
            font-size: 0.74rem;
            font-weight: 900;
            white-space: nowrap;
        }
        .greenhouse-dictionary-text {
            margin: 0.42rem 0 0 0;
            color: var(--elite-ink);
            font-size: 0.86rem;
            line-height: 1.45;
        }
        .greenhouse-dictionary-source {
            display: inline-flex;
            margin-top: 0.62rem;
            padding: 0.22rem 0.52rem;
            border-radius: 8px;
            background: rgba(61,187,118,0.10);
            color: #2f7652;
            font-size: 0.74rem;
            font-weight: 800;
        }
        @media (max-width: 900px) {
            .greenhouse-hero {
                grid-template-columns: 1fr;
            }
            .greenhouse-hero-badge {
                max-width: 220px;
            }
            .greenhouse-flow-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .greenhouse-metric-grid,
            .greenhouse-insight-grid,
            .greenhouse-reading-grid,
            .greenhouse-dictionary-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 640px) {
            .greenhouse-flow-grid,
            .greenhouse-metric-grid,
            .greenhouse-insight-grid,
            .greenhouse-reading-grid,
            .greenhouse-dictionary-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True
    )


def _render_greenhouse_hero(selected_block_label, selected_summary_df):
    efficiency_text = "Sin datos"
    if not selected_summary_df.empty:
        efficiency_text = _format_greenhouse_percent(selected_summary_df.iloc[0].get("% Real / Máx. Perm."))

    st.markdown(
        f"""
        <div class="greenhouse-hero">
            <div>
                <p class="greenhouse-kicker">Contexto técnico de ventilación</p>
                <h2 class="greenhouse-title">{html.escape(selected_block_label)}</h2>
                <p class="greenhouse-subtitle">
                    Lectura ejecutiva de geometría, capacidad instalada, apertura real y brechas operativas para conectar el comportamiento ambiental con la estructura del invernadero.
                </p>
            </div>
            <div class="greenhouse-hero-badge">
                <span class="greenhouse-hero-badge-label">Uso del máximo</span>
                <span class="greenhouse-hero-badge-value">{html.escape(efficiency_text)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def _render_greenhouse_metric_grid(title, metrics):
    card_html = []
    for metric in metrics:
        card_html.append(
            (
                f'<div class="greenhouse-metric-card" style="--greenhouse-accent: {metric["accent"]};">'
                f'<span class="greenhouse-metric-card-label">{html.escape(metric["label"])}</span>'
                f'<span class="greenhouse-metric-card-value">{html.escape(metric["value"])}</span>'
                f'<span class="greenhouse-metric-card-note">{html.escape(metric["note"])}</span>'
                '</div>'
            )
        )

    st.markdown(
        f"""
        <div class="greenhouse-section-title">{html.escape(title)}</div>
        <div class="greenhouse-metric-grid">{''.join(card_html)}</div>
        """,
        unsafe_allow_html=True
    )


def _render_greenhouse_flow_cards(title, cards):
    if not cards:
        return

    card_html = []
    for idx, card in enumerate(cards, start=1):
        accent = card.get("accent", BRAND_COLORS["hero"])
        card_html.append(
            (
                f'<div class="greenhouse-flow-card" style="--greenhouse-accent: {accent};">'
                f'<span class="greenhouse-flow-step">{idx:02d}</span>'
                f'<span class="greenhouse-flow-title">{html.escape(card.get("title", ""))}</span>'
                f'<span class="greenhouse-flow-copy">{html.escape(card.get("body", ""))}</span>'
                '</div>'
            )
        )

    st.markdown(
        f"""
        <div class="greenhouse-section-title">{html.escape(title)}</div>
        <div class="greenhouse-flow-grid">{''.join(card_html)}</div>
        """,
        unsafe_allow_html=True
    )


def _render_greenhouse_insight_cards(insights):
    if not insights:
        return

    rows = [
        f'<div class="greenhouse-insight-card"><strong>{idx}.</strong> {html.escape(insight)}</div>'
        for idx, insight in enumerate(insights, start=1)
    ]
    st.markdown(
        f"""
        <div class="greenhouse-section-title">Lectura rápida</div>
        <div class="greenhouse-insight-grid">{''.join(rows)}</div>
        """,
        unsafe_allow_html=True
    )


def _render_greenhouse_reading_cards(title, reading_df, title_col="Indicador", body_col="Interpretacion"):
    if reading_df.empty:
        return

    rows = []
    for _, reading_row in reading_df.iterrows():
        row_title = _clean_greenhouse_text(reading_row.get(title_col, ""))
        row_body = _clean_greenhouse_text(reading_row.get(body_col, ""))
        if not row_title and not row_body:
            continue
        rows.append(
            (
                '<div class="greenhouse-reading-card">'
                f'<span class="greenhouse-reading-card-title">{html.escape(row_title)}</span>'
                f'<span class="greenhouse-reading-card-body">{html.escape(row_body)}</span>'
                '</div>'
            )
        )

    if not rows:
        return

    st.markdown(
        f"""
        <div class="greenhouse-section-title">{html.escape(title)}</div>
        <div class="greenhouse-reading-grid">{''.join(rows)}</div>
        """,
        unsafe_allow_html=True
    )


def _render_greenhouse_dictionary_cards(dictionary_df):
    if dictionary_df.empty:
        st.info("No hay diccionario de variables disponible en el archivo.")
        return

    rows = []
    for _, dictionary_row in dictionary_df.iterrows():
        variable_name = _clean_greenhouse_text(dictionary_row.get("Variable / columna", ""))
        meaning = _clean_greenhouse_text(dictionary_row.get("Qué significa", ""))
        unit = _clean_greenhouse_text(dictionary_row.get("Unidad", ""))
        interpretation = _clean_greenhouse_text(dictionary_row.get("Cómo se interpreta", ""))
        source = _clean_greenhouse_text(dictionary_row.get("Dónde aparece", ""))
        if not variable_name:
            continue
        unit_html = html.escape(unit or "Referencia")
        rows.append(
            (
                '<div class="greenhouse-dictionary-card">'
                '<div class="greenhouse-dictionary-card-top">'
                f'<span class="greenhouse-dictionary-term">{html.escape(variable_name)}</span>'
                f'<span class="greenhouse-dictionary-unit">{unit_html}</span>'
                '</div>'
                f'<p class="greenhouse-dictionary-text">{html.escape(meaning)}</p>'
                f'<p class="greenhouse-dictionary-text"><strong>Lectura:</strong> {html.escape(interpretation)}</p>'
                f'<span class="greenhouse-dictionary-source">{html.escape(source)}</span>'
                '</div>'
            )
        )

    if rows:
        st.markdown(
            f'<div class="greenhouse-dictionary-grid">{"".join(rows)}</div>',
            unsafe_allow_html=True
        )


def _greenhouse_chart_config(file_stem):
    return {
        "displayModeBar": True,
        "displaylogo": False,
        "responsive": True,
        "toImageButtonOptions": {
            "format": "png",
            "filename": file_stem,
            "height": 900,
            "width": 1400,
            "scale": 2,
        },
    }


def _render_greenhouse_chart_panel(fig, title, key, selected_block_label, large_height=680):
    if fig is None:
        return

    file_stem = _build_report_slug("ficha-tecnica", selected_block_label, key)
    chart_config = _greenhouse_chart_config(file_stem)
    _plotly_chart(fig, config=chart_config)


def _build_greenhouse_report_excel_bytes(analysis_data, diagnostic_df=None):
    output = io.BytesIO()
    sheet_definitions = [
        ("Datos generales", analysis_data.get("general", pd.DataFrame())),
        ("Apertura calculada", analysis_data.get("areas", pd.DataFrame())),
        ("Indicadores resumen", analysis_data.get("summary", pd.DataFrame())),
        ("Lectura técnica", analysis_data.get("interpretations", pd.DataFrame())),
        ("Guía rápida", analysis_data.get("guide", pd.DataFrame())),
        ("Gráficas totales", analysis_data.get("chart_totals", pd.DataFrame())),
        ("Gráficas porcentuales", analysis_data.get("chart_ratios", pd.DataFrame())),
        ("Diccionario", analysis_data.get("dictionary", pd.DataFrame())),
    ]
    if isinstance(diagnostic_df, pd.DataFrame) and not diagnostic_df.empty:
        sheet_definitions.append(("Cruce ambiental", diagnostic_df))

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        sheets_written = []
        for sheet_title, frame in sheet_definitions:
            if not isinstance(frame, pd.DataFrame) or frame.empty:
                continue
            sheet_name = _sanitize_excel_sheet_name(sheet_title, sheets_written)
            frame.to_excel(writer, index=False, sheet_name=sheet_name)
            sheets_written.append(sheet_name)

        if not sheets_written:
            fallback_name = _sanitize_excel_sheet_name("Sin datos", sheets_written)
            pd.DataFrame({"Mensaje": ["No hay datos disponibles para exportar."]}).to_excel(
                writer,
                index=False,
                sheet_name=fallback_name
            )

        workbook = writer.book
        try:
            from openpyxl.styles import Alignment, Font, PatternFill

            header_fill = PatternFill("solid", fgColor="545386")
            header_font = Font(color="FFFFFF", bold=True)
            header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        except Exception:
            header_fill = header_font = header_alignment = None

        for worksheet in workbook.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            if header_fill and header_font and header_alignment:
                for cell in worksheet[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = header_alignment

            for column_cells in worksheet.columns:
                column_letter = column_cells[0].column_letter
                max_length = 0
                for cell in column_cells:
                    value = cell.value
                    if value is None:
                        continue
                    max_length = max(max_length, len(str(value)))
                worksheet.column_dimensions[column_letter].width = min(max(max_length + 2, 12), 42)

    output.seek(0)
    return output.getvalue()


def _render_greenhouse_report_download(analysis_data, selected_block_label, diagnostic_df=None, key_suffix="base"):
    try:
        report_bytes = _build_greenhouse_report_excel_bytes(analysis_data, diagnostic_df=diagnostic_df)
    except Exception as error:
        st.info(f"No fue posible preparar el reporte descargable. Detalle: {error}")
        return

    file_name = f"{_build_report_slug('ficha-tecnica-invernaderos', selected_block_label, key_suffix)}.xlsx"
    st.download_button(
        "Descargar reporte técnico",
        data=report_bytes,
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"download_greenhouse_report_{key_suffix}",
        help="Descarga un Excel con las tablas estructurales, lectura técnica, diccionario y cruce ambiental si está disponible."
    )


def _get_greenhouse_diagnostic_dates(df_variables_all, variable_blocks, window_days=7):
    if (
        df_variables_all.empty or
        "Bloque" not in df_variables_all.columns or
        "Fecha_Filtro" not in df_variables_all.columns or
        not variable_blocks
    ):
        return None, None

    date_series = pd.to_datetime(
        df_variables_all.loc[df_variables_all["Bloque"].isin(variable_blocks), "Fecha_Filtro"],
        errors="coerce"
    ).dropna()
    if date_series.empty:
        return None, None

    end_date = date_series.max().date()
    start_date = end_date - timedelta(days=max(1, int(window_days)) - 1)
    return start_date, end_date


def _classify_greenhouse_diagnostic(row):
    usage = _safe_float(row.get("Uso máximo permitido (%)"))
    temperature = _safe_float(row.get("Temperatura"))
    gap = _safe_float(row.get("Brecha operativa (m²)"))

    if usage is None:
        return "Sin lectura suficiente para priorizar."
    if usage < 85 and temperature is not None and temperature >= 27:
        return "Prioridad alta: menor uso de capacidad con temperatura elevada."
    if usage < 85:
        return "Revisar apertura real y restricciones de cortinas."
    if gap is not None and gap >= 200:
        return "Buena eficiencia relativa, pero con brecha absoluta importante."
    if usage >= 90:
        return "Operación alineada con la capacidad máxima permitida."
    return "Condición intermedia: mantener seguimiento operativo."


def _build_greenhouse_environment_diagnostic(summary_df, df_variables_all, window_days=7):
    empty_meta = {
        "start_date": None,
        "end_date": None,
        "records": 0,
        "mapped_blocks": 0,
    }
    if summary_df.empty or df_variables_all.empty:
        return pd.DataFrame(), empty_meta
    if "Bloque" not in summary_df.columns or "Bloque" not in df_variables_all.columns:
        return pd.DataFrame(), empty_meta

    _, variable_map, _ = _get_block_options(df_variables_all, pd.DataFrame(), selected_finca="La Ponderosa")
    block_lookup = {}
    for block_name in summary_df["Bloque"].dropna().astype(str).tolist():
        block_identifier = _extract_block_identifier(block_name)
        variable_block = variable_map.get(block_identifier)
        if variable_block:
            block_lookup[block_name] = variable_block

    if not block_lookup:
        return pd.DataFrame(), empty_meta

    variable_blocks = list(block_lookup.values())
    start_date, end_date = _get_greenhouse_diagnostic_dates(df_variables_all, variable_blocks, window_days=window_days)
    if start_date is None or end_date is None:
        return pd.DataFrame(), {**empty_meta, "mapped_blocks": len(block_lookup)}

    filtered_df = _filter_variables_multi_block_range(
        df_variables_all,
        start_date,
        end_date,
        bloques=variable_blocks
    )
    sensor_columns = [
        column_name
        for column_name in SENSOR_VARIABLES
        if column_name in filtered_df.columns and filtered_df[column_name].notna().any()
    ]
    if filtered_df.empty or not sensor_columns:
        return pd.DataFrame(), {
            **empty_meta,
            "start_date": start_date,
            "end_date": end_date,
            "mapped_blocks": len(block_lookup),
        }

    aggregate_df = filtered_df.groupby("Bloque", as_index=False)[sensor_columns].mean()
    record_counts = filtered_df.groupby("Bloque").size().reset_index(name="Registros")
    aggregate_df = aggregate_df.merge(record_counts, on="Bloque", how="left")
    reverse_lookup = {variable_block: block_name for block_name, variable_block in block_lookup.items()}
    aggregate_df["Bloque"] = aggregate_df["Bloque"].map(reverse_lookup)
    aggregate_df = aggregate_df.dropna(subset=["Bloque"]).reset_index(drop=True)
    if aggregate_df.empty:
        return pd.DataFrame(), {
            **empty_meta,
            "start_date": start_date,
            "end_date": end_date,
            "mapped_blocks": len(block_lookup),
            "records": int(len(filtered_df)),
        }

    summary_columns = [
        "Bloque",
        "% Real / Teórica",
        "% Real / Máx. Perm.",
        "Brecha Máx-Real (m²)",
        "% Pérdida Operativa",
    ]
    available_summary_columns = [column_name for column_name in summary_columns if column_name in summary_df.columns]
    merged_df = aggregate_df.merge(summary_df[available_summary_columns], on="Bloque", how="left")
    rename_map = {
        "% Real / Teórica": "Uso potencial teórico (%)",
        "% Real / Máx. Perm.": "Uso máximo permitido (%)",
        "Brecha Máx-Real (m²)": "Brecha operativa (m²)",
        "% Pérdida Operativa": "Pérdida operativa (%)",
    }
    merged_df = merged_df.rename(columns=rename_map)
    for column_name in [
        "Uso potencial teórico (%)",
        "Uso máximo permitido (%)",
        "Pérdida operativa (%)",
    ]:
        if column_name in merged_df.columns:
            merged_df[column_name] = pd.to_numeric(merged_df[column_name], errors="coerce") * 100
    if "Brecha operativa (m²)" in merged_df.columns:
        merged_df["Brecha operativa (m²)"] = pd.to_numeric(merged_df["Brecha operativa (m²)"], errors="coerce")

    for column_name in sensor_columns:
        merged_df[column_name] = pd.to_numeric(merged_df[column_name], errors="coerce").round(2)
    merged_df["Lectura operativa"] = merged_df.apply(_classify_greenhouse_diagnostic, axis=1)

    ordered_columns = [
        "Bloque",
        "Registros",
        *sensor_columns,
        "Uso potencial teórico (%)",
        "Uso máximo permitido (%)",
        "Brecha operativa (m²)",
        "Pérdida operativa (%)",
        "Lectura operativa",
    ]
    ordered_columns = [column_name for column_name in ordered_columns if column_name in merged_df.columns]
    merged_df = merged_df[ordered_columns].sort_values("Bloque").reset_index(drop=True)

    return merged_df, {
        "start_date": start_date,
        "end_date": end_date,
        "records": int(len(filtered_df)),
        "mapped_blocks": len(block_lookup),
    }


def _build_greenhouse_environment_scatter(diagnostic_df, metric_column, selected_block_label):
    if diagnostic_df.empty or metric_column not in diagnostic_df.columns:
        return None
    required_columns = ["Bloque", "Uso máximo permitido (%)", "Brecha operativa (m²)"]
    if any(column_name not in diagnostic_df.columns for column_name in required_columns):
        return None

    working_df = diagnostic_df.copy()
    working_df["Uso máximo permitido (%)"] = pd.to_numeric(working_df["Uso máximo permitido (%)"], errors="coerce")
    working_df[metric_column] = pd.to_numeric(working_df[metric_column], errors="coerce")
    working_df["Brecha operativa (m²)"] = pd.to_numeric(working_df["Brecha operativa (m²)"], errors="coerce")
    working_df = working_df.dropna(subset=["Uso máximo permitido (%)", metric_column, "Brecha operativa (m²)"])
    if working_df.empty:
        return None

    gap_min = float(working_df["Brecha operativa (m²)"].min())
    gap_max = float(working_df["Brecha operativa (m²)"].max())
    gap_range = gap_max - gap_min if gap_max != gap_min else 1.0
    marker_sizes = [
        18 + ((float(value) - gap_min) / gap_range) * 30
        for value in working_df["Brecha operativa (m²)"]
    ]
    marker_symbols = [
        "diamond" if str(block_name) == str(selected_block_label) else "circle"
        for block_name in working_df["Bloque"]
    ]

    fig = go.Figure(go.Scatter(
        x=working_df["Uso máximo permitido (%)"],
        y=working_df[metric_column],
        text=working_df["Bloque"],
        customdata=working_df[["Brecha operativa (m²)", "Registros", "Lectura operativa"]],
        mode="markers+text",
        textposition="top center",
        marker=dict(
            size=marker_sizes,
            symbol=marker_symbols,
            color=working_df["Brecha operativa (m²)"],
            colorscale=[
                [0.0, GREENHOUSE_COLORS["real"]],
                [0.55, GREENHOUSE_COLORS["gap"]],
                [1.0, BRAND_COLORS["rose"]],
            ],
            colorbar=dict(title="Brecha m²"),
            line=dict(color="rgba(255,255,255,0.95)", width=2),
            opacity=0.92,
        ),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Uso máximo permitido: %{x:.1f}%<br>"
            f"{VARIABLE_SELECTOR_LABELS.get(metric_column, metric_column)}: "
            f"%{{y:.2f}} {VARIABLE_UNITS.get(metric_column, '')}<br>"
            "Brecha operativa: %{customdata[0]:,.1f} m²<br>"
            "Registros del periodo: %{customdata[1]:,.0f}<br>"
            "%{customdata[2]}<extra></extra>"
        ),
    ))
    fig.update_layout(
        template="plotly_white",
        title=f"Cruce ambiental vs capacidad instalada · {VARIABLE_SELECTOR_LABELS.get(metric_column, metric_column)}",
        xaxis_title="Uso del máximo permitido (%)",
        yaxis_title=VARIABLE_SELECTOR_LABELS.get(metric_column, metric_column),
        height=520,
        margin=dict(l=20, r=20, t=80, b=36),
    )
    fig.update_xaxes(range=[max(0, float(working_df["Uso máximo permitido (%)"].min()) - 5), 105])
    return fig


def _render_greenhouse_environment_tab(summary_df, analysis_data, selected_block_label):
    _render_chart_explanation(
        "Cruce ambiental",
        "Esta lectura conecta la ficha estructural de ventilación con los sensores del periodo más reciente. Sirve para priorizar bloques donde una brecha de apertura podría coincidir con temperatura, humedad, PAR o gramos de agua."
    )

    with _loading_context(True, "Cargando contexto ambiental reciente..."):
        df_variables_all, _ = cargar_dashboard_completo()

    diagnostic_df, diagnostic_meta = _build_greenhouse_environment_diagnostic(summary_df, df_variables_all)
    if diagnostic_df.empty:
        st.info("No se encontró información ambiental suficiente para cruzar con la ficha técnica.")
        return

    period_text = "Periodo no disponible"
    if diagnostic_meta.get("start_date") and diagnostic_meta.get("end_date"):
        period_text = (
            f"{diagnostic_meta['start_date'].strftime('%d/%m/%Y')} - "
            f"{diagnostic_meta['end_date'].strftime('%d/%m/%Y')}"
        )
    st.caption(
        f"Periodo analizado: {period_text}. "
        f"Registros usados: {diagnostic_meta.get('records', 0):,}. "
        f"Bloques conectados: {diagnostic_meta.get('mapped_blocks', 0)}."
    )

    available_metrics = [
        variable_name
        for variable_name in SENSOR_VARIABLES
        if variable_name in diagnostic_df.columns and diagnostic_df[variable_name].notna().any()
    ]
    if not available_metrics:
        st.info("Hay bloques conectados, pero no se detectaron variables ambientales numéricas para graficar.")
        return

    metric_choice = st.selectbox(
        "Variable ambiental para cruzar con capacidad:",
        options=available_metrics,
        format_func=lambda value: VARIABLE_SELECTOR_LABELS.get(value, value),
        key="greenhouse_environment_metric"
    )

    selected_env_df = diagnostic_df[diagnostic_df["Bloque"].astype(str) == str(selected_block_label)].reset_index(drop=True)
    if not selected_env_df.empty:
        selected_env_row = selected_env_df.iloc[0]
        _render_greenhouse_metric_grid(
            "Lectura ambiental del bloque seleccionado",
            [
                {
                    "label": VARIABLE_SELECTOR_LABELS.get(metric_choice, metric_choice),
                    "value": _format_greenhouse_value(
                        selected_env_row.get(metric_choice),
                        2,
                        f" {VARIABLE_UNITS.get(metric_choice, '')}".rstrip()
                    ),
                    "note": "Promedio del periodo reciente",
                    "accent": VARIABLE_COLORS.get(metric_choice, BRAND_COLORS["hero"]),
                },
                {
                    "label": "Uso máximo",
                    "value": _format_greenhouse_value(selected_env_row.get("Uso máximo permitido (%)"), 1, "%"),
                    "note": "Ventilación real frente al máximo permitido",
                    "accent": GREENHOUSE_COLORS["real"],
                },
                {
                    "label": "Brecha operativa",
                    "value": _format_greenhouse_value(selected_env_row.get("Brecha operativa (m²)"), 1, " m²"),
                    "note": "Diferencia entre máximo permitido y real",
                    "accent": GREENHOUSE_COLORS["gap"],
                },
                {
                    "label": "Registros",
                    "value": _format_greenhouse_value(selected_env_row.get("Registros"), 0),
                    "note": "Datos ambientales usados",
                    "accent": BRAND_COLORS["graphite"],
                },
            ]
        )
        st.info(str(selected_env_row.get("Lectura operativa", "Lectura no disponible.")))

    environment_chart = _build_greenhouse_environment_scatter(
        diagnostic_df,
        metric_choice,
        selected_block_label
    )
    _render_greenhouse_chart_panel(
        environment_chart,
        "Cruce ambiental vs capacidad instalada",
        "cruce_ambiental_capacidad",
        selected_block_label,
        large_height=760
    )

    download_col, spacer_col = st.columns([0.28, 0.72])
    with download_col:
        _render_greenhouse_report_download(
            analysis_data,
            selected_block_label,
            diagnostic_df=diagnostic_df,
            key_suffix="cruce_ambiental"
        )
    with spacer_col:
        st.caption("El Excel descargable incluye la ficha técnica completa y la hoja adicional de cruce ambiental.")

    with st.expander("Ver tabla completa del cruce ambiental", expanded=False):
        _dataframe(diagnostic_df, hide_index=True, height=300)


def _build_greenhouse_component_chart(selected_areas_df, selected_block_label):
    if selected_areas_df.empty:
        return None

    row = selected_areas_df.iloc[0]
    components = [
        (
            "Lateral",
            row.get("Área lateral teórica (m²)"),
            row.get("Área lateral máxima permitida (m²)"),
            row.get("Área lateral real (m²)"),
        ),
        (
            "Frontal",
            row.get("Área frontal teórica (m²)"),
            row.get("Área frontal máxima permitida (m²)"),
            row.get("Área frontal real (m²)"),
        ),
        (
            "Culatas",
            row.get("Área culatas teórica (m²)"),
            row.get("Área culatas máxima permitida (m²)"),
            row.get("Área culatas real (m²)"),
        ),
    ]

    chart_df = pd.DataFrame(
        [
            {
                "Componente": component_name,
                "Teórica": _safe_float(theoretical_value) or 0.0,
                "Máx. permitida": _safe_float(max_value) or 0.0,
                "Real": _safe_float(real_value) or 0.0,
            }
            for component_name, theoretical_value, max_value, real_value in components
        ]
    )

    fig = go.Figure()
    series_config = [
        ("Teórica", GREENHOUSE_COLORS["theoretical"]),
        ("Máx. permitida", GREENHOUSE_COLORS["allowed"]),
        ("Real", GREENHOUSE_COLORS["real"]),
    ]
    for series_name, color in series_config:
        fig.add_trace(go.Bar(
            x=chart_df["Componente"],
            y=chart_df[series_name],
            name=series_name,
            marker=dict(color=color, line=dict(color="rgba(56,58,53,0.12)", width=1)),
            text=[f"{value:,.0f}" for value in chart_df[series_name]],
            textposition="outside",
            hovertemplate="%{x}<br>" + series_name + ": %{y:,.2f} m²<extra></extra>"
        ))

    fig.update_layout(
        template="plotly_white",
        barmode="group",
        title=f"Ventilación por componente · {selected_block_label}",
        yaxis_title="Área de ventilación (m²)",
        xaxis_title="",
        legend_title_text="Escenario",
        height=440,
        margin=dict(l=20, r=20, t=70, b=24),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        bargap=0.22,
        bargroupgap=0.08,
    )
    return fig


def _build_greenhouse_efficiency_donut(selected_summary_df, selected_block_label):
    if selected_summary_df.empty:
        return None

    row = selected_summary_df.iloc[0]
    total_real = _safe_float(row.get("Total Real (m²)"))
    total_max = _safe_float(row.get("Total Máx. Perm. (m²)"))
    if total_real is None or total_max is None or total_max <= 0:
        return None

    gap_value = max(total_max - total_real, 0.0)
    fig = go.Figure(go.Pie(
        labels=["Ventilación real", "Brecha operativa"],
        values=[total_real, gap_value],
        hole=0.68,
        marker=dict(
            colors=[GREENHOUSE_COLORS["real"], GREENHOUSE_COLORS["gap"]],
            line=dict(color="rgba(255,255,255,0.96)", width=3),
        ),
        sort=False,
        texttemplate="<b>%{label}</b><br>%{percent}",
        textposition="inside",
        insidetextfont=dict(color="#ffffff", size=12),
        hovertemplate="%{label}<br>%{value:,.2f} m²<extra></extra>"
    ))
    fig.update_layout(
        template="plotly_white",
        title=f"Eficiencia operativa · {selected_block_label}",
        height=390,
        margin=dict(l=20, r=20, t=70, b=38),
        annotations=[dict(
            text=f"{(total_real / total_max):.0%}<br><span style='font-size:12px;'>del máximo</span>",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=18, color="#383A35")
        )],
        uniformtext_minsize=11,
        uniformtext_mode="hide",
        legend=dict(orientation="h", yanchor="bottom", y=-0.16, xanchor="center", x=0.5)
    )
    return fig


def _build_greenhouse_composition_donut(selected_areas_df, selected_block_label):
    if selected_areas_df.empty:
        return None

    row = selected_areas_df.iloc[0]
    composition_rows = [
        ("Lateral", _safe_float(row.get("Área lateral real (m²)")) or 0.0, GREENHOUSE_COLORS["lateral"]),
        ("Frontal", _safe_float(row.get("Área frontal real (m²)")) or 0.0, GREENHOUSE_COLORS["frontal"]),
        ("Culatas", _safe_float(row.get("Área culatas real (m²)")) or 0.0, GREENHOUSE_COLORS["culatas"]),
    ]
    composition_rows = [item for item in composition_rows if item[1] > 0]
    if not composition_rows:
        return None

    total_real = sum(value for _, value, _ in composition_rows)
    fig = go.Figure(go.Pie(
        labels=[label for label, _, _ in composition_rows],
        values=[value for _, value, _ in composition_rows],
        hole=0.62,
        marker=dict(
            colors=[color for _, _, color in composition_rows],
            line=dict(color="rgba(255,255,255,0.96)", width=3),
        ),
        sort=False,
        texttemplate="<b>%{label}</b><br>%{percent}",
        textposition="inside",
        insidetextfont=dict(color="#ffffff", size=12),
        hovertemplate="%{label}<br>%{value:,.2f} m²<extra></extra>"
    ))
    fig.update_layout(
        template="plotly_white",
        title=f"Composición de la ventilación real · {selected_block_label}",
        height=390,
        margin=dict(l=20, r=20, t=70, b=38),
        annotations=[dict(
            text=f"{total_real:,.0f} m²<br><span style='font-size:12px;'>ventilación real</span>",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=18, color="#383A35")
        )],
        uniformtext_minsize=11,
        uniformtext_mode="hide",
        legend=dict(orientation="h", yanchor="bottom", y=-0.16, xanchor="center", x=0.5)
    )
    return fig


def _build_greenhouse_component_progress_chart(selected_areas_df, selected_block_label):
    if selected_areas_df.empty:
        return None

    row = selected_areas_df.iloc[0]
    components = [
        ("Lateral", row.get("Área lateral máxima permitida (m²)"), row.get("Área lateral real (m²)")),
        ("Frontal", row.get("Área frontal máxima permitida (m²)"), row.get("Área frontal real (m²)")),
        ("Culatas", row.get("Área culatas máxima permitida (m²)"), row.get("Área culatas real (m²)")),
    ]
    progress_rows = []
    for component_name, max_value, real_value in components:
        max_numeric = _safe_float(max_value)
        real_numeric = _safe_float(real_value)
        if max_numeric is None or max_numeric <= 0 or real_numeric is None:
            continue
        real_capped = min(real_numeric, max_numeric)
        gap_value = max(max_numeric - real_numeric, 0.0)
        progress_rows.append({
            "Componente": component_name,
            "Real": real_capped,
            "Brecha": gap_value,
            "Cumplimiento": real_numeric / max_numeric,
        })

    if not progress_rows:
        return None

    progress_df = pd.DataFrame(progress_rows)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=progress_df["Componente"],
        x=progress_df["Real"],
        orientation="h",
        name="Real",
        marker=dict(color=GREENHOUSE_COLORS["real"], line=dict(color="rgba(56,58,53,0.10)", width=1)),
        text=[f"{value:.0%}" for value in progress_df["Cumplimiento"]],
        textposition="inside",
        insidetextanchor="middle",
        hovertemplate="%{y}<br>Real: %{x:,.2f} m²<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        y=progress_df["Componente"],
        x=progress_df["Brecha"],
        orientation="h",
        name="Brecha",
        marker=dict(color=GREENHOUSE_COLORS["gap"], line=dict(color="rgba(56,58,53,0.10)", width=1)),
        hovertemplate="%{y}<br>Brecha: %{x:,.2f} m²<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_white",
        title=f"Uso del máximo permitido por componente · {selected_block_label}",
        barmode="stack",
        height=440,
        margin=dict(l=20, r=20, t=70, b=24),
        xaxis_title="Área máxima permitida (m²)",
        yaxis_title="",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def _build_greenhouse_block_ranking_chart(summary_df, selected_block_label):
    if summary_df.empty or "Bloque" not in summary_df.columns or "Total Real (m²)" not in summary_df.columns:
        return None

    ranking_df = summary_df.copy()
    ranking_df["Total Real (m²)"] = pd.to_numeric(ranking_df["Total Real (m²)"], errors="coerce")
    ranking_df = ranking_df.dropna(subset=["Total Real (m²)"]).sort_values("Total Real (m²)", ascending=False)
    if ranking_df.empty:
        return None

    bar_colors = [
        BRAND_COLORS["hero"] if str(block_name) == str(selected_block_label) else "#C9D7E7"
        for block_name in ranking_df["Bloque"]
    ]

    fig = go.Figure(go.Bar(
        x=ranking_df["Total Real (m²)"],
        y=ranking_df["Bloque"],
        orientation="h",
        marker_color=bar_colors,
        text=[f"{value:,.0f} m²" for value in ranking_df["Total Real (m²)"]],
        textposition="outside",
        hovertemplate="%{y}<br>Total real: %{x:,.2f} m²<extra></extra>"
    ))
    fig.update_layout(
        template="plotly_white",
        title="Comparación de ventilación real entre bloques",
        xaxis_title="Total real (m²)",
        yaxis_title="",
        height=420,
        margin=dict(l=20, r=20, t=70, b=24),
        yaxis=dict(autorange="reversed", categoryorder="array", categoryarray=ranking_df["Bloque"].tolist()),
    )
    return fig


def _build_greenhouse_gap_ranking_chart(summary_df, selected_block_label):
    if summary_df.empty or "Bloque" not in summary_df.columns or "Brecha Máx-Real (m²)" not in summary_df.columns:
        return None

    ranking_df = summary_df.copy()
    ranking_df["Brecha Máx-Real (m²)"] = pd.to_numeric(ranking_df["Brecha Máx-Real (m²)"], errors="coerce")
    ranking_df = ranking_df.dropna(subset=["Brecha Máx-Real (m²)"]).sort_values("Brecha Máx-Real (m²)", ascending=False)
    if ranking_df.empty:
        return None

    bar_colors = [
        GREENHOUSE_COLORS["gap"] if str(block_name) == str(selected_block_label) else "#D8D2C4"
        for block_name in ranking_df["Bloque"]
    ]

    fig = go.Figure(go.Bar(
        x=ranking_df["Brecha Máx-Real (m²)"],
        y=ranking_df["Bloque"],
        orientation="h",
        marker=dict(color=bar_colors, line=dict(color="rgba(56,58,53,0.10)", width=1)),
        text=[f"{value:,.0f} m²" for value in ranking_df["Brecha Máx-Real (m²)"]],
        textposition="outside",
        hovertemplate="%{y}<br>Brecha: %{x:,.2f} m²<extra></extra>"
    ))
    fig.update_layout(
        template="plotly_white",
        title="Ranking de brecha operativa por bloque",
        xaxis_title="Brecha máx-real (m²)",
        yaxis_title="",
        height=420,
        margin=dict(l=20, r=20, t=70, b=24),
        yaxis=dict(autorange="reversed", categoryorder="array", categoryarray=ranking_df["Bloque"].tolist()),
    )
    return fig


def _build_greenhouse_performance_heatmap(summary_df, selected_block_label):
    required_columns = [
        "Bloque",
        "% Real / Teórica",
        "% Real / Máx. Perm.",
        "Brecha Máx-Real (m²)",
    ]
    if summary_df.empty or any(column_name not in summary_df.columns for column_name in required_columns):
        return None

    heatmap_df = summary_df[required_columns].copy()
    heatmap_df["% Real / Teórica"] = pd.to_numeric(heatmap_df["% Real / Teórica"], errors="coerce")
    heatmap_df["% Real / Máx. Perm."] = pd.to_numeric(heatmap_df["% Real / Máx. Perm."], errors="coerce")
    heatmap_df["Brecha Máx-Real (m²)"] = pd.to_numeric(heatmap_df["Brecha Máx-Real (m²)"], errors="coerce")
    heatmap_df["Brecha normalizada"] = 1 - (
        heatmap_df["Brecha Máx-Real (m²)"] / heatmap_df["Brecha Máx-Real (m²)"].max()
    )
    heatmap_df = heatmap_df.dropna(subset=["% Real / Teórica", "% Real / Máx. Perm.", "Brecha normalizada"])
    if heatmap_df.empty:
        return None

    metric_labels = ["Real / teórica", "Real / máx.", "Brecha controlada"]
    z_values = heatmap_df[["% Real / Teórica", "% Real / Máx. Perm.", "Brecha normalizada"]].to_numpy()
    text_values = []
    for _, row in heatmap_df.iterrows():
        text_values.append([
            f"{row['% Real / Teórica']:.1%}",
            f"{row['% Real / Máx. Perm.']:.1%}",
            f"{row['Brecha Máx-Real (m²)']:,.0f} m²",
        ])

    fig = go.Figure(go.Heatmap(
        z=z_values,
        x=metric_labels,
        y=heatmap_df["Bloque"],
        text=text_values,
        texttemplate="%{text}",
        colorscale=[
            [0.0, "#D77A94"],
            [0.5, "#E7C87A"],
            [1.0, "#3DBB76"],
        ],
        zmin=0,
        zmax=1,
        colorbar=dict(
            title="Desempeño",
            tickvals=[0, 0.5, 1],
            ticktext=["Bajo", "Medio", "Alto"],
        ),
        hovertemplate="%{y}<br>%{x}: %{text}<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_white",
        title="Heatmap de desempeño técnico",
        height=410,
        margin=dict(l=20, r=20, t=70, b=24),
        xaxis_title="",
        yaxis_title="",
        yaxis=dict(autorange="reversed"),
    )
    return fig


def _build_greenhouse_capacity_slope_chart(summary_df, selected_block_label):
    required_columns = [
        "Bloque",
        "Total Teórica (m²)",
        "Total Máx. Perm. (m²)",
        "Total Real (m²)",
    ]
    if summary_df.empty or any(column_name not in summary_df.columns for column_name in required_columns):
        return None

    working_df = summary_df[required_columns].copy()
    for column_name in required_columns[1:]:
        working_df[column_name] = pd.to_numeric(working_df[column_name], errors="coerce")
    working_df = working_df.dropna(subset=required_columns[1:])
    if working_df.empty:
        return None

    stage_labels = ["Teórica", "Máx. permitida", "Real"]
    stage_columns = ["Total Teórica (m²)", "Total Máx. Perm. (m²)", "Total Real (m²)"]

    fig = go.Figure()
    for _, row in working_df.iterrows():
        is_selected = str(row["Bloque"]) == str(selected_block_label)
        line_color = BRAND_COLORS["hero"] if is_selected else "rgba(84,83,134,0.28)"
        line_width = 4 if is_selected else 2
        marker_size = 11 if is_selected else 8
        fig.add_trace(go.Scatter(
            x=stage_labels,
            y=[row[column_name] for column_name in stage_columns],
            mode="lines+markers+text" if is_selected else "lines+markers",
            name=str(row["Bloque"]),
            line=dict(color=line_color, width=line_width),
            marker=dict(size=marker_size, color=line_color),
            text=[f"{row[column_name]:,.0f}" for column_name in stage_columns] if is_selected else None,
            textposition="top center",
            hovertemplate=f"{row['Bloque']}<br>%{{x}}: %{{y:,.2f}} m²<extra></extra>",
        ))

    fig.update_layout(
        template="plotly_white",
        title="Trayectoria de capacidad: teórica → máxima → real",
        yaxis_title="Área de ventilación (m²)",
        xaxis_title="Etapa de capacidad",
        height=460,
        margin=dict(l=20, r=20, t=70, b=24),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def _build_greenhouse_insights(selected_general_df, selected_areas_df, selected_summary_df):
    insights = []
    if selected_general_df.empty or selected_areas_df.empty or selected_summary_df.empty:
        return insights

    general_row = selected_general_df.iloc[0]
    area_row = selected_areas_df.iloc[0]
    summary_row = selected_summary_df.iloc[0]

    culatas_count = _safe_float(general_row.get("N° Culatas"))
    if culatas_count == 0:
        insights.append("Este bloque no tiene culatas activas en el cálculo, así que su ventilación depende de laterales y frontales.")
    elif culatas_count is not None:
        insights.append(f"El bloque incorpora {int(culatas_count)} culatas consideradas en la capacidad de ventilación.")

    real_vs_theoretical = _safe_float(summary_row.get("% Real / Teórica"))
    if real_vs_theoretical is not None:
        insights.append(f"La ventilación real está en {real_vs_theoretical:.1%} del potencial teórico del bloque.")

    largest_gap = None
    largest_gap_label = None
    for component_name, max_column, real_column in [
        ("lateral", "Área lateral máxima permitida (m²)", "Área lateral real (m²)"),
        ("frontal", "Área frontal máxima permitida (m²)", "Área frontal real (m²)"),
        ("culatas", "Área culatas máxima permitida (m²)", "Área culatas real (m²)"),
    ]:
        max_value = _safe_float(area_row.get(max_column))
        real_value = _safe_float(area_row.get(real_column))
        if max_value is None or real_value is None:
            continue
        gap_value = max_value - real_value
        if largest_gap is None or gap_value > largest_gap:
            largest_gap = gap_value
            largest_gap_label = component_name

    if largest_gap_label is not None:
        insights.append(f"La mayor oportunidad operativa frente al máximo permitido está en la ventilación {largest_gap_label}, con una brecha de {largest_gap:,.1f} m².")

    return insights


@st.cache_data(show_spinner="Cargando análisis estructural de invernaderos...")
def cargar_analisis_invernaderos(ruta_bytes, cache_version=DATA_CACHE_VERSION):
    _ = cache_version
    if not ruta_bytes:
        return {
            "general": pd.DataFrame(),
            "areas": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "interpretations": pd.DataFrame(),
            "guide": pd.DataFrame(),
            "chart_totals": pd.DataFrame(),
            "chart_ratios": pd.DataFrame(),
            "dictionary": pd.DataFrame(),
        }

    try:
        workbook = pd.ExcelFile(io.BytesIO(ruta_bytes), engine="openpyxl")

        raw_general = workbook.parse("Datos por Bloque", header=None)
        raw_summary = workbook.parse("Indicadores Resumen", header=None)
        raw_dictionary = workbook.parse("Diccionario de Variables", header=None)

        general_header_idx = _find_excel_row_by_first_value(raw_general, "Bloque")
        area_header_idx = _find_excel_row_by_first_value(raw_general, "Bloque", start_idx=(general_header_idx or 0) + 1)
        guide_start_idx = _find_excel_row_by_first_value(raw_general, "GUÍA RÁPIDA DE LECTURA")
        summary_header_idx = _find_excel_row_by_first_value(raw_summary, "Bloque")
        interpretation_start_idx = _find_excel_row_by_first_value(raw_summary, "INTERPRETACIÓN TÉCNICA")
        chart_start_idx = _find_excel_row_by_first_value(raw_summary, "GRÁFICAS COMPARATIVAS – VENTILACIÓN POR BLOQUE")
        chart_total_header_idx = _find_sparse_header_row(raw_summary, chart_start_idx, "Teórica")
        chart_ratio_header_idx = _find_sparse_header_row(raw_summary, chart_start_idx, "% Real / Teórica")
        dictionary_header_idx = _find_excel_row_by_first_value(raw_dictionary, "Variable / columna")

        return {
            "general": _extract_excel_table(raw_general, general_header_idx),
            "areas": _extract_excel_table(raw_general, area_header_idx),
            "summary": _extract_excel_table(raw_summary, summary_header_idx),
            "interpretations": _build_greenhouse_interpretation_table(raw_summary, interpretation_start_idx),
            "guide": _build_greenhouse_guide_table(raw_general, guide_start_idx),
            "chart_totals": _extract_sparse_excel_table(raw_summary, chart_total_header_idx),
            "chart_ratios": _extract_sparse_excel_table(raw_summary, chart_ratio_header_idx),
            "dictionary": _extract_excel_table(raw_dictionary, dictionary_header_idx),
        }
    except Exception as error:
        st.error(f"No fue posible cargar el análisis de invernaderos. Detalle: {error}")
        return {
            "general": pd.DataFrame(),
            "areas": pd.DataFrame(),
            "summary": pd.DataFrame(),
            "interpretations": pd.DataFrame(),
            "guide": pd.DataFrame(),
            "chart_totals": pd.DataFrame(),
            "chart_ratios": pd.DataFrame(),
            "dictionary": pd.DataFrame(),
        }


def _render_greenhouse_analysis_dashboard():
    analysis_bytes = descargar_desde_github(URL_ANALYSIS_FALLBACKS)
    if analysis_bytes is None:
        analysis_bytes = _read_first_local_file_bytes(GREENHOUSE_ANALYSIS_LOCAL_EXCEL_PATHS)
    if analysis_bytes is None:
        st.warning("No se encontró el archivo de análisis de invernaderos en las rutas configuradas.")
        st.stop()

    analysis_data = cargar_analisis_invernaderos(analysis_bytes)
    general_df = analysis_data["general"]
    areas_df = analysis_data["areas"]
    summary_df = analysis_data["summary"]
    interpretations_df = analysis_data["interpretations"]
    guide_df = analysis_data["guide"]
    chart_totals_df = analysis_data["chart_totals"]
    chart_ratios_df = analysis_data["chart_ratios"]
    dictionary_df = analysis_data["dictionary"]

    available_blocks = []
    for source_df in (summary_df, general_df, areas_df):
        if "Bloque" in source_df.columns:
            available_blocks.extend(source_df["Bloque"].dropna().astype(str).tolist())
    available_blocks = list(dict.fromkeys(available_blocks))

    if not available_blocks:
        st.warning("El archivo de análisis no contiene bloques listos para mostrar.")
        st.stop()

    shared_block_code = st.session_state.get("bloque_compartido")
    default_block_label = next(
        (block_name for block_name in available_blocks if _extract_block_code(block_name) == shared_block_code),
        available_blocks[0]
    )
    if st.session_state.get("greenhouse_analysis_block") not in available_blocks:
        st.session_state["greenhouse_analysis_block"] = default_block_label

    with st.sidebar.expander("Bloque técnico", expanded=True):
        _sidebar_field_label("location", "Bloque analizado")
        selected_block_label = st.selectbox(
            "Seleccionar bloque técnico:",
            options=available_blocks,
            key="greenhouse_analysis_block",
            help="Muestra la ficha estructural y de ventilación calculada para el bloque seleccionado."
        )

    selected_block_code = _extract_block_code(selected_block_label)
    if selected_block_code:
        st.session_state["bloque_compartido"] = selected_block_code

    selected_general_df = (
        general_df[general_df["Bloque"].astype(str) == selected_block_label].reset_index(drop=True)
        if "Bloque" in general_df.columns else pd.DataFrame()
    )
    selected_areas_df = (
        areas_df[areas_df["Bloque"].astype(str) == selected_block_label].reset_index(drop=True)
        if "Bloque" in areas_df.columns else pd.DataFrame()
    )
    selected_summary_df = (
        summary_df[summary_df["Bloque"].astype(str) == selected_block_label].reset_index(drop=True)
        if "Bloque" in summary_df.columns else pd.DataFrame()
    )

    _render_greenhouse_styles()
    _render_greenhouse_hero(selected_block_label, selected_summary_df)

    download_col, download_note_col = st.columns([0.28, 0.72])
    with download_col:
        _render_greenhouse_report_download(analysis_data, selected_block_label, key_suffix="ficha_tecnica")
    with download_note_col:
        st.caption("Reporte listo para auditoría: datos generales, áreas calculadas, indicadores, lectura técnica, guía rápida y diccionario.")

    _render_greenhouse_flow_cards(
        "Ruta de lectura del contexto técnico",
        [
            {
                "title": "Resumen ejecutivo",
                "body": "Decisión rápida: capacidad, brecha, eficiencia y lectura principal del bloque.",
                "accent": BRAND_COLORS["hero"],
            },
            {
                "title": "Componentes",
                "body": "Detalle de geometría, laterales, frontales y culatas para explicar el resultado.",
                "accent": GREENHOUSE_COLORS["real"],
            },
            {
                "title": "Comparativo",
                "body": "Benchmark entre bloques para priorizar dónde revisar primero.",
                "accent": GREENHOUSE_COLORS["gap"],
            },
            {
                "title": "Cruce ambiental",
                "body": "Relación entre estructura de ventilación y comportamiento climático observado.",
                "accent": BRAND_COLORS["sky"],
            },
            {
                "title": "Datos y diccionario",
                "body": "Trazabilidad completa del Excel: tablas fuente, cálculos y definiciones.",
                "accent": BRAND_COLORS["graphite"],
            },
        ]
    )

    tab_exec, tab_components, tab_compare, tab_environment_new, tab_data = st.tabs([
        "1. Resumen ejecutivo",
        "2. Componentes",
        "3. Comparativo",
        "4. Cruce ambiental",
        "5. Datos y diccionario",
    ])

    with tab_exec:
        _render_chart_explanation(
            "Lectura ejecutiva del bloque",
            "Concentra capacidad instalada, uso real y brecha operativa para tomar una decisión rápida antes de entrar al detalle técnico.",
            accent=BRAND_COLORS['hero'],
            kicker='Contexto técnico'
        )

        if not selected_summary_df.empty:
            summary_row = selected_summary_df.iloc[0]
            real_max_ratio = _safe_float(summary_row.get("% Real / Máx. Perm."))
            loss_ratio = max(0.0, 1 - real_max_ratio) if real_max_ratio is not None else None
            _render_greenhouse_metric_grid(
                "Capacidad de ventilación",
                [
                    {"label": "Total teórica", "value": _format_greenhouse_value(summary_row.get("Total Teórica (m²)"), 2, " m²"), "note": "Potencial geométrico calculado", "accent": GREENHOUSE_COLORS["theoretical"]},
                    {"label": "Máx. permitida", "value": _format_greenhouse_value(summary_row.get("Total Máx. Perm. (m²)"), 2, " m²"), "note": "Límite operativo instalado", "accent": GREENHOUSE_COLORS["allowed"]},
                    {"label": "Total real", "value": _format_greenhouse_value(summary_row.get("Total Real (m²)"), 2, " m²"), "note": "Ventilación efectiva disponible", "accent": GREENHOUSE_COLORS["real"]},
                    {"label": "Brecha máx-real", "value": _format_greenhouse_value(summary_row.get("Brecha Máx-Real (m²)"), 2, " m²"), "note": "Oportunidad frente al máximo", "accent": GREENHOUSE_COLORS["gap"]},
                ]
            )
            _render_greenhouse_metric_grid(
                "Indicadores de cumplimiento",
                [
                    {"label": "Real / teórica", "value": _format_greenhouse_percent(summary_row.get("% Real / Teórica")), "note": "Uso del potencial geométrico", "accent": BRAND_COLORS["sky"]},
                    {"label": "Real / máx. permitida", "value": _format_greenhouse_percent(summary_row.get("% Real / Máx. Perm.")), "note": "Uso de la capacidad instalada", "accent": BRAND_COLORS["hero"]},
                    {"label": "Pérdida operativa", "value": _format_greenhouse_percent(loss_ratio), "note": "Brecha relativa al máximo", "accent": BRAND_COLORS["rose"]},
                    {"label": "Bloque evaluado", "value": selected_block_label, "note": "Fuente: Datos por Bloque", "accent": BRAND_COLORS["graphite"]},
                ]
            )

        _render_greenhouse_insight_cards(_build_greenhouse_insights(selected_general_df, selected_areas_df, selected_summary_df))
        exec_left, exec_right = st.columns(2)
        with exec_left:
            _render_greenhouse_chart_panel(_build_greenhouse_efficiency_donut(selected_summary_df, selected_block_label), "Eficiencia operativa", "ejecutivo_eficiencia_operativa", selected_block_label, large_height=620)
        with exec_right:
            _render_greenhouse_chart_panel(_build_greenhouse_composition_donut(selected_areas_df, selected_block_label), "Composición de la ventilación real", "ejecutivo_composicion_ventilacion_real", selected_block_label, large_height=620)

    with tab_components:
        _render_chart_explanation(
            "Componentes estructurales",
            "Separa geometría, ventilación lateral, frontal y culatas para entender de dónde viene la capacidad real del bloque.",
            accent=GREENHOUSE_COLORS["real"],
            kicker='Detalle técnico'
        )
        if not selected_general_df.empty:
            general_row = selected_general_df.iloc[0]
            _render_greenhouse_metric_grid(
                "Geometría del invernadero",
                [
                    {"label": "Cuadros", "value": _format_greenhouse_value(general_row.get("N° Cuadros"), 0), "note": "Módulos estructurales", "accent": GREENHOUSE_COLORS["lateral"]},
                    {"label": "Naves", "value": _format_greenhouse_value(general_row.get("N° Naves"), 0), "note": "Configuración del bloque", "accent": GREENHOUSE_COLORS["frontal"]},
                    {"label": "Culatas", "value": _format_greenhouse_value(general_row.get("N° Culatas"), 0), "note": "Aperturas consideradas", "accent": GREENHOUSE_COLORS["culatas"]},
                    {"label": "Tamaño nave", "value": _format_greenhouse_value(general_row.get("Tamaño de la nave (m)"), 1, " m"), "note": "Medida base de cálculo", "accent": BRAND_COLORS["beige"]},
                ]
            )
        comp_left, comp_right = st.columns(2)
        with comp_left:
            _render_greenhouse_chart_panel(_build_greenhouse_component_chart(selected_areas_df, selected_block_label), "Ventilación por componente", "componentes_ventilacion_por_componente", selected_block_label, large_height=680)
        with comp_right:
            _render_greenhouse_chart_panel(_build_greenhouse_component_progress_chart(selected_areas_df, selected_block_label), "Uso del máximo permitido por componente", "componentes_uso_maximo_por_componente", selected_block_label, large_height=680)
        _render_greenhouse_reading_cards("Guía rápida de lectura", guide_df, title_col="Concepto", body_col="Descripcion")
        detail_left, detail_right = st.columns(2)
        with detail_left:
            with st.expander("Datos generales y aperturas lineales", expanded=False):
                _dataframe(_format_single_block_detail_table(selected_general_df), hide_index=True)
        with detail_right:
            with st.expander("Áreas de ventilación calculadas", expanded=False):
                _dataframe(_format_single_block_detail_table(selected_areas_df), hide_index=True)

    with tab_compare:
        _render_chart_explanation(
            "Comparativo entre bloques",
            "Ubica el bloque seleccionado frente al resto para priorizar brechas, eficiencia relativa y posición técnica.",
            accent=GREENHOUSE_COLORS["gap"],
            kicker='Benchmark técnico'
        )
        diagnostic_left, diagnostic_right = st.columns(2)
        with diagnostic_left:
            _render_greenhouse_chart_panel(_build_greenhouse_performance_heatmap(summary_df, selected_block_label), "Heatmap de desempeño técnico", "comparativo_heatmap_desempeno_tecnico", selected_block_label, large_height=650)
        with diagnostic_right:
            _render_greenhouse_chart_panel(_build_greenhouse_gap_ranking_chart(summary_df, selected_block_label), "Ranking de brecha operativa", "comparativo_ranking_brecha_operativa", selected_block_label, large_height=650)
        _render_greenhouse_chart_panel(_build_greenhouse_capacity_slope_chart(summary_df, selected_block_label), "Trayectoria de capacidad", "comparativo_trayectoria_capacidad", selected_block_label, large_height=680)
        _render_greenhouse_chart_panel(_build_greenhouse_block_ranking_chart(summary_df, selected_block_label), "Comparación de ventilación real entre bloques", "comparativo_ranking_ventilacion_real", selected_block_label, large_height=650)
        with st.expander("Tabla comparativa por bloque", expanded=True):
            _dataframe(_format_analysis_block_table(summary_df), hide_index=True)
        _render_greenhouse_reading_cards("Lectura técnica del archivo", interpretations_df)

    with tab_environment_new:
        _render_greenhouse_environment_tab(summary_df, analysis_data, selected_block_label)

    with tab_data:
        _render_chart_explanation(
            "Base técnica y trazabilidad",
            "Esta pestaña conserva las tablas originales, las bases de gráficas y el diccionario para auditar de dónde sale cada indicador del contexto técnico.",
            accent=BRAND_COLORS["graphite"],
            kicker="Soporte de datos"
        )
        _render_greenhouse_metric_grid(
            "Trazabilidad del archivo",
            [
                {"label": "Bloques técnicos", "value": f"{len(available_blocks):,}", "note": "Bloques detectados en el Excel", "accent": BRAND_COLORS["hero"]},
                {"label": "Datos generales", "value": f"{len(general_df):,}", "note": "Filas de geometría y aperturas", "accent": GREENHOUSE_COLORS["lateral"]},
                {"label": "Áreas calculadas", "value": f"{len(areas_df):,}", "note": "Filas de ventilación en m²", "accent": GREENHOUSE_COLORS["real"]},
                {"label": "Variables definidas", "value": f"{len(dictionary_df):,}", "note": "Conceptos documentados", "accent": GREENHOUSE_COLORS["gap"]},
            ]
        )
        st.markdown(
            """
            <div class="greenhouse-divider-note">
                Usa esta zona como respaldo técnico: primero están las tablas fuente, luego las bases usadas para gráficas comparativas
                y al final el diccionario con el significado operativo de cada variable.
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown("### Tablas fuente del Excel")
        with st.expander("Datos generales de todos los bloques", expanded=False):
            _dataframe(general_df, hide_index=True, height=260)
        with st.expander("Apertura calculada en m² de todos los bloques", expanded=False):
            _dataframe(_format_analysis_block_table(areas_df), hide_index=True, height=280)
        with st.expander("Datos base de gráficas comparativas", expanded=False):
            if not chart_totals_df.empty:
                st.markdown("#### Ventilación por bloque")
                _dataframe(chart_totals_df, hide_index=True)
            if not chart_ratios_df.empty:
                st.markdown("#### Indicadores porcentuales")
                _dataframe(_format_analysis_block_table(chart_ratios_df), hide_index=True)
        st.markdown("### Diccionario de variables")
        _render_greenhouse_dictionary_cards(dictionary_df)
        with st.expander("Ver diccionario en tabla completa", expanded=False):
            _dataframe(dictionary_df, hide_index=True, height=360)

    return

    tab_block, tab_summary, tab_environment, tab_dictionary = st.tabs([
        "Datos por bloque",
        "Resumen comparativo",
        "Cruce ambiental",
        "Diccionario",
    ])

    with tab_block:
        _render_chart_explanation(
            "Datos por bloque",
            "Esta vista resume la geometría del invernadero, la capacidad de ventilación por componente y la posición relativa del bloque seleccionado frente a los demás."
        )

        if not selected_summary_df.empty:
            summary_row = selected_summary_df.iloc[0]
            real_max_ratio = _safe_float(summary_row.get("% Real / Máx. Perm."))
            loss_ratio = max(0.0, 1 - real_max_ratio) if real_max_ratio is not None else None
            _render_greenhouse_metric_grid(
                "Capacidad de ventilación",
                [
                    {
                        "label": "Total teórica",
                        "value": _format_greenhouse_value(summary_row.get("Total Teórica (m²)"), 2, " m²"),
                        "note": "Potencial geométrico calculado",
                        "accent": GREENHOUSE_COLORS["theoretical"],
                    },
                    {
                        "label": "Máx. permitida",
                        "value": _format_greenhouse_value(summary_row.get("Total Máx. Perm. (m²)"), 2, " m²"),
                        "note": "Límite operativo instalado",
                        "accent": GREENHOUSE_COLORS["allowed"],
                    },
                    {
                        "label": "Total real",
                        "value": _format_greenhouse_value(summary_row.get("Total Real (m²)"), 2, " m²"),
                        "note": "Ventilación efectiva disponible",
                        "accent": GREENHOUSE_COLORS["real"],
                    },
                    {
                        "label": "Brecha máx-real",
                        "value": _format_greenhouse_value(summary_row.get("Brecha Máx-Real (m²)"), 2, " m²"),
                        "note": "Oportunidad frente al máximo",
                        "accent": GREENHOUSE_COLORS["gap"],
                    },
                ]
            )
            _render_greenhouse_metric_grid(
                "Indicadores de cumplimiento",
                [
                    {
                        "label": "Real / teórica",
                        "value": _format_greenhouse_percent(summary_row.get("% Real / Teórica")),
                        "note": "Uso del potencial geométrico",
                        "accent": BRAND_COLORS["sky"],
                    },
                    {
                        "label": "Real / máx. permitida",
                        "value": _format_greenhouse_percent(summary_row.get("% Real / Máx. Perm.")),
                        "note": "Uso de la capacidad instalada",
                        "accent": BRAND_COLORS["hero"],
                    },
                    {
                        "label": "Pérdida operativa",
                        "value": _format_greenhouse_percent(loss_ratio),
                        "note": "Brecha relativa al máximo",
                        "accent": BRAND_COLORS["rose"],
                    },
                    {
                        "label": "Bloque evaluado",
                        "value": selected_block_label,
                        "note": "Fuente: Datos por Bloque",
                        "accent": BRAND_COLORS["graphite"],
                    },
                ]
            )

        if not selected_general_df.empty:
            general_row = selected_general_df.iloc[0]
            _render_greenhouse_metric_grid(
                "Geometría del invernadero",
                [
                    {
                        "label": "Cuadros",
                        "value": _format_greenhouse_value(general_row.get("N° Cuadros"), 0),
                        "note": "Módulos estructurales",
                        "accent": GREENHOUSE_COLORS["lateral"],
                    },
                    {
                        "label": "Naves",
                        "value": _format_greenhouse_value(general_row.get("N° Naves"), 0),
                        "note": "Configuración del bloque",
                        "accent": GREENHOUSE_COLORS["frontal"],
                    },
                    {
                        "label": "Culatas",
                        "value": _format_greenhouse_value(general_row.get("N° Culatas"), 0),
                        "note": "Aperturas consideradas",
                        "accent": GREENHOUSE_COLORS["culatas"],
                    },
                    {
                        "label": "Tamaño nave",
                        "value": _format_greenhouse_value(general_row.get("Tamaño de la nave (m)"), 1, " m"),
                        "note": "Medida base de cálculo",
                        "accent": BRAND_COLORS["beige"],
                    },
                ]
            )

        insight_rows = _build_greenhouse_insights(selected_general_df, selected_areas_df, selected_summary_df)
        _render_greenhouse_insight_cards(insight_rows)

        donut_left, donut_right = st.columns(2)
        with donut_left:
            efficiency_donut = _build_greenhouse_efficiency_donut(selected_summary_df, selected_block_label)
            _render_greenhouse_chart_panel(
                efficiency_donut,
                "Eficiencia operativa",
                "eficiencia_operativa",
                selected_block_label,
                large_height=720
            )
        with donut_right:
            composition_donut = _build_greenhouse_composition_donut(selected_areas_df, selected_block_label)
            _render_greenhouse_chart_panel(
                composition_donut,
                "Composición de la ventilación real",
                "composicion_ventilacion_real",
                selected_block_label,
                large_height=720
            )

        chart_left, chart_right = st.columns(2)
        with chart_left:
            component_chart = _build_greenhouse_component_chart(selected_areas_df, selected_block_label)
            _render_greenhouse_chart_panel(
                component_chart,
                "Ventilación por componente",
                "ventilacion_por_componente",
                selected_block_label,
                large_height=760
            )
        with chart_right:
            progress_chart = _build_greenhouse_component_progress_chart(selected_areas_df, selected_block_label)
            _render_greenhouse_chart_panel(
                progress_chart,
                "Uso del máximo permitido por componente",
                "uso_maximo_por_componente",
                selected_block_label,
                large_height=760
            )

        _render_greenhouse_reading_cards("Guía rápida de lectura", guide_df, title_col="Concepto", body_col="Descripcion")

        st.markdown("### Datos completos del Excel")
        with st.expander("Datos generales de todos los bloques", expanded=True):
            _dataframe(general_df, hide_index=True, height=230)
        with st.expander("Apertura calculada en m² de todos los bloques", expanded=True):
            _dataframe(_format_analysis_block_table(areas_df), hide_index=True, height=250)

        detail_left, detail_right = st.columns(2)
        with detail_left:
            with st.expander("Ver datos generales y aperturas lineales", expanded=False):
                _dataframe(_format_single_block_detail_table(selected_general_df), hide_index=True)
        with detail_right:
            with st.expander("Ver áreas de ventilación calculadas", expanded=False):
                _dataframe(_format_single_block_detail_table(selected_areas_df), hide_index=True)

    with tab_summary:
        _render_chart_explanation(
            "Resumen comparativo",
            "Aquí puedes revisar rápidamente cómo se comporta cada bloque frente al resto usando los indicadores globales del archivo."
        )

        diagnostic_left, diagnostic_right = st.columns(2)
        with diagnostic_left:
            heatmap_chart = _build_greenhouse_performance_heatmap(summary_df, selected_block_label)
            _render_greenhouse_chart_panel(
                heatmap_chart,
                "Heatmap de desempeño técnico",
                "heatmap_desempeno_tecnico",
                selected_block_label,
                large_height=720
            )
        with diagnostic_right:
            gap_chart = _build_greenhouse_gap_ranking_chart(summary_df, selected_block_label)
            _render_greenhouse_chart_panel(
                gap_chart,
                "Ranking de brecha operativa",
                "ranking_brecha_operativa",
                selected_block_label,
                large_height=720
            )

        slope_chart = _build_greenhouse_capacity_slope_chart(summary_df, selected_block_label)
        _render_greenhouse_chart_panel(
            slope_chart,
            "Trayectoria de capacidad",
            "trayectoria_capacidad",
            selected_block_label,
            large_height=760
        )

        ranking_chart = _build_greenhouse_block_ranking_chart(summary_df, selected_block_label)
        _render_greenhouse_chart_panel(
            ranking_chart,
            "Comparación de ventilación real entre bloques",
            "ranking_ventilacion_real",
            selected_block_label,
            large_height=720
        )

        st.markdown("### Tabla comparativa por bloque")
        _dataframe(_format_analysis_block_table(summary_df), hide_index=True)

        _render_greenhouse_reading_cards("Lectura técnica del archivo", interpretations_df)

        with st.expander("Datos base de gráficas comparativas del archivo", expanded=False):
            if not chart_totals_df.empty:
                st.markdown("#### Ventilación por bloque")
                _dataframe(chart_totals_df, hide_index=True)
            if not chart_ratios_df.empty:
                st.markdown("#### Indicadores porcentuales")
                _dataframe(_format_analysis_block_table(chart_ratios_df), hide_index=True)

    with tab_environment:
        _render_greenhouse_environment_tab(summary_df, analysis_data, selected_block_label)

    with tab_dictionary:
        st.markdown("### Diccionario de variables")
        _render_greenhouse_dictionary_cards(dictionary_df)
        with st.expander("Ver diccionario en tabla completa", expanded=False):
            _dataframe(dictionary_df, hide_index=True, height=360)


def _render_correlacion(
    df_variables,
    datos_cortinas_sel,
    fecha_variables,
    variables_seleccionadas=None,
    block_label=None,
    show_ideal_aperturas=False,
    df_variables_almacen=None,
    compare_with_almacen=False,
    chart_title='Correlación entre Variables y Cortinas',
    explanation_title='Correlación entre variables y cortinas',
    explanation_text=None
):
    fecha_inicio, fecha_fin = fecha_variables
    multi_day_view = fecha_inicio != fecha_fin
    hover_time_format = '%d/%m %H:%M' if multi_day_view else '%H:%M'
    xaxis_tickformat = '%H:%M\n%d/%m' if multi_day_view else '%H:%M'
    xaxis_title_text = '<b>Fecha y hora</b>' if multi_day_view else '<b>Hora del Día</b>'
    single_day_xaxis_range = None if multi_day_view else [
        datetime.combine(fecha_inicio, datetime.min.time()),
        datetime.combine(fecha_inicio, datetime.min.time()) + timedelta(hours=23, minutes=30)
    ]
    single_day_trace_times = []

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
        'Radiación PAR': 4,
        'LUX': 5
    }
    sensor_traces = []
    compare_sensor_traces = []
    cortina_traces = []
    cortina_axis_max = 100.0 if not use_cortina_area else 0.0
    sensor_legend_title_added = False
    cortina_legend_title_added = False
    plot_compaction_messages = []

    for order, var_name in enumerate(selected_vars):
        if var_name in selected_sensors:
            display_var_name = VARIABLE_SELECTOR_LABELS.get(var_name, var_name)
            serie = df_plot[['DateTime', var_name]].dropna(subset=[var_name]).copy()
            if serie.empty:
                continue
            serie_plot, compaction_meta = _prepare_sensor_series_for_plot(serie, var_name, multi_day_view=multi_day_view)
            if compaction_meta:
                plot_compaction_messages.append(
                    f"{VARIABLE_SELECTOR_LABELS.get(var_name, var_name)}: {compaction_meta['original_points']} registros resumidos a {compaction_meta['display_points']} puntos en bloques de {compaction_meta['rule']}."
                )
            if not multi_day_view:
                single_day_trace_times.extend(pd.to_datetime(serie_plot['DateTime'], errors='coerce').dropna().tolist())
            trace = dict(
                x=serie_plot['DateTime'],
                y=serie_plot[var_name],
                name=display_var_name,
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
                    display_var_name + ': %{y:.2f} ' +
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
                    serie_almacen_plot, _ = _prepare_sensor_series_for_plot(serie_almacen, var_name, multi_day_view=multi_day_view)
                    if not multi_day_view:
                        single_day_trace_times.extend(pd.to_datetime(serie_almacen_plot['DateTime'], errors='coerce').dropna().tolist())
                    almacen_trace = dict(
                        x=serie_almacen_plot['DateTime'],
                        y=serie_almacen_plot[var_name],
                        name=f'{display_var_name} - Estación externa',
                        mode='lines' if multi_day_view else 'lines+markers',
                    line=dict(
                        color=VARIABLE_COLORS.get(var_name, palette[order % len(palette)]),
                        width=2,
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
                            f'{display_var_name} - Estación externa: ' +
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
                if not multi_day_view:
                    single_day_trace_times.extend(pd.to_datetime(df_state['Hora'], errors='coerce').dropna().tolist())
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
                    line=dict(color=color, width=2.2, shape='hv'),
                        opacity=0.68,
                        hoverinfo='skip',
                        legendgroup=str(var_name),
                        legendrank=order * 10 + 2,
                        showlegend=False
                    )
                    cortina_traces.append((f'{var_name}_ideal', trace_ideal, color))
                break

    if not multi_day_view and single_day_trace_times:
        trace_times = pd.Series(single_day_trace_times).dropna().sort_values()
        min_time = pd.Timestamp(trace_times.iloc[0]).floor('30min').to_pydatetime()
        max_time = pd.Timestamp(trace_times.iloc[-1]).ceil('30min').to_pydatetime()
        single_day_xaxis_range = [min_time, max_time]

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
    axis_layout = _resolve_correlacion_axis_layout(num_axes, has_cortina_axis)
    x_domain_end = axis_layout['x_domain_end']
    right_positions = axis_layout['sensor_positions']
    cortina_axis_position = axis_layout['cortina_position']
    right_margin = axis_layout['right_margin']
    sensor_axis_names = ['y', 'y3', 'y4', 'y5']
    sensor_axis_map = {}

    sensor_traces = sorted(sensor_traces, key=lambda item: item[3])

    for idx, (var_name, trace, color, _) in enumerate(sensor_traces):
        axis_name = sensor_axis_names[idx] if idx < len(sensor_axis_names) else f'y{idx + 2}'
        sensor_axis_map[var_name] = axis_name
        trace['yaxis'] = None if axis_name == 'y' else axis_name
        fig_corr.add_trace((go.Scattergl if multi_day_view else go.Scatter)(**trace))

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
        padding = 2 if axis_var_name == 'Temperatura' else 5 if axis_var_name == 'Humedad Relativa' else max(100, (max_val - min_val) * 0.08) if axis_var_name == 'Radiación PAR' else max(5000, (max_val - min_val) * 0.08) if axis_var_name == 'LUX' else 2
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
                font=dict(color=color, size=11, family='Montserrat, sans-serif')
            ),
            tickfont=dict(color=color, size=10, family='Montserrat, sans-serif'),
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
            title_standoff=10
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
        fig_corr.add_trace((go.Scattergl if multi_day_view else go.Scatter)(**trace))

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
                    font=dict(color=cortina_color, size=11, family='Montserrat, sans-serif')
                ),
                tickfont=dict(color=cortina_color, size=10, family='Montserrat, sans-serif'),
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
                title_standoff=10
            )
        else:
            axis_configs['y2'] = dict(
                title=dict(
                    text=CORR_AXIS_TITLES['% Apertura Cortinas'],
                    font=dict(color=cortina_color, size=11, family='Montserrat, sans-serif')
                ),
                tickfont=dict(color=cortina_color, size=10, family='Montserrat, sans-serif'),
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
                title_standoff=10
            )

    fig_corr.update_layout(
        title=dict(
            text=chart_title,
            x=0,
            xanchor='left',
            y=0.98,
            yanchor='top',
            pad=dict(b=8),
            font=dict(size=22, color=BRAND_COLORS['graphite'], family='Montserrat, sans-serif')
        ),
        xaxis=dict(
            title=dict(
                text=xaxis_title_text,
                font=dict(size=14, family='Montserrat, sans-serif', color=BRAND_COLORS['graphite'])
            ),
            tickmode='linear' if not multi_day_view else 'auto',
            dtick=30 * 60 * 1000 if not multi_day_view else None,
            tickformat=xaxis_tickformat,
            range=single_day_xaxis_range,
            tickfont=dict(size=11, family='Montserrat, sans-serif', color=BRAND_COLORS['graphite']),
            domain=[0, x_domain_end],
            showgrid=True,
            gridcolor='rgba(76, 70, 120, 0.07)',
            zeroline=False
        ),
        hovermode='x unified',
        template='plotly_white',
        font=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['graphite']),
        paper_bgcolor='rgba(255,255,255,0)',
        plot_bgcolor='rgba(250,248,243,0.65)',
        hoverlabel=dict(
            bgcolor='rgba(249, 246, 240, 0.98)',
            bordercolor='rgba(76, 70, 120, 0.16)',
            font=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['graphite'], size=12)
        ),
        height=600,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.055,
            xanchor='left',
            x=0,
            traceorder='normal',
            font=dict(size=11, family='Montserrat, sans-serif', color=BRAND_COLORS['graphite']),
            grouptitlefont=dict(size=11, family='Montserrat, sans-serif', color=BRAND_COLORS['hero']),
            bgcolor='rgba(255,255,255,0.76)',
            bordercolor='rgba(76, 70, 120, 0.08)',
            borderwidth=1
        ),
        margin=dict(l=50, r=right_margin, t=104, b=70),
        **{f'yaxis{axis_name[1:]}': config for axis_name, config in axis_configs.items()}
    )

    cortina_help = (
        ' Cuando hay frentes o puertas activos, esas líneas muestran la apertura de motores y permiten relacionar el movimiento de cortinas con los cambios ambientales.'
        if selected_cortinas else
        ''
    )
    if explanation_text is None:
        ppfd_help = f" {PPFD_HELP_TEXT}" if 'Radiación PAR' in variables_seleccionadas else ''
        explanation_text = 'Esta gráfica pone todas las variables seleccionadas sobre la misma línea de tiempo. Cada color tiene su propia escala a la derecha; pasa el cursor por la gráfica para ver la hora exacta y el valor de cada serie.' + ppfd_help + cortina_help
    _plotly_chart(fig_corr)
    _render_chart_explanation(
        explanation_title,
        explanation_text,
        accent=BRAND_COLORS['hero']
    )
    if plot_compaction_messages:
        st.caption("Para mantener fluida la página, las series largas se muestran resumidas automáticamente por franjas de tiempo.")

    if selected_cortinas and not cortina_traces and selected_sensors:
        st.info('No hay información de motores para el periodo seleccionado. Se muestran únicamente las variables ambientales.')


def _build_focus_variable_chart(df_variables, fecha_variables, variable_name, chart_title, block_label=None):
    if df_variables.empty or 'DateTime' not in df_variables.columns or variable_name not in df_variables.columns:
        return None

    chart_df = df_variables[['DateTime', variable_name]].dropna(subset=['DateTime', variable_name]).copy()
    if chart_df.empty:
        return None

    fecha_inicio, fecha_fin = fecha_variables
    multi_day_view = fecha_inicio != fecha_fin
    chart_df, _ = _prepare_sensor_series_for_plot(chart_df, variable_name, multi_day_view=multi_day_view)
    hover_time_format = '%d/%m %H:%M' if multi_day_view else '%H:%M'
    xaxis_tickformat = '%d/%m' if multi_day_view else '%H:%M'
    xaxis_title = 'Fecha' if multi_day_view else 'Hora del día'
    resolved_title = chart_title if not block_label else f'{chart_title} | {block_label}'
    mini_chart_xaxis_range = None

    if not multi_day_view:
        min_time = pd.Timestamp(chart_df['DateTime'].min()).floor('30min').to_pydatetime()
        max_time = pd.Timestamp(chart_df['DateTime'].max()).ceil('30min').to_pydatetime()
        mini_chart_xaxis_range = [min_time, max_time]

    unit_label = VARIABLE_UNITS.get(variable_name, '')
    yaxis_title = VARIABLE_LABELS.get(variable_name, variable_name)
    color = VARIABLE_COLORS.get(variable_name, BRAND_COLORS['hero'])

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=chart_df['DateTime'],
            y=chart_df[variable_name],
            name=variable_name,
            mode='lines' if multi_day_view else 'lines+markers',
            line=dict(color=color, width=2.5),
            marker=dict(size=5, color=color),
            hovertemplate=(
                f'<b>%{{x|{hover_time_format}}}</b><br>'
                f'{variable_name}: %{{y:.2f}} {unit_label}'
                '<extra></extra>'
            )
        )
    )
    fig.update_layout(
        title=dict(
            text=resolved_title,
            x=0,
            xanchor='left',
            font=dict(size=16, color=BRAND_COLORS['graphite'], family='Montserrat, sans-serif')
        ),
        xaxis=dict(
            title=xaxis_title,
            tickformat=xaxis_tickformat,
            tickmode='linear' if not multi_day_view else 'auto',
            dtick=30 * 60 * 1000 if not multi_day_view else None,
            range=mini_chart_xaxis_range,
            showgrid=True,
            gridcolor='rgba(76, 70, 120, 0.07)',
            zeroline=False,
            tickfont=dict(size=10, family='Montserrat, sans-serif', color=BRAND_COLORS['graphite'])
        ),
        yaxis=dict(
            title=yaxis_title,
            showgrid=True,
            gridcolor='rgba(76, 70, 120, 0.07)',
            zeroline=False,
            tickfont=dict(size=10, family='Montserrat, sans-serif', color=BRAND_COLORS['graphite'])
        ),
        template='plotly_white',
        paper_bgcolor='rgba(255,255,255,0)',
        plot_bgcolor='rgba(250,248,243,0.65)',
        hovermode='x unified',
        showlegend=False,
        height=TEMP_FOCUS_CHART_HEIGHT,
        margin=dict(l=52, r=24, t=58, b=44),
        font=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['graphite'])
    )
    return fig


def _render_focus_chart_grid(df_variables, fecha_variables, block_label=None, heading=None):
    if df_variables.empty:
        return

    figures = [
        _build_focus_variable_chart(
            df_variables,
            fecha_variables,
            variable_name,
            chart_title,
            block_label=block_label
        )
        for enabled, variable_name, chart_title in FOCUS_CHART_CONFIGS
        if enabled
    ]
    figures = [fig for fig in figures if fig is not None]

    if not figures:
        return

    if heading:
        st.markdown(f"#### {heading}")
        focus_description = (
            'Estas gráficas separan las variables del bloque seleccionado para ver cada comportamiento sin mezclar escalas. Úsalas para detectar picos, caídas o franjas del día con cambios fuertes.'
            if 'externa' not in str(heading).lower() else
            'Estas gráficas muestran las mismas variables medidas por la estación externa. Sirven como referencia para comparar si el bloque se comportó diferente al ambiente exterior.'
        )
        _render_chart_explanation(
            'Variables ambientales individuales',
            focus_description,
            accent=BRAND_COLORS['hero']
        )

    if TEMP_FOCUS_CHART_PLACEMENT == 'below':
        for start_index in range(0, len(figures), 2):
            row_columns = st.columns(TEMP_FOCUS_CHART_COLUMN_LAYOUT)
            for column, figure in zip(row_columns, figures[start_index:start_index + 2]):
                with column:
                    _plotly_chart(figure)
    elif TEMP_FOCUS_CHART_PLACEMENT == 'left':
        left_col, right_col = st.columns(TEMP_FOCUS_CHART_COLUMN_LAYOUT)
        with left_col:
            _plotly_chart(figures[0])
    elif TEMP_FOCUS_CHART_PLACEMENT == 'right':
        left_col, right_col = st.columns(TEMP_FOCUS_CHART_COLUMN_LAYOUT)
        with right_col:
            _plotly_chart(figures[0])
    else:
        _plotly_chart(figures[0])


def _build_motor_focus_chart(datos_cortinas_sel, fecha_variables, block_label=None):
    if not MOTOR_FOCUS_CHART_ENABLED or datos_cortinas_sel.empty:
        return None

    fecha_inicio, fecha_fin = fecha_variables
    multi_day_view = fecha_inicio != fecha_fin
    hover_time_format = '%d/%m %H:%M' if multi_day_view else '%H:%M'
    xaxis_tickformat = '%d/%m' if multi_day_view else '%H:%M'
    xaxis_title = 'Fecha' if multi_day_view else 'Hora del día'

    fig_motor = go.Figure()
    profile_times = []

    for motor_name in MOTOR_VARIABLES:
        df_state = pd.DataFrame()
        for config in SIDE_CONFIGS.values():
            if config['element_col'] not in datos_cortinas_sel.columns:
                continue
            df_state = _build_cortina_apertura_profile(datos_cortinas_sel, motor_name, config)
            if not df_state.empty:
                break
        if df_state.empty:
            continue

        profile_times.extend(pd.to_datetime(df_state['Hora'], errors='coerce').dropna().tolist())
        color = CORTINA_COLORS.get(motor_name, BRAND_COLORS['hero'])
        fig_motor.add_trace(
            go.Scatter(
                x=df_state['Hora'],
                y=df_state['Apertura'],
                name=motor_name,
                mode='lines+markers',
                line=dict(color=color, width=2.4, shape='hv'),
                marker=dict(size=4, color=color),
                hovertemplate=(
                    f'<b>%{{x|{hover_time_format}}}</b><br>'
                    f'{motor_name}: %{{y:.0f}}% abierto'
                    '<extra></extra>'
                )
            )
        )

    if not fig_motor.data:
        return None

    xaxis_range = None
    if not multi_day_view and profile_times:
        min_time = pd.Timestamp(min(profile_times)).floor('30min').to_pydatetime()
        max_time = pd.Timestamp(max(profile_times)).ceil('30min').to_pydatetime()
        xaxis_range = [min_time, max_time]

    resolved_title = MOTOR_FOCUS_CHART_TITLE if not block_label else f'{MOTOR_FOCUS_CHART_TITLE} | {block_label}'
    fig_motor.update_layout(
        title=dict(
            text=resolved_title,
            x=0,
            xanchor='left',
            font=dict(size=16, color=BRAND_COLORS['graphite'], family='Montserrat, sans-serif')
        ),
        xaxis=dict(
            title=xaxis_title,
            tickformat=xaxis_tickformat,
            tickmode='linear' if not multi_day_view else 'auto',
            dtick=30 * 60 * 1000 if not multi_day_view else None,
            range=xaxis_range,
            showgrid=True,
            gridcolor='rgba(76, 70, 120, 0.07)',
            zeroline=False,
            tickfont=dict(size=10, family='Montserrat, sans-serif', color=BRAND_COLORS['graphite'])
        ),
        yaxis=dict(
            title='Apertura (%)',
            range=[0, 100],
            showgrid=True,
            gridcolor='rgba(76, 70, 120, 0.07)',
            zeroline=False,
            tickfont=dict(size=10, family='Montserrat, sans-serif', color=BRAND_COLORS['graphite'])
        ),
        template='plotly_white',
        paper_bgcolor='rgba(255,255,255,0)',
        plot_bgcolor='rgba(250,248,243,0.65)',
        hovermode='x unified',
        height=TEMP_FOCUS_CHART_HEIGHT + 20,
        margin=dict(l=52, r=24, t=58, b=44),
        font=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['graphite']),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='left',
            x=0,
            font=dict(size=11, family='Montserrat, sans-serif', color=BRAND_COLORS['graphite'])
        )
    )
    return fig_motor


def _render_temperature_focus_chart(df_variables, fecha_variables, block_label=None, df_external=None, datos_cortinas_sel=None):
    if not any(enabled for enabled, _, _ in FOCUS_CHART_CONFIGS) and not MOTOR_FOCUS_CHART_ENABLED:
        return

    internal_available = isinstance(df_variables, pd.DataFrame) and not df_variables.empty
    external_available = isinstance(df_external, pd.DataFrame) and not df_external.empty
    motor_fig = _build_motor_focus_chart(datos_cortinas_sel, fecha_variables, block_label=block_label)

    if not internal_available and not external_available and motor_fig is None:
        return

    if internal_available:
        _render_focus_chart_grid(
            df_variables,
            fecha_variables,
            block_label=block_label,
            heading=FOCUS_CHARTS_INTERNAL_HEADING
        )

    if external_available:
        _render_focus_chart_grid(
            df_external,
            fecha_variables,
            block_label='Estación externa',
            heading=FOCUS_CHARTS_EXTERNAL_HEADING
        )

    if motor_fig is not None:
        st.markdown(f"#### {MOTOR_FOCUS_CHART_TITLE}")
        _render_chart_explanation(
            'Apertura de frentes y puertas',
            'Esta gráfica muestra cuándo y cuánto se abrieron los motores del bloque. Ayuda a explicar cambios de temperatura, humedad o radiación después de movimientos de ventilación.',
            accent=BRAND_COLORS['hero']
        )
        _plotly_chart(motor_fig)

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


def _get_block_analysis_color(block_name, variable_name=None):
    block_identifier = _extract_block_identifier(block_name)
    return BLOCK_ANALYSIS_COLORS.get(block_identifier, VARIABLE_COLORS.get(variable_name, BRAND_COLORS['hero']))


def _format_block_display_name(block_name):
    raw_name = str(block_name)
    if raw_name.upper().startswith('ECOWITT'):
        return raw_name

    block_identifier = _extract_block_identifier(block_name)
    if block_identifier in SPECIAL_BLOCK_LABELS:
        return SPECIAL_BLOCK_LABELS[block_identifier]
    if block_identifier and str(block_identifier).isdigit():
        return f'Bloque {block_identifier}'
    return raw_name


def _build_hourly_block_analysis(df_variables, variable_name):
    required_cols = {'DateTime', 'Bloque', variable_name}
    if df_variables.empty or not required_cols.issubset(df_variables.columns):
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    data = df_variables[['DateTime', 'Bloque', variable_name]].dropna(subset=['DateTime', 'Bloque', variable_name]).copy()
    if data.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # Normaliza pequeñas desviaciones del Excel como 01:31 o 01:32
    # para consolidar la lectura en franjas limpias de 30 minutos.
    data['FranjaDateTime'] = data['DateTime'].dt.round('30min')
    data['FranjaMinutos'] = data['FranjaDateTime'].dt.hour * 60 + data['FranjaDateTime'].dt.minute
    data['Franja'] = data['FranjaDateTime'].dt.strftime('%H:%M')

    grouped = (
        data.groupby(['FranjaMinutos', 'Franja', 'Bloque'], as_index=False)
        .agg(
            Promedio=(variable_name, 'mean'),
            DesviacionEstandar=(variable_name, lambda serie: serie.std(ddof=1) if len(serie) > 1 else 0.0),
            Varianza=(variable_name, lambda serie: serie.var(ddof=1) if len(serie) > 1 else 0.0),
            Registros=(variable_name, 'count')
        )
        .sort_values(['FranjaMinutos', 'Bloque'])
        .reset_index(drop=True)
    )
    grouped['DesviacionEstandar'] = grouped['DesviacionEstandar'].fillna(0.0)
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
    pivot_desviacion = (
        grouped.pivot(index=base_columns, columns='Bloque', values='DesviacionEstandar')
        .reset_index()
        .sort_values('FranjaMinutos')
        .reindex(columns=base_columns + ordered_blocks)
    )

    return grouped, pivot_promedio, pivot_varianza, pivot_desviacion


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


def _render_analysis_block_color_reference(grouped_df, variable_name=None):
    if grouped_df.empty or 'Bloque' not in grouped_df.columns:
        return

    ordered_blocks = _sort_block_names(grouped_df['Bloque'].dropna().unique().tolist())
    if not ordered_blocks:
        return

    chips_html = []
    for block_name in ordered_blocks:
        block_label = _format_block_display_name(block_name)
        color = _get_block_analysis_color(block_name, variable_name)
        chips_html.append(
            (
                '<div style="display:inline-flex;align-items:center;gap:0.45rem;'
                'padding:0.38rem 0.74rem;border-radius:999px;'
                'background:rgba(255,255,255,0.86);border:1px solid rgba(76, 70, 120, 0.10);'
                'box-shadow:0 8px 18px rgba(42, 46, 53, 0.05);'
                'margin:0 0.42rem 0.42rem 0;font-family:\'Montserrat\', sans-serif;'
                f'font-size:0.86rem;color:{BRAND_COLORS["graphite"]};white-space:nowrap;">'
                f'<div style="width:0.72rem;height:0.72rem;border-radius:999px;background:{color};'
                'box-shadow:inset 0 0 0 1px rgba(255,255,255,0.78);flex:0 0 auto;"></div>'
                f'<div>{html.escape(block_label)}</div>'
                '</div>'
            )
        )

    reference_html = (
        '<div style="margin:0.35rem 0 0.9rem 0;">'
        '<p class="analysis-note" style="margin-bottom:0.5rem;"><strong>Referencia de colores por bloque</strong></p>'
        '<div style="display:flex;flex-wrap:wrap;align-items:center;gap:0.18rem 0.22rem;">'
        f'{"".join(chips_html)}'
        '</div>'
        '</div>'
    )
    st.markdown(reference_html, unsafe_allow_html=True)


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
    if metric_column == 'Promedio':
        metric_title = 'Promedio por franja horaria'
    elif metric_column == 'DesviacionEstandar':
        metric_title = 'Desviacion estandar por franja horaria'
    else:
        metric_title = 'Varianza por franja horaria'

    metric_label = VARIABLE_LABELS.get(variable_name, variable_name)
    fig = go.Figure()
    for block_name in ordered_blocks:
        serie = grouped_df[grouped_df['Bloque'] == block_name].sort_values('FranjaMinutos')
        if serie.empty:
            continue

        block_label = _format_block_display_name(block_name)
        color = _get_block_analysis_color(block_name, variable_name)
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
            font=dict(family='Montserrat', size=20, color=BRAND_COLORS['ink'])
        ),
        hovermode='x unified',
        template='plotly_white',
        font=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['graphite']),
        hoverlabel=dict(
            bgcolor='rgba(249, 246, 240, 0.98)',
            bordercolor='rgba(76, 70, 120, 0.16)',
            font=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['graphite'], size=12)
        ),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.06,
            xanchor='left',
            x=0,
            traceorder='normal',
            font=dict(size=11, family='Montserrat, sans-serif', color=BRAND_COLORS['graphite']),
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
            tickfont=dict(size=10, family='Montserrat, sans-serif', color=BRAND_COLORS['graphite']),
            gridcolor='rgba(76, 70, 120, 0.07)',
            linecolor='rgba(45, 48, 64, 0.18)',
            zeroline=False,
            automargin=True
        ),
        yaxis=dict(
            title=(
                '<b>Promedio</b>' if metric_column == 'Promedio' else
                '<b>Desviacion estandar</b>' if metric_column == 'DesviacionEstandar' else
                '<b>Varianza</b>'
            ),
            tickfont=dict(size=11, family='Montserrat, sans-serif', color=BRAND_COLORS['graphite']),
            gridcolor='rgba(76, 70, 120, 0.07)',
            linecolor='rgba(45, 48, 64, 0.18)',
            zerolinecolor='rgba(45, 48, 64, 0.10)'
        )
    )

    metric_description = (
        'Cada punto resume el valor promedio de una variable en una franja horaria. Úsalo para comparar el comportamiento típico entre bloques y ubicar las horas de mayor o menor intensidad.'
        if metric_column == 'Promedio' else
        'Cada punto muestra cuánto se alejan, en promedio, las mediciones de su valor central dentro de esa franja horaria. Valores bajos sugieren estabilidad; valores altos indican una dispersión más fuerte.'
        if metric_column == 'DesviacionEstandar' else
        'Cada punto muestra qué tanto variaron las mediciones dentro de esa franja horaria durante el periodo. Valores cercanos a cero indican estabilidad; valores altos indican cambios más fuertes.'
    )
    _plotly_chart(
        fig,
        config={
            'displaylogo': False,
            'responsive': True,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d']
        }
    )
    _render_analysis_block_color_reference(grouped_df, variable_name)
    _render_chart_explanation(
        f'{metric_title} - {metric_label}',
        metric_description,
        accent=VARIABLE_COLORS.get(variable_name, BRAND_COLORS['hero'])
    )


def _collect_analysis_metrics(df_source, tab_label, variable_options=None):
    metrics_data = {}
    if not isinstance(df_source, pd.DataFrame) or df_source.empty:
        return metrics_data

    variable_options = variable_options or SENSOR_VARIABLES
    for variable_name in variable_options:
        required_cols = {'DateTime', 'Bloque', variable_name}
        if not required_cols.issubset(df_source.columns):
            continue

        valid_rows = df_source['DateTime'].notna() & df_source['Bloque'].notna()
        series = pd.to_numeric(df_source.loc[valid_rows, variable_name], errors='coerce').dropna()
        if series.empty:
            continue

        if tab_label == "Promedio":
            principal_value = series.mean()
        elif tab_label == "Desviacion estandar":
            principal_value = series.std(ddof=1) if len(series) > 1 else 0.0
        else:
            principal_value = series.var(ddof=1) if len(series) > 1 else 0.0

        metrics_data[variable_name] = {
            'principal': principal_value,
            'minimo': series.min(),
            'maximo': series.max()
        }

    return metrics_data


def _format_metric_card_value(value, decimals=2, scientific_threshold=100000):
    numeric_value = pd.to_numeric(pd.Series([value]), errors='coerce').iloc[0]
    if pd.isna(numeric_value):
        return "Sin dato"

    numeric_value = float(numeric_value)
    if abs(numeric_value) >= scientific_threshold:
        mantissa, exponent = f"{numeric_value:.{decimals}e}".split("e")
        return f"{mantissa} &times; 10<sup>{int(exponent)}</sup>"

    return f"{numeric_value:.{decimals}f}"


def _format_analysis_unit_text(unit):
    return str(unit or '').replace('Âµmol mâ»Â² sâ»Â¹', 'Âµmol/mÂ²/s').replace('µmol m⁻² s⁻¹', 'µmol/m²/s').replace('µmol m-2 s-1', 'µmol/m²/s')


def _build_analysis_distribution_table(df_source, variable_name, group_col='Bloque', group_label='Bloque'):
    if not isinstance(df_source, pd.DataFrame) or df_source.empty:
        return pd.DataFrame()
    if group_col not in df_source.columns or variable_name not in df_source.columns:
        return pd.DataFrame()

    data = df_source[[group_col, variable_name]].copy()
    data[group_col] = data[group_col].fillna('Sin grupo')
    data[variable_name] = pd.to_numeric(data[variable_name], errors='coerce')
    data = data.dropna(subset=[variable_name])
    if data.empty:
        return pd.DataFrame()

    records = []
    for group_name, group_df in data.groupby(group_col, dropna=False):
        series = group_df[variable_name].dropna()
        if series.empty:
            continue

        mean_value = series.mean()
        std_value = series.std(ddof=1) if len(series) > 1 else 0.0
        var_value = series.var(ddof=1) if len(series) > 1 else 0.0
        min_value = series.min()
        max_value = series.max()
        cv_value = (std_value / mean_value * 100) if mean_value not in (0, None) and not pd.isna(mean_value) else None

        records.append({
            group_label: group_name,
            'Registros': int(series.count()),
            'Promedio': mean_value,
            'Mediana': series.median(),
            'Minimo': min_value,
            'Maximo': max_value,
            'Rango': max_value - min_value,
            'Desviacion estandar': std_value,
            'Varianza': var_value,
            'Coef. variacion (%)': cv_value,
        })

    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records)


def _render_analysis_distribution_cards(
    stats_df,
    variable_name,
    unit='',
    title='Resumen estadístico',
    group_column='Bloque',
    accent_getter=None,
):
    if stats_df.empty or group_column not in stats_df.columns:
        st.info("No hay datos suficientes para construir el resumen estadístico.")
        return

    unit_text = _format_analysis_unit_text(unit)
    st.markdown(
        f'<p class="analysis-note"><strong>{html.escape(title)}</strong></p>',
        unsafe_allow_html=True
    )

    cards_html = []
    for _, row in stats_df.iterrows():
        group_name = str(row.get(group_column, 'Sin grupo'))
        accent = accent_getter(group_name) if callable(accent_getter) else BRAND_COLORS['hero']
        promedio = _format_metric_card_value(row.get('Promedio'), decimals=2)
        mediana = _format_metric_card_value(row.get('Mediana'), decimals=2)
        minimo = _format_metric_card_value(row.get('Minimo'), decimals=2)
        maximo = _format_metric_card_value(row.get('Maximo'), decimals=2)
        rango = _format_metric_card_value(row.get('Rango'), decimals=2)
        desviacion = _format_metric_card_value(row.get('Desviacion estandar'), decimals=2)
        varianza = _format_metric_card_value(row.get('Varianza'), decimals=2)
        registros = _format_metric_card_value(row.get('Registros'), decimals=0)
        cv_value = row.get('Coef. variacion (%)')
        cv_text = _format_metric_card_value(cv_value, decimals=1) if pd.notna(cv_value) else "Sin dato"

        cards_html.append(
            '<div class="analysis-stat-card" style="--analysis-accent: {accent};">'
            '<p class="analysis-stat-label">{group_name}</p>'
            '<div class="analysis-stat-main">'
            '<span class="analysis-stat-main-value">{promedio}</span>'
            '<span class="analysis-stat-unit">{unit}</span>'
            '</div>'
            '<p class="analysis-stat-subtitle">Promedio de {variable}. Mediana: <strong>{mediana}</strong>.</p>'
            '<div class="analysis-stat-mini-grid">'
            '<div class="analysis-stat-mini"><span>Minimo</span><strong>{minimo}</strong></div>'
            '<div class="analysis-stat-mini"><span>Maximo</span><strong>{maximo}</strong></div>'
            '<div class="analysis-stat-mini"><span>Rango</span><strong>{rango}</strong></div>'
            '<div class="analysis-stat-mini"><span>Desv. est.</span><strong>{desviacion}</strong></div>'
            '<div class="analysis-stat-mini"><span>Varianza</span><strong>{varianza}</strong></div>'
            '<div class="analysis-stat-mini"><span>Registros</span><strong>{registros}</strong></div>'
            '<div class="analysis-stat-mini"><span>Coef. var.</span><strong>{cv}%</strong></div>'
            '</div>'
            '</div>'.format(
                accent=html.escape(str(accent)),
                group_name=html.escape(group_name),
                promedio=promedio,
                unit=html.escape(unit_text),
                variable=html.escape(variable_name),
                mediana=mediana,
                minimo=minimo,
                maximo=maximo,
                rango=rango,
                desviacion=desviacion,
                varianza=varianza,
                registros=registros,
                cv=cv_text,
            )
        )

    cards_markup = '<div class="analysis-stat-grid">' + ''.join(cards_html) + '</div>'
    st.markdown(cards_markup, unsafe_allow_html=True)


def _build_variable_distribution_table(df_source, variables):
    if not isinstance(df_source, pd.DataFrame) or df_source.empty:
        return pd.DataFrame()

    records = []
    for variable_name in variables:
        if variable_name not in df_source.columns:
            continue

        series = pd.to_numeric(df_source[variable_name], errors='coerce').dropna()
        if series.empty:
            records.append({
                'Variable': variable_name,
                'Registros': 0,
                'Promedio': None,
                'Mediana': None,
                'Minimo': None,
                'Maximo': None,
                'Rango': None,
                'Desviacion estandar': None,
                'Varianza': None,
                'Coef. variacion (%)': None,
            })
            continue

        mean_value = series.mean()
        std_value = series.std(ddof=1) if len(series) > 1 else 0.0
        var_value = series.var(ddof=1) if len(series) > 1 else 0.0
        min_value = series.min()
        max_value = series.max()
        cv_value = (std_value / mean_value * 100) if mean_value not in (0, None) and not pd.isna(mean_value) else None

        records.append({
            'Variable': variable_name,
            'Registros': int(series.count()),
            'Promedio': mean_value,
            'Mediana': series.median(),
            'Minimo': min_value,
            'Maximo': max_value,
            'Rango': max_value - min_value,
            'Desviacion estandar': std_value,
            'Varianza': var_value,
            'Coef. variacion (%)': cv_value,
        })

    return pd.DataFrame(records)


def _render_variable_distribution_cards(stats_df, variable_configs=None, title='Resumen estadístico'):
    if stats_df.empty or 'Variable' not in stats_df.columns:
        st.info("No hay datos suficientes para construir el resumen estadístico.")
        return

    variable_configs = variable_configs or {}
    st.markdown(
        f'<p class="analysis-note"><strong>{html.escape(title)}</strong></p>',
        unsafe_allow_html=True
    )

    cards_html = []
    for _, row in stats_df.iterrows():
        variable_name = row.get('Variable', 'Variable')
        config = variable_configs.get(variable_name, {})
        display_name = _format_variable_display_title(config.get('title', variable_name))
        unit_text = _format_analysis_unit_text(config.get('unit', VARIABLE_UNITS.get(variable_name, '')))
        accent = config.get('accent', VARIABLE_COLORS.get(variable_name, BRAND_COLORS['hero']))

        promedio = _format_metric_card_value(row.get('Promedio'), decimals=2)
        mediana = _format_metric_card_value(row.get('Mediana'), decimals=2)
        minimo = _format_metric_card_value(row.get('Minimo'), decimals=2)
        maximo = _format_metric_card_value(row.get('Maximo'), decimals=2)
        rango = _format_metric_card_value(row.get('Rango'), decimals=2)
        desviacion = _format_metric_card_value(row.get('Desviacion estandar'), decimals=2)
        varianza = _format_metric_card_value(row.get('Varianza'), decimals=2)
        registros = _format_metric_card_value(row.get('Registros'), decimals=0)
        cv_value = row.get('Coef. variacion (%)')
        cv_text = _format_metric_card_value(cv_value, decimals=1) if pd.notna(cv_value) else "Sin dato"
        cv_display = f"{cv_text}%" if cv_text != "Sin dato" else cv_text

        cards_html.append(
            '<div class="analysis-stat-card" style="--analysis-accent: {accent};">'
            '<p class="analysis-stat-label">{display_name}</p>'
            '<div class="analysis-stat-main">'
            '<span class="analysis-stat-main-value">{promedio}</span>'
            '<span class="analysis-stat-unit">{unit}</span>'
            '</div>'
            '<p class="analysis-stat-subtitle">Promedio del periodo. Mediana: <strong>{mediana}</strong>.</p>'
            '<div class="analysis-stat-mini-grid">'
            '<div class="analysis-stat-mini"><span>Mínimo</span><strong>{minimo}</strong></div>'
            '<div class="analysis-stat-mini"><span>Máximo</span><strong>{maximo}</strong></div>'
            '<div class="analysis-stat-mini"><span>Rango</span><strong>{rango}</strong></div>'
            '<div class="analysis-stat-mini"><span>Desv. est.</span><strong>{desviacion}</strong></div>'
            '<div class="analysis-stat-mini"><span>Varianza</span><strong>{varianza}</strong></div>'
            '<div class="analysis-stat-mini"><span>Registros</span><strong>{registros}</strong></div>'
            '<div class="analysis-stat-mini"><span>Coef. var.</span><strong>{cv}</strong></div>'
            '</div>'
            '</div>'.format(
                accent=html.escape(str(accent)),
                display_name=html.escape(display_name),
                promedio=promedio,
                unit=html.escape(unit_text),
                mediana=mediana,
                minimo=minimo,
                maximo=maximo,
                rango=rango,
                desviacion=desviacion,
                varianza=varianza,
                registros=registros,
                cv=cv_display,
            )
        )

    st.markdown('<div class="analysis-stat-grid">' + ''.join(cards_html) + '</div>', unsafe_allow_html=True)


def _make_variable_stat_bar_chart(stats_df, metric_key, metric_label, variable_configs=None, block_label=None):
    if stats_df.empty or metric_key not in stats_df.columns or 'Variable' not in stats_df.columns:
        return None

    variable_configs = variable_configs or {}
    chart_df = stats_df[['Variable', metric_key]].copy()
    chart_df[metric_key] = pd.to_numeric(chart_df[metric_key], errors='coerce')
    chart_df = chart_df.dropna(subset=[metric_key])
    if chart_df.empty:
        return None

    chart_df['Variable visible'] = chart_df['Variable'].apply(
        lambda value: _format_variable_display_title(
            variable_configs.get(value, {}).get('title', VARIABLE_SELECTOR_LABELS.get(value, value))
        )
    )
    chart_df['Color'] = chart_df['Variable'].apply(
        lambda value: variable_configs.get(value, {}).get('accent', VARIABLE_COLORS.get(value, BRAND_COLORS['hero']))
    )

    fig = go.Figure(go.Bar(
        x=chart_df['Variable visible'],
        y=chart_df[metric_key],
        marker=dict(color=chart_df['Color'], line=dict(color='rgba(56,58,53,0.18)', width=1)),
        text=chart_df[metric_key].apply(lambda value: f"{value:,.2f}"),
        textposition='outside',
        hovertemplate='<b>%{x}</b><br>' + metric_label + ': %{y:,.2f}<extra></extra>',
    ))
    fig.update_layout(
        template='plotly_white',
        title=f"{metric_label} por variable" + (f" - {block_label}" if block_label else ""),
        height=430,
        margin=dict(l=20, r=20, t=70, b=45),
        xaxis_title='Variable',
        yaxis_title=metric_label,
        bargap=0.34,
        font=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['graphite']),
    )
    fig.update_yaxes(showgrid=True, gridcolor='rgba(84,83,134,0.10)', zeroline=False)
    fig.update_xaxes(showgrid=False)
    return fig


def _render_variable_statistics_charts(stats_df, variable_configs=None, block_label=None):
    if stats_df.empty:
        st.info("No hay datos suficientes para graficar el análisis estadístico.")
        return

    metric_options = [
        ("Promedio", "Promedio"),
        ("Mediana", "Mediana"),
        ("Mínimo", "Minimo"),
        ("Máximo", "Maximo"),
        ("Desv. est.", "Desviacion estandar"),
        ("Varianza", "Varianza"),
    ]
    metric_tabs = st.tabs([label for label, _ in metric_options])
    for tab, (metric_label, metric_key) in zip(metric_tabs, metric_options):
        with tab:
            fig = _make_variable_stat_bar_chart(
                stats_df,
                metric_key,
                metric_label,
                variable_configs=variable_configs,
                block_label=block_label
            )
            if fig is None:
                st.info(f"No hay datos suficientes para graficar {metric_label.lower()}.")
            else:
                _plotly_chart(fig)


def _build_variables_30min_report(df_variables, variables):
    if (
        not isinstance(df_variables, pd.DataFrame) or
        df_variables.empty or
        'DateTime' not in df_variables.columns
    ):
        return pd.DataFrame()

    available_variables = [var for var in variables if var in df_variables.columns]
    if not available_variables:
        return pd.DataFrame()

    working = df_variables[['DateTime', *available_variables]].copy()
    working['DateTime'] = pd.to_datetime(working['DateTime'], errors='coerce')
    working = working.dropna(subset=['DateTime'])
    if working.empty:
        return pd.DataFrame()

    for variable_name in available_variables:
        working[variable_name] = pd.to_numeric(working[variable_name], errors='coerce')

    working['FechaHora'] = working['DateTime'].dt.floor(MARLEY_TIME_BUCKET)
    average_table = working.groupby('FechaHora', as_index=False)[available_variables].mean()
    count_table = (
        working.groupby('FechaHora')[available_variables]
        .count()
        .add_suffix(' registros')
        .reset_index()
    )
    report = average_table.merge(count_table, on='FechaHora', how='left')
    report.insert(1, 'Fecha', report['FechaHora'].dt.date)
    report.insert(2, 'Hora', report['FechaHora'].dt.strftime('%H:%M'))
    return report


def _build_cortinas_30min_report(datos_cortinas, selected_range, block_label=None):
    if not isinstance(datos_cortinas, pd.DataFrame) or datos_cortinas.empty:
        return pd.DataFrame()

    motores = _get_available_cortina_vars(datos_cortinas)
    if not motores:
        return pd.DataFrame()

    start_date, end_date = selected_range
    full_index = pd.date_range(
        start=pd.Timestamp(start_date),
        end=pd.Timestamp(end_date) + MARLEY_SERIES_END_OFFSET,
        freq=MARLEY_TIME_BUCKET
    )
    report_rows = []

    for motor_name in motores:
        motor_profiles = []
        for config in SIDE_CONFIGS.values():
            profile = _build_cortina_apertura_profile(datos_cortinas, motor_name, config)
            if not profile.empty and {'Hora', 'Apertura'}.issubset(profile.columns):
                motor_profiles.append(profile[['Hora', 'Apertura', 'Evento']].copy())

        if not motor_profiles:
            continue

        profile = pd.concat(motor_profiles, ignore_index=True)
        profile['Hora'] = pd.to_datetime(profile['Hora'], errors='coerce')
        profile['Apertura'] = pd.to_numeric(profile['Apertura'], errors='coerce')
        profile = profile.dropna(subset=['Hora']).sort_values('Hora')
        if profile.empty:
            continue

        timeline_index = pd.DatetimeIndex(profile['Hora'].drop_duplicates()).union(full_index).sort_values()
        timeline = (
            profile.drop_duplicates(subset=['Hora'], keep='last')
            .set_index('Hora')
            .reindex(timeline_index)
            .ffill()
            .reindex(full_index)
            .reset_index()
            .rename(columns={'index': 'FechaHora'})
        )
        timeline['Bloque'] = block_label or 'Bloque seleccionado'
        timeline['Motor'] = motor_name
        timeline['Fecha'] = timeline['FechaHora'].dt.date
        timeline['Hora'] = timeline['FechaHora'].dt.strftime('%H:%M')
        timeline.rename(columns={'Apertura': 'Apertura estimada (%)', 'Evento': 'Ultimo evento'}, inplace=True)
        report_rows.append(timeline[['FechaHora', 'Fecha', 'Hora', 'Bloque', 'Motor', 'Apertura estimada (%)', 'Ultimo evento']])

    return pd.concat(report_rows, ignore_index=True) if report_rows else pd.DataFrame()


def _build_cortinas_event_report(datos_cortinas):
    if not isinstance(datos_cortinas, pd.DataFrame) or datos_cortinas.empty:
        return pd.DataFrame()

    preferred_columns = [
        'Fecha',
        'Frente A',
        'Hora Apertura A',
        '% Apertura A',
        'Duracion Apertura A',
        'Hora Cierre A',
        '% Cierre A',
        'Duracion Cierre A',
        'Anotacion A',
        'Frente B',
        'Hora Apertura B',
        '% Apertura B',
        'Duracion Apertura B',
        'Hora Cierre B',
        '% Cierre B',
        'Duracion Cierre B',
        'Anotacion B',
        'Culatas %',
    ]
    available_columns = [column for column in preferred_columns if column in datos_cortinas.columns]
    return datos_cortinas[available_columns].copy() if available_columns else datos_cortinas.copy()


def _render_analysis_metric_cards_row(metrics_data, tab_label, single_day_analysis, heading=None, variable_options=None):
    if not metrics_data:
        return

    if heading:
        st.markdown(
            f'<p class="analysis-note"><strong>{html.escape(heading)}</strong></p>',
            unsafe_allow_html=True
        )

    variable_options = [variable for variable in (variable_options or SENSOR_VARIABLES) if variable in metrics_data]
    metric_cols = st.columns(min(4, max(1, len(variable_options))))
    for idx, variable_name in enumerate(variable_options):
        if variable_name not in metrics_data:
            continue

        with metric_cols[idx % len(metric_cols)]:
            stats_payload = metrics_data[variable_name]
            value = stats_payload['principal']
            color = VARIABLE_COLORS.get(variable_name, BRAND_COLORS['graphite'])
            unit = VARIABLE_UNITS.get(variable_name, '')
            card_unit = unit.replace('µmol m⁻² s⁻¹', 'µmol/m²/s').replace('µmol m-2 s-1', 'µmol/m²/s')
            min_value = stats_payload['minimo']
            max_value = stats_payload['maximo']

            if tab_label == "Promedio":
                display_value = _format_metric_card_value(value, decimals=1)
                if single_day_analysis:
                    descriptor = "Promedio general de todas las mediciones del día seleccionado."
                    footer_label = "Promedio general del día"
                else:
                    descriptor = "Promedio general de todas las mediciones del rango seleccionado."
                    footer_label = "Promedio general del periodo"
            elif tab_label == "Desviacion estandar":
                display_value = _format_metric_card_value(value, decimals=2)
                descriptor = "Desviacion estandar general calculada con todas las mediciones del rango seleccionado."
                footer_label = "Desviacion estandar del periodo"
                if single_day_analysis:
                    display_value = "0.00"
                    descriptor = "En un solo dia la desviacion estandar se reporta en 0 por consistencia analitica."
                    footer_label = "Desviacion estandar en un dia"
            else:
                display_value = _format_metric_card_value(value, decimals=2)
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
                    font-family: 'Montserrat', sans-serif;
                    font-size: 13px;
                    color: {color};
                    font-weight: 500;
                    margin: 0 0 12px 0;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                ">{html.escape(variable_name)}</p>
                <div style="display: flex; align-items: baseline; gap: 0.45rem; flex-wrap: wrap;">
                    <p style="
                        font-family: 'Montserrat', sans-serif;
                        font-size: 1.72rem;
                        font-weight: 700;
                        color: {BRAND_COLORS['ink']};
                        margin: 0;
                        line-height: 1.08;
                        overflow-wrap: anywhere;
                    ">{display_value}</p>
                    <p style="
                        font-family: 'Montserrat', sans-serif;
                        font-size: 0.78rem;
                        color: {BRAND_COLORS['graphite']};
                        margin: 0;
                        font-weight: 700;
                        word-break: break-word;
                        line-height: 1.3;
                        max-width: 5.8rem;
                    ">{card_unit}</p>
                </div>
                <p style="
                    font-family: 'Montserrat', sans-serif;
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
                            font-family: 'Montserrat', sans-serif;
                            font-size: 10px;
                            color: {BRAND_COLORS['graphite']};
                            margin: 0 0 4px 0;
                            text-transform: uppercase;
                        ">Mínimo</p>
                        <p style="
                            font-family: 'Montserrat', sans-serif;
                            font-size: 14px;
                            font-weight: 700;
                            color: {BRAND_COLORS['ink']};
                            margin: 0;
                        ">{min_value:.2f}</p>
                    </div>
                    <div style="text-align: right;">
                        <p style="
                            font-family: 'Montserrat', sans-serif;
                            font-size: 10px;
                            color: {BRAND_COLORS['graphite']};
                            margin: 0 0 4px 0;
                            text-transform: uppercase;
                        ">Máximo</p>
                        <p style="
                            font-family: 'Montserrat', sans-serif;
                            font-size: 14px;
                            font-weight: 700;
                            color: {BRAND_COLORS['ink']};
                            margin: 0;
                        ">{max_value:.2f}</p>
                    </div>
                </div>
                <p style="
                    font-family: 'Montserrat', sans-serif;
                    font-size: 11px;
                    color: {color};
                    margin: 10px 0 0 0;
                    font-weight: 500;
                ">{footer_label}</p>
            </div>
            '''
            st.markdown(metric_card_html, unsafe_allow_html=True)


def _render_hourly_metric_visual(grouped_df, variable_name, tab_label, single_day_analysis):
    if tab_label == "Promedio":
        _render_hourly_metric_chart(grouped_df, variable_name, 'Promedio')
    elif tab_label == "Desviacion estandar" and single_day_analysis:
        _render_chart_explanation(
            f'Desviacion estandar por franja horaria - {VARIABLE_SELECTOR_LABELS.get(variable_name, variable_name)}',
            'La desviacion estandar necesita al menos dos dias para comparar la misma franja horaria entre dias. Con un solo dia se muestra la aclaracion, pero no se grafica una dispersion representativa.',
            accent=VARIABLE_COLORS.get(variable_name, BRAND_COLORS['hero'])
        )
        st.info(
            f'Desviacion estandar de un solo dia para {VARIABLE_SELECTOR_LABELS.get(variable_name, variable_name)}: '
            'se muestra en 0 porque con un unico dia no hay suficiente repeticion por franja horaria para calcular una dispersion representativa.'
        )
    elif tab_label == "Desviacion estandar":
        _render_hourly_metric_chart(grouped_df, variable_name, 'DesviacionEstandar')
    elif single_day_analysis:
        _render_chart_explanation(
            f'Varianza por franja horaria - {VARIABLE_SELECTOR_LABELS.get(variable_name, variable_name)}',
            'La varianza necesita al menos dos dias para comparar la misma franja horaria entre dias. Con un solo dia se muestra la aclaracion, pero no se grafica una variacion representativa.',
            accent=VARIABLE_COLORS.get(variable_name, BRAND_COLORS['hero'])
        )
        st.info(
            f'Varianza de un solo dia para {VARIABLE_SELECTOR_LABELS.get(variable_name, variable_name)}: '
            'se muestra en 0 porque con un unico dia no hay suficiente repeticion por franja horaria para calcular una dispersion representativa.'
        )
    else:
        _render_hourly_metric_chart(grouped_df, variable_name, 'Varianza')


def _render_hourly_metric_table(
    tab_label,
    pivot_promedio,
    pivot_varianza,
    pivot_desviacion,
    variable_name,
    period_text,
    variable_state_key,
):
    if tab_label == "Promedio":
        table = _prepare_hourly_pivot_display(pivot_promedio)
        metric_slug = "promedio"
        label = "promedio"
    elif tab_label == "Desviacion estandar":
        table = _prepare_hourly_pivot_display(pivot_desviacion)
        metric_slug = "desviacion_estandar"
        label = "desviacion estandar"
    else:
        table = _prepare_hourly_pivot_display(pivot_varianza)
        metric_slug = "varianza"
        label = "varianza"

    if table.empty:
        st.info("No hay datos suficientes para construir la tabla de esta metrica.")
        return

    st.caption("Tabla calculada con los mismos valores de la grafica visible, ordenada por franja horaria.")
    report_slug = _build_report_slug("ponderosa", metric_slug, variable_name, period_text, variable_state_key)
    _render_table_download_button(
        table,
        f"Descargar tabla de {label}",
        f"ponderosa_{metric_slug}_{report_slug}.xlsx",
        f"descargar_ponderosa_{metric_slug}_{report_slug}",
        help_text="Descarga un Excel con la tabla calculada a partir de la grafica visible."
    )
    _dataframe(table)


def _render_hourly_analysis_view(
    df_variables,
    fecha_variables,
    selected_blocks,
    df_external_station=None,
    forced_metric=None,
    variable_options=None,
    variable_state_key="analisis_variable_option"
):
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

    metric_options = ["Promedio", "Desviacion estandar", "Varianza"]
    if forced_metric in metric_options:
        tab_label = forced_metric
    else:
        if st.session_state.get("analisis_metric_option") not in metric_options:
            st.session_state["analisis_metric_option"] = metric_options[0]
        tab_label = st.segmented_control(
            "Métrica del análisis",
            options=metric_options,
            key="analisis_metric_option",
            help="Calcula solo la métrica visible para mantener esta vista más rápida.",
            width="stretch"
        )

    variable_options = variable_options or SENSOR_VARIABLES
    if st.session_state.get(variable_state_key) not in variable_options:
        st.session_state[variable_state_key] = variable_options[0]
    variable_name = st.segmented_control(
        "Variable del análisis",
        options=variable_options,
        format_func=lambda value: VARIABLE_SELECTOR_LABELS.get(value, VARIABLE_LABELS.get(value, value)),
        key=variable_state_key,
        help="Calcula solo la variable seleccionada para evitar cargar todas las gráficas a la vez.",
        width="stretch"
    )

    grouped_df, pivot_promedio, pivot_varianza, pivot_desviacion = _build_hourly_block_analysis(df_variables, variable_name)
    if grouped_df.empty:
        st.info(f'No se encontraron datos para {variable_name} en el rango seleccionado.')
        return

    if tab_label == "Promedio":
        _render_hourly_metric_chart(grouped_df, variable_name, 'Promedio')
        promedio_table = _prepare_hourly_pivot_display(pivot_promedio)
        with st.expander('Ver tabla dinámica de promedio', expanded=False):
            report_slug = _build_report_slug("ponderosa", "promedio", variable_name, period_text, variable_state_key)
            _render_table_download_button(
                promedio_table,
                "Descargar tabla de promedio",
                f"ponderosa_promedio_{report_slug}.xlsx",
                f"descargar_ponderosa_promedio_{report_slug}",
                help_text="Descarga un Excel con la tabla calculada a partir de la gráfica visible."
            )
            _dataframe(promedio_table)
    elif tab_label == "Desviacion estandar" and single_day_analysis:
        _render_chart_explanation(
            f'Desviacion estandar por franja horaria - {VARIABLE_SELECTOR_LABELS.get(variable_name, variable_name)}',
            'La desviacion estandar necesita al menos dos dias para comparar la misma franja horaria entre dias. Con un solo dia se muestra la aclaracion, pero no se grafica una dispersion representativa.',
            accent=VARIABLE_COLORS.get(variable_name, BRAND_COLORS['hero'])
        )
        st.info(
            f'Desviacion estandar de un solo dia para {VARIABLE_SELECTOR_LABELS.get(variable_name, variable_name)}: '
            'se muestra en 0 porque con un unico dia no hay suficiente repeticion por franja horaria para calcular una dispersion representativa.'
        )
    elif tab_label == "Desviacion estandar":
        _render_hourly_metric_chart(grouped_df, variable_name, 'DesviacionEstandar')
        desviacion_table = _prepare_hourly_pivot_display(pivot_desviacion)
        with st.expander('Ver tabla dinamica de desviacion estandar', expanded=False):
            report_slug = _build_report_slug("ponderosa", "desviacion_estandar", variable_name, period_text, variable_state_key)
            _render_table_download_button(
                desviacion_table,
                "Descargar tabla de desviacion estandar",
                f"ponderosa_desviacion_estandar_{report_slug}.xlsx",
                f"descargar_ponderosa_desviacion_estandar_{report_slug}",
                help_text="Descarga un Excel con la tabla calculada a partir de la grafica visible."
            )
            _dataframe(desviacion_table)
    elif single_day_analysis:
        _render_chart_explanation(
            f'Varianza por franja horaria - {VARIABLE_SELECTOR_LABELS.get(variable_name, variable_name)}',
            'La varianza necesita al menos dos días para comparar la misma franja horaria entre días. Con un solo día se muestra la aclaración, pero no se grafica una variación representativa.',
            accent=VARIABLE_COLORS.get(variable_name, BRAND_COLORS['hero'])
        )
        st.info(
            f'Varianza de un solo día para {VARIABLE_SELECTOR_LABELS.get(variable_name, variable_name)}: '
            'se muestra en 0 porque con un único día no hay suficiente repetición por franja horaria para calcular una dispersión representativa.'
        )
    else:
        _render_hourly_metric_chart(grouped_df, variable_name, 'Varianza')
        varianza_table = _prepare_hourly_pivot_display(pivot_varianza)
        with st.expander('Ver tabla dinámica de varianza', expanded=False):
            report_slug = _build_report_slug("ponderosa", "varianza", variable_name, period_text, variable_state_key)
            _render_table_download_button(
                varianza_table,
                "Descargar tabla de varianza",
                f"ponderosa_varianza_{report_slug}.xlsx",
                f"descargar_ponderosa_varianza_{report_slug}",
                help_text="Descarga un Excel con la tabla calculada a partir de la gráfica visible."
            )
            _dataframe(varianza_table)

    metrics_data = _collect_analysis_metrics(df_variables, tab_label, variable_options)
    _render_analysis_metric_cards_row(metrics_data, tab_label, single_day_analysis, variable_options=variable_options)

    external_metrics_data = _collect_analysis_metrics(df_external_station, tab_label, variable_options)
    _render_analysis_metric_cards_row(
        external_metrics_data,
        tab_label,
        single_day_analysis,
        heading='Estación externa',
        variable_options=variable_options
    )

    if len(selected_blocks) == 1 and tab_label == "Promedio":
        _render_chart_explanation(
            'Promedio general del bloque',
            'Este resumen muestra el promedio consolidado del bloque seleccionado dentro del periodo filtrado y los extremos observados para cada variable.',
            accent=BRAND_COLORS['hero'],
            kicker='Cómo leer este análisis'
        )
    elif len(selected_blocks) == 1 and tab_label == "Desviacion estandar":
        _render_chart_explanation(
            'Desviacion estandar general del bloque',
            'La desviacion estandar resume cuanto se apartan las mediciones de su promedio dentro del periodo. Con un solo dia no hay dispersion temporal suficiente para una lectura util por franja.',
            accent=BRAND_COLORS['hero'],
            kicker='Como leer este analisis'
        )
    elif len(selected_blocks) == 1 and tab_label == "Varianza":
        _render_chart_explanation(
            'Varianza general del bloque',
            'La varianza resume qué tanto cambian las mediciones dentro del periodo. Con un solo día no hay dispersión temporal suficiente para una varianza útil por franja.',
            accent=BRAND_COLORS['hero'],
            kicker='Cómo leer este análisis'
        )
    elif tab_label == "Promedio":
        _render_chart_explanation(
            'Promedio comparativo entre bloques',
            'Explora cada variable para ver el valor promedio por franja horaria y comparar el comportamiento típico de los bloques seleccionados.',
            accent=BRAND_COLORS['hero'],
            kicker='Cómo leer este análisis'
        )
    elif tab_label == "Desviacion estandar":
        _render_chart_explanation(
            'Desviacion estandar comparativa entre bloques',
            'Explora cada variable para ver cuanto se dispersa cada bloque por franja horaria. Valores mas altos indican mediciones menos estables dentro del periodo analizado.',
            accent=BRAND_COLORS['hero'],
            kicker='Como leer este analisis'
        )
    else:
        _render_chart_explanation(
            'Varianza comparativa entre bloques',
            'Explora cada variable para ver qué tanto fluctúa cada bloque por franja horaria. Valores más altos indican mayor variabilidad dentro del periodo analizado.',
            accent=BRAND_COLORS['hero'],
            kicker='Cómo leer este análisis'
        )


def _render_hourly_analysis_view_organized(
    df_variables,
    fecha_variables,
    selected_blocks,
    df_external_station=None,
    forced_metric=None,
    variable_options=None,
    variable_state_key="analisis_variable_option"
):
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
    period_text = (
        fecha_inicio.strftime("%Y-%m-%d")
        if fecha_inicio == fecha_fin else
        f'{fecha_inicio.strftime("%Y-%m-%d")} a {fecha_fin.strftime("%Y-%m-%d")}'
    )
    single_day_analysis = fecha_inicio == fecha_fin

    metric_options = ["Promedio", "Desviacion estandar", "Varianza"]
    if forced_metric in metric_options:
        tab_label = forced_metric
    else:
        if st.session_state.get("analisis_metric_option") not in metric_options:
            st.session_state["analisis_metric_option"] = metric_options[0]
        tab_label = st.segmented_control(
            "Métrica del análisis",
            options=metric_options,
            key="analisis_metric_option",
            help="Calcula solo la métrica visible para mantener esta vista más rápida.",
            width="stretch"
        )

    variable_options = variable_options or SENSOR_VARIABLES
    if st.session_state.get(variable_state_key) not in variable_options:
        st.session_state[variable_state_key] = variable_options[0]
    variable_name = st.segmented_control(
        "Variable del análisis",
        options=variable_options,
        format_func=lambda value: VARIABLE_SELECTOR_LABELS.get(value, VARIABLE_LABELS.get(value, value)),
        key=variable_state_key,
        help="Calcula solo la variable seleccionada para evitar cargar todas las gráficas a la vez.",
        width="stretch"
    )

    grouped_df, pivot_promedio, pivot_varianza, pivot_desviacion = _build_hourly_block_analysis(df_variables, variable_name)
    if grouped_df.empty:
        st.info(f'No se encontraron datos para {variable_name} en el rango seleccionado.')
        return

    tab_grafica, tab_resumen, tab_tabla = st.tabs(["Gráfica", "Resumen estadístico", "Tabla"])
    with tab_grafica:
        _render_hourly_metric_visual(grouped_df, variable_name, tab_label, single_day_analysis)

    with tab_resumen:
        selected_stats = _build_analysis_distribution_table(
            df_variables,
            variable_name,
            group_col='Bloque',
            group_label='Bloque'
        )
        _render_analysis_distribution_cards(
            selected_stats,
            VARIABLE_SELECTOR_LABELS.get(variable_name, variable_name),
            unit=VARIABLE_UNITS.get(variable_name, ''),
            title=f"Resumen estadístico por bloque - {VARIABLE_SELECTOR_LABELS.get(variable_name, variable_name)}",
            group_column='Bloque',
            accent_getter=lambda group_name: _get_block_analysis_color(group_name, variable_name)
        )
        if not selected_stats.empty:
            with st.expander("Ver resumen estadístico en tabla", expanded=False):
                _dataframe(selected_stats.round(2), hide_index=True)

        metrics_data = _collect_analysis_metrics(df_variables, tab_label, variable_options)
        _render_analysis_metric_cards_row(
            metrics_data,
            tab_label,
            single_day_analysis,
            heading='Resumen de la métrica seleccionada por variable',
            variable_options=variable_options
        )

        external_metrics_data = _collect_analysis_metrics(df_external_station, tab_label, variable_options)
        _render_analysis_metric_cards_row(
            external_metrics_data,
            tab_label,
            single_day_analysis,
            heading='Estacion externa',
            variable_options=variable_options
        )

    with tab_tabla:
        _render_hourly_metric_table(
            tab_label,
            pivot_promedio,
            pivot_varianza,
            pivot_desviacion,
            variable_name,
            period_text,
            variable_state_key
        )


def _build_marley_metric_stats_source(df, variable):
    if df.empty:
        return pd.DataFrame()

    frames = []
    for source_name in MARLEY_SENSOR_NAMES:
        column_name = f"{variable} - {source_name}"
        if column_name not in df.columns:
            continue
        source_values = pd.to_numeric(df[column_name], errors='coerce').dropna()
        if source_values.empty:
            continue
        frames.append(pd.DataFrame({
            'Sensor': source_name,
            variable: source_values
        }))

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _render_marley_metric_analysis_tabs(filtered_df, selected_range, selected_variable, dashboard_mode, grouped_metric, show_marley_details):
    config = MARLEY_VARIABLES[selected_variable]
    tab_grafica, tab_resumen, tab_tabla = st.tabs(["Gráfica", "Resumen estadístico", "Tabla"])

    with tab_grafica:
        _render_chart_explanation(
            f'{dashboard_mode} por franja horaria',
            (
                'Esta gráfica muestra qué tanto se alejan las lecturas de cada sensor respecto a su valor central dentro de una misma hora del día durante el rango seleccionado. Valores bajos indican mayor estabilidad; valores altos indican una dispersión más amplia.'
                if dashboard_mode == "Desviacion estandar" else
                'Esta gráfica muestra qué tanto cambió cada sensor dentro de una misma hora del día durante el rango seleccionado. Valores bajos indican lecturas más estables; valores altos indican mayor fluctuación.'
                if dashboard_mode == "Varianza" else
                'Esta gráfica resume el valor promedio de cada sensor por franja de 30 minutos para comparar el comportamiento típico dentro del periodo seleccionado.'
            ),
            accent=config['accent']
        )
        _plotly_chart(_make_marley_hourly_metric_chart(grouped_metric, selected_variable, dashboard_mode))
        if show_marley_details:
            detail_resolution = st.radio(
                "Resolución de las gráficas individuales:",
                options=SOURCE_RESOLUTION_OPTIONS,
                horizontal=True,
                key=f"marley_{dashboard_mode.lower()}_detail_resolution",
                help=f"El análisis de {dashboard_mode.lower()} se mantiene por franja horaria; este control aplica solo a las gráficas individuales con promedio, punto por punto o valor más cercano cada 30 minutos."
            )
            _render_marley_individual_variable_charts(
                filtered_df,
                selected_range,
                resolution_label=detail_resolution
            )

    with tab_resumen:
        stats_source = _build_marley_metric_stats_source(filtered_df, selected_variable)
        stats_df = _build_analysis_distribution_table(
            stats_source,
            selected_variable,
            group_col='Sensor',
            group_label='Sensor'
        )
        _render_analysis_distribution_cards(
            stats_df,
            _format_variable_display_title(config['title']),
            unit=config['unit'],
            title=f"Resumen estadístico por sensor - {_format_variable_display_title(config['title'])}",
            group_column='Sensor',
            accent_getter=lambda sensor_name: config['colors'].get(sensor_name, config['accent'])
        )
        if not stats_df.empty:
            with st.expander("Ver resumen estadístico en tabla", expanded=False):
                _dataframe(stats_df.round(2), hide_index=True)

    with tab_tabla:
        metric_table = _prepare_marley_hourly_metric_table(grouped_metric)
        st.caption("Tabla calculada con los mismos valores de la gráfica, ordenada por franja horaria.")
        report_slug = _build_report_slug("marly", dashboard_mode, selected_variable)
        _render_table_download_button(
            metric_table,
            f"Descargar tabla de {dashboard_mode.lower()}",
            f"marly_{dashboard_mode.lower()}_{report_slug}.xlsx",
            f"descargar_marley_{dashboard_mode.lower()}_{report_slug}",
            help_text="Descarga un Excel con la tabla calculada a partir de la gráfica visible."
        )
        _dataframe(metric_table, hide_index=True)


def _build_ponderosa_ecowitt_metric_frame(ecowitt_df):
    if ecowitt_df.empty:
        return pd.DataFrame()

    df = ecowitt_df[['FechaHora', 'Fecha_Filtro', *PONDEROSA_ECOWITT_VARIABLES.keys()]].copy()
    df = df.rename(columns={'FechaHora': 'DateTime'})
    df['Bloque'] = f"ECOWITT Bloque {PONDEROSA_ECOWITT_BLOCK_CODE}"
    for variable in PONDEROSA_ECOWITT_VARIABLES:
        df[variable] = pd.to_numeric(df[variable], errors='coerce')
    return df[['DateTime', 'Fecha_Filtro', 'Bloque', *PONDEROSA_ECOWITT_VARIABLES.keys()]]


def _get_ponderosa_metric_variable_options(source_option):
    if source_option == "WIGA":
        return list(PONDEROSA_WIGA_VARIABLES.keys())
    if source_option == "ECOWITT":
        return list(PONDEROSA_ECOWITT_VARIABLES.keys())
    return list(PONDEROSA_COMPARISON_VARIABLES.keys())


def _render_ponderosa_metric_dashboard(df_variables_all, df_cortinas_all, selected_finca, metric_name):
    source_options = ["WIGA", "ECOWITT", "WIGA + ECOWITT"]
    metric_key = _build_normalized_text_key(metric_name).replace(' ', '_')

    with st.sidebar.expander("Fuente", expanded=True):
        _sidebar_field_label("filter", "Fuente del análisis")
        source_option = st.radio(
            "Analizar:",
            options=source_options,
            horizontal=False,
            key=f"ponderosa_{metric_key}_source",
            help="Elige si quieres calcular la métrica sobre WIGA, ECOWITT o ambos en la misma vista."
        )

    include_wiga = source_option in ("WIGA", "WIGA + ECOWITT")
    include_ecowitt = source_option in ("ECOWITT", "WIGA + ECOWITT")
    comparison_source = source_option == "WIGA + ECOWITT"
    wiga_block_context = (metric_key, source_option)
    if st.session_state.get(f"ponderosa_{metric_key}_wiga_block_context") != wiga_block_context:
        for state_key in list(st.session_state.keys()):
            if str(state_key).startswith(f"ponderosa_{metric_key}_wiga_block_"):
                del st.session_state[state_key]
        st.session_state[f"ponderosa_{metric_key}_wiga_block_context"] = wiga_block_context

    block_codes, variable_block_map, _ = _get_block_options(
        df_variables_all,
        df_cortinas_all,
        selected_finca=selected_finca
    )
    selected_wiga_block_names = []
    if include_wiga:
        wiga_block_codes = block_codes
        if comparison_source:
            wiga_block_codes = [
                block_code
                for block_code in block_codes
                if str(block_code) == PONDEROSA_ECOWITT_BLOCK_CODE
            ]
        with st.sidebar.expander("Bloques WIGA", expanded=True):
            if not block_codes:
                st.warning("No hay bloques WIGA disponibles para La Ponderosa.")
            elif comparison_source and not wiga_block_codes:
                st.warning(f"No se encontró el Bloque {PONDEROSA_ECOWITT_BLOCK_CODE} en los datos WIGA.")
            else:
                _sidebar_field_label("location", "Bloques incluidos")
                if comparison_source:
                    st.caption(
                        f"ECOWITT Ponderosa corresponde solo al Bloque {PONDEROSA_ECOWITT_BLOCK_CODE}; "
                        "por eso esta comparación se limita a ese bloque."
                    )
                for block_code in wiga_block_codes:
                    block_state_key = f"ponderosa_{metric_key}_wiga_block_{block_code}"
                    if block_state_key not in st.session_state:
                        st.session_state[block_state_key] = True
                    st.checkbox(
                        _format_block_display_name(block_code),
                        key=block_state_key,
                        disabled=comparison_source,
                        help=FILTER_HELP_TEXTS['bloques_comparados']
                    )

                selected_wiga_block_names = [
                    variable_block_map[block_code]
                    for block_code in wiga_block_codes
                    if st.session_state.get(f"ponderosa_{metric_key}_wiga_block_{block_code}", False)
                    and block_code in variable_block_map
                ]

    ecowitt_df = pd.DataFrame()
    if include_ecowitt:
        try:
            ecowitt_df = _load_ponderosa_ecowitt_data()
        except Exception as error:
            st.error(f"No fue posible cargar ECOWITT Ponderosa. Detalle: {error}")
            st.stop()

    available_dates_set = set()
    if include_wiga and selected_wiga_block_names:
        available_dates_set.update(_get_all_variable_dates_for_blocks(df_variables_all, selected_wiga_block_names))
    if include_ecowitt and not ecowitt_df.empty:
        available_dates_set.update(ecowitt_df['Fecha_Filtro'].dropna().unique().tolist())

    available_dates = sorted(available_dates_set)
    if not available_dates:
        st.warning("No hay fechas disponibles para la fuente seleccionada.")
        st.stop()

    min_date = available_dates[0]
    max_date = available_dates[-1]
    navigation_state_key = None
    date_state_keys = (
        f"ponderosa_{metric_key}_fecha_unica",
        f"ponderosa_{metric_key}_fecha_un_dia",
        f"ponderosa_{metric_key}_fecha_inicio",
        f"ponderosa_{metric_key}_fecha_fin",
    )
    metric_date_mode_key = f"ponderosa_{metric_key}_modo_fechas"
    for state_key in date_state_keys:
        if state_key in st.session_state and st.session_state[state_key] not in available_dates:
            del st.session_state[state_key]

    with st.sidebar.expander("Periodo", expanded=True):
        if min_date == max_date:
            fecha_unica = _date_input_with_state(
                "Seleccionar fecha:",
                default_value=max_date,
                key=f"ponderosa_{metric_key}_fecha_unica",
                min_value=min_date,
                max_value=max_date,
                help_text=FILTER_HELP_TEXTS['fecha']
            )
            fecha_unica = _get_nearest_available_date(fecha_unica, available_dates)
            selected_range = (fecha_unica, fecha_unica)
            navigation_state_key = f"ponderosa_{metric_key}_fecha_unica"
        else:
            if metric_name in ("Varianza", "Desviacion estandar"):
                modo_fechas = "Varios días"
                st.session_state[metric_date_mode_key] = modo_fechas
                st.caption("La varianza se calcula automáticamente con varios días.")
            else:
                modo_fechas = st.radio(
                    "Modo de fechas:",
                    options=["Un día", "Varios días"],
                    horizontal=True,
                    key=metric_date_mode_key,
                    help=FILTER_HELP_TEXTS['modo_fechas']
                )
            if modo_fechas == "Un día":
                fecha_unica_default = _get_nearest_available_date(
                    st.session_state.get(f"ponderosa_{metric_key}_fecha_un_dia", max_date),
                    available_dates
                )
                _sidebar_field_label("calendar", "Seleccionar fecha")
                fecha_unica = _date_input_with_state(
                    "Seleccionar fecha:",
                    default_value=fecha_unica_default,
                    key=f"ponderosa_{metric_key}_fecha_un_dia",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                fecha_unica = _get_nearest_available_date(fecha_unica, available_dates)
                selected_range = (fecha_unica, fecha_unica)
                navigation_state_key = f"ponderosa_{metric_key}_fecha_un_dia"
            else:
                default_range_end = _get_sidebar_default_range_end(min_date, max_date, default_days=7)
                fecha_inicio_default = _get_nearest_available_date(
                    st.session_state.get(f"ponderosa_{metric_key}_fecha_inicio", min_date),
                    available_dates
                )
                fecha_fin_default = _get_nearest_available_date(
                    st.session_state.get(f"ponderosa_{metric_key}_fecha_fin", default_range_end),
                    available_dates
                )
                _sidebar_field_label("calendar", "Fecha inicio")
                fecha_inicio = _date_input_with_state(
                    "Fecha inicio:",
                    default_value=fecha_inicio_default,
                    key=f"ponderosa_{metric_key}_fecha_inicio",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                _sidebar_field_label("calendar", "Fecha fin")
                fecha_fin = _date_input_with_state(
                    "Fecha fin:",
                    default_value=fecha_fin_default,
                    key=f"ponderosa_{metric_key}_fecha_fin",
                    min_value=min_date,
                    max_value=max_date,
                    help_text=FILTER_HELP_TEXTS['fecha']
                )
                fecha_inicio = _get_nearest_available_date(fecha_inicio, available_dates)
                fecha_fin = _get_nearest_available_date(fecha_fin, available_dates)
                selected_range = _normalize_sidebar_date_range(fecha_inicio, fecha_fin, min_date, max_date)

    fecha_inicio, fecha_fin = selected_range
    frames = []
    if include_wiga and selected_wiga_block_names:
        wiga_frame = _filter_variables_multi_block_range(
            df_variables_all,
            fecha_inicio,
            fecha_fin,
            selected_wiga_block_names
        )
        if not wiga_frame.empty:
            frames.append(wiga_frame)

    if include_ecowitt and not ecowitt_df.empty:
        ecowitt_metric_frame = _build_ponderosa_ecowitt_metric_frame(ecowitt_df)
        ecowitt_metric_frame = ecowitt_metric_frame[
            ecowitt_metric_frame['Fecha_Filtro'].between(fecha_inicio, fecha_fin)
        ].copy()
        if not ecowitt_metric_frame.empty:
            frames.append(ecowitt_metric_frame)

    if not frames:
        st.warning("No hay datos para calcular la métrica en el periodo seleccionado.")
        st.stop()

    analysis_df = pd.concat(frames, ignore_index=True, sort=False)
    selected_blocks = _sort_block_names(analysis_df['Bloque'].dropna().unique().tolist())
    variable_options = _get_ponderosa_metric_variable_options(source_option)

    _render_selected_period_banner(
        selected_range,
        min_fecha=min_date,
        max_fecha=max_date,
        navigation_state_key=navigation_state_key,
        title_text=f'Periodo de {metric_name.lower()}',
        available_dates=available_dates
    )

    st.markdown(f"## La Ponderosa - {metric_name}")
    st.caption(f"Análisis de {metric_name.lower()} para {source_option}. ECOWITT corresponde al Bloque {PONDEROSA_ECOWITT_BLOCK_CODE}.")
    _render_hourly_analysis_view_organized(
        analysis_df,
        selected_range,
        selected_blocks,
        forced_metric=metric_name,
        variable_options=variable_options,
        variable_state_key=f"ponderosa_{metric_key}_variable"
    )
    st.stop()


_df_variables_all = pd.DataFrame()
_df_cortinas_all = pd.DataFrame()

if 'mostrar_aperturas_ideales' not in st.session_state:
    st.session_state.mostrar_aperturas_ideales = False
if 'comparar_con_almacen' not in st.session_state:
    st.session_state.comparar_con_almacen = False
if 'mostrar_marley_detalles' not in st.session_state:
    st.session_state.mostrar_marley_detalles = MARLEY_DETAIL_CHARTS_DEFAULT
if 'mostrar_marley_registros' not in st.session_state:
    st.session_state.mostrar_marley_registros = MARLEY_RECORDS_DEFAULT
if 'mostrar_ponderosa_ecowitt_detalles' not in st.session_state:
    st.session_state.mostrar_ponderosa_ecowitt_detalles = PONDEROSA_ECOWITT_DETAILS_DEFAULT
if 'mostrar_ponderosa_ecowitt_registros' not in st.session_state:
    st.session_state.mostrar_ponderosa_ecowitt_registros = PONDEROSA_ECOWITT_RECORDS_DEFAULT

st.sidebar.markdown(
    f"""
    <div class="sidebar-title">
        <span class="sidebar-title-icon">{_sidebar_icon_svg('filter')}</span>
        <span>Filtros</span>
    </div>
    """,
    unsafe_allow_html=True
)

with st.sidebar.expander("Finca", expanded=True):
    _sidebar_field_label("location", "Seleccionar finca")
    selected_finca = st.selectbox(
        "Seleccionar finca:",
        options=FINCA_OPTIONS,
        key="finca_compartida",
        help=FILTER_HELP_TEXTS['finca']
    )

dashboard_view_groups = MARLY_VIEW_GROUPS if selected_finca == 'Marly' else PONDEROSA_VIEW_GROUPS
dashboard_view_options = [
    option
    for group_options in dashboard_view_groups.values()
    for option in group_options
]
if st.session_state.get("modo_dashboard") not in dashboard_view_options:
    st.session_state["modo_dashboard"] = dashboard_view_options[0]
default_view_group = _get_view_group_for_mode(dashboard_view_groups, st.session_state.get("modo_dashboard"))
if st.session_state.get("modo_dashboard_grupo") not in dashboard_view_groups:
    st.session_state["modo_dashboard_grupo"] = default_view_group

with st.sidebar.expander("Vista", expanded=True):
    _sidebar_field_label(
        "filter",
        "Seleccionar análisis" if selected_finca == 'Marly' else "Seleccionar vista"
    )
    selected_view_group = st.radio(
        "Grupo:",
        options=list(dashboard_view_groups.keys()),
        key="modo_dashboard_grupo",
        help=(
            "Comparativas cruza sensores o cortinas; Análisis contiene promedio, desviacion estandar y varianza; Fuentes individuales muestra cada origen por separado."
        )
    )
    group_view_options = dashboard_view_groups[selected_view_group]
    if st.session_state.get("modo_dashboard") not in group_view_options:
        st.session_state["modo_dashboard"] = group_view_options[0]
    dashboard_mode = st.radio(
        "Seleccionar vista:",
        options=group_view_options,
        format_func=_format_dashboard_view_option,
        key="modo_dashboard",
        help=(
            "Elige una vista de Marly: comparativa WIGA / ECOWITT, análisis estadístico o lecturas individuales por sensor."
            if selected_finca == 'Marly' else
            "Elige una vista de Ponderosa: comparativas, análisis estadístico o fuentes individuales."
        )
    )

previous_dashboard_mode = st.session_state.get("_last_dashboard_mode")
force_all_correlacion_series = dashboard_mode == "WIGA con cortinas" and previous_dashboard_mode != dashboard_mode
st.session_state["_last_dashboard_mode"] = dashboard_mode

if selected_finca == 'Marly':
    with _loading_context(
        st.session_state.get("marley_modo_fechas") == "Varios días",
        "Cargando gráficas de Marly..."
    ):
        _render_marley_dashboard(dashboard_mode)
    st.stop()

if dashboard_mode == PONDEROSA_BLOCK_INFO_VIEW_NAME:
    _render_greenhouse_analysis_dashboard()
    st.stop()

_df_variables_all, _df_cortinas_all = cargar_dashboard_completo()

if dashboard_mode == "WIGA":
    with _loading_context(
        st.session_state.get("ponderosa_wiga_only_modo_fechas") == "Varios días",
        "Cargando variables WIGA de Ponderosa..."
    ):
        _render_ponderosa_wiga_values_dashboard(_df_variables_all, _df_cortinas_all, selected_finca)
    st.stop()

if dashboard_mode == "Cortinas":
    with _loading_context(
        st.session_state.get("ponderosa_cortinas_modo_fechas") == "Varios días",
        "Cargando comportamiento de bloques..."
    ):
        _render_ponderosa_cortinas_dashboard(_df_cortinas_all, selected_finca)
    st.stop()

if dashboard_mode == "WIGA relacion ECOWITT":
    _render_ponderosa_ecowitt_dashboard(_df_variables_all, _df_cortinas_all, selected_finca)
    st.stop()

if dashboard_mode == PONDEROSA_LIGHT_VIEW_NAME:
    _render_ponderosa_apogee_mci_wiga_dashboard(_df_variables_all, _df_cortinas_all, selected_finca)
    st.stop()

if dashboard_mode == "ECOWITT":
    with _loading_context(
        st.session_state.get("ponderosa_ecowitt_only_modo_fechas") == "Varios días",
        "Cargando variables ECOWITT de Ponderosa..."
    ):
        _render_ponderosa_ecowitt_values_dashboard()
    st.stop()

if dashboard_mode == "APOGEE":
    with _loading_context(
        st.session_state.get("ponderosa_apogee_modo_fechas") == "Varios días",
        "Cargando luminosidad APOGEE de Ponderosa..."
    ):
        _render_ponderosa_apogee_values_dashboard()
    st.stop()

if dashboard_mode in ("Varianza", "Desviacion estandar", "Promedio"):
    with _loading_context(
        st.session_state.get(f"ponderosa_{_build_normalized_text_key(dashboard_mode).replace(' ', '_')}_modo_fechas") == "Varios días",
        f"Cargando {dashboard_mode.lower()} de Ponderosa..."
    ):
        _render_ponderosa_metric_dashboard(_df_variables_all, _df_cortinas_all, selected_finca, dashboard_mode)
    st.stop()

if dashboard_mode == "Varianza Y Promedio":
    analysis_block_codes, analysis_variable_map, _ = _get_block_options(
        _df_variables_all,
        _df_cortinas_all,
        selected_finca=selected_finca
    )
    fecha_analisis = None
    analysis_block_names = []
    analysis_navigation_state_key = None
    analysis_min_fecha = None
    analysis_max_fecha = None

    with st.sidebar.expander("Periodo", expanded=True):
        if _df_variables_all.empty:
            st.write("No hay datos de variables para habilitar el filtro de fechas.")
        elif not analysis_variable_map:
            st.warning(f"No hay bloques con datos disponibles para la finca {selected_finca}.")
        else:
            fechas_disponibles = _get_all_variable_dates_for_blocks(
                _df_variables_all,
                list(analysis_variable_map.values())
            )
            if not fechas_disponibles:
                st.warning(f"No hay fechas disponibles en variables para la finca {selected_finca}.")
            else:
                min_fecha = min(fechas_disponibles)
                max_fecha = max(fechas_disponibles)
                analysis_min_fecha = min_fecha
                analysis_max_fecha = max_fecha

                if min_fecha == max_fecha:
                    fecha_unica_default = _clamp_sidebar_date(
                        _coerce_sidebar_date(
                            st.session_state.get("fecha_analisis_unica", max_fecha),
                            max_fecha
                        ),
                        min_fecha,
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
                    analysis_navigation_state_key = "fecha_analisis_unica"
                else:
                    modo_fechas_analisis = st.radio(
                        "Modo de fechas del análisis:",
                        options=["Un día", "Varios días"],
                        horizontal=True,
                        key="modo_fechas_analisis",
                        help=FILTER_HELP_TEXTS['modo_fechas']
                    )

                    if modo_fechas_analisis == "Un día":
                        fecha_unica_default = _clamp_sidebar_date(
                            _coerce_sidebar_date(
                                st.session_state.get("fecha_analisis_un_dia", max_fecha),
                                max_fecha
                            ),
                            min_fecha,
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
                        analysis_navigation_state_key = "fecha_analisis_un_dia"
                    else:
                        default_range_end = _get_sidebar_default_range_end(min_fecha, max_fecha, default_days=7)
                        _sidebar_field_label("calendar", "Fecha inicio")
                        fecha_inicio_analisis = st.date_input(
                            "Fecha inicio del análisis:",
                            value=min_fecha,
                            key="fecha_inicio_analisis",
                            min_value=min_fecha,
                            max_value=max_fecha,
                            help=FILTER_HELP_TEXTS['fecha']
                        )
                        _sidebar_field_label("calendar", "Fecha fin")
                        fecha_fin_analisis = st.date_input(
                            "Fecha fin del análisis:",
                            value=default_range_end,
                            key="fecha_fin_analisis",
                            min_value=min_fecha,
                            max_value=max_fecha,
                            help=FILTER_HELP_TEXTS['fecha']
                        )
                        fecha_inicio_analisis, fecha_fin_analisis = _normalize_sidebar_date_range(
                            fecha_inicio_analisis,
                            fecha_fin_analisis,
                            min_fecha,
                            max_fecha
                        )
                        fecha_analisis = (fecha_inicio_analisis, fecha_fin_analisis)

    with st.sidebar.expander("Bloques comparados", expanded=True):
        if _df_variables_all.empty:
            st.write("No se encontraron datos para habilitar la comparación de bloques.")
        elif not analysis_block_codes:
            st.warning(f"No se detectaron bloques válidos para la finca {selected_finca}.")
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
        st.warning("No se encontraron datos de variables para construir el análisis de promedio, desviacion estandar y varianza.")
    elif fecha_analisis is None:
        st.warning("Selecciona el periodo del análisis en la barra lateral.")
    elif not analysis_block_names:
        st.warning(f"Selecciona al menos un bloque para comparar dentro de la finca {selected_finca}.")
    else:
        _render_selected_period_banner(
            fecha_analisis,
            min_fecha=analysis_min_fecha,
            max_fecha=analysis_max_fecha,
            navigation_state_key=analysis_navigation_state_key,
            title_text='Periodo del análisis'
        )
        fecha_inicio_analisis, fecha_fin_analisis = fecha_analisis
        df_variables_analisis = _filter_variables_multi_block_range(
            _df_variables_all,
            fecha_inicio_analisis,
            fecha_fin_analisis,
            analysis_block_names
        )
        estacion_externa_name = analysis_variable_map.get('ALMACEN')
        df_estacion_externa_analisis = (
            _filter_variables_multi_block_range(
                _df_variables_all,
                fecha_inicio_analisis,
                fecha_fin_analisis,
                [estacion_externa_name]
            )
            if estacion_externa_name else pd.DataFrame()
        )
        with _loading_context(
            st.session_state.get("modo_fechas_analisis") == "Varios días",
            "Cargando análisis de varios días..."
        ):
            _render_hourly_analysis_view_organized(
                df_variables_analisis,
                fecha_analisis,
                analysis_block_names,
                df_external_station=df_estacion_externa_analisis
            )
    st.stop()

block_codes, variable_block_map, cortina_block_map = _get_block_options(
    _df_variables_all,
    _df_cortinas_all,
    selected_finca=selected_finca
)
bloque_variables = None
bloque_seleccionado = None
correlation_navigation_state_key = None
correlation_min_fecha = None
correlation_max_fecha = None
selected_block_code_current = st.session_state.get("bloque_compartido")
if not selected_block_code_current and block_codes:
    selected_block_code_current = block_codes[0]
if selected_block_code_current and selected_block_code_current not in block_codes:
    selected_block_code_current = block_codes[0] if block_codes else None
if selected_block_code_current is not None:
    st.session_state["bloque_compartido"] = selected_block_code_current
if selected_block_code_current in variable_block_map:
    bloque_variables = variable_block_map.get(selected_block_code_current)
    bloque_seleccionado = cortina_block_map.get(selected_block_code_current)

with st.sidebar.expander("Periodo", expanded=True):
    fecha_variables = None
    fecha_cortinas = None

    if _df_variables_all.empty:
        st.write("No hay datos de variables para habilitar el filtro de fechas.")
    elif bloque_variables is None:
        if block_codes:
            st.write("Selecciona primero el bloque.")
        else:
            st.write(f"No hay bloques disponibles para la finca {selected_finca}.")
    else:
        fechas_disponibles = _get_available_variable_dates(_df_variables_all, bloque_variables)

        if not fechas_disponibles:
            st.warning("No hay fechas disponibles en variables para el bloque seleccionado.")
        else:
            min_fecha = min(fechas_disponibles)
            max_fecha = max(fechas_disponibles)
            correlation_min_fecha = min_fecha
            correlation_max_fecha = max_fecha

            if min_fecha == max_fecha:
                st.caption("Solo hay una fecha con datos en variables para este bloque, pero puedes consultar cualquier día desde el calendario.")
                fecha_unica_default = _clamp_sidebar_date(
                    _coerce_sidebar_date(
                        st.session_state.get("fecha_calendario_unica", max_fecha),
                        max_fecha
                    ),
                    min_fecha,
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
                correlation_navigation_state_key = "fecha_calendario_unica"
            else:
                modo_fechas = st.radio(
                    "Modo de fechas:",
                    options=["Un día", "Varios días"],
                    horizontal=True,
                    key="modo_fechas_compartidas",
                    help=FILTER_HELP_TEXTS['modo_fechas']
                )

                if modo_fechas == "Un día":
                    fecha_unica_default = _clamp_sidebar_date(
                        _coerce_sidebar_date(
                            st.session_state.get("fecha_calendario_un_dia", max_fecha),
                            max_fecha
                        ),
                        min_fecha,
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
                    correlation_navigation_state_key = "fecha_calendario_un_dia"
                else:
                    default_range_end = _get_sidebar_default_range_end(min_fecha, max_fecha, default_days=7)
                    _sidebar_field_label("calendar", "Fecha inicio")
                    fecha_inicio = st.date_input(
                        "Fecha inicio:",
                        value=min_fecha,
                        key="fecha_inicio_compartida",
                        min_value=min_fecha,
                        max_value=max_fecha,
                        help=FILTER_HELP_TEXTS['fecha']
                    )
                    _sidebar_field_label("calendar", "Fecha fin")
                    fecha_fin = st.date_input(
                        "Fecha fin:",
                        value=default_range_end,
                        key="fecha_fin_compartida",
                        min_value=min_fecha,
                        max_value=max_fecha,
                        help=FILTER_HELP_TEXTS['fecha']
                    )
                    fecha_inicio, fecha_fin = _normalize_sidebar_date_range(
                        fecha_inicio,
                        fecha_fin,
                        min_fecha,
                        max_fecha
                    )
                    fecha_variables = (fecha_inicio, fecha_fin)
                    fecha_cortinas = (fecha_inicio, fecha_fin)

with st.sidebar.expander("Bloque", expanded=True):
    if _df_variables_all.empty:
        st.write("No se encontraron datos de variables para habilitar los bloques.")
    elif not block_codes:
        st.warning(f"No se detectaron bloques válidos para la finca {selected_finca}.")
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

if bloque_variables is not None and fecha_variables is not None and available_correlacion_vars:
    current_context = (
        str(bloque_variables),
        str(fecha_variables[0]),
        str(fecha_variables[1]),
        tuple(available_correlacion_vars)
    )
    previous_context = st.session_state.get('variables_correlacion_context')
    if previous_context != current_context or force_all_correlacion_series:
        _reset_correlacion_selector(available_correlacion_vars)
        st.session_state['variables_correlacion_context'] = current_context

# Vista principal
tab_correlacion = st.container()

with tab_correlacion:
    if _df_variables_all.empty:
        st.warning("No se encontraron datos de variables para visualizar este análisis.")
    elif fecha_variables is None or fecha_cortinas is None or bloque_variables is None:
        st.warning("Selecciona bloque y fechas en los filtros de la barra lateral.")
    else:
        _render_selected_period_banner(
            fecha_variables,
            min_fecha=correlation_min_fecha,
            max_fecha=correlation_max_fecha,
            navigation_state_key=correlation_navigation_state_key,
            title_text='Periodo del bloque'
        )
        fecha_inicio, fecha_fin = fecha_variables
        rango_multiple = fecha_inicio != fecha_fin
        variables_sensor = _get_available_sensor_vars(df_variables_corr)
        datos_sensores_corr = (
            df_variables_corr[['DateTime'] + variables_sensor].dropna(how='all', subset=variables_sensor)
            if variables_sensor else pd.DataFrame()
        )
        block_label = _format_block_display_name(bloque_seleccionado or bloque_variables)
        summary_reference_df = (
            df_variables_almacen_corr
            if not df_variables_almacen_corr.empty and selected_block_code != 'ALMACEN'
            else None
        )

        block_modification = _get_block_modification(block_label)
        culatas_observation = _get_culatas_daily_observation(datos_cortinas_sel, block_label)
        culatas_by_day = _get_culatas_observation_by_day(datos_cortinas_sel, block_label)
        daily_annotations = _get_daily_annotations(datos_cortinas_sel)
        annotations_by_day = _get_annotations_by_day(datos_cortinas_sel)

        selected_vars = st.session_state.get('variables_correlacion', available_correlacion_vars.copy())

        if df_variables_corr.empty:
            fecha_label = fecha_inicio.strftime('%Y-%m-%d') if not rango_multiple else f"{fecha_inicio.strftime('%Y-%m-%d')} a {fecha_fin.strftime('%Y-%m-%d')}"
            st.warning(f"No se encontraron datos de variables para el rango seleccionado: {fecha_label}.")
        elif not available_correlacion_vars:
            st.warning("No se encontraron variables con datos para graficar en el rango seleccionado.")
        elif datos_cortinas_sel.empty:
            st.info("No hay información de motores para este periodo. Se mostrarán las variables ambientales disponibles.")

        tab_chart, tab_observations, tab_stats, tab_detail, tab_records = st.tabs([
            "Gráfica",
            "Observaciones del bloque",
            "Análisis estadístico",
            "Gráficas individuales",
            "Registros"
        ])
        with tab_chart:
            selected_vars = _render_correlacion_series_panel(
                available_correlacion_vars,
                selected_block_code,
                df_variables_almacen_corr
            )
            _render_chart_explanation(
                f"Bloque en visualización: {block_label}",
                "La gráfica cruza las variables ambientales seleccionadas con el comportamiento disponible de cortinas para el periodo filtrado.",
                accent=BRAND_COLORS['hero'],
                kicker='Vista activa'
            )
            if not df_variables_corr.empty and available_correlacion_vars:
                if not selected_vars:
                    st.warning('Selecciona al menos una variable para mostrar la correlación.')
                else:
                    with _loading_context(
                        st.session_state.get("modo_fechas_compartidas") == "Varios días",
                        "Cargando gráficas de correlación..."
                    ):
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

        with tab_observations:
            _render_chart_explanation(
                "Observaciones, modificación y estado de culatas",
                "Esta lectura consolida las anotaciones operativas del bloque, la modificación configurada y el estado de culatas del periodo seleccionado.",
                accent=BRAND_COLORS['rose'],
                kicker='Contexto del bloque'
            )
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

        with tab_stats:
            _render_chart_explanation(
                "Análisis estadístico de variables",
                "Esta sección resume el comportamiento del bloque con métricas de tendencia central y dispersión. Usa las pestañas para revisar cada medida sin mezclar interpretaciones.",
                accent=BRAND_COLORS['hero'],
                kicker='Estadística del periodo'
            )
            stats_variables = [variable for variable in variables_sensor if variable in df_variables_corr.columns]
            stats_df = _build_variable_distribution_table(df_variables_corr, stats_variables)
            variable_stat_configs = {
                variable_name: {
                    'title': VARIABLE_SELECTOR_LABELS.get(variable_name, VARIABLE_LABELS.get(variable_name, variable_name)),
                    'unit': VARIABLE_UNITS.get(variable_name, ''),
                    'accent': VARIABLE_COLORS.get(variable_name, BRAND_COLORS['hero'])
                }
                for variable_name in stats_variables
            }
            _render_variable_statistics_charts(
                stats_df,
                variable_stat_configs,
                block_label=block_label
            )
            _render_variable_distribution_cards(
                stats_df,
                variable_stat_configs,
                title=f"Análisis estadístico de variables - {block_label}"
            )
            with st.expander("Ver estadística en tabla", expanded=False):
                _dataframe(stats_df, hide_index=True)

        with tab_detail:
            _render_temperature_focus_chart(
                df_variables_corr,
                fecha_variables,
                block_label=block_label,
                df_external=df_variables_almacen_corr,
                datos_cortinas_sel=datos_cortinas_sel
            )

        with tab_records:
            sensor_30min_report = _build_variables_30min_report(df_variables_corr, variables_sensor)
            cortinas_30min_report = _build_cortinas_30min_report(datos_cortinas_sel, fecha_variables, block_label)
            cortinas_event_report = _build_cortinas_event_report(datos_cortinas_sel)
            record_content_options = [
                "Variables cada 30 min",
                "Cortinas cada 30 min",
                "Eventos de cortinas",
                "Registros crudos"
            ]
            if st.session_state.get("vista_registros_correlacion") not in record_content_options:
                st.session_state["vista_registros_correlacion"] = record_content_options[0]
            selected_record_content = st.segmented_control(
                "Reporte",
                options=record_content_options,
                key="vista_registros_correlacion",
                help=FILTER_HELP_TEXTS['registros'],
                width="stretch"
            )
            if selected_record_content == "Variables cada 30 min":
                if sensor_30min_report.empty:
                    st.info("No hay registros de variables para generar el reporte cada 30 minutos.")
                else:
                    _render_table_download_button(
                        sensor_30min_report,
                        "Descargar reporte de variables",
                        f"reporte_variables_30min_{_build_report_slug(block_label)}.xlsx",
                        "download_correlacion_variables_30min",
                        variable_column='Fecha'
                    )
                    _dataframe(sensor_30min_report, hide_index=True)
            elif selected_record_content == "Cortinas cada 30 min":
                if cortinas_30min_report.empty:
                    st.info("No hay registros de cortinas para generar el reporte cada 30 minutos.")
                else:
                    _render_table_download_button(
                        cortinas_30min_report,
                        "Descargar reporte de cortinas",
                        f"reporte_cortinas_30min_{_build_report_slug(block_label)}.xlsx",
                        "download_correlacion_cortinas_30min",
                        variable_column='Motor'
                    )
                    _dataframe(cortinas_30min_report, hide_index=True)
            elif selected_record_content == "Eventos de cortinas":
                if cortinas_event_report.empty:
                    st.info("No hay eventos de cortinas para los filtros seleccionados.")
                else:
                    _render_table_download_button(
                        cortinas_event_report,
                        "Descargar eventos de cortinas",
                        f"eventos_cortinas_{_build_report_slug(block_label)}.xlsx",
                        "download_correlacion_eventos_cortinas",
                        variable_column='Fecha'
                    )
                    _dataframe(cortinas_event_report, hide_index=True)
            elif selected_record_content == "Registros crudos":
                raw_tab_sensors, raw_tab_cortinas = st.tabs(["Sensores", "Cortinas"])
                with raw_tab_sensors:
                    if datos_sensores_corr.empty:
                        st.info("No hay registros de sensores para los filtros seleccionados.")
                    else:
                        _dataframe(datos_sensores_corr)
                with raw_tab_cortinas:
                    if datos_cortinas_sel.empty:
                        st.info("No hay registros de cortinas para los filtros seleccionados.")
                    else:
                        _dataframe(datos_cortinas_sel)

        st.stop()

        if not df_variables_corr.empty and available_correlacion_vars:
            if not selected_vars:
                st.warning('Selecciona al menos una variable para mostrar la correlación.')
            else:
                with _loading_context(
                    st.session_state.get("modo_fechas_compartidas") == "Varios días",
                    "Cargando gráficas de correlación..."
                ):
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

        _render_summary_cards_selector(
            df_variables_corr,
            fecha_variables,
            df_reference=summary_reference_df,
            reference_label='Estación externa',
            base_label=block_label
        )

        _render_temperature_focus_chart(
            df_variables_corr,
            fecha_variables,
            block_label=block_label,
            df_external=df_variables_almacen_corr,
            datos_cortinas_sel=datos_cortinas_sel
        )

        record_content_options = ["Ocultar registros", "Sensores", "Cortinas"]
        if st.session_state.get("vista_registros_correlacion") not in record_content_options:
            st.session_state["vista_registros_correlacion"] = record_content_options[0]
        selected_record_content = st.segmented_control(
            "Registros",
            options=record_content_options,
            key="vista_registros_correlacion",
            help=FILTER_HELP_TEXTS['registros'],
            width="stretch"
        )

        if selected_record_content == "Sensores":
            if datos_sensores_corr.empty:
                st.info("No hay registros de sensores para los filtros seleccionados.")
            else:
                _dataframe(datos_sensores_corr)
        elif selected_record_content == "Cortinas":
            if datos_cortinas_sel.empty:
                st.info("No hay registros de cortinas para los filtros seleccionados.")
            else:
                _dataframe(datos_cortinas_sel)

