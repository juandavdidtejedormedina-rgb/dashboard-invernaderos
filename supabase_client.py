import pandas as pd
import requests
import streamlit as st


SUPABASE_TABLES = {
    "variables": "variables_ambientales",
    "cortinas": "registros_cortinas",
    "analisis": "analisis_invernaderos_bloques",
    "indicadores": "indicadores_ventilacion_bloques",
}

SUPABASE_PAGE_SIZE = 1000


def _get_secret_value(*names):
    for name in names:
        try:
            value = st.secrets.get(name)
        except Exception:
            value = None
        if value:
            return str(value).strip()
    return None


def get_supabase_settings():
    url = _get_secret_value("SUPABASE_URL", "supabase_url")
    key = _get_secret_value("SUPABASE_KEY", "SUPABASE_ANON_KEY", "supabase_key")
    if not url or not key:
        raise RuntimeError(
            "Faltan SUPABASE_URL y SUPABASE_KEY en Streamlit secrets."
        )
    return url.rstrip("/"), key


def supabase_is_configured():
    try:
        get_supabase_settings()
        return True
    except RuntimeError:
        return False


@st.cache_data(ttl=300, show_spinner="Cargando datos desde Supabase...")
def load_supabase_table(table_name, cache_version="supabase-v1"):
    _ = cache_version
    url, key = get_supabase_settings()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }

    rows = []
    offset = 0
    while True:
        response = requests.get(
            f"{url}/rest/v1/{table_name}",
            headers=headers,
            params={
                "select": "*",
                "limit": SUPABASE_PAGE_SIZE,
                "offset": offset,
            },
            timeout=45,
        )
        response.raise_for_status()
        page = response.json()
        if not page:
            break
        rows.extend(page)
        if len(page) < SUPABASE_PAGE_SIZE:
            break
        offset += SUPABASE_PAGE_SIZE

    return pd.DataFrame(rows)
