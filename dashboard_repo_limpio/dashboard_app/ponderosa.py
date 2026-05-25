from .shared import *
from .marly import *
from .analysis import *

def _load_ponderosa_ecowitt_data():
    return load_ponderosa_ecowitt_data(DATA_CACHE_VERSION)


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
    config = PONDEROSA_COMPARISON_VARIABLES.get(variable)
    if config is None:
        return None

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

    config = PONDEROSA_COMPARISON_VARIABLES.get(variable)
    if config is None:
        return None

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
    if not all(sensor_name in comparison.columns for sensor_name in PONDEROSA_SENSOR_NAMES):
        return None

    hourly = comparison.dropna(subset=list(PONDEROSA_SENSOR_NAMES)).copy()
    if hourly.empty:
        return None

    config = PONDEROSA_COMPARISON_VARIABLES.get(variable)
    if config is None:
        return None

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
    wiga_variables = _render_variable_visibility_selector(
        wiga_variables,
        key_prefix="ponderosa_wiga_only_variables",
        label_map={
            variable: _format_variable_display_title(PONDEROSA_WIGA_VARIABLES.get(variable, {}).get('title', variable))
            for variable in wiga_variables
        },
        title="Variables visibles WIGA",
        description="La seleccion se aplica a la grafica, el resumen estadistico, el detalle individual y la tabla de registros graficados.",
        expander_label="Variables visibles WIGA",
        expanded=True,
    )
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
    _ensure_cortina_visibility_state(available_motors)
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
    selected_motors = _get_selected_cortina_motors(available_motors)
    tab_chart, tab_summary, tab_records = st.tabs(["Gráfica", "Resumen operativo", "Registros"])
    with tab_chart:
        chart_col, controls_col = st.columns([4.45, 0.95], vertical_alignment="top")
        with controls_col:
            _render_cortina_visibility_panel(available_motors)
        selected_motors = _get_selected_cortina_motors(available_motors)
        with chart_col:
            if not selected_motors:
                st.warning("Selecciona al menos una cortina para graficar.")
            else:
                chart = _build_cortinas_only_chart(filtered_df, selected_range, selected_motors, block_label=block_label)
                if chart is None:
                    st.warning("No hay informacion de apertura para las cortinas seleccionadas.")
                else:
                    _plotly_chart(chart)
                    _render_chart_explanation(
                        "Comportamiento de cortinas",
                        "Las cortinas cerradas se muestran en 0% como en el registro original. El eje de tiempo se resume por horas para leer mejor el dia completo; pasa el cursor por cada punto para ver inicio de apertura, duracion y cierre cuando esa informacion exista en el registro.",
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
    ecowitt_variables = _render_variable_visibility_selector(
        ecowitt_variables,
        key_prefix="ponderosa_ecowitt_only_variables",
        label_map={
            variable: _format_variable_display_title(PONDEROSA_ECOWITT_VARIABLES.get(variable, {}).get('title', variable))
            for variable in ecowitt_variables
        },
        title="Variables visibles ECOWITT",
        description="La seleccion se aplica a la grafica, el resumen estadistico, el detalle individual y la tabla de registros graficados.",
        expander_label="Variables visibles ECOWITT",
        expanded=True,
    )
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
            _render_ponderosa_source_individual_charts(
                filtered_df,
                selected_range,
                ecowitt_variables,
                ("ECOWITT",),
                "Variables individuales ECOWITT Ponderosa",
                "Estas graficas muestran las variables ECOWITT/MCI seleccionadas, sin mezclar la luminosidad de APOGEE.",
                ecowitt_resolution
            )

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

    light_variables = list(PONDEROSA_LIGHT_VARIABLES.keys())
    if st.session_state.get("ponderosa_light_chart_variable") not in light_variables:
        st.session_state["ponderosa_light_chart_variable"] = light_variables[0]
    if st.session_state.get("ponderosa_light_stats_variable") not in light_variables:
        st.session_state["ponderosa_light_stats_variable"] = light_variables[0]

    tab_compare, tab_stats, tab_detail, tab_records = st.tabs([
        "Gráfica",
        "Análisis estadístico",
        "Gráficas individuales",
        "Registros"
    ])
    with tab_compare:
        _render_chart_explanation(
            "Comparación directa APOGEE / MCI / WIGA",
            "Elige LUX o PPFD (PAR) para revisar los tres sensores sobre la misma línea de tiempo. Las diferencias y tablas quedan organizadas en análisis y registros.",
            accent=BRAND_COLORS['hero'],
            kicker='Vista principal'
        )
        _render_selected_period_banner(
            selected_range,
            min_fecha=min_date,
            max_fecha=max_date,
            navigation_state_key=navigation_state_key,
            title_text='Periodo APOGEE / MCI / WIGA',
            available_dates=available_dates,
            context_text=f'Estás viendo {block_label}; WIGA usa Datos_Variables y MCI/APOGEE usan ECOWITT Ponderosa.'
        )
        selected_light_chart_variable = st.segmented_control(
            "Variable en gráfica:",
            options=light_variables,
            format_func=lambda value: _format_variable_display_title(PONDEROSA_LIGHT_VARIABLES.get(value, {}).get('title', value)),
            key="ponderosa_light_chart_variable",
            width="stretch"
        )
        if selected_light_chart_variable not in light_variables:
            selected_light_chart_variable = light_variables[0]
        comparison = comparisons.get(selected_light_chart_variable, pd.DataFrame())
        chart = _make_ponderosa_light_comparison_chart(
            comparison,
            selected_light_chart_variable,
            selected_range,
            comparison_resolution
        )
        if chart is None:
            st.info(f"No hay suficientes datos para graficar {PONDEROSA_LIGHT_VARIABLES[selected_light_chart_variable]['title'].lower()}.")
        else:
            _plotly_chart(chart)

    with tab_stats:
        _render_chart_explanation(
            "Análisis de relación APOGEE / MCI / WIGA",
            (
                "Esta sección muestra la lectura visual de los tres sensores: comportamiento por franja, "
                "tarjetas de resumen y diferencias contra WIGA. Las tablas y descargas están reunidas en Registros."
            ),
            accent=BRAND_COLORS['rose'],
            kicker='Lectura estadística'
        )
        light_stats_source = _build_ponderosa_light_stats_source(filtered_df, light_variables)
        if light_stats_source.empty:
            st.info("No hay datos suficientes para construir la gráfica estadística APOGEE / MCI / WIGA.")
        else:
            _render_ponderosa_light_combined_metric_analysis(
                light_stats_source,
                selected_range,
                light_variables
            )

        selected_light_stats_variable = st.segmented_control(
            "Variable para diferencia:",
            options=light_variables,
            format_func=lambda value: _format_variable_display_title(PONDEROSA_LIGHT_VARIABLES.get(value, {}).get('title', value)),
            key="ponderosa_light_stats_variable",
            width="stretch"
        )
        if selected_light_stats_variable not in light_variables:
            selected_light_stats_variable = light_variables[0]
        stats_comparison = comparisons.get(selected_light_stats_variable, pd.DataFrame())
        difference_chart = _make_ponderosa_light_difference_chart(
            stats_comparison,
            selected_light_stats_variable,
            selected_range,
            comparison_resolution
        )
        if difference_chart is not None:
            _render_chart_explanation(
                f'Diferencia de {PONDEROSA_LIGHT_VARIABLES[selected_light_stats_variable]["title"].replace("Comparativa de ", "")}',
                'Esta gráfica no muestra el valor absoluto, sino cuánto se separan MCI y APOGEE respecto a WIGA. La línea cero significa que el sensor está igual a WIGA; arriba mide más alto y abajo mide más bajo.',
                accent=PONDEROSA_LIGHT_VARIABLES[selected_light_stats_variable]['accent']
            )
            _plotly_chart(difference_chart)
        else:
            st.info("No hay suficientes datos comparables para construir la gráfica de diferencias.")

    with tab_detail:
        _render_ponderosa_light_individual_charts(comparisons, selected_range, comparison_resolution)

    with tab_records:
        _render_chart_explanation(
            "Registros y reportes APOGEE / MCI / WIGA",
            "Aquí quedan reunidas las tablas que soportan la comparación: resumen por sensor, tabla por franja, diferencias y registros base.",
            accent=BRAND_COLORS['hero'],
            kicker='Datos fuente'
        )
        table_mode = (
            "Promedio de cada sensor en bloques de 30 minutos"
            if comparison_resolution == COMPARISON_RESOLUTION_OPTIONS[0] else
            "WIGA crudo con MCI/APOGEE más cercanos"
            if comparison_resolution == COMPARISON_RESOLUTION_OPTIONS[1] else
            "WIGA 30 min con MCI/APOGEE más cercanos"
        )
        summary_rows = []
        for source_name, source_df in source_frames.items():
            current = source_df[source_df['Fecha_Filtro'].between(*selected_range)] if not source_df.empty else pd.DataFrame()
            summary_rows.append({
                'Sensor': source_name,
                'Registros': len(current),
                'Inicio': current['FechaHora'].min().strftime('%Y-%m-%d %H:%M') if not current.empty else '-',
                'Fin': current['FechaHora'].max().strftime('%Y-%m-%d %H:%M') if not current.empty else '-',
            })
        source_summary_table = pd.DataFrame(summary_rows)
        consolidated_records = filtered_df.drop(columns=['Fecha_Filtro'], errors='ignore')

        record_report_options = [
            "Resumen por sensor",
            "Tabla por franja",
            "Diferencias y comparativa",
            "Registros consolidados",
        ]
        if st.session_state.get("ponderosa_light_records_report") not in record_report_options:
            st.session_state["ponderosa_light_records_report"] = record_report_options[0]
        selected_records_report = st.segmented_control(
            "Reporte",
            options=record_report_options,
            key="ponderosa_light_records_report",
            help="Selecciona qué tabla quieres revisar o descargar.",
            width="stretch"
        )

        if selected_records_report == "Resumen por sensor":
            st.caption("Conteo y ventana temporal disponible por sensor dentro del periodo seleccionado.")
            _dataframe(source_summary_table, hide_index=True)

        elif selected_records_report == "Tabla por franja":
            if light_stats_source.empty:
                st.info("No hay datos suficientes para construir la tabla por franja.")
            else:
                selected_metric_label = st.session_state.get("ponderosa_light_stats_metric", "Promedio")
                metric_column = {
                    "Promedio": "Promedio",
                    "Desviacion estandar": "DesviacionEstandar",
                    "Varianza": "Varianza",
                }.get(selected_metric_label, "Promedio")
                selected_variable_table = st.session_state.get("ponderosa_light_stats_graph_variable", light_variables[0])
                if selected_variable_table not in light_variables:
                    selected_variable_table = light_variables[0]
                grouped_df, pivot_promedio, pivot_varianza, pivot_desviacion = _build_hourly_block_analysis(
                    light_stats_source,
                    selected_variable_table
                )
                pivot_map = {
                    "Promedio": pivot_promedio,
                    "DesviacionEstandar": pivot_desviacion,
                    "Varianza": pivot_varianza,
                }
                table = _prepare_hourly_pivot_display(pivot_map.get(metric_column, pivot_promedio))
                if table.empty:
                    st.info("No hay tabla disponible para la métrica y variable seleccionadas en análisis.")
                else:
                    st.caption(
                        "Tabla calculada con la métrica y variable seleccionadas en Análisis estadístico. "
                        "Cambia la gráfica allí para actualizar esta salida."
                    )
                    report_slug = _build_report_slug(block_label, selected_variable_table, selected_metric_label, comparison_resolution)
                    _render_table_download_button(
                        table,
                        f"Descargar tabla de {selected_metric_label.lower()}",
                        f"apogee_mci_wiga_franja_{report_slug}.xlsx",
                        "download_ponderosa_light_tabla_franja"
                    )
                    _dataframe(table, hide_index=True)

        elif selected_records_report == "Diferencias y comparativa":
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
                    download_file_name=f"reporte_apogee_mci_wiga_{_build_report_slug(block_label, table_mode)}.xlsx",
                    download_key="descargar_ponderosa_light_reporte"
                )

        elif selected_records_report == "Registros consolidados":
            st.caption("Datos base consolidados que alimentan las gráficas y cálculos de APOGEE / MCI / WIGA.")
            _render_table_download_button(
                consolidated_records,
                "Descargar registros consolidados",
                f"registros_apogee_mci_wiga_{_build_report_slug(block_label, comparison_resolution)}.xlsx",
                "download_ponderosa_light_registros",
                variable_column='__consolidado__'
            )
            _dataframe(consolidated_records, hide_index=True)

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


def _build_ponderosa_ecowitt_comparison(filtered_df, variable_name, selected_range, resolution_label):
    if resolution_label == COMPARISON_RESOLUTION_OPTIONS[1]:
        return _build_point_comparison(filtered_df, variable_name, PONDEROSA_SENSOR_NAMES)
    if resolution_label == COMPARISON_RESOLUTION_OPTIONS[2]:
        return _build_wiga_anchor_nearest_comparison(
            filtered_df,
            variable_name,
            PONDEROSA_SENSOR_NAMES,
            selected_range,
            _build_ponderosa_hourly_series
        )
    return _build_ponderosa_hourly_comparison(filtered_df, variable_name, selected_range)


def _build_ponderosa_ecowitt_period_summary(filtered_df, variables, selected_range, resolution_label, metric_name='Promedio'):
    rows = []
    metric_lookup = {
        'Promedio': 'mean',
        'Desviacion estandar': 'std',
        'Varianza': 'var',
    }
    aggregation = metric_lookup.get(metric_name, 'mean')
    multi_day = selected_range[0] != selected_range[1]

    for variable_name in variables:
        comparison = _build_ponderosa_ecowitt_comparison(
            filtered_df,
            variable_name,
            selected_range,
            resolution_label
        )
        if comparison.empty or not all(sensor_name in comparison.columns for sensor_name in PONDEROSA_SENSOR_NAMES):
            continue

        comparison = comparison.dropna(subset=list(PONDEROSA_SENSOR_NAMES)).copy()
        if comparison.empty:
            continue

        comparison['Fecha'] = pd.to_datetime(comparison['FechaHora'], errors='coerce').dt.date
        config = PONDEROSA_COMPARISON_VARIABLES.get(variable_name, {})
        variable_label = _format_variable_display_title(config.get('title', variable_name))

        grouped = comparison.groupby(['Fecha'], dropna=False) if multi_day else [(None, comparison)]
        for group_key, group_df in grouped:
            wiga_value = getattr(group_df['WIGA'], aggregation)()
            ecowitt_value = getattr(group_df['ECOWITT'], aggregation)()
            signed_diff_value = getattr(group_df['SignedDiff'], aggregation)() if 'SignedDiff' in group_df.columns else pd.NA
            diff_value = getattr(group_df['DiffValue'], aggregation)() if 'DiffValue' in group_df.columns else pd.NA

            if metric_name != 'Promedio':
                wiga_value = 0.0 if pd.isna(wiga_value) else wiga_value
                ecowitt_value = 0.0 if pd.isna(ecowitt_value) else ecowitt_value
                signed_diff_value = 0.0 if pd.isna(signed_diff_value) else signed_diff_value
                diff_value = 0.0 if pd.isna(diff_value) else diff_value

            rows.append({
                'Fecha': group_key if multi_day else f"{selected_range[0]}",
                'Variable': variable_label,
                'Unidad': config.get('unit', VARIABLE_UNITS.get(variable_name, '')),
                'Metrica': metric_name,
                'WIGA': round(float(wiga_value), 2) if pd.notna(wiga_value) else pd.NA,
                'ECOWITT': round(float(ecowitt_value), 2) if pd.notna(ecowitt_value) else pd.NA,
                'WIGA - ECOWITT': round(float(signed_diff_value), 2) if pd.notna(signed_diff_value) else pd.NA,
                'Diferencia absoluta': round(float(diff_value), 2) if pd.notna(diff_value) else pd.NA,
                'Registros comparables': len(group_df),
            })

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(['Fecha', 'Variable']).reset_index(drop=True)


def _build_ponderosa_ecowitt_stats_source(filtered_df, variables):
    if filtered_df.empty or 'FechaHora' not in filtered_df.columns:
        return pd.DataFrame()

    frames = []
    for source_name in PONDEROSA_SENSOR_NAMES:
        rename_map = {}
        source_columns = ['FechaHora']
        for variable_name in variables:
            column_name = f"{variable_name} - {source_name}"
            if column_name in filtered_df.columns:
                source_columns.append(column_name)
                rename_map[column_name] = variable_name
        if len(source_columns) == 1:
            continue

        source_df = filtered_df[source_columns].copy().rename(columns=rename_map)
        source_df['DateTime'] = pd.to_datetime(source_df['FechaHora'], errors='coerce')
        source_df = source_df.dropna(subset=['DateTime'])
        source_df['Fecha_Filtro'] = source_df['DateTime'].dt.date
        source_df['Bloque'] = source_name
        for variable_name in variables:
            if variable_name in source_df.columns:
                source_df[variable_name] = pd.to_numeric(source_df[variable_name], errors='coerce')
        frames.append(source_df[['DateTime', 'Fecha_Filtro', 'Bloque', *[var for var in variables if var in source_df.columns]]])

    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _build_ponderosa_light_stats_source(filtered_df, variables):
    if filtered_df.empty or 'FechaHora' not in filtered_df.columns:
        return pd.DataFrame()

    frames = []
    for source_name in PONDEROSA_LIGHT_SENSOR_NAMES:
        rename_map = {}
        source_columns = ['FechaHora']
        for variable_name in variables:
            column_name = f"{variable_name} - {source_name}"
            if column_name in filtered_df.columns:
                source_columns.append(column_name)
                rename_map[column_name] = variable_name
        if len(source_columns) == 1:
            continue

        source_df = filtered_df[source_columns].copy().rename(columns=rename_map)
        source_df['DateTime'] = pd.to_datetime(source_df['FechaHora'], errors='coerce')
        source_df = source_df.dropna(subset=['DateTime'])
        source_df['Fecha_Filtro'] = source_df['DateTime'].dt.date
        source_df['Bloque'] = source_name
        for variable_name in variables:
            if variable_name in source_df.columns:
                source_df[variable_name] = pd.to_numeric(source_df[variable_name], errors='coerce')
        frames.append(source_df[['DateTime', 'Fecha_Filtro', 'Bloque', *[var for var in variables if var in source_df.columns]]])

    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def _render_ponderosa_light_difference_heatmap(grouped_df, selected_variable, metric_column, metric_label, unit_text):
    if grouped_df.empty or metric_column not in grouped_df.columns:
        return

    available_sensors = [
        sensor_name for sensor_name in PONDEROSA_LIGHT_SENSOR_NAMES
        if sensor_name in grouped_df['Bloque'].dropna().unique().tolist()
    ]
    if len(available_sensors) < 2:
        return

    pair_options = []
    for idx, first_sensor in enumerate(available_sensors):
        for second_sensor in available_sensors[idx + 1:]:
            pair_options.append(f"{first_sensor} - {second_sensor}")
    if not pair_options:
        return

    selected_pairs = st.segmented_control(
        "Diferencias visibles:",
        options=pair_options,
        selection_mode="multi",
        default=[
            pair for pair in st.session_state.get("ponderosa_light_difference_pairs", pair_options)
            if pair in pair_options
        ] or pair_options,
        key="ponderosa_light_difference_pairs",
        help="Elige qué pares de sensores quieres comparar. La diferencia se calcula como primer sensor menos segundo sensor.",
        width="stretch"
    )
    if not selected_pairs:
        selected_pairs = pair_options

    pivot_df = (
        grouped_df
        .pivot_table(index=['FranjaMinutos', 'Franja'], columns='Bloque', values=metric_column, aggfunc='mean')
        .reset_index()
        .sort_values('FranjaMinutos')
    )
    if pivot_df.empty:
        return

    display_slots = [
        f'{hour:02d}:{minute:02d}'
        for hour in range(24)
        for minute in (0, 30)
    ]
    x_values = pivot_df['Franja'].tolist()
    z_values = []
    custom_data = []
    y_values = []

    for pair_label in selected_pairs:
        first_sensor, second_sensor = [part.strip() for part in pair_label.split(' - ', 1)]
        if first_sensor not in pivot_df.columns or second_sensor not in pivot_df.columns:
            continue

        first_values = pd.to_numeric(pivot_df[first_sensor], errors='coerce')
        second_values = pd.to_numeric(pivot_df[second_sensor], errors='coerce')
        signed_diff = first_values - second_values
        y_values.append(pair_label)
        z_values.append([float(value) if pd.notna(value) else None for value in signed_diff])
        custom_data.append([
            [
                float(first_value) if pd.notna(first_value) else None,
                float(second_value) if pd.notna(second_value) else None,
                abs(float(diff_value)) if pd.notna(diff_value) else None,
            ]
            for first_value, second_value, diff_value in zip(first_values, second_values, signed_diff)
        ])

    if not y_values:
        st.info("No hay pares de sensores suficientes para construir el mapa de diferencias.")
        return

    valid_diffs = [
        abs(value)
        for row in z_values
        for value in row
        if value is not None
    ]
    color_limit = max(valid_diffs) if valid_diffs else 1
    color_limit = max(color_limit, 1)
    config = PONDEROSA_LIGHT_VARIABLES.get(selected_variable, {})

    fig = go.Figure(
        data=go.Heatmap(
            x=x_values,
            y=y_values,
            z=z_values,
            customdata=custom_data,
            zmid=0,
            zmin=-color_limit,
            zmax=color_limit,
            colorscale=[
                [0.0, '#5E5AAE'],
                [0.5, '#F7F4EE'],
                [1.0, '#E07A2F'],
            ],
            colorbar=dict(title=f"Dif. ({unit_text})" if unit_text else "Diferencia"),
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Franja: %{x}<br>"
                f"{metric_label} diferencia: %{{z:+.2f}} {unit_text}<br>"
                f"Primer sensor: %{{customdata[0]:.2f}} {unit_text}<br>"
                f"Segundo sensor: %{{customdata[1]:.2f}} {unit_text}<br>"
                f"Diferencia absoluta: %{{customdata[2]:.2f}} {unit_text}"
                "<extra></extra>"
            )
        )
    )
    fig.update_layout(
        title=dict(
            text=f"Diferencia real por franja - {_format_variable_display_title(config.get('title', selected_variable))}",
            x=0,
            xanchor='left',
            font=dict(size=19, color=BRAND_COLORS['graphite'], family='Montserrat, sans-serif')
        ),
        height=330 + max(0, len(y_values) - 2) * 54,
        margin=dict(l=118, r=28, t=82, b=88),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(250,248,243,0.68)',
        template='plotly_white',
        font=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['graphite']),
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
            side='bottom',
        ),
        yaxis=dict(
            title='',
            automargin=True,
        ),
    )
    _plotly_chart(
        fig,
        config={
            'displaylogo': False,
            'responsive': True,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d']
        }
    )
    _render_chart_explanation(
        "Mapa de diferencias",
        (
            "Cada celda muestra la diferencia real entre dos sensores en una franja de 30 minutos. "
            "Valores positivos significan que el primer sensor del par midió más alto; valores negativos indican que el segundo sensor quedó por encima."
        ),
        accent=config.get('accent', BRAND_COLORS['hero']),
        kicker='Comparación entre sensores'
    )


def _render_ponderosa_light_combined_metric_analysis(light_stats_source, selected_range, light_variables):
    if light_stats_source.empty:
        st.info("No hay datos suficientes para construir la gráfica estadística APOGEE / MCI / WIGA.")
        return

    fecha_inicio, fecha_fin = selected_range
    single_day = fecha_inicio == fecha_fin
    metric_options = ["Promedio"]
    if not single_day:
        metric_options.extend(["Desviacion estandar", "Varianza"])

    if st.session_state.get("ponderosa_light_stats_graph_variable") not in light_variables:
        st.session_state["ponderosa_light_stats_graph_variable"] = light_variables[0]
    selected_variable = st.segmented_control(
        "Variable del análisis:",
        options=light_variables,
        format_func=lambda value: _format_variable_display_title(PONDEROSA_LIGHT_VARIABLES.get(value, {}).get('title', value)),
        key="ponderosa_light_stats_graph_variable",
        help="Calcula solo la variable seleccionada para mantener esta vista clara y rápida.",
        width="stretch"
    )
    if selected_variable not in light_variables:
        selected_variable = light_variables[0]

    metric_state_key = "ponderosa_light_stats_metric_single"
    if st.session_state.get(metric_state_key) not in metric_options:
        st.session_state[metric_state_key] = metric_options[0]
    selected_metric = st.segmented_control(
        "Métrica visible:",
        options=metric_options,
        key=metric_state_key,
        help="Elige la métrica que quieres graficar para WIGA, MCI y APOGEE.",
        width="stretch"
    )
    if selected_metric not in metric_options:
        selected_metric = metric_options[0]
    st.session_state["ponderosa_light_stats_metric"] = selected_metric

    if single_day:
        st.caption("Con un solo día se grafica el promedio por franja de 30 minutos. La desviación estándar y la varianza se habilitan al seleccionar varios días.")

    grouped_df, _, _, _ = _build_hourly_block_analysis(light_stats_source, selected_variable)
    if grouped_df.empty:
        st.info(f"No se encontraron datos para {selected_variable} en el rango seleccionado.")
        return

    metric_columns = {
        "Promedio": "Promedio",
        "Desviacion estandar": "DesviacionEstandar",
        "Varianza": "Varianza",
    }
    metric_labels = {
        "Promedio": "Promedio",
        "Desviacion estandar": "Desviación estándar",
        "Varianza": "Varianza",
    }
    ordered_sensors = [
        sensor_name for sensor_name in PONDEROSA_LIGHT_SENSOR_NAMES
        if sensor_name in grouped_df['Bloque'].dropna().unique().tolist()
    ]
    display_slots = [
        f'{hour:02d}:{minute:02d}'
        for hour in range(24)
        for minute in (0, 30)
    ]
    config = PONDEROSA_LIGHT_VARIABLES.get(selected_variable, {})
    unit_text = config.get('unit', VARIABLE_UNITS.get(selected_variable, ''))
    metric_column = metric_columns[selected_metric]
    metric_label = metric_labels[selected_metric]

    fig = go.Figure()
    for sensor_name in ordered_sensors:
        sensor_df = grouped_df[grouped_df['Bloque'] == sensor_name].sort_values('FranjaMinutos')
        if sensor_df.empty:
            continue
        color = _get_block_analysis_color(sensor_name, selected_variable)
        if metric_column not in sensor_df.columns:
            continue
        metric_df = sensor_df.dropna(subset=[metric_column])
        if metric_df.empty:
            continue
        fig.add_trace(go.Scatter(
            x=metric_df['Franja'],
            y=metric_df[metric_column],
            mode='lines+markers',
            name=f"{sensor_name} · {metric_label}",
            line=dict(color=color, width=3, dash='solid'),
            marker=dict(size=6, color=color, line=dict(color='rgba(255,255,255,0.82)', width=1)),
            customdata=metric_df[['Registros']],
            hovertemplate=(
                '<b>%{x}</b><br>'
                f'{sensor_name}<br>'
                f'{metric_label}: %{{y:.2f}} {unit_text}<br>'
                'Registros: %{customdata[0]}'
                '<extra></extra>'
            ),
        ))

    if not fig.data:
        st.info("No hay datos suficientes para construir la gráfica con las métricas seleccionadas.")
        return

    yaxis_title = f"{metric_label} ({unit_text})" if unit_text else metric_label

    fig.update_layout(
        title=dict(
            text=f"{metric_label} por franja - {_format_variable_display_title(config.get('title', selected_variable))}",
            x=0,
            xanchor='left',
            font=dict(size=19, color=BRAND_COLORS['graphite'], family='Montserrat, sans-serif')
        ),
        height=540,
        margin=dict(l=44, r=28, t=86, b=92),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(250,248,243,0.68)',
        hovermode='x unified',
        template='plotly_white',
        font=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['graphite']),
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.04,
            xanchor='left',
            x=0,
            traceorder='normal',
            bgcolor='rgba(255,255,255,0.76)',
            bordercolor='rgba(76, 70, 120, 0.08)',
            borderwidth=1,
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
            zeroline=False,
            automargin=True,
        ),
        yaxis=dict(
            title=f'<b>{yaxis_title}</b>',
            tickfont=dict(size=11, family='Montserrat, sans-serif', color=BRAND_COLORS['graphite']),
            gridcolor='rgba(76, 70, 120, 0.08)',
            zeroline=False,
        )
    )
    _plotly_chart(
        fig,
        config={
            'displaylogo': False,
            'responsive': True,
            'modeBarButtonsToRemove': ['lasso2d', 'select2d']
        }
    )
    _render_chart_explanation(
        f"{metric_label} por franja",
        (
            "La gráfica compara WIGA, MCI y APOGEE para la métrica seleccionada. "
            "Promedio resume el comportamiento típico por cada media hora; al seleccionar varios días, desviación estándar y varianza muestran estabilidad o variabilidad entre jornadas. "
            "Puedes ocultar o mostrar sensores desde la leyenda."
        ),
        accent=config.get('accent', BRAND_COLORS['hero']),
        kicker='Cómo leer esta gráfica'
    )
    _render_ponderosa_light_difference_heatmap(
        grouped_df,
        selected_variable,
        metric_column,
        metric_label,
        unit_text
    )

    selected_stats = _build_analysis_distribution_table(
        light_stats_source,
        selected_variable,
        group_col='Bloque',
        group_label='Sensor'
    )
    _render_analysis_distribution_cards(
        selected_stats,
        _format_variable_display_title(config.get('title', selected_variable)),
        unit=unit_text,
        title=f"Resumen por sensor - {_format_variable_display_title(config.get('title', selected_variable))}",
        group_column='Sensor',
        accent_getter=lambda group_name: _get_block_analysis_color(group_name, selected_variable)
    )


def _render_ponderosa_comparison_metric_cards(overlap, selected_variable):
    config = PONDEROSA_COMPARISON_VARIABLES.get(selected_variable)
    if config is None:
        st.info("La variable seleccionada ya no está disponible para la comparación WIGA / ECOWITT.")
        return

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
    single_day = selected_range[0] == selected_range[1]

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
    compared_variables = [
        variable_name
        for variable_name in PONDEROSA_COMPARISON_VARIABLES
        if f"{variable_name} - WIGA" in filtered_df.columns or f"{variable_name} - ECOWITT" in filtered_df.columns
    ]
    if not compared_variables:
        st.warning("No hay variables compartidas disponibles para comparar WIGA / ECOWITT en este periodo.")
        st.stop()
    compared_variables = _render_variable_visibility_selector(
        compared_variables,
        key_prefix="ponderosa_ecowitt_comparison_variables",
        label_map={
            variable: _format_variable_display_title(PONDEROSA_COMPARISON_VARIABLES.get(variable, {}).get('title', variable))
            for variable in compared_variables
        },
        title="Variables activas WIGA / ECOWITT",
        description="Estos botones controlan la grafica principal, el analisis estadistico, los detalles individuales y las tablas de soporte.",
        expander_label="Variables visibles de la comparativa",
        expanded=True,
    )

    if st.session_state.get("ponderosa_ecowitt_stats_variable") not in compared_variables:
        st.session_state["ponderosa_ecowitt_stats_variable"] = compared_variables[0]
    if st.session_state.get("ponderosa_ecowitt_chart_variable") not in compared_variables:
        st.session_state["ponderosa_ecowitt_chart_variable"] = compared_variables[0]

    tab_compare, tab_stats, tab_detail, tab_records = st.tabs([
        "Gráfica",
        "Análisis estadístico",
        "Gráficas individuales",
        "Registros"
    ])

    with tab_compare:
        _render_chart_explanation(
            "Comparación directa WIGA / ECOWITT",
            "Elige una variable para comparar ambos sensores sobre la misma línea de tiempo. La diferencia y el detalle estadístico quedan reunidos en la pestaña de análisis.",
            accent=BRAND_COLORS['hero'],
            kicker='Vista principal'
        )
        _render_selected_period_banner(
            selected_range,
            min_fecha=min_date,
            max_fecha=max_date,
            navigation_state_key=navigation_state_key,
            title_text='Periodo WIGA / ECOWITT',
            available_dates=available_dates,
            context_text=f'Estás viendo {block_label} frente a ECOWITT Ponderosa.'
        )
        selected_chart_variable = st.segmented_control(
            "Variable en gráfica:",
            options=compared_variables,
            format_func=lambda value: _format_variable_display_title(PONDEROSA_COMPARISON_VARIABLES.get(value, {}).get('title', value)),
            key="ponderosa_ecowitt_chart_variable",
            width="stretch"
        )
        if selected_chart_variable not in compared_variables:
            selected_chart_variable = compared_variables[0]
        comparison = _build_ponderosa_ecowitt_comparison(
            filtered_df,
            selected_chart_variable,
            selected_range,
            comparison_resolution
        )
        if comparison.empty or comparison.dropna(how='all', subset=list(PONDEROSA_SENSOR_NAMES)).empty:
            variable_title = PONDEROSA_COMPARISON_VARIABLES.get(selected_chart_variable, {}).get('title', selected_chart_variable)
            st.info(f"No hay datos suficientes para graficar {_format_variable_display_title(variable_title)}.")
        else:
            comparison_chart = _make_ponderosa_comparison_chart(comparison, selected_chart_variable, selected_range, comparison_resolution)
            if comparison_chart is not None:
                _plotly_chart(comparison_chart)

    with tab_stats:
        _render_chart_explanation(
            "Análisis de relación WIGA / ECOWITT",
            (
                "Esta sección muestra la lectura visual de la relación entre sensores: comportamiento por franja, "
                "tarjetas de diferencia, dispersión y estabilidad. Las tablas y descargas están reunidas en Registros."
            ),
            accent=BRAND_COLORS['rose'],
            kicker='Lectura estadística'
        )
        stats_source_df = _build_ponderosa_ecowitt_stats_source(filtered_df, compared_variables)
        if stats_source_df.empty:
            st.info("No hay datos suficientes para construir la gráfica estadística WIGA / ECOWITT.")
        else:
            _render_hourly_analysis_view_organized(
                stats_source_df,
                selected_range,
                list(PONDEROSA_SENSOR_NAMES),
                variable_options=compared_variables,
                variable_state_key="ponderosa_ecowitt_stats_graph_variable",
                metric_state_key="ponderosa_ecowitt_stats_metric",
                show_table_tab=False,
                show_inline_tables=False
            )

        selected_variable_stats = st.segmented_control(
            "Variable para detalle estadístico:",
            options=compared_variables,
            format_func=lambda value: _format_variable_display_title(PONDEROSA_COMPARISON_VARIABLES.get(value, {}).get('title', value)),
            key="ponderosa_ecowitt_stats_variable",
            width="stretch"
        )
        if selected_variable_stats not in compared_variables:
            selected_variable_stats = compared_variables[0]
        comparison_stats = _build_ponderosa_ecowitt_comparison(
            filtered_df,
            selected_variable_stats,
            selected_range,
            comparison_resolution
        )
        if not all(sensor_name in comparison_stats.columns for sensor_name in PONDEROSA_SENSOR_NAMES):
            st.info("No hay columnas suficientes para construir el resumen estadístico de esta variable.")
        else:
            overlap = comparison_stats.dropna(subset=list(PONDEROSA_SENSOR_NAMES)).copy()
            _render_ponderosa_comparison_metric_cards(overlap, selected_variable_stats)
            difference_chart = _make_ponderosa_difference_chart(comparison_stats, selected_variable_stats, selected_range, comparison_resolution)
            if difference_chart is not None:
                selected_config = PONDEROSA_COMPARISON_VARIABLES.get(selected_variable_stats, {})
                _render_chart_explanation(
                    'Diferencia WIGA - ECOWITT',
                    'Valores sobre cero significan que WIGA midió más alto; valores bajo cero significan que ECOWITT midió más alto.',
                    accent=selected_config.get('colors', {}).get('ECOWITT', BRAND_COLORS['hero'])
                )
                _plotly_chart(difference_chart)
            scatter_chart = _make_ponderosa_scatter_chart(comparison_stats, selected_variable_stats)
            if scatter_chart is not None:
                selected_config = PONDEROSA_COMPARISON_VARIABLES.get(selected_variable_stats, {})
                _render_chart_explanation(
                    'Dispersión entre sensores',
                    'Cada punto cruza una lectura simultánea de WIGA y ECOWITT. Mientras más cerca esté de la línea diagonal, más parecidos fueron ambos sensores.',
                    accent=selected_config.get('colors', {}).get('WIGA', BRAND_COLORS['hero'])
                )
                _plotly_chart(scatter_chart)
            else:
                st.info("No hay suficientes datos simultáneos para construir la dispersión entre sensores.")

    with tab_detail:
        _render_ponderosa_source_individual_charts(
            filtered_df,
            selected_range,
            compared_variables,
            PONDEROSA_SENSOR_NAMES,
            "Variables individuales WIGA / ECOWITT Ponderosa",
            "Estas gráficas separan cada variable compartida por sensor para revisar la forma de cada lectura sin la superposición de la comparativa.",
            comparison_resolution
        )

    with tab_records:
        _render_chart_explanation(
            "Registros consolidados WIGA / ECOWITT",
            "Aquí quedan reunidas las tablas que soportan la comparación: conteo por equipo, consolidado base, resumen estadístico y diferencias por franja.",
            accent=BRAND_COLORS['hero'],
            kicker='Datos fuente'
        )
        summary_rows = []
        for source_name, source_df in source_frames.items():
            current = source_df[source_df['Fecha_Filtro'].between(*selected_range)] if not source_df.empty else pd.DataFrame()
            summary_rows.append({
                'Equipo': source_name,
                'Registros': len(current),
                'Inicio': current['FechaHora'].min().strftime('%Y-%m-%d %H:%M') if not current.empty else '-',
                'Fin': current['FechaHora'].max().strftime('%Y-%m-%d %H:%M') if not current.empty else '-',
            })
        source_summary_table = pd.DataFrame(summary_rows)
        consolidated_records = filtered_df.drop(columns=['Fecha_Filtro'], errors='ignore')

        record_report_options = [
            "Resumen por equipo",
            "Resumen estadístico",
            "Tabla por franja",
            "Diferencias WIGA - ECOWITT",
            "Registros consolidados",
        ]
        if st.session_state.get("ponderosa_ecowitt_records_report") not in record_report_options:
            st.session_state["ponderosa_ecowitt_records_report"] = record_report_options[0]
        selected_records_report = st.segmented_control(
            "Reporte",
            options=record_report_options,
            key="ponderosa_ecowitt_records_report",
            help="Selecciona qué tabla quieres revisar o descargar.",
            width="stretch"
        )

        if selected_records_report == "Resumen por equipo":
            st.caption("Conteo y ventana temporal disponible por fuente dentro del periodo seleccionado.")
            _dataframe(source_summary_table, hide_index=True)

        elif selected_records_report == "Resumen estadístico":
            summary_metric_options = ["Promedio"] if single_day else ["Promedio", "Desviacion estandar", "Varianza"]
            if st.session_state.get("ponderosa_ecowitt_summary_metric") not in summary_metric_options:
                st.session_state["ponderosa_ecowitt_summary_metric"] = summary_metric_options[0]
            records_summary_metric = st.segmented_control(
                "Métrica del resumen:",
                options=summary_metric_options,
                key="ponderosa_ecowitt_summary_metric",
                width="stretch"
            )
            if records_summary_metric not in summary_metric_options:
                records_summary_metric = summary_metric_options[0]
            records_summary_table = _build_ponderosa_ecowitt_period_summary(
                filtered_df,
                compared_variables,
                selected_range,
                comparison_resolution,
                records_summary_metric
            )
            if records_summary_table.empty:
                st.info("No hay suficientes lecturas comparables para construir el resumen estadístico.")
            else:
                st.caption("Resumen generado con los mismos datos de la comparación visible.")
                _render_table_download_button(
                    records_summary_table,
                    "Descargar resumen estadístico",
                    f"resumen_wiga_ecowitt_{_build_report_slug(block_label, records_summary_metric, comparison_resolution)}.xlsx",
                    "download_ponderosa_ecowitt_registros_resumen"
                )
                _dataframe(records_summary_table, hide_index=True)

        elif selected_records_report == "Tabla por franja":
            stats_source_records = _build_ponderosa_ecowitt_stats_source(filtered_df, compared_variables)
            if stats_source_records.empty:
                st.info("No hay datos suficientes para construir la tabla por franja.")
            else:
                selected_metric_label = st.session_state.get("ponderosa_ecowitt_stats_metric", "Promedio")
                metric_column = {
                    "Promedio": "Promedio",
                    "Desviacion estandar": "DesviacionEstandar",
                    "Varianza": "Varianza",
                }.get(selected_metric_label, "Promedio")
                selected_variable_table = st.session_state.get("ponderosa_ecowitt_stats_graph_variable", compared_variables[0])
                if selected_variable_table not in compared_variables:
                    selected_variable_table = compared_variables[0]
                grouped_df, pivot_promedio, pivot_varianza, pivot_desviacion = _build_hourly_block_analysis(
                    stats_source_records,
                    selected_variable_table
                )
                pivot_map = {
                    "Promedio": pivot_promedio,
                    "DesviacionEstandar": pivot_desviacion,
                    "Varianza": pivot_varianza,
                }
                table = _prepare_hourly_pivot_display(pivot_map.get(metric_column, pivot_promedio))
                if table.empty:
                    st.info("No hay tabla disponible para la métrica y variable seleccionadas en análisis.")
                else:
                    st.caption(
                        "Tabla calculada con la métrica y variable seleccionadas en Análisis estadístico. "
                        "Cambia la gráfica allí para actualizar esta salida."
                    )
                    report_slug = _build_report_slug(block_label, selected_variable_table, selected_metric_label, comparison_resolution)
                    _render_table_download_button(
                        table,
                        f"Descargar tabla de {selected_metric_label.lower()}",
                        f"wiga_ecowitt_franja_{report_slug}.xlsx",
                        "download_ponderosa_ecowitt_tabla_franja"
                    )
                    _dataframe(table, hide_index=True)

        elif selected_records_report == "Diferencias WIGA - ECOWITT":
            difference_table, difference_table_mode = _build_difference_table_30min(
                filtered_df,
                compared_variables,
                PONDEROSA_SENSOR_NAMES,
                selected_range,
                comparison_resolution,
                _build_ponderosa_hourly_comparison,
                _build_ponderosa_hourly_series,
                PONDEROSA_COMPARISON_VARIABLES
            )
            if difference_table.empty:
                st.info("No hay datos suficientes para construir la tabla de diferencias.")
            else:
                st.caption(f"Tabla calculada con: {difference_table_mode}. La diferencia se calcula como WIGA - ECOWITT.")
                _render_comparison_table_summary(difference_table, title="Resumen ejecutivo de diferencias")
                _render_variable_split_tables(
                    difference_table,
                    default_expanded=True,
                    download_label="Descargar reporte WIGA vs ECOWITT",
                    download_file_name=f"reporte_wiga_ecowitt_{_build_report_slug(block_label, difference_table_mode)}.xlsx",
                    download_key="download_ponderosa_ecowitt_registros_diferencias"
                )

        elif selected_records_report == "Registros consolidados":
            st.caption("Datos base consolidados que alimentan las gráficas y cálculos de WIGA / ECOWITT.")
            _render_table_download_button(
                consolidated_records,
                "Descargar registros consolidados",
                f"registros_wiga_ecowitt_{_build_report_slug(block_label, comparison_resolution)}.xlsx",
                "download_ponderosa_ecowitt_registros",
                variable_column='__consolidado__'
            )
            _dataframe(consolidated_records, hide_index=True)

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




__all__ = [name for name in globals() if not name.startswith("__")]
