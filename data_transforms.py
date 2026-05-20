from datetime import datetime

import pandas as pd


SENSOR_VARIABLES = ["Temperatura", "Humedad Relativa", "Radiación PAR", "Gramos de agua"]
PONDEROSA_ECOWITT_VARIABLES = ["Temperatura", "Humedad Relativa", "Radiación PAR"]
PONDEROSA_ECOWITT_DATA_VARIABLES = ["Temperatura", "Humedad Relativa", "Radiación PAR", "LUX"]
MARLEY_VARIABLES = [
    "Gramos de agua (g)",
    "Humedad Relativa (%)",
    "Temperatura (°C)",
    "Radiación PAR (µmol m-2 s-1)",
]

CORTINAS_NUMERIC_COLUMNS = [
    "% Apertura A", "% Cierre A", "% Apertura B", "% Cierre B",
    "Duracion Apertura A", "Duracion Cierre A",
    "Duracion Apertura B", "Duracion Cierre B", "Culatas %",
]
CORTINAS_TIME_COLUMNS = ["Hora Apertura A", "Hora Cierre A", "Hora Apertura B", "Hora Cierre B"]
CORTINAS_COLUMNAS = [
    "Fecha", "Hora Apertura A", "% Apertura A", "Duracion Apertura A",
    "Hora Cierre A", "% Cierre A", "Duracion Cierre A", "Frente A", "Anotacion A",
    "Hora Apertura B", "% Apertura B", "Duracion Apertura B", "Hora Cierre B",
    "% Cierre B", "Duracion Cierre B", "Puerta B", "Anotacion B", "Culatas %",
]
WEEKDAY_ES = {
    0: "Lunes",
    1: "Martes",
    2: "Miércoles",
    3: "Jueves",
    4: "Viernes",
    5: "Sábado",
    6: "Domingo",
}


def clean_supabase_text(value):
    if pd.isna(value):
        return value
    text = str(value).strip()
    return text.replace("MONTA?A", "MONTAÑA")


def _coerce_datetime(series):
    return pd.to_datetime(series, errors="coerce", utc=True).dt.tz_convert(None)


def _parse_time(value):
    if pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.time()
    if hasattr(value, "hour") and hasattr(value, "minute"):
        return value
    text = str(value).strip()
    try:
        parsed = pd.to_datetime(text, errors="coerce")
        return parsed.time() if not pd.isna(parsed) else None
    except Exception:
        return None


def prepare_ponderosa_variables(df):
    if df.empty:
        return pd.DataFrame()

    data = df.copy()
    data["finca"] = data["finca"].apply(clean_supabase_text)
    data["bloque"] = data["bloque"].apply(clean_supabase_text)
    data["sensor"] = data["sensor"].apply(clean_supabase_text)
    data = data[
        data["finca"].eq("Ponderosa") &
        data["sensor"].str.upper().eq("WIGGA")
    ].copy()
    if data.empty:
        return pd.DataFrame()

    data["DateTime"] = _coerce_datetime(data["fecha"])
    data = data.dropna(subset=["DateTime"]).sort_values("DateTime")
    data["Fecha_Filtro"] = data["DateTime"].dt.date
    data["Bloque"] = data["bloque"]
    data["Temperatura"] = pd.to_numeric(data["temperatura"], errors="coerce")
    data["Humedad Relativa"] = pd.to_numeric(data["humedad_relativa"], errors="coerce")
    data["Radiación PAR"] = pd.to_numeric(data["radiacion_par"], errors="coerce")
    data["Gramos de agua"] = pd.to_numeric(data["gramos_agua"], errors="coerce")
    return data[["DateTime", "Fecha_Filtro", "Bloque", *SENSOR_VARIABLES]].copy()


def prepare_cortinas(df):
    if df.empty:
        return pd.DataFrame()

    data = df.copy().rename(columns={
        "fecha": "Fecha",
        "bloque": "Bloque",
        "lado_a_hora_apertura": "Hora Apertura A",
        "lado_a_porcentaje_apertura": "% Apertura A",
        "lado_a_duracion_apertura_min": "Duracion Apertura A",
        "lado_a_hora_cierre": "Hora Cierre A",
        "lado_a_porcentaje_cierre": "% Cierre A",
        "lado_a_duracion_cierre_min": "Duracion Cierre A",
        "lado_a_frente": "Frente A",
        "lado_a_anotacion": "Anotacion A",
        "lado_b_hora_apertura": "Hora Apertura B",
        "lado_b_porcentaje_apertura": "% Apertura B",
        "lado_b_duracion_apertura_min": "Duracion Apertura B",
        "lado_b_hora_cierre": "Hora Cierre B",
        "lado_b_porcentaje_cierre": "% Cierre B",
        "lado_b_duracion_cierre_min": "Duracion Cierre B",
        "lado_b_puerta": "Puerta B",
        "lado_b_anotacion": "Anotacion B",
        "culatas_porcentaje": "Culatas %",
    })

    keep_columns = [column for column in [*CORTINAS_COLUMNAS, "Bloque"] if column in data.columns]
    data = data[keep_columns].copy()
    data["Bloque"] = data["Bloque"].apply(clean_supabase_text)
    data["Fecha"] = pd.to_datetime(data["Fecha"], errors="coerce").dt.date
    data = data[data["Fecha"].notna()].copy()
    data["Dia"] = pd.to_datetime(data["Fecha"], errors="coerce").dt.weekday.map(WEEKDAY_ES)

    for column in CORTINAS_NUMERIC_COLUMNS:
        if column in data.columns:
            data[column] = pd.to_numeric(data[column], errors="coerce")
            if column in ["% Apertura A", "% Cierre A", "% Apertura B", "% Cierre B", "Culatas %"]:
                mask = data[column].notna() & (data[column] <= 1)
                data.loc[mask, column] = data.loc[mask, column] * 100

    for column in CORTINAS_TIME_COLUMNS:
        if column in data.columns:
            data[column] = data[column].apply(_parse_time)

    ordered_columns = [column for column in [*CORTINAS_COLUMNAS, "Bloque", "Dia"] if column in data.columns]
    return data[ordered_columns].copy()


def prepare_ponderosa_ecowitt(df):
    if df.empty:
        return pd.DataFrame()

    data = df.copy()
    data["finca"] = data["finca"].apply(clean_supabase_text)
    data["bloque"] = data["bloque"].apply(clean_supabase_text)
    data["sensor"] = data["sensor"].apply(clean_supabase_text).str.upper()
    data = data[
        data["finca"].eq("Ponderosa") &
        data["bloque"].eq("EXTERNO ALMACEN") &
        data["sensor"].isin(["ECOWITT", "APOGEE"])
    ].copy()
    if data.empty:
        return pd.DataFrame()

    data["FechaHora"] = _coerce_datetime(data["fecha"])
    data = data.dropna(subset=["FechaHora"]).sort_values("FechaHora")
    ecowitt = data[data["sensor"].eq("ECOWITT")].copy()
    apogee = data[data["sensor"].eq("APOGEE")].copy()

    frames = []
    if not ecowitt.empty:
        frames.append(pd.DataFrame({
            "FechaHora": ecowitt["FechaHora"],
            "Temperatura": pd.to_numeric(ecowitt["temperatura"], errors="coerce"),
            "Humedad Relativa": pd.to_numeric(ecowitt["humedad_relativa"], errors="coerce"),
            "Radiación PAR": pd.to_numeric(ecowitt["radiacion_par"], errors="coerce"),
        }))
    if not apogee.empty:
        frames.append(pd.DataFrame({
            "FechaHora": apogee["FechaHora"],
            "LUX": pd.to_numeric(apogee["luz_lux"], errors="coerce"),
        }))

    if not frames:
        return pd.DataFrame()
    result = frames[0]
    for frame in frames[1:]:
        result = result.merge(frame, on="FechaHora", how="outer")

    result = result.sort_values("FechaHora").reset_index(drop=True)
    result["Fecha_Filtro"] = result["FechaHora"].dt.date
    for variable in PONDEROSA_ECOWITT_DATA_VARIABLES:
        if variable not in result.columns:
            result[variable] = pd.NA
        result[variable] = pd.to_numeric(result[variable], errors="coerce")
    return result[["FechaHora", "Fecha_Filtro", *PONDEROSA_ECOWITT_DATA_VARIABLES]].copy()


def _prepare_marley_source_frame(df, db_sensor, source_name):
    source = df[df["sensor"].str.upper().eq(db_sensor)].copy()
    if source.empty:
        return pd.DataFrame()

    source["FechaHora"] = _coerce_datetime(source["fecha"])
    source = source.dropna(subset=["FechaHora"]).sort_values("FechaHora")
    source["Fecha_Filtro"] = source["FechaHora"].dt.date
    source["Gramos de agua (g)"] = pd.to_numeric(source["gramos_agua"], errors="coerce")
    source["Humedad Relativa (%)"] = pd.to_numeric(source["humedad_relativa"], errors="coerce")
    source["Radiación PAR (µmol m-2 s-1)"] = pd.to_numeric(source["radiacion_par"], errors="coerce")
    source["Temperatura (°C)"] = pd.to_numeric(source["temperatura"], errors="coerce")
    source = source[["FechaHora", "Fecha_Filtro", *MARLEY_VARIABLES]].copy()
    for variable in MARLEY_VARIABLES:
        source.rename(columns={variable: f"{variable} - {source_name}"}, inplace=True)
    return source


def prepare_marley(df):
    if df.empty:
        return pd.DataFrame(), {}

    data = df.copy()
    data["finca"] = data["finca"].apply(clean_supabase_text)
    data["bloque"] = data["bloque"].apply(clean_supabase_text)
    data["sensor"] = data["sensor"].apply(clean_supabase_text)
    data = data[
        data["finca"].eq("Marley") &
        data["bloque"].isin(["MONTAÑA", "MONTANA", "MONTA?A"])
    ].copy()
    if data.empty:
        return pd.DataFrame(), {}

    source_frames = {
        "WIGA": _prepare_marley_source_frame(data, "WIGGA", "WIGA"),
        "ECOWITT": _prepare_marley_source_frame(data, "ECOWITT", "ECOWITT"),
    }
    source_frames = {name: frame for name, frame in source_frames.items() if not frame.empty}

    merged = None
    for frame in source_frames.values():
        merge_frame = frame.drop(columns=["Fecha_Filtro"], errors="ignore")
        merged = merge_frame if merged is None else merged.merge(merge_frame, on="FechaHora", how="outer")

    if merged is None or merged.empty:
        return pd.DataFrame(), source_frames

    merged = merged.sort_values("FechaHora").reset_index(drop=True)
    merged["Fecha_Filtro"] = merged["FechaHora"].dt.date
    return merged, source_frames


def _build_greenhouse_general(analysis):
    if analysis.empty:
        return pd.DataFrame()

    data = analysis.copy().sort_values("bloque")
    return pd.DataFrame({
        "Bloque": data["bloque"],
        "N° Cuadros": pd.to_numeric(data["numero_cuadros"], errors="coerce"),
        "N° Naves": pd.to_numeric(data["numero_naves"], errors="coerce"),
        "N° Culatas": pd.to_numeric(data["numero_culatas"], errors="coerce"),
        "Tamaño del cuadro (m)": pd.to_numeric(data["tamano_cuadro_m"], errors="coerce"),
        "Tamaño de la nave (m)": pd.to_numeric(data["tamano_nave_m"], errors="coerce"),
        "Ancho de culata (m)": pd.to_numeric(data["ancho_culata_m"], errors="coerce"),
        "Alto de culata (m)": pd.to_numeric(data["alto_culata_m"], errors="coerce"),
        "Apertura lateral teórica (m)": pd.to_numeric(data["apertura_lateral_teorica_m"], errors="coerce"),
        "Apertura lateral máxima permitida (m)": pd.to_numeric(data["apertura_lateral_maxima_permitida_m"], errors="coerce"),
        "Apertura lateral real (m)": pd.to_numeric(data["apertura_lateral_real_m"], errors="coerce"),
        "Apertura frontal teórica (m)": pd.to_numeric(data["apertura_frontal_teorica_m"], errors="coerce"),
        "Apertura frontal máxima permitida (m)": pd.to_numeric(data["apertura_frontal_maxima_permitida_m"], errors="coerce"),
        "Apertura frontal real (m)": pd.to_numeric(data["apertura_frontal_real_m"], errors="coerce"),
        "Apertura culatas teórica (m)": pd.to_numeric(data["apertura_culatas_teorica_m"], errors="coerce"),
        "Apertura culatas máxima permitida (m)": pd.to_numeric(data["apertura_culatas_maxima_permitida_m"], errors="coerce"),
        "Apertura culatas real (m)": pd.to_numeric(data["apertura_culatas_real_m"], errors="coerce"),
    })


def _build_greenhouse_areas(general):
    if general.empty:
        return pd.DataFrame()

    rows = []
    for _, row in general.iterrows():
        lateral_factor = (row["N° Cuadros"] - 1) * row["Tamaño del cuadro (m)"] * 2
        frontal_factor = row["N° Naves"] * row["Tamaño de la nave (m)"] * 2
        culatas_factor = row["N° Culatas"] * row["Ancho de culata (m)"]
        area_row = {
            "Bloque": row["Bloque"],
            "Área lateral teórica (m²)": row["Apertura lateral teórica (m)"] * lateral_factor,
            "Área lateral máxima permitida (m²)": row["Apertura lateral máxima permitida (m)"] * lateral_factor,
            "Área lateral real (m²)": row["Apertura lateral real (m)"] * lateral_factor,
            "Área frontal teórica (m²)": row["Apertura frontal teórica (m)"] * frontal_factor,
            "Área frontal máxima permitida (m²)": row["Apertura frontal máxima permitida (m)"] * frontal_factor,
            "Área frontal real (m²)": row["Apertura frontal real (m)"] * frontal_factor,
            "Área culatas teórica (m²)": row["Apertura culatas teórica (m)"] * culatas_factor,
            "Área culatas máxima permitida (m²)": row["Apertura culatas máxima permitida (m)"] * culatas_factor,
            "Área culatas real (m²)": row["Apertura culatas real (m)"] * culatas_factor,
        }
        area_row["Total área teórica (m²)"] = (
            area_row["Área lateral teórica (m²)"] +
            area_row["Área frontal teórica (m²)"] +
            area_row["Área culatas teórica (m²)"]
        )
        area_row["Total área máxima permitida (m²)"] = (
            area_row["Área lateral máxima permitida (m²)"] +
            area_row["Área frontal máxima permitida (m²)"] +
            area_row["Área culatas máxima permitida (m²)"]
        )
        area_row["Total área real (m²)"] = (
            area_row["Área lateral real (m²)"] +
            area_row["Área frontal real (m²)"] +
            area_row["Área culatas real (m²)"]
        )
        area_row["Brecha de ventilación (máx. permitida - real) m²"] = (
            area_row["Total área máxima permitida (m²)"] - area_row["Total área real (m²)"]
        )
        area_row["% máxima permitida frente a teórica"] = (
            area_row["Total área máxima permitida (m²)"] / area_row["Total área teórica (m²)"]
            if area_row["Total área teórica (m²)"] else pd.NA
        )
        area_row["% apertura real frente a máxima permitida"] = (
            area_row["Total área real (m²)"] / area_row["Total área máxima permitida (m²)"]
            if area_row["Total área máxima permitida (m²)"] else pd.NA
        )
        area_row["% apertura real frente a teórica"] = (
            area_row["Total área real (m²)"] / area_row["Total área teórica (m²)"]
            if area_row["Total área teórica (m²)"] else pd.NA
        )
        area_row["% pérdida operativa"] = 1 - area_row["% apertura real frente a máxima permitida"]
        rows.append(area_row)
    return pd.DataFrame(rows)


def _build_greenhouse_summary(indicators):
    if indicators.empty:
        return pd.DataFrame()
    data = indicators.copy().sort_values("bloque")
    return pd.DataFrame({
        "Bloque": data["bloque"],
        "Total Teórica (m²)": pd.to_numeric(data["total_teorica_m2"], errors="coerce"),
        "Total Máx. Perm. (m²)": pd.to_numeric(data["total_maxima_permitida_m2"], errors="coerce"),
        "Total Real (m²)": pd.to_numeric(data["total_real_m2"], errors="coerce"),
        "Brecha Máx-Real (m²)": pd.to_numeric(data["brecha_max_real_m2"], errors="coerce"),
        "% Real / Teórica": pd.to_numeric(data["porcentaje_real_teorica"], errors="coerce"),
        "% Real / Máx. Perm.": pd.to_numeric(data["porcentaje_real_maxima_permitida"], errors="coerce"),
    })


def prepare_greenhouse_analysis(analysis, indicators):
    general = _build_greenhouse_general(analysis)
    areas = _build_greenhouse_areas(general)
    summary = _build_greenhouse_summary(indicators)
    return {
        "general": general,
        "areas": areas,
        "summary": summary,
        "interpretations": pd.DataFrame([
            {"Indicador": "Brecha Máx-Real", "Interpretacion": "Diferencia entre la apertura máxima permitida y la apertura real."},
            {"Indicador": "% Real / Máx. Perm.", "Interpretacion": "Mide cuánto de la capacidad instalada se está usando en operación."},
            {"Indicador": "% Real / Teórica", "Interpretacion": "Compara la ventilación real contra el potencial geométrico del invernadero."},
        ]),
        "guide": pd.DataFrame([
            {"Concepto": "Apertura teórica", "Descripcion": "Capacidad estimada según geometría o referencia base del invernadero."},
            {"Concepto": "Apertura máxima permitida", "Descripcion": "Apertura máxima que permite el sistema instalado."},
            {"Concepto": "Apertura real", "Descripcion": "Apertura efectivamente observada durante la operación."},
        ]),
        "chart_totals": summary[["Bloque", "Total Teórica (m²)", "Total Máx. Perm. (m²)", "Total Real (m²)"]].copy() if not summary.empty else pd.DataFrame(),
        "chart_ratios": summary[["Bloque", "% Real / Teórica", "% Real / Máx. Perm."]].copy() if not summary.empty else pd.DataFrame(),
        "dictionary": pd.DataFrame([
            {"Variable / columna": "Temperatura", "Qué significa": "Temperatura del aire.", "Unidad": "°C", "Cómo se interpreta": "Permite identificar calentamiento o enfriamiento del ambiente.", "Dónde aparece": "variables_ambientales"},
            {"Variable / columna": "Humedad Relativa", "Qué significa": "Porcentaje de humedad del aire.", "Unidad": "%", "Cómo se interpreta": "Ayuda a evaluar déficit o exceso de humedad.", "Dónde aparece": "variables_ambientales"},
            {"Variable / columna": "Radiación PAR", "Qué significa": "Radiación fotosintéticamente activa.", "Unidad": "µmol m-2 s-1", "Cómo se interpreta": "Indica disponibilidad de luz útil para el cultivo.", "Dónde aparece": "variables_ambientales"},
            {"Variable / columna": "Gramos de agua", "Qué significa": "Contenido absoluto de agua.", "Unidad": "g", "Cómo se interpreta": "Complementa la lectura de humedad y temperatura.", "Dónde aparece": "variables_ambientales"},
        ]),
    }
