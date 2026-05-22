import pandas as pd

from supabase_client import SUPABASE_TABLES, load_supabase_table
from data_transforms import (
    prepare_cortinas,
    prepare_greenhouse_analysis,
    prepare_marley,
    prepare_ponderosa_ecowitt,
    prepare_ponderosa_variables,
)


VARIABLE_SELECT = (
    "fecha,finca,bloque,sensor,temperatura,humedad_relativa,"
    "radiacion_par,gramos_agua,luz_lux"
)


def load_variables_table(cache_version):
    return load_supabase_table(
        SUPABASE_TABLES["variables"],
        cache_version=cache_version,
        select=VARIABLE_SELECT,
    )


def load_ponderosa_wigga_table(cache_version):
    return load_supabase_table(
        SUPABASE_TABLES["variables"],
        cache_version=cache_version,
        select=VARIABLE_SELECT,
        query_params=(
            ("finca", "eq.Ponderosa"),
            ("sensor", "eq.WIGGA"),
        ),
    )


def load_ponderosa_external_table(cache_version):
    return load_supabase_table(
        SUPABASE_TABLES["variables"],
        cache_version=cache_version,
        select=VARIABLE_SELECT,
        query_params=(
            ("finca", "eq.Ponderosa"),
            ("bloque", "eq.EXTERNO ALMACEN"),
            ("sensor", "in.(ECOWITT,APOGEE)"),
        ),
    )


def load_marley_variables_table(cache_version):
    return load_supabase_table(
        SUPABASE_TABLES["variables"],
        cache_version=cache_version,
        select=VARIABLE_SELECT,
        query_params=(
            ("finca", "eq.Marley"),
            ("bloque", "in.(MONTAÑA,MONTANA,MONTA?A)"),
        ),
    )


def load_dashboard_data(cache_version):
    variables = load_ponderosa_wigga_table(cache_version)
    cortinas = load_supabase_table(SUPABASE_TABLES["cortinas"], cache_version=cache_version)
    return prepare_ponderosa_variables(variables), prepare_cortinas(cortinas)


def load_ponderosa_ecowitt_data(cache_version):
    variables = load_ponderosa_external_table(cache_version)
    return prepare_ponderosa_ecowitt(variables)


def load_marley_data(cache_version):
    variables = load_marley_variables_table(cache_version)
    return prepare_marley(variables)


def load_greenhouse_analysis(cache_version):
    analysis = load_supabase_table(SUPABASE_TABLES["analisis"], cache_version=cache_version)
    indicators = load_supabase_table(SUPABASE_TABLES["indicadores"], cache_version=cache_version)
    if analysis.empty and indicators.empty:
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
    return prepare_greenhouse_analysis(analysis, indicators)
