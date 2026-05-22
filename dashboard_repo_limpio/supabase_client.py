import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import count

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
SUPABASE_MAX_WORKERS = 16
SUPABASE_CACHE_TTL_SECONDS = 3600


def _get_secret_value(*names):
    for name in names:
        try:
            value = st.secrets.get(name)
        except Exception:
            value = None
        if not value:
            value = os.environ.get(name)
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


def _parse_content_range_total(content_range):
    if not content_range or "/" not in content_range:
        return None
    total_text = content_range.rsplit("/", 1)[-1].strip()
    if not total_text or total_text == "*":
        return None
    try:
        return int(total_text)
    except ValueError:
        return None


def _build_supabase_params(offset, select="*", query_params=None):
    params = {
        "select": select,
        "limit": SUPABASE_PAGE_SIZE,
        "offset": offset,
    }
    for key, value in tuple(query_params or ()):
        params[key] = value
    return params


def _fetch_supabase_page(url, table_name, headers, offset, select="*", query_params=None):
    response = requests.get(
        f"{url}/rest/v1/{table_name}",
        headers=headers,
        params=_build_supabase_params(offset, select=select, query_params=query_params),
        timeout=45,
    )
    response.raise_for_status()
    return offset, response.json(), response.headers


def _load_supabase_table_sequential(
    url,
    table_name,
    headers,
    first_rows=None,
    first_offset=0,
    select="*",
    query_params=None,
):
    rows = list(first_rows or [])
    offset = first_offset + SUPABASE_PAGE_SIZE

    while True:
        _, page, _ = _fetch_supabase_page(
            url,
            table_name,
            headers,
            offset,
            select=select,
            query_params=query_params,
        )
        if not page:
            break
        rows.extend(page)
        if len(page) < SUPABASE_PAGE_SIZE:
            break
        offset += SUPABASE_PAGE_SIZE

    return rows


def _load_supabase_table_parallel_until_last(url, table_name, headers, first_page, select="*", query_params=None):
    rows_by_offset = {0: first_page}

    for batch_number in count(start=0):
        batch_offsets = [
            offset
            for offset in range(
                SUPABASE_PAGE_SIZE + (batch_number * SUPABASE_MAX_WORKERS * SUPABASE_PAGE_SIZE),
                SUPABASE_PAGE_SIZE + ((batch_number + 1) * SUPABASE_MAX_WORKERS * SUPABASE_PAGE_SIZE),
                SUPABASE_PAGE_SIZE,
            )
        ]
        reached_last_page = False

        with ThreadPoolExecutor(max_workers=SUPABASE_MAX_WORKERS) as executor:
            futures = {
                executor.submit(
                    _fetch_supabase_page,
                    url,
                    table_name,
                    headers,
                    offset,
                    select,
                    query_params,
                ): offset
                for offset in batch_offsets
            }
            for future in as_completed(futures):
                offset, page, _ = future.result()
                if page:
                    rows_by_offset[offset] = page
                if len(page) < SUPABASE_PAGE_SIZE:
                    reached_last_page = True

        if reached_last_page:
            break

    rows = []
    for offset in sorted(rows_by_offset):
        rows.extend(rows_by_offset[offset])
    return rows


@st.cache_data(ttl=SUPABASE_CACHE_TTL_SECONDS, show_spinner="Cargando datos desde Supabase...")
def load_supabase_table(table_name, cache_version="supabase-v1", select="*", query_params=None):
    _ = cache_version
    query_params = tuple(query_params or ())
    url, key = get_supabase_settings()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    count_headers = {
        **headers,
        "Prefer": "count=exact",
    }

    try:
        active_headers = count_headers
        _, first_page, first_headers = _fetch_supabase_page(
            url,
            table_name,
            active_headers,
            0,
            select=select,
            query_params=query_params,
        )
    except requests.HTTPError:
        active_headers = headers
        _, first_page, first_headers = _fetch_supabase_page(
            url,
            table_name,
            active_headers,
            0,
            select=select,
            query_params=query_params,
        )
    if not first_page:
        return pd.DataFrame()
    if len(first_page) < SUPABASE_PAGE_SIZE:
        return pd.DataFrame(first_page)

    total_rows = _parse_content_range_total(first_headers.get("Content-Range"))
    if not total_rows:
        try:
            rows = _load_supabase_table_parallel_until_last(
                url,
                table_name,
                active_headers,
                first_page,
                select=select,
                query_params=query_params,
            )
        except Exception:
            rows = _load_supabase_table_sequential(
                url,
                table_name,
                active_headers,
                first_page,
                0,
                select=select,
                query_params=query_params,
            )
        return pd.DataFrame(rows)

    if total_rows <= len(first_page):
        rows = _load_supabase_table_sequential(
            url,
            table_name,
            active_headers,
            first_page,
            0,
            select=select,
            query_params=query_params,
        )
        return pd.DataFrame(rows)

    offsets = list(range(SUPABASE_PAGE_SIZE, total_rows, SUPABASE_PAGE_SIZE))
    pages = {0: first_page}

    try:
        with ThreadPoolExecutor(max_workers=SUPABASE_MAX_WORKERS) as executor:
            futures = {
                executor.submit(
                    _fetch_supabase_page,
                    url,
                    table_name,
                    active_headers,
                    offset,
                    select,
                    query_params,
                ): offset
                for offset in offsets
            }
            for future in as_completed(futures):
                offset, page, _ = future.result()
                pages[offset] = page
    except Exception:
        rows = _load_supabase_table_sequential(
            url,
            table_name,
            active_headers,
            first_page,
            0,
            select=select,
            query_params=query_params,
        )
        return pd.DataFrame(rows)

    rows = []
    for offset in sorted(pages):
        rows.extend(pages[offset])
    return pd.DataFrame(rows)
