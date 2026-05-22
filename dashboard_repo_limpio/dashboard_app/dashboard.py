from .foundation import *
from .shared import *
from .marly import *
from .analysis import *
from .greenhouse import *
from .ponderosa import *


def run():
    render_app_foundation()

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
                stats_variables = [variable for variable in variables_sensor if variable in df_variables_corr.columns]
                variable_stat_configs = {
                    variable_name: {
                        'title': VARIABLE_SELECTOR_LABELS.get(variable_name, VARIABLE_LABELS.get(variable_name, variable_name)),
                        'unit': VARIABLE_UNITS.get(variable_name, ''),
                        'accent': VARIABLE_COLORS.get(variable_name, BRAND_COLORS['hero'])
                    }
                    for variable_name in stats_variables
                }
                _render_correlacion_statistics_dashboard(
                    df_variables_corr,
                    fecha_variables,
                    stats_variables,
                    variable_stat_configs,
                    block_label=block_label
                )

            with tab_detail:
                _render_temperature_focus_chart(
                    df_variables_corr,
                    fecha_variables,
                    block_label=block_label,
                    df_external=df_variables_almacen_corr,
                    datos_cortinas_sel=datos_cortinas_sel
                )

            with tab_records:
                _render_correlacion_records_tab(
                    df_variables_corr,
                    datos_sensores_corr,
                    datos_cortinas_sel,
                    variables_sensor,
                    fecha_variables,
                    block_label
                )

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
