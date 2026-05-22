from .shared import *
from .analysis import (
    _build_analysis_distribution_table,
    _build_variable_distribution_table,
    _render_analysis_distribution_cards,
    _render_variable_distribution_cards,
)

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


def _load_marley_data():
    return load_marley_data(DATA_CACHE_VERSION)


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
            aggregation = 'std'
        else:
            aggregation = 'var'
        grouped = (
            source_df.groupby(['FranjaMinutos', 'Franja'], as_index=False)
            .agg(Valor=(column_name, aggregation), Registros=(column_name, 'count'))
        )
        if metric_column != 'Promedio':
            grouped['Valor'] = grouped['Valor'].fillna(0.0)
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


def _build_marley_comparison_for_resolution(
    filtered_df,
    variable_name,
    selected_range,
    comparison_resolution
):
    point_mode = comparison_resolution == COMPARISON_RESOLUTION_OPTIONS[1]
    nearest_wiga_mode = comparison_resolution == COMPARISON_RESOLUTION_OPTIONS[2]
    return (
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


def _render_marley_comparison_metric_cards(overlap, selected_variable):
    config = MARLEY_VARIABLES.get(selected_variable)
    if config is None:
        st.info("La variable seleccionada ya no esta disponible para la comparacion WIGA / ECOWITT.")
        return

    avg_abs_diff = overlap['DiffValue'].mean() if not overlap.empty else None
    avg_signed_diff = overlap['SignedDiff'].mean() if not overlap.empty else None
    std_diff = overlap['SignedDiff'].std() if not overlap.empty else None
    unit = config.get('unit', '')

    if pd.isna(avg_signed_diff):
        signed_interpretation = "Sin lecturas simultaneas suficientes para identificar que sensor quedo por encima."
    elif avg_signed_diff > 0:
        signed_interpretation = "En promedio, WIGA estuvo por encima de ECOWITT."
    elif avg_signed_diff < 0:
        signed_interpretation = "En promedio, ECOWITT estuvo por encima de WIGA."
    else:
        signed_interpretation = "En promedio, ambos sensores quedaron practicamente alineados."

    if pd.isna(std_diff):
        std_interpretation = "Sin lecturas comparables suficientes para medir estabilidad."
    elif std_diff <= 0.3:
        std_interpretation = "La diferencia entre sensores fue bastante estable durante el periodo."
    elif std_diff <= 0.8:
        std_interpretation = "La diferencia entre sensores tuvo una variacion moderada."
    else:
        std_interpretation = "La diferencia entre sensores cambio bastante entre franjas."

    metrics = [
        {
            'label': 'Diferencia absoluta media',
            'value': f"{avg_abs_diff:.2f}" if pd.notna(avg_abs_diff) else "Sin datos",
            'accent': config['colors']['WIGA'],
            'note': f"Separacion promedio sin importar que sensor quedo arriba. Unidad: {unit}.",
        },
        {
            'label': 'Diferencia media WIGA - ECOWITT',
            'value': f"{avg_signed_diff:+.2f}" if pd.notna(avg_signed_diff) else "Sin datos",
            'accent': config['colors']['ECOWITT'],
            'note': f"{signed_interpretation} Unidad: {unit}.",
        },
        {
            'label': 'Estabilidad de la diferencia',
            'value': f"{std_diff:.2f}" if pd.notna(std_diff) else "Sin datos",
            'accent': config.get('accent', BRAND_COLORS['hero']),
            'note': f"{std_interpretation} Unidad: {unit}.",
        },
    ]

    cards_html = ['<div class="analysis-metrics-grid">']
    for metric in metrics:
        cards_html.append(
            '<div class="analysis-metric-card" style="--analysis-accent: {accent};">'
            '<p class="analysis-metric-label">{label}</p>'
            '<p class="analysis-metric-value">{value}</p>'
            '<p class="analysis-note">{note}</p>'
            '</div>'.format(
                accent=html.escape(metric['accent']),
                label=html.escape(metric['label']),
                value=html.escape(metric['value']),
                note=html.escape(metric['note']),
            )
        )
    cards_html.append('</div>')
    st.markdown(''.join(cards_html), unsafe_allow_html=True)


def _render_marley_comparison_tabs(
    filtered_df,
    selected_range,
    compared_variables,
    comparison_resolution,
    marley_source_data
):
    if st.session_state.get("marley_chart_variable") not in compared_variables:
        st.session_state["marley_chart_variable"] = compared_variables[0]
    if st.session_state.get("marley_stats_variable") not in compared_variables:
        st.session_state["marley_stats_variable"] = compared_variables[0]

    tab_compare, tab_stats, tab_detail, tab_records = st.tabs([
        "Grafica",
        "Analisis estadistico",
        "Graficas individuales",
        "Registros",
    ])

    with tab_compare:
        _render_chart_explanation(
            "Comparacion directa WIGA / ECOWITT",
            "Elige una variable para comparar ambos sensores sobre la misma linea de tiempo. Marly queda organizado igual que Ponderosa y solo se calcula la grafica activa.",
            accent=BRAND_COLORS['hero'],
            kicker='Vista principal'
        )
        selected_chart_variable = st.segmented_control(
            "Variable en grafica:",
            options=compared_variables,
            format_func=lambda value: _format_variable_display_title(MARLEY_VARIABLES.get(value, {}).get('title', value)),
            key="marley_chart_variable",
            width="stretch"
        )
        if selected_chart_variable not in compared_variables:
            selected_chart_variable = compared_variables[0]
        comparison = _build_marley_comparison_for_resolution(
            filtered_df,
            selected_chart_variable,
            selected_range,
            comparison_resolution
        )
        if comparison.empty or comparison.dropna(how='all', subset=list(MARLEY_SENSOR_NAMES)).empty:
            variable_title = MARLEY_VARIABLES.get(selected_chart_variable, {}).get('title', selected_chart_variable)
            st.info(f"No hay datos suficientes para graficar {_format_variable_display_title(variable_title)}.")
        else:
            _plotly_chart(_make_marley_comparison_chart(comparison, selected_chart_variable, selected_range, comparison_resolution))

    with tab_stats:
        _render_chart_explanation(
            "Analisis de relacion WIGA / ECOWITT",
            "Aqui queda la lectura estadistica de una variable: diferencias, dispersion y estabilidad. Cambia la variable sin recalcular todas las graficas de Marly.",
            accent=BRAND_COLORS['rose'],
            kicker='Lectura estadistica'
        )
        selected_variable_stats = st.segmented_control(
            "Variable para detalle estadistico:",
            options=compared_variables,
            format_func=lambda value: _format_variable_display_title(MARLEY_VARIABLES.get(value, {}).get('title', value)),
            key="marley_stats_variable",
            width="stretch"
        )
        if selected_variable_stats not in compared_variables:
            selected_variable_stats = compared_variables[0]
        comparison_stats = _build_marley_comparison_for_resolution(
            filtered_df,
            selected_variable_stats,
            selected_range,
            comparison_resolution
        )
        if not all(sensor_name in comparison_stats.columns for sensor_name in MARLEY_SENSOR_NAMES):
            st.info("No hay columnas suficientes para construir el resumen estadistico de esta variable.")
        else:
            overlap = comparison_stats.dropna(subset=list(MARLEY_SENSOR_NAMES)).copy()
            _render_marley_comparison_metric_cards(overlap, selected_variable_stats)
            difference_chart = _make_marley_difference_chart(comparison_stats, selected_variable_stats, selected_range, comparison_resolution)
            if difference_chart is not None:
                _render_chart_explanation(
                    'Diferencia WIGA - ECOWITT',
                    'Valores sobre cero significan que WIGA midio mas alto; valores bajo cero significan que ECOWITT midio mas alto.',
                    accent=MARLEY_VARIABLES[selected_variable_stats]['colors']['ECOWITT']
                )
                _plotly_chart(difference_chart)
            scatter_chart = _make_marley_scatter_chart(comparison_stats, selected_variable_stats)
            if scatter_chart is not None:
                _render_chart_explanation(
                    'Dispersion entre sensores',
                    'Cada punto cruza una lectura simultanea de WIGA y ECOWITT. Mientras mas cerca este de la linea diagonal, mas parecidos fueron ambos sensores.',
                    accent=MARLEY_VARIABLES[selected_variable_stats]['colors']['WIGA']
                )
                _plotly_chart(scatter_chart)
            else:
                st.info("No hay suficientes datos simultaneos entre WIGA y ECOWITT para construir la dispersion.")

    with tab_detail:
        if st.checkbox(
            "Cargar variables individuales",
            key="mostrar_marley_detalles",
            help=FILTER_HELP_TEXTS['graficas_detalladas']
        ):
            _render_marley_individual_variable_charts(
                filtered_df,
                selected_range,
                resolution_label=comparison_resolution
            )

    with tab_records:
        _render_chart_explanation(
            "Registros consolidados Marly",
            "Tablas de soporte para la comparacion: resumen por equipo, diferencias por franja y registros consolidados.",
            accent=BRAND_COLORS['hero'],
            kicker='Datos fuente'
        )
        record_report_options = [
            "Resumen por equipo",
            "Diferencias WIGA - ECOWITT",
            "Registros consolidados",
        ]
        if st.session_state.get("marley_records_report") not in record_report_options:
            st.session_state["marley_records_report"] = record_report_options[0]
        selected_records_report = st.segmented_control(
            "Reporte",
            options=record_report_options,
            key="marley_records_report",
            help="Selecciona que tabla quieres revisar o descargar.",
            width="stretch"
        )

        if selected_records_report == "Resumen por equipo":
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

        elif selected_records_report == "Diferencias WIGA - ECOWITT":
            difference_table, difference_table_mode = _build_difference_table_30min(
                filtered_df,
                compared_variables,
                MARLEY_SENSOR_NAMES,
                selected_range,
                comparison_resolution,
                _build_marley_hourly_comparison,
                _build_marley_hourly_series,
                MARLEY_VARIABLES
            )
            if difference_table.empty:
                st.info("No hay datos suficientes para construir la tabla de diferencias.")
            else:
                st.caption(f"Tabla calculada con: {difference_table_mode}. La diferencia se calcula como WIGA - ECOWITT.")
                _render_comparison_table_summary(difference_table, title="Resumen ejecutivo de diferencias")
                _render_variable_split_tables(
                    difference_table,
                    default_expanded=True,
                    download_label="Descargar reporte Marly WIGA vs ECOWITT",
                    download_file_name=f"marly_wiga_ecowitt_{_build_report_slug(difference_table_mode)}.xlsx",
                    download_key="download_marley_difference_report"
                )

        elif selected_records_report == "Registros consolidados":
            _dataframe(filtered_df.drop(columns=['Fecha_Filtro'], errors='ignore'), hide_index=True)


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
            f'Elige una variable de {source_name} con los botones de la vista principal. El detalle completo queda bajo demanda para mantener el dashboard liviano.',
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

        source_variables = list(MARLEY_VARIABLES.keys())
        source_variable_key = f"marley_{source_name.lower()}_source_variable"
        if st.session_state.get(source_variable_key) not in source_variables:
            st.session_state[source_variable_key] = source_variables[0]
        graphed_frame = _build_single_source_correlacion_frame(
            filtered_df,
            selected_range,
            source_variables,
            source_name,
            _build_marley_individual_series,
            source_resolution,
        )
        if graphed_frame.empty:
            st.warning(f"No hay datos suficientes para graficar las variables de {source_name} en el periodo seleccionado.")
            st.stop()

        tab_general, tab_stats, tab_detail, tab_records = st.tabs(["Gráfica", "Resumen estadístico", "Detalle individual", "Registros"])
        with tab_general:
            _render_chart_explanation(
                f"Variable {source_name}",
                "Selecciona una variable para verla limpia y con mas espacio. El resto de variables queda disponible en los botones superiores, igual que en las comparativas.",
                accent=BRAND_COLORS['hero'],
                kicker='Vista principal'
            )
            selected_source_variable = st.segmented_control(
                "Variable en grafica:",
                options=source_variables,
                format_func=lambda value: _format_variable_display_title(MARLEY_VARIABLES.get(value, {}).get('title', value)),
                key=source_variable_key,
                width="stretch"
            )
            if selected_source_variable not in source_variables:
                selected_source_variable = source_variables[0]
            selected_chart = _make_marley_individual_variable_chart(
                filtered_df,
                selected_source_variable,
                source_name,
                selected_range,
                source_resolution
            )
            if selected_chart is None:
                variable_title = MARLEY_VARIABLES.get(selected_source_variable, {}).get('title', selected_source_variable)
                st.info(f"No hay datos suficientes para graficar {_format_variable_display_title(variable_title)}.")
            else:
                selected_chart.update_layout(height=430, margin=dict(l=28, r=20, t=58, b=48))
                _plotly_chart(selected_chart)

        with tab_stats:
            stats_table = _build_variable_distribution_table(graphed_frame, source_variables)
            _render_variable_distribution_cards(
                stats_table,
                MARLEY_VARIABLES,
                title=f"Resumen estadístico {source_name} - Marly"
            )
            if not stats_table.empty:
                with st.expander("Ver resumen estadístico en tabla", expanded=False):
                    _dataframe(stats_table.round(2), hide_index=True)

        with tab_detail:
            if st.checkbox(
                f"Cargar detalle individual {source_name}",
                key=f"mostrar_marley_{source_name.lower()}_detalle",
                help=FILTER_HELP_TEXTS['graficas_detalladas']
            ):
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
                source_variables,
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

    if dashboard_mode in ("Varianza", "Desviacion estandar", "Promedio"):
        show_marley_details = st.checkbox(
            "Cargar variables individuales",
            key="mostrar_marley_detalles",
            help=FILTER_HELP_TEXTS['graficas_detalladas']
        )
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
    _render_marley_comparison_tabs(
        filtered_df,
        selected_range,
        compared_variables,
        comparison_resolution,
        marley_source_data
    )
    st.stop()

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




__all__ = [name for name in globals() if not name.startswith("__")]
