from .shared import *

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

    visible_cortina_legend_items = sum(
        1 for _, trace, _ in cortina_traces
        if trace.get('showlegend', True)
    )
    legend_item_count = len(sensor_traces) + len(compare_sensor_traces) + visible_cortina_legend_items
    legend_columns = 4 if legend_item_count >= 4 else max(1, legend_item_count)
    legend_rows = max(1, math.ceil(legend_item_count / legend_columns)) if legend_item_count else 1
    legend_band_height = 38 + max(0, legend_rows - 1) * 25
    chart_height = 600 + max(0, legend_rows - 1) * 14

    fig_corr.update_layout(
        title=dict(
            text=chart_title,
            x=0,
            xanchor='left',
            y=0.99,
            yanchor='top',
            pad=dict(b=4),
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
        height=chart_height,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.045,
            xanchor='left',
            x=0,
            traceorder='normal',
            font=dict(size=11, family='Montserrat, sans-serif', color=BRAND_COLORS['graphite']),
            grouptitlefont=dict(size=11, family='Montserrat, sans-serif', color=BRAND_COLORS['hero']),
            bgcolor='rgba(255,255,255,0.76)',
            bordercolor='rgba(76, 70, 120, 0.08)',
            borderwidth=1,
            entrywidth=242 if legend_item_count > 4 else 150,
            entrywidthmode='pixels',
            itemsizing='trace'
        ),
        margin=dict(l=50, r=right_margin, t=96 + legend_band_height, b=70),
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
        for figure in figures:
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
    if str(block_name).upper() in PONDEROSA_SENSOR_NAMES and variable_name in PONDEROSA_COMPARISON_VARIABLES:
        return PONDEROSA_COMPARISON_VARIABLES[variable_name].get('colors', {}).get(
            str(block_name).upper(),
            VARIABLE_COLORS.get(variable_name, BRAND_COLORS['hero'])
        )
    if str(block_name).upper() in PONDEROSA_LIGHT_SENSOR_NAMES and variable_name in PONDEROSA_LIGHT_VARIABLES:
        return PONDEROSA_LIGHT_VARIABLES[variable_name].get('colors', {}).get(
            str(block_name).upper(),
            VARIABLE_COLORS.get(variable_name, BRAND_COLORS['hero'])
        )
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
            DesviacionEstandar=(variable_name, 'std'),
            Varianza=(variable_name, 'var'),
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


def _build_variable_daily_distribution_table(df_source, variables):
    if not isinstance(df_source, pd.DataFrame) or df_source.empty or 'DateTime' not in df_source.columns:
        return pd.DataFrame()

    available_variables = [variable for variable in variables if variable in df_source.columns]
    if not available_variables:
        return pd.DataFrame()

    data = df_source[['DateTime'] + available_variables].copy()
    data['DateTime'] = pd.to_datetime(data['DateTime'], errors='coerce')
    data = data.dropna(subset=['DateTime'])
    if data.empty:
        return pd.DataFrame()

    data['Fecha'] = data['DateTime'].dt.date
    records = []
    for fecha_value, day_df in data.groupby('Fecha'):
        day_stats = _build_variable_distribution_table(day_df, variables)
        if day_stats.empty:
            continue
        day_stats.insert(0, 'Fecha', fecha_value)
        records.append(day_stats)

    if not records:
        return pd.DataFrame()

    return pd.concat(records, ignore_index=True, sort=False)


def _format_variable_daily_distribution_table(daily_stats_df, variable_configs=None):
    if daily_stats_df.empty:
        return pd.DataFrame()

    variable_configs = variable_configs or {}
    table = daily_stats_df.copy()
    if 'Fecha' in table.columns:
        table['Fecha'] = pd.to_datetime(table['Fecha'], errors='coerce').dt.strftime('%Y-%m-%d')
    if 'Variable' in table.columns:
        table['Variable'] = table['Variable'].apply(
            lambda value: _format_variable_display_title(
                variable_configs.get(value, {}).get('title', value)
            )
        )

    table = table.rename(columns={
        'Desviacion estandar': 'Desv. est.',
        'Coef. variacion (%)': 'Coef. var. (%)',
    })
    numeric_columns = [column for column in table.columns if column not in ('Fecha', 'Variable')]
    for column in numeric_columns:
        decimals = 0 if column == 'Registros' else 2
        table[column] = pd.to_numeric(table[column], errors='coerce').round(decimals)

    preferred_columns = [
        'Fecha', 'Variable', 'Promedio', 'Mediana', 'Minimo', 'Maximo',
        'Rango', 'Desv. est.', 'Varianza', 'Coef. var. (%)', 'Registros'
    ]
    return table[[column for column in preferred_columns if column in table.columns]].reset_index(drop=True)


def _render_variable_distribution_cards(stats_df, variable_configs=None, title='Resumen estadístico', dispersion_available=True):
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
        desviacion = _format_metric_card_value(row.get('Desviacion estandar'), decimals=2) if dispersion_available else "Varios días"
        varianza = _format_metric_card_value(row.get('Varianza'), decimals=2) if dispersion_available else "Varios días"
        registros = _format_metric_card_value(row.get('Registros'), decimals=0)
        cv_value = row.get('Coef. variacion (%)')
        if dispersion_available:
            cv_text = _format_metric_card_value(cv_value, decimals=1) if pd.notna(cv_value) else "Sin dato"
            cv_display = f"{cv_text}%" if cv_text != "Sin dato" else cv_text
        else:
            cv_display = "Varios días"

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


def _build_correlacion_30min_stats(df_variables, variables):
    if not isinstance(df_variables, pd.DataFrame) or df_variables.empty or 'DateTime' not in df_variables.columns:
        return pd.DataFrame()

    records = []
    for variable_name in variables:
        if variable_name not in df_variables.columns:
            continue

        data = df_variables[['DateTime', variable_name]].copy()
        data['DateTime'] = pd.to_datetime(data['DateTime'], errors='coerce')
        data[variable_name] = pd.to_numeric(data[variable_name], errors='coerce')
        data = data.dropna(subset=['DateTime', variable_name])
        if data.empty:
            continue

        data['Fecha'] = data['DateTime'].dt.date
        data['FranjaDateTime'] = data['DateTime'].dt.round('30min')
        data['FranjaMinutos'] = data['FranjaDateTime'].dt.hour * 60 + data['FranjaDateTime'].dt.minute
        data['Franja'] = data['FranjaDateTime'].dt.strftime('%H:%M')

        grouped = (
            data.groupby(['FranjaMinutos', 'Franja'], as_index=False)
            .agg(
                Promedio=(variable_name, 'mean'),
                DesviacionEstandar=(variable_name, 'std'),
                Varianza=(variable_name, 'var'),
                Registros=(variable_name, 'count'),
                Dias=('Fecha', 'nunique'),
            )
            .sort_values('FranjaMinutos')
        )
        grouped['DesviacionEstandar'] = grouped['DesviacionEstandar'].fillna(0.0)
        grouped['Varianza'] = grouped['Varianza'].fillna(0.0)
        grouped['Variable'] = variable_name
        records.append(grouped)

    if not records:
        return pd.DataFrame()

    return pd.concat(records, ignore_index=True, sort=False)


def _build_correlacion_30min_metric_chart(hourly_stats_df, variable_name, metric_column, block_label, fecha_variables):
    if hourly_stats_df.empty or metric_column not in hourly_stats_df.columns:
        return None

    chart_df = hourly_stats_df[hourly_stats_df['Variable'] == variable_name].copy()
    chart_df[metric_column] = pd.to_numeric(chart_df[metric_column], errors='coerce')
    chart_df = chart_df.dropna(subset=[metric_column]).sort_values('FranjaMinutos')
    if chart_df.empty:
        return None

    display_slots = [
        f'{hour:02d}:{minute:02d}'
        for hour in range(24)
        for minute in (0, 30)
    ]
    metric_labels = {
        'Promedio': 'Promedio',
        'DesviacionEstandar': 'Desviación estándar',
        'Varianza': 'Varianza',
    }
    metric_colors = {
        'Promedio': VARIABLE_COLORS.get(variable_name, BRAND_COLORS['hero']),
        'DesviacionEstandar': BRAND_COLORS['rose'],
        'Varianza': BRAND_COLORS['beige'],
    }
    metric_label = metric_labels.get(metric_column, metric_column)
    unit_text = _format_analysis_unit_text(VARIABLE_UNITS.get(variable_name, ''))
    if metric_column == 'Varianza' and unit_text:
        unit_text = f'{unit_text}²'
    yaxis_title = f'{metric_label} ({unit_text})' if unit_text else metric_label
    fecha_inicio, fecha_fin = fecha_variables
    period_label = _format_selected_period_label(fecha_inicio, fecha_fin)
    color = metric_colors.get(metric_column, BRAND_COLORS['hero'])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=chart_df['Franja'],
        y=chart_df[metric_column],
        customdata=chart_df[['Registros', 'Dias']],
        mode='lines+markers',
        name=metric_label,
        line=dict(color=color, width=3.4, shape='spline', smoothing=0.42),
        marker=dict(size=7, color=color, line=dict(color='rgba(255,255,255,0.86)', width=1)),
        fill='tozeroy' if metric_column == 'Promedio' else None,
        fillcolor=f"rgba{tuple(int(color.lstrip('#')[idx:idx+2], 16) for idx in (0, 2, 4)) + (0.13,)}" if str(color).startswith('#') else 'rgba(84,83,134,0.10)',
        hovertemplate=(
            '<b>%{x}</b><br>'
            f'{metric_label}: %{{y:.2f}} {unit_text}<br>'
            'Registros: %{customdata[0]}<br>'
            'Días representados: %{customdata[1]}'
            '<extra></extra>'
        )
    ))
    fig.update_layout(
        template='plotly_white',
        title=dict(
            text=f'{metric_label} cada 30 min · {VARIABLE_SELECTOR_LABELS.get(variable_name, variable_name)} · {block_label}',
            x=0,
            xanchor='left',
            font=dict(size=19, color=BRAND_COLORS['graphite'], family='Montserrat, sans-serif')
        ),
        height=520,
        margin=dict(l=44, r=28, t=86, b=92),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(250,248,243,0.68)',
        hovermode='x unified',
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
            gridcolor='rgba(76, 70, 120, 0.07)',
            zeroline=False,
        ),
        yaxis=dict(
            title=f'<b>{yaxis_title}</b>',
            tickfont=dict(size=11, family='Montserrat, sans-serif', color=BRAND_COLORS['graphite']),
            gridcolor='rgba(76, 70, 120, 0.08)',
            zeroline=False,
        ),
        annotations=[
            dict(
                text=f'Periodo: {period_label}',
                xref='paper',
                yref='paper',
                x=0,
                y=1.10,
                showarrow=False,
                align='left',
                font=dict(size=12, color='#707684', family='Montserrat, sans-serif')
            )
        ],
    )
    return fig


def _format_correlacion_30min_table(hourly_stats_df, variable_name, single_day):
    if hourly_stats_df.empty:
        return pd.DataFrame()

    table = hourly_stats_df[hourly_stats_df['Variable'] == variable_name].copy()
    if table.empty:
        return pd.DataFrame()

    columns = ['Franja', 'Promedio', 'Registros']
    if not single_day:
        columns = ['Franja', 'Promedio', 'DesviacionEstandar', 'Varianza', 'Registros', 'Dias']
    table = table[columns].rename(columns={
        'Franja': 'Franja 30 min',
        'DesviacionEstandar': 'Desviación estándar',
        'Dias': 'Días',
    })
    numeric_cols = [column for column in table.columns if column not in ('Franja 30 min',)]
    table[numeric_cols] = table[numeric_cols].apply(pd.to_numeric, errors='coerce').round(2)
    return table.reset_index(drop=True)


def _render_correlacion_statistics_dashboard(df_variables_corr, fecha_variables, stats_variables, variable_stat_configs, block_label):
    if not stats_variables:
        st.info("No hay variables ambientales suficientes para construir el análisis estadístico.")
        return

    fecha_inicio, fecha_fin = fecha_variables
    single_day = fecha_inicio == fecha_fin
    period_title = "Lectura de un día" if single_day else "Lectura de varios días"
    period_copy = (
        "Para un solo día se muestra el perfil promedio por franjas de 30 minutos. La desviación estándar y la varianza se reservan para varios días, porque ahí sí comparan la dispersión de una misma hora entre jornadas."
        if single_day else
        "Para varios días, cada punto agrupa la misma franja horaria de todos los días seleccionados. Así el promedio muestra el comportamiento típico, y la desviación estándar y la varianza muestran qué tan estable o variable fue cada franja."
    )
    _render_chart_explanation(
        period_title,
        period_copy,
        accent=BRAND_COLORS['hero'],
        kicker='Estadística por franjas de 30 min'
    )

    stats_df = _build_variable_distribution_table(df_variables_corr, stats_variables)
    daily_stats_df = (
        _build_variable_daily_distribution_table(df_variables_corr, stats_variables)
        if not single_day else
        pd.DataFrame()
    )
    stats_view_options = ["Resumen del periodo"]
    if not single_day:
        stats_view_options.extend(["Listado por día", "Tabla variable/día"])
    if st.session_state.get("correlacion_stats_summary_view") not in stats_view_options:
        st.session_state["correlacion_stats_summary_view"] = stats_view_options[0]
    selected_stats_view = st.segmented_control(
        "Vista del resumen estadístico:",
        options=stats_view_options,
        key="correlacion_stats_summary_view",
        help="Cambia entre el resumen consolidado del rango, el desglose por cada día y una tabla completa por variable y fecha.",
        width="stretch"
    )

    if selected_stats_view == "Resumen del periodo":
        _render_variable_distribution_cards(
            stats_df,
            variable_stat_configs,
            title=f"Resumen estadístico ambiental - {block_label}",
            dispersion_available=not single_day
        )
    elif selected_stats_view == "Listado por día":
        if daily_stats_df.empty:
            st.info("No hay datos suficientes para construir el listado diario.")
        else:
            st.markdown(
                f'<p class="analysis-note"><strong>Resumen diario ambiental - {html.escape(str(block_label))}</strong></p>',
                unsafe_allow_html=True
            )
            for fecha_value in sorted(daily_stats_df['Fecha'].dropna().unique()):
                day_stats = daily_stats_df[daily_stats_df['Fecha'] == fecha_value].drop(columns=['Fecha'], errors='ignore')
                fecha_label = pd.to_datetime(fecha_value).strftime('%Y-%m-%d')
                with st.expander(f"Resumen del día {fecha_label}", expanded=False):
                    _render_variable_distribution_cards(
                        day_stats,
                        variable_stat_configs,
                        title=f"Variables ambientales - {fecha_label}",
                        dispersion_available=True
                    )
    else:
        daily_table = _format_variable_daily_distribution_table(daily_stats_df, variable_stat_configs)
        if daily_table.empty:
            st.info("No hay datos suficientes para construir la tabla diaria.")
        else:
            report_slug = _build_report_slug(block_label, "resumen_diario")
            _render_table_download_button(
                daily_table,
                "Descargar resumen diario",
                f"resumen_diario_variables_{report_slug}.xlsx",
                f"download_correlacion_stats_daily_{report_slug}",
                variable_column='Variable',
                help_text="Descarga el resumen estadístico por variable y por día."
            )
            _dataframe(daily_table, hide_index=True, height=420)

    hourly_stats_df = _build_correlacion_30min_stats(df_variables_corr, stats_variables)
    if hourly_stats_df.empty:
        st.info("No hay datos suficientes para calcular las franjas de 30 minutos.")
        return

    metric_options = ["Promedio"]
    if not single_day:
        metric_options.extend(["Desviación estándar", "Varianza"])
    if st.session_state.get("correlacion_stats_metric") not in metric_options:
        st.session_state["correlacion_stats_metric"] = metric_options[0]
    selected_metric_label = st.segmented_control(
        "Métrica por franja:",
        options=metric_options,
        key="correlacion_stats_metric",
        help="Promedio siempre está disponible. Desviación estándar y varianza se habilitan cuando analizas varios días.",
        width="stretch"
    )
    metric_column = {
        "Promedio": "Promedio",
        "Desviación estándar": "DesviacionEstandar",
        "Varianza": "Varianza",
    }[selected_metric_label]

    if st.session_state.get("correlacion_stats_variable") not in stats_variables:
        st.session_state["correlacion_stats_variable"] = stats_variables[0]
    selected_variable = st.segmented_control(
        "Variable ambiental:",
        options=stats_variables,
        format_func=lambda value: VARIABLE_SELECTOR_LABELS.get(value, VARIABLE_LABELS.get(value, value)),
        key="correlacion_stats_variable",
        width="stretch"
    )

    metric_chart = _build_correlacion_30min_metric_chart(
        hourly_stats_df,
        selected_variable,
        metric_column,
        block_label,
        fecha_variables
    )
    if metric_chart is None:
        st.info("No hay datos suficientes para construir la gráfica seleccionada.")
    else:
        _plotly_chart(
            metric_chart,
            config={
                'displaylogo': False,
                'responsive': True,
                'modeBarButtonsToRemove': ['lasso2d', 'select2d']
            }
        )

    table = _format_correlacion_30min_table(hourly_stats_df, selected_variable, single_day)
    with st.expander("Ver tabla por franjas de 30 minutos", expanded=False):
        if table.empty:
            st.info("No hay tabla disponible para esta selección.")
        else:
            report_slug = _build_report_slug(block_label, selected_variable, selected_metric_label)
            _render_table_download_button(
                table,
                "Descargar tabla estadística",
                f"estadistica_30min_{report_slug}.xlsx",
                f"download_correlacion_stats_30min_{report_slug}",
                variable_column='Variable',
                help_text="Descarga la tabla calculada por franjas de 30 minutos."
            )
            _dataframe(table, hide_index=True, height=300)


def _render_correlacion_records_overview(sensor_30min_report, cortinas_30min_report, cortinas_event_report, datos_sensores_corr, datos_cortinas_sel):
    overview_columns = st.columns(4)
    overview_items = [
        ("Variables 30 min", len(sensor_30min_report), "Promedios ambientales"),
        ("Cortinas 30 min", len(cortinas_30min_report), "Estados por franja"),
        ("Eventos cortinas", len(cortinas_event_report), "Movimientos registrados"),
        ("Crudos", len(datos_sensores_corr) + len(datos_cortinas_sel), "Filas originales"),
    ]
    for column, (label, value, help_text) in zip(overview_columns, overview_items):
        with column:
            st.metric(label, f"{value:,}", help=help_text)


def _render_correlacion_records_tab(df_variables_corr, datos_sensores_corr, datos_cortinas_sel, variables_sensor, fecha_variables, block_label):
    _render_chart_explanation(
        "Registros y exportables",
        "Esta pestaña deja trazabilidad de lo que se está graficando: variables ambientales consolidadas cada 30 minutos, estados de cortinas por franja, eventos operativos y registros crudos del Excel.",
        accent=BRAND_COLORS['hero'],
        kicker='Base de datos visible'
    )
    sensor_30min_report = _build_variables_30min_report(df_variables_corr, variables_sensor)
    cortinas_30min_report = _build_cortinas_30min_report(datos_cortinas_sel, fecha_variables, block_label)
    cortinas_event_report = _build_cortinas_event_report(datos_cortinas_sel)
    _render_correlacion_records_overview(
        sensor_30min_report,
        cortinas_30min_report,
        cortinas_event_report,
        datos_sensores_corr,
        datos_cortinas_sel
    )

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
            st.caption("Promedio de cada variable ambiental por franja de 30 minutos.")
            _render_table_download_button(
                sensor_30min_report,
                "Descargar reporte de variables",
                f"reporte_variables_30min_{_build_report_slug(block_label)}.xlsx",
                "download_correlacion_variables_30min",
                variable_column='Fecha'
            )
            _dataframe(sensor_30min_report, hide_index=True, height=360)
    elif selected_record_content == "Cortinas cada 30 min":
        if cortinas_30min_report.empty:
            st.info("No hay registros de cortinas para generar el reporte cada 30 minutos.")
        else:
            st.caption("Estado estimado de frentes, puertas y culatas por franja de 30 minutos.")
            _render_table_download_button(
                cortinas_30min_report,
                "Descargar reporte de cortinas",
                f"reporte_cortinas_30min_{_build_report_slug(block_label)}.xlsx",
                "download_correlacion_cortinas_30min",
                variable_column='Motor'
            )
            _dataframe(cortinas_30min_report, hide_index=True, height=360)
    elif selected_record_content == "Eventos de cortinas":
        if cortinas_event_report.empty:
            st.info("No hay eventos de cortinas para los filtros seleccionados.")
        else:
            st.caption("Eventos operativos tal como aparecen en el registro de cortinas.")
            _render_table_download_button(
                cortinas_event_report,
                "Descargar eventos de cortinas",
                f"eventos_cortinas_{_build_report_slug(block_label)}.xlsx",
                "download_correlacion_eventos_cortinas",
                variable_column='Fecha'
            )
            _dataframe(cortinas_event_report, hide_index=True, height=360)
    elif selected_record_content == "Registros crudos":
        raw_tab_sensors, raw_tab_cortinas = st.tabs(["Sensores", "Cortinas"])
        with raw_tab_sensors:
            if datos_sensores_corr.empty:
                st.info("No hay registros de sensores para los filtros seleccionados.")
            else:
                st.caption("Filas ambientales originales filtradas para el bloque y periodo seleccionado.")
                _dataframe(datos_sensores_corr, hide_index=True, height=360)
        with raw_tab_cortinas:
            if datos_cortinas_sel.empty:
                st.info("No hay registros de cortinas para los filtros seleccionados.")
            else:
                st.caption("Filas originales de cortinas filtradas para el bloque y periodo seleccionado.")
                _dataframe(datos_cortinas_sel, hide_index=True, height=360)


def _prepare_variable_stats_chart_df(stats_df, metric_key, variable_configs=None):
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
    chart_df['Unidad'] = chart_df['Variable'].apply(
        lambda value: variable_configs.get(value, {}).get('unit', VARIABLE_UNITS.get(value, ''))
    )
    return chart_df


def _make_variable_stat_bar_chart(stats_df, metric_key, metric_label, variable_configs=None, block_label=None):
    chart_df = _prepare_variable_stats_chart_df(stats_df, metric_key, variable_configs)
    if chart_df is None:
        return None

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


def _make_variable_cv_chart(stats_df, variable_configs=None, block_label=None):
    chart_df = _prepare_variable_stats_chart_df(stats_df, 'Coef. variacion (%)', variable_configs)
    if chart_df is None:
        return None

    chart_df = chart_df.sort_values('Coef. variacion (%)', ascending=True)
    fig = go.Figure(go.Bar(
        x=chart_df['Coef. variacion (%)'],
        y=chart_df['Variable visible'],
        orientation='h',
        marker=dict(color=chart_df['Color'], line=dict(color='rgba(56,58,53,0.18)', width=1)),
        text=chart_df['Coef. variacion (%)'].apply(lambda value: f"{value:,.1f}%"),
        textposition='outside',
        hovertemplate='<b>%{y}</b><br>Coef. variación: %{x:,.1f}%<extra></extra>',
    ))
    fig.update_layout(
        template='plotly_white',
        title="Estabilidad relativa por variable" + (f" - {block_label}" if block_label else ""),
        height=420,
        margin=dict(l=20, r=45, t=70, b=40),
        xaxis_title='Coeficiente de variación (%)',
        yaxis_title='Variable',
        font=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['graphite']),
    )
    fig.update_xaxes(showgrid=True, gridcolor='rgba(84,83,134,0.10)', zeroline=False)
    fig.update_yaxes(showgrid=False)
    return fig


def _make_variable_stat_small_multiples(stats_df, metric_key, metric_label, variable_configs=None, block_label=None):
    chart_df = _prepare_variable_stats_chart_df(stats_df, metric_key, variable_configs)
    if chart_df is None:
        return None

    subplot_count = len(chart_df)
    cols = min(2, max(1, subplot_count))
    rows = math.ceil(subplot_count / cols)
    fig = make_subplots(
        rows=rows,
        cols=cols,
        subplot_titles=chart_df['Variable visible'].tolist(),
        vertical_spacing=0.18 if rows > 1 else 0.12,
        horizontal_spacing=0.12,
    )

    for idx, (_, row) in enumerate(chart_df.iterrows(), start=1):
        row_idx = math.ceil(idx / cols)
        col_idx = ((idx - 1) % cols) + 1
        unit = str(row.get('Unidad') or '').strip()
        if metric_key == "Varianza" and unit:
            unit = f"{unit}²"
        unit_suffix = f" {unit}" if unit else ""
        value = row[metric_key]
        fig.add_trace(
            go.Bar(
                x=[metric_label],
                y=[value],
                marker=dict(color=row['Color'], line=dict(color='rgba(56,58,53,0.18)', width=1)),
                text=[f"{value:,.2f}{unit_suffix}"],
                textposition='outside',
                hovertemplate=f"<b>{row['Variable visible']}</b><br>{metric_label}: %{{y:,.2f}}{unit_suffix}<extra></extra>",
                showlegend=False,
            ),
            row=row_idx,
            col=col_idx,
        )
        fig.update_yaxes(
            title_text=metric_label,
            showgrid=True,
            gridcolor='rgba(84,83,134,0.10)',
            zeroline=False,
            row=row_idx,
            col=col_idx,
        )
        fig.update_xaxes(showticklabels=False, row=row_idx, col=col_idx)

    fig.update_layout(
        template='plotly_white',
        title=f"{metric_label} por variable" + (f" - {block_label}" if block_label else ""),
        height=max(420, rows * 320),
        margin=dict(l=20, r=20, t=82, b=35),
        font=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['graphite']),
    )
    return fig


def _render_variable_statistics_charts(stats_df, variable_configs=None, block_label=None):
    if stats_df.empty:
        st.info("No hay datos suficientes para graficar el análisis estadístico.")
        return

    metric_tabs = st.tabs([
        "Promedio / media",
        "Mediana",
        "Mínimo",
        "Máximo",
        "Estabilidad relativa",
        "Desv. est.",
        "Varianza",
    ])

    comparable_metrics = [
        ("Promedio / media", "Promedio", metric_tabs[0]),
        ("Mediana", "Mediana", metric_tabs[1]),
        ("Mínimo", "Minimo", metric_tabs[2]),
        ("Máximo", "Maximo", metric_tabs[3]),
    ]
    for metric_label, metric_key, tab in comparable_metrics:
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

    with metric_tabs[4]:
        _render_chart_explanation(
            "Coeficiente de variación",
            "Esta gráfica compara la variabilidad relativa entre variables. Es más justa que comparar desviaciones o varianzas crudas porque expresa la dispersión como porcentaje del promedio.",
            accent=BRAND_COLORS['sky'],
            kicker='Comparación estadística'
        )
        cv_fig = _make_variable_cv_chart(stats_df, variable_configs=variable_configs, block_label=block_label)
        if cv_fig is None:
            st.info("No hay datos suficientes para graficar el coeficiente de variación.")
        else:
            _plotly_chart(cv_fig)

    for tab, metric_label, metric_key, description in [
        (
            metric_tabs[5],
            "Desviación estándar",
            "Desviacion estandar",
            "Cada panel usa su propia escala porque las variables tienen unidades diferentes. Lee este valor dentro de cada variable, no como competencia directa entre barras."
        ),
        (
            metric_tabs[6],
            "Varianza",
            "Varianza",
            "La varianza queda en unidades al cuadrado, por eso se muestra separada por variable. Sirve para entender dispersión interna del periodo, no para mezclar escalas distintas."
        ),
    ]:
        with tab:
            _render_chart_explanation(
                metric_label,
                description,
                accent=BRAND_COLORS['hero'],
                kicker='Dispersión por variable'
            )
            fig = _make_variable_stat_small_multiples(
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
    variable_state_key="analisis_variable_option",
    metric_state_key="analisis_metric_option",
    show_table_tab=True,
    show_inline_tables=True
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
        if st.session_state.get(metric_state_key) not in metric_options:
            st.session_state[metric_state_key] = metric_options[0]
        tab_label = st.segmented_control(
            "Métrica del análisis",
            options=metric_options,
            key=metric_state_key,
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
    variable_state_key="analisis_variable_option",
    metric_state_key="analisis_metric_option",
    show_table_tab=True,
    show_inline_tables=True
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

    analysis_tabs = st.tabs(["Gráfica", "Resumen estadístico", "Tabla"] if show_table_tab else ["Gráfica", "Resumen estadístico"])
    tab_grafica = analysis_tabs[0]
    tab_resumen = analysis_tabs[1]
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
        if show_inline_tables and not selected_stats.empty:
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

    if show_table_tab:
        tab_tabla = analysis_tabs[2]
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


__all__ = [name for name in globals() if not name.startswith("__")]
