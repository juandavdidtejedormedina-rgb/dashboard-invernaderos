"""Import environmental Excel files into Supabase safely.

Default behavior is a dry run: it reads the Excel files, creates a staging CSV
and reports how many rows are already present in Supabase. Use --upload only
after reviewing the report.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = REPO_ROOT.parent
sys.path.insert(0, str(REPO_ROOT))

from supabase_client import get_supabase_settings, load_supabase_table  # noqa: E402


TARGET_TABLE = "variables_ambientales"
OUTPUT_COLUMNS = [
    "fecha",
    "finca",
    "bloque",
    "sensor",
    "temperatura",
    "humedad_relativa",
    "radiacion_par",
    "gramos_agua",
    "luz_lux",
]
UNIQUE_KEY = ["fecha", "finca", "bloque", "sensor"]
BATCH_SIZE = 500


def _default_data_dir() -> Path:
    return PROJECT_ROOT / "Datos" / "Datos 22-02-2026"


def _default_output_dir() -> Path:
    return PROJECT_ROOT / "staging_supabase" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def _normalize_text(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return "".join(char.lower() if char.isalnum() else " " for char in text).strip()


def _find_column(df: pd.DataFrame, *keywords: str) -> str:
    normalized_keywords = [_normalize_text(keyword) for keyword in keywords]
    for column in df.columns:
        normalized_column = _normalize_text(column)
        if all(keyword in normalized_column for keyword in normalized_keywords):
            return column
    raise ValueError(f"No encontre columna con palabras: {keywords}. Columnas: {list(df.columns)}")


def _find_any_column(df: pd.DataFrame, *keyword_options: tuple[str, ...]) -> str:
    errors = []
    for keywords in keyword_options:
        try:
            return _find_column(df, *keywords)
        except ValueError as error:
            errors.append(str(error))
    raise ValueError("No encontre ninguna columna candidata. " + " | ".join(errors))


def _coerce_number(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _combine_fecha_hora(fecha: pd.Series, hora: pd.Series) -> pd.Series:
    fecha_text = pd.to_datetime(fecha, errors="coerce").dt.strftime("%Y-%m-%d")
    hora_text = hora.apply(_format_time_value)
    return pd.to_datetime(fecha_text + " " + hora_text, errors="coerce")


def _format_time_value(value: object) -> str:
    if pd.isna(value):
        return ""
    if hasattr(value, "hour") and hasattr(value, "minute"):
        second = getattr(value, "second", 0)
        return f"{value.hour:02d}:{value.minute:02d}:{second:02d}"
    text = str(value).strip()
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return text
    return parsed.strftime("%H:%M:%S")


def _to_supabase_timestamp(series: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce")
    return parsed.dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _build_frame(
    fecha: pd.Series,
    finca: str,
    bloque: str,
    sensor: str,
    temperatura: pd.Series | None = None,
    humedad_relativa: pd.Series | None = None,
    radiacion_par: pd.Series | None = None,
    gramos_agua: pd.Series | None = None,
    luz_lux: pd.Series | None = None,
) -> pd.DataFrame:
    row_count = len(fecha)
    data = pd.DataFrame({
        "fecha": _to_supabase_timestamp(fecha),
        "finca": finca,
        "bloque": bloque,
        "sensor": sensor,
        "temperatura": _coerce_number(temperatura) if temperatura is not None else [pd.NA] * row_count,
        "humedad_relativa": _coerce_number(humedad_relativa) if humedad_relativa is not None else [pd.NA] * row_count,
        "radiacion_par": _coerce_number(radiacion_par) if radiacion_par is not None else [pd.NA] * row_count,
        "gramos_agua": _coerce_number(gramos_agua) if gramos_agua is not None else [pd.NA] * row_count,
        "luz_lux": _coerce_number(luz_lux) if luz_lux is not None else [pd.NA] * row_count,
    })
    data = data.dropna(subset=["fecha"])
    return data[OUTPUT_COLUMNS]


def _load_ponderosa_wigga(path: Path) -> pd.DataFrame:
    frames = []
    workbook = pd.ExcelFile(path)
    for sheet in workbook.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet)
        if df.empty:
            continue

        fecha = _combine_fecha_hora(df[_find_column(df, "fecha")], df[_find_column(df, "hora")])
        bloque = "EXTERNO ALMACEN" if _normalize_text(sheet) == "almacen" else sheet.strip().upper()
        frames.append(_build_frame(
            fecha=fecha,
            finca="Ponderosa",
            bloque=bloque,
            sensor="WIGGA",
            temperatura=df[_find_column(df, "temperatura")],
            humedad_relativa=df[_find_column(df, "humedad")],
            radiacion_par=df[_find_column(df, "radiacion", "par")],
            gramos_agua=df[_find_column(df, "gramos")],
        ))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=OUTPUT_COLUMNS)


def _load_ponderosa_ecowitt_apogee(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name=0)
    timestamp = pd.to_datetime(df[_find_column(df, "timestamp")], errors="coerce")
    if timestamp.isna().all():
        timestamp = pd.to_datetime(df[_find_column(df, "tiempo")], errors="coerce")

    ecowitt = _build_frame(
        fecha=timestamp,
        finca="Ponderosa",
        bloque="EXTERNO ALMACEN",
        sensor="ECOWITT",
        temperatura=df[_find_column(df, "temperatura")],
        humedad_relativa=df[_find_column(df, "humedad")],
        radiacion_par=df[_find_any_column(df, ("radiacion",), ("ppfd",), ("par",))],
    )
    apogee = _build_frame(
        fecha=timestamp,
        finca="Ponderosa",
        bloque="EXTERNO ALMACEN",
        sensor="APOGEE",
        luz_lux=df[_find_column(df, "lux")],
    )
    return pd.concat([ecowitt, apogee], ignore_index=True)


def _load_marley(path: Path) -> pd.DataFrame:
    frames = []
    workbook = pd.ExcelFile(path)
    for sheet in workbook.sheet_names:
        df = pd.read_excel(path, sheet_name=sheet)
        if df.empty:
            continue

        normalized_sheet = _normalize_text(sheet)
        if "wigga" in normalized_sheet or "wiga" in normalized_sheet:
            fecha = _combine_fecha_hora(df[_find_column(df, "fecha")], df[_find_column(df, "hora")])
            sensor = "WIGGA"
        elif "ecowitt" in normalized_sheet:
            fecha = pd.to_datetime(df[_find_column(df, "tiempo")], errors="coerce")
            sensor = "ECOWITT"
        else:
            continue

        frames.append(_build_frame(
            fecha=fecha,
            finca="Marley",
            bloque="MONTAÑA",
            sensor=sensor,
            temperatura=df[_find_column(df, "temperatura")],
            humedad_relativa=df[_find_column(df, "humedad")],
            radiacion_par=df[_find_column(df, "radiacion")],
            gramos_agua=df[_find_column(df, "gramos")],
        ))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=OUTPUT_COLUMNS)


def _key_frame(df: pd.DataFrame) -> pd.Series:
    return df[UNIQUE_KEY].fillna("").astype(str).agg("|".join, axis=1)


def _deduplicate_staging(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    before = len(df)
    df = df.drop_duplicates(subset=UNIQUE_KEY, keep="last").copy()
    return df, before - len(df)


def _split_existing_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    existing = load_supabase_table(
        TARGET_TABLE,
        cache_version=f"import-existing-keys-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        select="fecha,finca,bloque,sensor",
    )
    if existing.empty:
        return df.copy(), df.iloc[0:0].copy()

    existing_keys = set(_key_frame(existing))
    staging_keys = _key_frame(df)
    already_exists = staging_keys.isin(existing_keys)
    return df.loc[~already_exists].copy(), df.loc[already_exists].copy()


def _records_for_json(df: pd.DataFrame) -> list[dict]:
    records = []
    for record in df[OUTPUT_COLUMNS].to_dict(orient="records"):
        clean_record = {}
        for key, value in record.items():
            if value is pd.NA or value is None:
                clean_record[key] = None
            elif isinstance(value, float) and math.isnan(value):
                clean_record[key] = None
            else:
                clean_record[key] = value
        records.append(clean_record)
    return records


def _insert_records(df: pd.DataFrame) -> None:
    if df.empty:
        return

    url, key = get_supabase_settings()
    endpoint = f"{url}/rest/v1/{TARGET_TABLE}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    records = _records_for_json(df)
    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start:start + BATCH_SIZE]
        response = requests.post(endpoint, headers=headers, json=batch, timeout=60)
        response.raise_for_status()


def build_staging(data_dir: Path) -> tuple[pd.DataFrame, dict]:
    sources = {
        "Datos_Variables.xlsx": _load_ponderosa_wigga(data_dir / "Datos_Variables.xlsx"),
        "ECOWITT Ponderosa.xlsx": _load_ponderosa_ecowitt_apogee(data_dir / "ECOWITT Ponderosa.xlsx"),
        "Datos Final Marley.xlsx": _load_marley(data_dir / "Datos Final Marley.xlsx"),
    }
    combined = pd.concat(sources.values(), ignore_index=True)
    deduped, source_duplicate_rows = _deduplicate_staging(combined)
    report = {
        "source_rows_by_file": {name: int(len(frame)) for name, frame in sources.items()},
        "source_rows_total": int(len(combined)),
        "source_duplicate_rows_removed": int(source_duplicate_rows),
        "staging_rows_after_source_dedupe": int(len(deduped)),
        "date_min": str(pd.to_datetime(deduped["fecha"], errors="coerce").min()) if not deduped.empty else None,
        "date_max": str(pd.to_datetime(deduped["fecha"], errors="coerce").max()) if not deduped.empty else None,
        "rows_by_finca_bloque_sensor": (
            deduped.groupby(["finca", "bloque", "sensor"], dropna=False)
            .size()
            .reset_index(name="rows")
            .to_dict(orient="records")
        ),
    }
    return deduped, report


def _print_permission_error(error: PermissionError) -> None:
    print("")
    print("No pude leer uno de los Excel porque Windows lo tiene bloqueado.")
    print("Cierra el archivo en Excel y espera unos segundos a que OneDrive termine de sincronizar.")
    print(f"Archivo bloqueado: {error.filename}")
    print("")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare or upload variables_ambientales from Excel files.")
    parser.add_argument("--data-dir", type=Path, default=_default_data_dir())
    parser.add_argument("--output-dir", type=Path, default=_default_output_dir())
    parser.add_argument("--upload", action="store_true", help="Insert only rows that do not already exist in Supabase.")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        staging, report = build_staging(args.data_dir)
    except PermissionError as error:
        _print_permission_error(error)
        return 1
    new_rows, existing_rows = _split_existing_rows(staging)
    report.update({
        "rows_already_in_supabase": int(len(existing_rows)),
        "rows_ready_to_insert": int(len(new_rows)),
        "upload_executed": bool(args.upload),
    })

    staging_path = args.output_dir / "variables_ambientales_staging_all.csv"
    new_rows_path = args.output_dir / "variables_ambientales_new_rows.csv"
    existing_rows_path = args.output_dir / "variables_ambientales_already_existing.csv"
    report_path = args.output_dir / "import_report.json"

    staging.to_csv(staging_path, index=False, encoding="utf-8-sig")
    new_rows.to_csv(new_rows_path, index=False, encoding="utf-8-sig")
    existing_rows.to_csv(existing_rows_path, index=False, encoding="utf-8-sig")

    if args.upload:
        _insert_records(new_rows)
        report["uploaded_rows"] = int(len(new_rows))
    else:
        report["uploaded_rows"] = 0

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Output: {args.output_dir}")
    print(f"Total leido: {report['source_rows_total']}")
    print(f"Duplicados dentro de archivos removidos: {report['source_duplicate_rows_removed']}")
    print(f"Ya existian en Supabase: {report['rows_already_in_supabase']}")
    print(f"Listos para insertar: {report['rows_ready_to_insert']}")
    print(f"Upload ejecutado: {report['upload_executed']}")
    if not args.upload:
        print("Modo vista previa. Para subir, vuelve a ejecutar con --upload.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
