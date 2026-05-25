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


def _normalize_secret_value(value):
    if value is None:
        return None
    value = str(value).strip().strip('"').strip("'")
    if "=" in value and value.upper().startswith(("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_ANON_KEY")):
        value = value.split("=", 1)[1].strip().strip('"').strip("'")
    return value or None


def _is_valid_supabase_url(url):
    return bool(url and url.startswith("https://") and "supabase.co" in url)


def _is_valid_supabase_key(key):
    return bool(key and (key.startswith("sb_publishable_") or key.startswith("eyJ")))


def get_supabase_settings():
    url = _normalize_secret_value(_get_secret_value("SUPABASE_URL", "supabase_url"))
    key = _normalize_secret_value(_get_secret_value("SUPABASE_KEY", "SUPABASE_ANON_KEY", "supabase_key"))
    if not _is_valid_supabase_url(url):
        raise RuntimeError(
            "Falta SUPABASE_URL o no tiene el formato esperado. Configuralo en "
            "Streamlit Secrets o como variable de entorno."
        )
    if not _is_valid_supabase_key(key):
        raise RuntimeError(
            "Falta SUPABASE_KEY o no tiene el formato esperado. Configurala en "
            "Streamlit Secrets o como variable de entorno."
        )
    return url.rstrip("/"), key


def _get_supabase_setting_candidates():
    return [get_supabase_settings()]


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


def _build_supabase_headers(key):
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }


def _get_response_error_detail(error):
    response = getattr(error, "response", None)
    if response is None:
        return "sin respuesta de Supabase"

    detail = response.text or response.reason or ""
    detail = " ".join(str(detail).split())
    if len(detail) > 400:
        detail = f"{detail[:400]}..."
    return f"HTTP {response.status_code}: {detail}"


def _raise_supabase_error(table_name, errors):
    details = [_get_response_error_detail(error) for error in errors if error is not None]
    unique_details = []
    for detail in details:
        if detail not in unique_details:
            unique_details.append(detail)
    details_text = " | ".join(unique_details) or "sin detalle"
    raise RuntimeError(
        "No fue posible leer la tabla "
        f"'{table_name}' desde Supabase. Revisa en Streamlit Cloud que "
        "SUPABASE_URL y SUPABASE_KEY esten bien configurados, y que la tabla "
        f"tenga permisos de lectura para la publishable key. Detalle: {details_text}"
    )


def _fetch_first_page_with_fallback(url, table_name, headers, select="*", query_params=None):
    query_params = tuple(query_params or ())
    count_headers = {
        **headers,
        "Prefer": "count=exact",
    }

    attempts = [
        (count_headers, query_params),
        (headers, query_params),
    ]
    if query_params:
        attempts.extend([
            (count_headers, ()),
            (headers, ()),
        ])

    last_error = None
    for active_headers, active_query_params in attempts:
        try:
            offset, page, response_headers = _fetch_supabase_page(
                url,
                table_name,
                active_headers,
                0,
                select=select,
                query_params=active_query_params,
            )
            return offset, page, response_headers, active_headers, active_query_params
        except requests.HTTPError as error:
            last_error = error

    raise last_error


def _download_supabase_table(url, key, table_name, select="*", query_params=None):
    headers = _build_supabase_headers(key)
    _, first_page, first_headers, active_headers, active_query_params = _fetch_first_page_with_fallback(
        url,
        table_name,
        headers,
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
                query_params=active_query_params,
            )
        except Exception:
            rows = _load_supabase_table_sequential(
                url,
                table_name,
                active_headers,
                first_page,
                0,
                select=select,
                query_params=active_query_params,
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
            query_params=active_query_params,
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
                    active_query_params,
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
            query_params=active_query_params,
        )
        return pd.DataFrame(rows)

    rows = []
    for offset in sorted(pages):
        rows.extend(pages[offset])
    return pd.DataFrame(rows)


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
    errors = []
    for url, key in _get_supabase_setting_candidates():
        try:
            return _download_supabase_table(
                url,
                key,
                table_name,
                select=select,
                query_params=query_params,
            )
        except requests.HTTPError as error:
            errors.append(error)
        except requests.RequestException as error:
            errors.append(error)

    _raise_supabase_error(table_name, errors)
