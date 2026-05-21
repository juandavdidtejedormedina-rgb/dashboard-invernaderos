from .foundation import *

def _limpiar_columnas(df):
    df = df.copy()
    df.columns = (
        df.columns.str.strip()
            .str.replace(r'\s*B\d+\s*$', '', regex=True)
            .str.replace(r'\s+', ' ', regex=True)
    )
    return df


def _build_normalized_text_key(value):
    text = str(value).replace('Âµ', 'u').replace('Â°', ' ')
    return _normalize_text_key_cached(text)
    normalized = unicodedata.normalize('NFKD', str(value))
    normalized = ''.join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace('µ', 'u').replace('°', ' ')
    normalized = normalized.lower()
    normalized = re.sub(r'[^a-z0-9]+', ' ', normalized)
    return re.sub(r'\s+', ' ', normalized).strip()


def _parse_date_series(date_series):
    if pd.api.types.is_datetime64_any_dtype(date_series):
        return date_series

    text_values = date_series.astype(str).str.strip()
    text_values = text_values.replace({'': None, 'nan': None, 'NaT': None, 'None': None})
    parsed_dates = pd.Series(pd.NaT, index=text_values.index, dtype='datetime64[ns]')

    iso_mask = text_values.notna() & text_values.str.match(r'^\d{4}-\d{2}-\d{2}$')
    if iso_mask.any():
        parsed_dates.loc[iso_mask] = pd.to_datetime(
            text_values.loc[iso_mask],
            format='%Y-%m-%d',
            errors='coerce'
        )

    remaining_mask = text_values.notna() & parsed_dates.isna()
    if remaining_mask.any():
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            parsed_dates.loc[remaining_mask] = pd.to_datetime(
                text_values.loc[remaining_mask],
                errors='coerce',
                dayfirst=True
            )

    return parsed_dates


def _normalize_variable_column_name(column_name):
    text = re.sub(r'\s+', ' ', str(column_name).strip())
    normalized_key = _build_normalized_text_key(text)

    if normalized_key == 'datetime':
        return 'DateTime'
    if normalized_key == 'fecha':
        return 'Fecha'
    if normalized_key == 'hora':
        return 'Hora'

    normalized_key = re.sub(r'\bb\d+\b', ' ', normalized_key)
    normalized_key = re.sub(r'\bumol\b.*$', ' ', normalized_key)
    normalized_key = re.sub(r'\bg\b$', ' ', normalized_key)
    normalized_key = re.sub(r'\bc\b$', ' ', normalized_key)
    normalized_key = re.sub(r'\s+', ' ', normalized_key).strip()

    if 'temperatura' in normalized_key:
        return 'Temperatura'
    if 'humedad relativa' in normalized_key:
        return 'Humedad Relativa'
    if 'radiacion par' in normalized_key:
        return 'Radiación PAR'
    if 'gramos de agua' in normalized_key:
        return 'Gramos de agua'

    return text


def _combine_fecha_hora_columns(df):
    if 'Fecha' not in df.columns or 'Hora' not in df.columns:
        return df

    df = df.copy()
    fecha_series = _parse_date_series(df['Fecha'])
    hora_series = df['Hora'].astype(str).str.strip().replace({'NaT': '', 'nan': '', 'None': ''})
    df['DateTime'] = pd.to_datetime(
        fecha_series.dt.strftime('%Y-%m-%d') + ' ' + hora_series,
        errors='coerce'
    )
    return df


def _prepare_variables_sheet(df_sheet):
    df_sheet = df_sheet.copy()
    df_sheet.columns = [_normalize_variable_column_name(col) for col in df_sheet.columns]
    if 'DateTime' not in df_sheet.columns and {'Fecha', 'Hora'}.issubset(df_sheet.columns):
        df_sheet = _combine_fecha_hora_columns(df_sheet)
    return df_sheet


def _coerce_sidebar_date(value, fallback):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, date):
        return value
    return fallback


def _clamp_sidebar_date(value, min_date, max_date):
    if value < min_date:
        return min_date
    if value > max_date:
        return max_date
    return value


def _get_nearest_available_date(value, available_dates):
    if not available_dates:
        return value

    ordered_dates = sorted(available_dates)
    value = _coerce_sidebar_date(value, ordered_dates[-1])
    if value in ordered_dates:
        return value

    previous_dates = [available_date for available_date in ordered_dates if available_date <= value]
    if previous_dates:
        return previous_dates[-1]
    return ordered_dates[0]


def _date_input_with_state(label, default_value, key, min_value, max_value, help_text=None):
    kwargs = {
        'key': key,
        'min_value': min_value,
        'max_value': max_value,
        'help': help_text,
    }
    if key not in st.session_state:
        kwargs['value'] = default_value
    return st.date_input(label, **kwargs)


def _loading_context(enabled, message):
    return st.spinner(message, show_time=True) if enabled else nullcontext()


def _get_sidebar_default_range_end(fecha_inicio, max_date, default_days=7):
    default_span_days = max(1, int(default_days))
    return min(fecha_inicio + timedelta(days=default_span_days - 1), max_date)


def _normalize_sidebar_date_range(fecha_inicio, fecha_fin, min_date, max_date):
    fecha_inicio = _clamp_sidebar_date(fecha_inicio, min_date, max_date)
    fecha_fin = _clamp_sidebar_date(fecha_fin, min_date, max_date)

    if fecha_fin < fecha_inicio:
        fecha_inicio, fecha_fin = fecha_fin, fecha_inicio

    return fecha_inicio, fecha_fin


def _format_selected_period_label(fecha_inicio, fecha_fin):
    if fecha_inicio is None or fecha_fin is None:
        return "Sin periodo seleccionado"
    if fecha_inicio == fecha_fin:
        return fecha_inicio.strftime('%d/%m/%Y')
    return f"{fecha_inicio.strftime('%d/%m/%Y')} a {fecha_fin.strftime('%d/%m/%Y')}"


def _shift_selected_period_day(navigation_state_key, current_date, delta_days, min_fecha, max_fecha, available_dates=None):
    if available_dates:
        ordered_dates = sorted({_coerce_sidebar_date(value, value) for value in available_dates})
        if ordered_dates:
            if current_date in ordered_dates:
                current_index = ordered_dates.index(current_date)
            else:
                candidates = [
                    index
                    for index, available_date in enumerate(ordered_dates)
                    if available_date <= current_date
                ]
                current_index = candidates[-1] if candidates else 0
            target_index = max(0, min(current_index + delta_days, len(ordered_dates) - 1))
            st.session_state[navigation_state_key] = ordered_dates[target_index]
            return

    shifted_date = current_date + timedelta(days=delta_days)
    st.session_state[navigation_state_key] = _clamp_sidebar_date(shifted_date, min_fecha, max_fecha)


def _render_selected_period_banner(
    fecha_periodo,
    min_fecha=None,
    max_fecha=None,
    navigation_state_key=None,
    title_text='Periodo visible',
    available_dates=None,
    context_text=None
):
    if not fecha_periodo:
        return

    fecha_inicio, fecha_fin = fecha_periodo
    single_day = fecha_inicio == fecha_fin
    period_label = _format_selected_period_label(fecha_inicio, fecha_fin)
    helper_text = (
        'Estás viendo un solo día del historial.'
        if single_day else
        'Estás viendo un rango completo de días.'
    )
    if context_text:
        helper_text = f"{context_text} {helper_text}"

    col_info, col_prev, col_next = st.columns([8.5, 1.1, 1.1])
    with col_info:
        st.markdown(
            f"""
            <div style="
                margin: 0.2rem 0 1rem 0;
                padding: 0.95rem 1rem;
                border-radius: 8px;
                background: linear-gradient(135deg, rgba(194,223,234,0.18) 0%, rgba(244,199,206,0.14) 100%);
                border: 1px solid rgba(84, 83, 134, 0.08);
            ">
                <div style="
                    font-family: 'Montserrat', sans-serif;
                    font-size: 0.78rem;
                    font-weight: 800;
                    letter-spacing: 0.04em;
                    text-transform: uppercase;
                    color: {BRAND_COLORS['hero']};
                    margin-bottom: 0.35rem;
                ">
                    {html.escape(title_text)}
                </div>
                <div style="
                    font-family: 'Montserrat', sans-serif;
                    font-size: 1.3rem;
                    font-weight: 800;
                    color: {BRAND_COLORS['graphite']};
                    margin-bottom: 0.2rem;
                ">
                    {html.escape(period_label)}
                </div>
                <div style="
                    font-family: 'Montserrat', sans-serif;
                    font-size: 0.92rem;
                    line-height: 1.5;
                    color: rgba(56, 58, 53, 0.78);
                ">
                    {html.escape(helper_text)}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    can_navigate = bool(
        single_day and
        navigation_state_key and
        min_fecha is not None and
        max_fecha is not None
    )
    ordered_available_dates = sorted(available_dates) if available_dates else None
    prev_limit = ordered_available_dates[0] if ordered_available_dates else min_fecha
    next_limit = ordered_available_dates[-1] if ordered_available_dates else max_fecha
    prev_disabled = (not can_navigate) or fecha_inicio <= prev_limit
    next_disabled = (not can_navigate) or fecha_inicio >= next_limit

    with col_prev:
        st.button(
            "◀",
            key=f"{navigation_state_key}_prev" if navigation_state_key else "period_prev_disabled",
            disabled=prev_disabled,
            width="stretch",
        on_click=_shift_selected_period_day if can_navigate else None,
        args=(navigation_state_key, fecha_inicio, -1, min_fecha, max_fecha, ordered_available_dates) if can_navigate else None
    )

    with col_next:
        st.button(
            "▶",
            key=f"{navigation_state_key}_next" if navigation_state_key else "period_next_disabled",
            disabled=next_disabled,
            width="stretch",
        on_click=_shift_selected_period_day if can_navigate else None,
        args=(navigation_state_key, fecha_inicio, 1, min_fecha, max_fecha, ordered_available_dates) if can_navigate else None
    )


def _render_chart_explanation(title, description, accent=None, kicker='Guía de lectura'):
    if not description:
        return

    accent_color = accent or BRAND_COLORS['hero']
    st.markdown(
        f"""
        <div style="
            position: relative;
            overflow: hidden;
            margin: 0.35rem 0 0.8rem 0;
            padding: 0.86rem 1rem 0.84rem 1.05rem;
            border-radius: 8px;
            border: 1px solid rgba(84, 83, 134, 0.09);
            border-left: 4px solid {accent_color};
            background:
                linear-gradient(135deg, rgba(255,255,255,0.94) 0%, rgba(247,244,238,0.90) 100%);
            box-shadow: 0 14px 32px rgba(45, 48, 64, 0.055);
        ">
            <div style="
                font-family: 'Montserrat', sans-serif;
                font-size: 0.70rem;
                font-weight: 800;
                letter-spacing: 0.10em;
                text-transform: uppercase;
                color: {accent_color};
                margin-bottom: 0.26rem;
            ">
                {html.escape(kicker)}
            </div>
            <div style="
                font-family: 'Montserrat', sans-serif;
                font-size: 1rem;
                font-weight: 800;
                color: {BRAND_COLORS['ink']};
                margin-bottom: 0.22rem;
            ">
                {html.escape(title)}
            </div>
            <div style="
                font-family: 'Montserrat', sans-serif;
                font-size: 0.91rem;
                line-height: 1.55;
                color: rgba(56, 58, 53, 0.82);
            ">
                {html.escape(description)}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def _sidebar_icon_svg(icon_name):
    icons = {
        'filter': (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="M4 7h16"></path>'
            '<path d="M7 12h10"></path>'
            '<path d="M10 17h4"></path>'
            '</svg>'
        ),
        'calendar': (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<rect x="3" y="5" width="18" height="16" rx="2"></rect>'
            '<path d="M16 3v4"></path>'
            '<path d="M8 3v4"></path>'
            '<path d="M3 10h18"></path>'
            '</svg>'
        ),
        'location': (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="M12 21s6-5.2 6-11a6 6 0 1 0-12 0c0 5.8 6 11 6 11Z"></path>'
            '<circle cx="12" cy="10" r="2.4"></circle>'
            '</svg>'
        )
    }
    return icons.get(icon_name, '')


def _sidebar_field_label(icon_name, text):
    st.markdown(
        (
            f'<div class="sidebar-field-label">'
            f'<span class="sidebar-field-icon">{_sidebar_icon_svg(icon_name)}</span>'
            f'<span>{html.escape(text)}</span>'
            f'</div>'
        ),
        unsafe_allow_html=True
    )


def _plotly_chart(fig, **kwargs):
    if fig is not None:
        try:
            fig.update_layout(
                font=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['graphite']),
                paper_bgcolor='rgba(255,255,255,0)',
                plot_bgcolor='rgba(255,255,255,0.66)',
                hoverlabel=dict(
                    bgcolor='rgba(255,255,255,0.96)',
                    bordercolor='rgba(84,83,134,0.18)',
                    font=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['ink'])
                )
            )
            fig.update_xaxes(
                gridcolor='rgba(84,83,134,0.08)',
                zerolinecolor='rgba(84,83,134,0.18)',
                linecolor='rgba(84,83,134,0.16)',
                tickfont=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['graphite'])
            )
            fig.update_yaxes(
                gridcolor='rgba(84,83,134,0.08)',
                zerolinecolor='rgba(84,83,134,0.18)',
                linecolor='rgba(84,83,134,0.16)',
                tickfont=dict(family='Montserrat, sans-serif', color=BRAND_COLORS['graphite'])
            )
        except Exception:
            pass
    st.plotly_chart(fig, width='stretch', **kwargs)


def _dataframe(data, **kwargs):
    st.dataframe(data, width='stretch', **kwargs)


def _format_dashboard_view_option(view_name):
    return VIEW_DISPLAY_LABELS.get(view_name, view_name)


def _get_view_group_for_mode(view_groups, mode):
    for group_name, group_options in view_groups.items():
        if mode in group_options:
            return group_name
    return next(iter(view_groups))


def _format_variable_display_title(title):
    clean_title = str(title or "").replace("Comparativa de ", "").strip()
    if 'ppfd' in _build_normalized_text_key(clean_title):
        return PPFD_DISPLAY_NAME
    return clean_title[:1].upper() + clean_title[1:] if clean_title else clean_title


def _hex_to_rgba(hex_color, alpha):
    color = str(hex_color).strip().lstrip('#')
    if len(color) != 6:
        return f'rgba(84, 83, 134, {alpha})'

    try:
        red = int(color[0:2], 16)
        green = int(color[2:4], 16)
        blue = int(color[4:6], 16)
    except ValueError:
        return f'rgba(84, 83, 134, {alpha})'

    return f'rgba({red}, {green}, {blue}, {alpha})'


def _resolve_correlacion_axis_layout(num_sensor_axes, has_cortina_axis):
    total_right_axes = max(1, num_sensor_axes + (1 if has_cortina_axis else 0))
    right_axis_step = 0.041
    axis_end = 0.997
    axis_start = axis_end - right_axis_step * (total_right_axes - 1)
    x_domain_end = max(0.76, axis_start - 0.014)
    right_margin = 58 + total_right_axes * 18

    return {
        'x_domain_end': x_domain_end,
        'sensor_positions': [
            axis_start + right_axis_step * index
            for index in range(num_sensor_axes)
        ],
        'cortina_position': axis_end if has_cortina_axis else None,
        'right_margin': right_margin,
    }


def _format_summary_number(value, decimals):
    if decimals <= 0:
        return f"{round(value):,.0f}".replace(',', '.')

    formatted = f"{value:,.{decimals}f}"
    return formatted.replace(',', '_').replace('.', ',').replace('_', '.')


def _get_summary_metric_config(var_name):
    normalized_key = _build_normalized_text_key(var_name)

    if normalized_key.startswith('temperatura'):
        return {
            'label': 'Temperatura',
            'unit_html': '&deg;C',
            'delta_unit_html': '&deg;C',
            'decimals': 1,
            'icon_svg': (
                '<svg viewBox="0 0 24 24" aria-hidden="true">'
                '<path d="M10 14.5V6a2 2 0 1 1 4 0v8.5a4 4 0 1 1-4 0Z"></path>'
                '<path d="M12 9v5"></path>'
                '</svg>'
            )
        }
    if normalized_key.startswith('humedad relativa'):
        return {
            'label': 'Humedad Relativa',
            'unit_html': '%',
            'delta_unit_html': '%',
            'decimals': 1,
            'icon_svg': (
                '<svg viewBox="0 0 24 24" aria-hidden="true">'
                '<path d="M12 3C9.2 7.1 6.5 9.8 6.5 13a5.5 5.5 0 0 0 11 0C17.5 9.8 14.8 7.1 12 3Z"></path>'
                '</svg>'
            )
        }
    if normalized_key.startswith('radiacion par'):
        return {
            'label': 'PPFD (PAR)',
            'unit_html': 'PPFD &micro;mol m<sup>-2</sup> s<sup>-1</sup>',
            'delta_unit_html': 'PPFD umol/m2/s',
            'decimals': 0,
            'icon_svg': (
                '<svg viewBox="0 0 24 24" aria-hidden="true">'
                '<circle cx="12" cy="12" r="3.5"></circle>'
                '<path d="M12 2.5v2.4"></path>'
                '<path d="M12 19.1v2.4"></path>'
                '<path d="M4.9 4.9 6.6 6.6"></path>'
                '<path d="M17.4 17.4 19.1 19.1"></path>'
                '<path d="M2.5 12h2.4"></path>'
                '<path d="M19.1 12h2.4"></path>'
                '<path d="M4.9 19.1 6.6 17.4"></path>'
                '<path d="M17.4 6.6 19.1 4.9"></path>'
                '</svg>'
            )
        }
    if normalized_key.startswith('gramos de agua'):
        return {
            'label': 'Gramos de agua',
            'unit_html': 'g',
            'delta_unit_html': 'g',
            'decimals': 1,
            'icon_svg': (
                '<svg viewBox="0 0 24 24" aria-hidden="true">'
                '<path d="M4 15c1.4 0 1.4-1.8 2.8-1.8S8.2 15 9.6 15s1.4-1.8 2.8-1.8S13.8 15 15.2 15s1.4-1.8 2.8-1.8S19.4 15 20.8 15"></path>'
                '<path d="M4 18.8c1.4 0 1.4-1.8 2.8-1.8s1.4 1.8 2.8 1.8 1.4-1.8 2.8-1.8 1.4 1.8 2.8 1.8 1.4-1.8 2.8-1.8 1.4 1.8 2.8 1.8"></path>'
                '<path d="M7 9.2h10"></path>'
                '</svg>'
            )
        }

    return {
        'label': str(var_name),
        'unit_html': '',
        'delta_unit_html': '',
        'decimals': 1,
        'icon_svg': (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<circle cx="12" cy="12" r="5"></circle>'
            '</svg>'
        )
    }


def _get_summary_mode_config(summary_mode, single_day):
    mode_key = str(summary_mode).strip().lower()
    mode_map = {
        'promedio': {
            'label': 'Promedio',
            'calculator': lambda serie: float(serie.mean())
        },
        'máximo': {
            'label': 'Máximo',
            'calculator': lambda serie: float(serie.max())
        },
        'maximo': {
            'label': 'Máximo',
            'calculator': lambda serie: float(serie.max())
        },
        'mínimo': {
            'label': 'Mínimo',
            'calculator': lambda serie: float(serie.min())
        },
        'minimo': {
            'label': 'Mínimo',
            'calculator': lambda serie: float(serie.min())
        }
    }
    selected_mode = mode_map.get(mode_key, mode_map['promedio'])
    chip_text = (
        f"{selected_mode['label']} diario"
        if single_day else
        f"{selected_mode['label']} por día"
    )
    return {
        'label': selected_mode['label'],
        'calculator': selected_mode['calculator'],
        'chip_text': chip_text
    }


def _get_summary_selected_dates(fecha_variables):
    if fecha_variables is None:
        return []

    fecha_inicio, fecha_fin = fecha_variables
    return [item.date() for item in pd.date_range(start=fecha_inicio, end=fecha_fin, freq='D')]


def _get_summary_daily_values(df_variables, var_name, fecha_variables, summary_mode_config):
    if df_variables.empty or var_name not in df_variables.columns or fecha_variables is None:
        return []

    if 'Fecha_Filtro' in df_variables.columns:
        fechas = pd.Series(df_variables['Fecha_Filtro'])
    elif 'DateTime' in df_variables.columns:
        fechas = pd.to_datetime(df_variables['DateTime'], errors='coerce').dt.date
    else:
        return []

    working_df = pd.DataFrame({
        'Fecha': fechas,
        'Valor': pd.to_numeric(df_variables[var_name], errors='coerce')
    }).dropna(subset=['Fecha'])

    valores_por_dia = {}
    for fecha, datos_dia in working_df.groupby('Fecha', sort=True):
        serie = datos_dia['Valor'].dropna()
        valores_por_dia[fecha] = (
            summary_mode_config['calculator'](serie)
            if not serie.empty else None
        )

    return [
        {
            'fecha': fecha,
            'value': valores_por_dia.get(fecha)
        }
        for fecha in _get_summary_selected_dates(fecha_variables)
    ]


def _build_summary_daily_list_html(daily_values, config):
    if not daily_values:
        return (
            '<div class="summary-card-value is-empty">'
            '<span class="summary-card-empty">Sin datos</span>'
            '</div>'
        )

    rows = []
    for item in daily_values:
        fecha_label = _format_info_day_label(item.get('fecha'))
        value = item.get('value')

        if value is None or pd.isna(value):
            value_html = '<span class="summary-card-day-empty">Sin datos</span>'
        else:
            number_text = _format_summary_number(float(value), config['decimals'])
            value_html = (
                '<span class="summary-card-day-reading">'
                f'<span class="summary-card-day-number">{number_text}</span>'
                f'<span class="summary-card-day-unit">{config["unit_html"]}</span>'
                '</span>'
            )

        rows.append(
            (
                '<div class="summary-card-day-item">'
                f'<span class="summary-card-day-date">{html.escape(fecha_label)}</span>'
                f'{value_html}'
                '</div>'
            )
        )

    return (
        '<div class="summary-card-day-list-wrap">'
        f'<div class="summary-card-day-list">{"".join(rows)}</div>'
        '</div>'
    )


def _calculate_summary_value(df_variables, var_name, summary_mode_config):
    if df_variables.empty or var_name not in df_variables.columns:
        return None

    serie = pd.to_numeric(df_variables[var_name], errors='coerce').dropna()
    if serie.empty:
        return None

    return summary_mode_config['calculator'](serie)


def _build_summary_delta_html(df_variables, df_reference, var_name, config, summary_mode_config, reference_label):
    summary_value = _calculate_summary_value(df_variables, var_name, summary_mode_config)
    reference_value = _calculate_summary_value(df_reference, var_name, summary_mode_config)

    if summary_value is None or reference_value is None:
        return ''

    delta_value = float(summary_value) - float(reference_value)
    delta_text = _format_summary_number(abs(delta_value), config['decimals'])
    sign = '+' if delta_value > 0 else '-' if delta_value < 0 else ''
    delta_class = 'is-positive' if delta_value > 0 else 'is-negative' if delta_value < 0 else 'is-neutral'

    return (
        f'<span class="summary-card-delta {delta_class}">'
        f'<span class="summary-card-delta-value">{sign}{delta_text} {config.get("delta_unit_html", config["unit_html"])}</span>'
        f'<span class="summary-card-delta-label">vs {html.escape(reference_label)}</span>'
        '</span>'
    )


def _build_summary_cards_html(df_variables, fecha_variables, summary_mode='Promedio', df_reference=None, reference_label='Estación externa'):
    if fecha_variables is None:
        return ''

    fecha_inicio, fecha_fin = fecha_variables
    single_day = fecha_inicio == fecha_fin
    summary_mode_config = _get_summary_mode_config(summary_mode, single_day)
    df_reference = df_reference if isinstance(df_reference, pd.DataFrame) else pd.DataFrame()
    period_chip = summary_mode_config['chip_text']
    period_text = (
        fecha_inicio.strftime('%d/%m/%Y')
        if single_day else
        f"{fecha_inicio.strftime('%d/%m/%Y')} - {fecha_fin.strftime('%d/%m/%Y')}"
    )

    cards_html = []

    for var_name in SENSOR_VARIABLES:
        config = _get_summary_metric_config(var_name)
        accent_color = VARIABLE_COLORS.get(var_name, BRAND_COLORS['hero'])
        accent_soft = _hex_to_rgba(accent_color, 0.14)
        value_markup = (
            '<div class="summary-card-value is-empty">'
            '<span class="summary-card-empty">Sin datos</span>'
            '</div>'
        )
        delta_markup = _build_summary_delta_html(
            df_variables,
            df_reference,
            var_name,
            config,
            summary_mode_config,
            reference_label
        ) if single_day else ''

        if not df_variables.empty and var_name in df_variables.columns:
            if single_day:
                summary_value = _calculate_summary_value(df_variables, var_name, summary_mode_config)
                if summary_value is not None:
                    number_text = _format_summary_number(summary_value, config['decimals'])
                    value_markup = (
                        '<div class="summary-card-value">'
                        f'<span class="summary-card-number">{number_text}</span>'
                        f'<span class="summary-card-unit">{config["unit_html"]}</span>'
                        '</div>'
                    )
            else:
                daily_values = _get_summary_daily_values(
                    df_variables,
                    var_name,
                    fecha_variables,
                    summary_mode_config
                )
                value_markup = _build_summary_daily_list_html(daily_values, config)

        cards_html.append(
            (
                f'<div class="summary-card" style="--summary-accent: {accent_color}; --summary-accent-soft: {accent_soft};">'
                '<div class="summary-card-header">'
                f'<span class="summary-card-icon">{config["icon_svg"]}</span>'
                f'<span class="summary-card-label">{html.escape(config["label"])}</span>'
                '</div>'
                f'{value_markup}'
                f'{delta_markup}'
                '<div class="summary-card-footer">'
                f'<span class="summary-card-chip">{html.escape(period_chip)}</span>'
                f'<span class="summary-card-period">{html.escape(period_text)}</span>'
                '</div>'
                '</div>'
            )
        )

    return f'<div class="summary-grid">{"".join(cards_html)}</div>'


def _render_summary_cards(df_variables, fecha_variables, summary_mode='Promedio', df_reference=None, reference_label='Estación externa'):
    cards_html = _build_summary_cards_html(
        df_variables,
        fecha_variables,
        summary_mode=summary_mode,
        df_reference=df_reference,
        reference_label=reference_label
    )
    if cards_html:
        st.markdown(cards_html, unsafe_allow_html=True)


def _render_reference_summary_cards(df_reference, fecha_variables, summary_mode, reference_label, df_base=None, base_label='Bloque seleccionado'):
    if not isinstance(df_reference, pd.DataFrame) or df_reference.empty:
        return

    st.markdown(
        f'<p class="analysis-note"><strong>{html.escape(reference_label)}</strong></p>',
        unsafe_allow_html=True
    )
    _render_summary_cards(
        df_reference,
        fecha_variables,
        summary_mode=summary_mode,
        df_reference=df_base,
        reference_label=base_label
    )


def _render_summary_cards_selector(df_variables, fecha_variables, df_reference=None, reference_label='Estación externa', base_label='Bloque seleccionado'):
    _render_chart_explanation(
        'Resumen rápido del periodo',
        'Estas tarjetas condensan las variables ambientales del periodo filtrado. Cambia entre promedio, máximo y mínimo para entender el comportamiento general antes de revisar las gráficas.',
        accent=BRAND_COLORS['hero'],
        kicker='Resumen del análisis'
    )
    summary_modes = ["Promedio", "Máximo", "Mínimo"]
    if st.session_state.get("resumen_metric_option") not in summary_modes:
        st.session_state["resumen_metric_option"] = summary_modes[0]
    summary_mode = st.segmented_control(
        "Métrica del resumen",
        options=summary_modes,
        key="resumen_metric_option",
        help="Calcula solo el resumen visible para mantener la carga más liviana.",
        width="stretch"
    )
    _render_summary_cards(
        df_variables,
        fecha_variables,
        summary_mode=summary_mode,
        df_reference=df_reference,
        reference_label=reference_label
    )
    _render_reference_summary_cards(
        df_reference,
        fecha_variables,
        summary_mode,
        reference_label,
        df_base=df_variables,
        base_label=base_label
    )


def _info_panel_icon_svg(icon_name):
    icons = {
        'modificacion': (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="M4 7.5h16"></path>'
            '<path d="M7 12h10"></path>'
            '<path d="M10 16.5h4"></path>'
            '</svg>'
        ),
        'observaciones': (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="M8 9h8"></path>'
            '<path d="M8 13h5"></path>'
            '<path d="M6 20V5.8A1.8 1.8 0 0 1 7.8 4h8.4A1.8 1.8 0 0 1 18 5.8V20l-6-3-6 3Z"></path>'
            '</svg>'
        ),
        'culatas': (
            '<svg viewBox="0 0 24 24" aria-hidden="true">'
            '<path d="M12 3C9.2 7.1 6.5 9.8 6.5 13a5.5 5.5 0 0 0 11 0C17.5 9.8 14.8 7.1 12 3Z"></path>'
            '<path d="M12 9.2v5.2"></path>'
            '</svg>'
        )
    }
    return icons.get(icon_name, '')


def _render_info_panels(
    block_label,
    block_modification,
    culatas_observation,
    daily_annotations,
    rango_multiple,
    annotations_by_day=None,
    culatas_by_day=None
):
    period_context = 'del periodo' if rango_multiple else 'del día'
    period_tag = 'Periodo' if rango_multiple else 'Día'
    observation_title = 'Observaciones'
    culatas_title = 'Estado de culatas'
    block_title = 'Modificación aplicada'
    block_tag_text = str(block_label) if block_label else 'Sin bloque'
    block_tag = html.escape(block_tag_text)
    annotations_by_day = annotations_by_day or []
    culatas_by_day = culatas_by_day or []

    observations_html = ''
    if rango_multiple and annotations_by_day:
        annotation_count = sum(len(item.get('entries', [])) for item in annotations_by_day)
        annotation_label = 'evento registrado' if annotation_count == 1 else 'eventos registrados'
        day_groups = []

        for item in annotations_by_day:
            fecha_label = _format_info_day_label(item.get('fecha'))
            entries = item.get('entries', [])
            day_chip_text = 'Sin novedades' if not entries else (
                '1 evento' if len(entries) == 1 else f'{len(entries)} eventos'
            )
            day_lines = (
                ''.join(
                    f'<p class="info-panel-day-line">{html.escape(entry)}</p>'
                    for entry in entries
                )
                if entries else
                '<p class="info-panel-day-line is-muted">Sin anotaciones registradas.</p>'
            )
            day_groups.append(
                (
                    '<div class="info-panel-day-card">'
                    '<div class="info-panel-day-header">'
                    f'<span class="info-panel-day-date">{html.escape(fecha_label)}</span>'
                    f'<span class="info-panel-day-chip">{html.escape(day_chip_text)}</span>'
                    '</div>'
                    f'<div class="info-panel-day-lines">{day_lines}</div>'
                    '</div>'
                )
            )

        observations_html = (
            '<div class="info-panel-body">'
            '<div class="info-panel-stat-row">'
            f'<span class="info-panel-stat-value">{annotation_count}</span>'
            f'<span class="info-panel-stat-caption">{html.escape(annotation_label)}</span>'
            '</div>'
            f'<div class="info-panel-day-scroll"><div class="info-panel-day-groups">{"".join(day_groups)}</div></div>'
            '<p class="info-panel-footer-note">Eventos organizados por fecha dentro del periodo seleccionado.</p>'
            '</div>'
        )
    elif daily_annotations:
        annotation_count = len(daily_annotations)
        annotation_label = 'evento registrado' if annotation_count == 1 else 'eventos registrados'
        observation_items = []
        for item in daily_annotations:
            observation_items.append(
                (
                    '<li class="info-panel-list-item">'
                    '<span class="info-panel-dot"></span>'
                    f'<span class="info-panel-list-text">{html.escape(item)}</span>'
                    '</li>'
                )
            )
        observations_html = (
            '<div class="info-panel-body">'
            '<div class="info-panel-stat-row">'
            f'<span class="info-panel-stat-value">{annotation_count}</span>'
            f'<span class="info-panel-stat-caption">{html.escape(annotation_label)}</span>'
            '</div>'
            f'<div class="info-panel-list-wrap"><ul class="info-panel-list">{"".join(observation_items)}</ul></div>'
            f'<p class="info-panel-footer-note">Eventos registrados {period_context}.</p>'
            '</div>'
        )
    else:
        observations_html = (
            '<div class="info-panel-body">'
            '<div class="info-panel-empty-state info-panel-empty-state--centered">'
            '<span class="info-panel-state-badge" style="background: rgba(244, 199, 206, 0.18); color: #B56576;">Sin novedades</span>'
            '<p class="info-panel-empty-title">Sin novedades operativas</p>'
            f'<p class="info-panel-empty">No se registran anotaciones {period_context}.</p>'
            '</div>'
            '</div>'
        )

    mod_text = block_modification or 'No hay una modificación documentada para este bloque.'
    mod_html = (
        '<div class="info-panel-body">'
        f'<p class="info-panel-copy">{html.escape(mod_text)}</p>'
        f'<p class="info-panel-footer-note">Configuración de referencia para {block_tag}.</p>'
        '</div>'
    )

    culatas_state = culatas_observation or 'Sin información disponible'
    culatas_style = _get_culatas_state_style(culatas_state)
    culatas_badge_bg = culatas_style['badge_bg']
    culatas_badge_color = culatas_style['badge_color']
    culatas_tag = culatas_style['tag']

    if rango_multiple and culatas_by_day:
        day_states = []
        for item in culatas_by_day:
            fecha_label = _format_info_day_label(item.get('fecha'))
            state_text = item.get('state') or 'Sin información disponible'
            state_style = _get_culatas_state_style(state_text)
            day_states.append(
                (
                    '<div class="info-panel-day-card">'
                    '<div class="info-panel-day-header">'
                    f'<span class="info-panel-day-date">{html.escape(fecha_label)}</span>'
                    '</div>'
                    '<div class="info-panel-day-state-row">'
                    f'<span class="info-panel-state-badge" style="background:{state_style["badge_bg"]}; color:{state_style["badge_color"]};">{html.escape(state_style["tag"])}</span>'
                    f'<span class="info-panel-day-line">{html.escape(state_text)}</span>'
                    '</div>'
                    '</div>'
                )
            )

        culatas_html = (
            '<div class="info-panel-body">'
            f'<div class="info-panel-day-scroll"><div class="info-panel-day-groups">{"".join(day_states)}</div></div>'
            '<p class="info-panel-footer-note">Estado consolidado por fecha dentro del periodo seleccionado.</p>'
            '</div>'
        )
    else:
        culatas_html = (
            '<div class="info-panel-body">'
            '<div class="info-panel-state">'
            f'<span class="info-panel-state-badge" style="background:{culatas_badge_bg}; color:{culatas_badge_color};">{html.escape(culatas_tag)}</span>'
            f'<span class="info-panel-state-text">{html.escape(culatas_state)}</span>'
            '</div>'
            f'<p class="info-panel-copy">Estado operativo {period_context} para {html.escape(block_tag_text.lower()) if block_label else "el bloque seleccionado"}.</p>'
            '</div>'
        )

    info_cards = {
        'observaciones': (
            f'<div class="info-panel-card info-panel-card--observaciones" style="--info-accent: {BRAND_COLORS["rose"]}; --info-accent-soft: rgba(231, 210, 218, 0.22);">'
            '<div class="info-panel-header">'
            '<div class="info-panel-header-main">'
            f'<span class="info-panel-icon">{_info_panel_icon_svg("observaciones")}</span>'
            '<div class="info-panel-heading">'
            f'<h3 class="info-panel-title">{html.escape(observation_title)}</h3>'
            '</div>'
            '</div>'
            f'<span class="info-panel-tag">{html.escape(period_tag)}</span>'
            '</div>'
            f'{observations_html}'
            '</div>'
        ),
        'modificacion': (
            f'<div class="info-panel-card info-panel-card--compact" style="--info-accent: {BRAND_COLORS["hero"]}; --info-accent-soft: rgba(76, 70, 120, 0.15);">'
            '<div class="info-panel-header">'
            '<div class="info-panel-header-main">'
            f'<span class="info-panel-icon">{_info_panel_icon_svg("modificacion")}</span>'
            '<div class="info-panel-heading">'
            f'<h3 class="info-panel-title">{html.escape(block_title)}</h3>'
            '</div>'
            '</div>'
            f'<span class="info-panel-tag">{block_tag}</span>'
            '</div>'
            f'{mod_html}'
            '</div>'
        ),
        'culatas': (
            f'<div class="info-panel-card info-panel-card--compact" style="--info-accent: {BRAND_COLORS["sky"]}; --info-accent-soft: rgba(214, 229, 236, 0.28);">'
            '<div class="info-panel-header">'
            '<div class="info-panel-header-main">'
            f'<span class="info-panel-icon">{_info_panel_icon_svg("culatas")}</span>'
            '<div class="info-panel-heading">'
            f'<h3 class="info-panel-title">{html.escape(culatas_title)}</h3>'
            '</div>'
            '</div>'
            f'<span class="info-panel-tag">{html.escape(period_tag)}</span>'
            '</div>'
            f'{culatas_html}'
            '</div>'
        )
    }

    st.markdown(
        (
            '<div class="info-panels-layout">'
            '<div class="info-panels-grid">'
            f'{info_cards["observaciones"]}'
            f'{info_cards["modificacion"]}'
            f'{info_cards["culatas"]}'
            '</div>'
            '</div>'
        ),
        unsafe_allow_html=True
    )


def _selector_state_key(var_name):
    safe_name = re.sub(r'[^a-z0-9]+', '_', str(var_name).lower()).strip('_')
    return f'variables_correlacion_{safe_name}'


def _reset_correlacion_selector(options):
    st.session_state['variables_correlacion'] = options.copy()
    known_options = list(dict.fromkeys((SENSOR_VARIABLES + MOTOR_VARIABLES) + list(options)))
    for option in known_options:
        st.session_state[_selector_state_key(option)] = option in options


def _get_selected_correlacion_vars(options):
    selected_vars = [option for option in options if st.session_state.get(_selector_state_key(option), True)]
    st.session_state['variables_correlacion'] = selected_vars
    return selected_vars


def _cortina_visibility_state_key(motor_name):
    safe_name = _build_normalized_text_key(motor_name).replace(' ', '_')
    return f"ponderosa_cortina_visible_{safe_name}"


def _ensure_cortina_visibility_state(available_motors):
    for motor_name in available_motors:
        key = _cortina_visibility_state_key(motor_name)
        if key not in st.session_state:
            st.session_state[key] = True


def _get_selected_cortina_motors(available_motors):
    return [
        motor_name
        for motor_name in available_motors
        if st.session_state.get(_cortina_visibility_state_key(motor_name), True)
    ]


def _render_cortina_visibility_panel(available_motors):
    st.markdown(
        """
        <span class="series-side-panel-marker"></span>
        <div class="series-control-card">
            <p class="series-control-kicker">Cortinas visibles</p>
            <h3 class="series-control-title">Series activas</h3>
            <p class="series-control-copy">
                Elige los frentes y puertas que quieres mantener visibles en la grafica principal.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    if not available_motors:
        st.info("No hay frentes o puertas disponibles en este periodo.")
        return

    _ensure_cortina_visibility_state(available_motors)
    for motor_name in available_motors:
        st.checkbox(
            VARIABLE_SELECTOR_LABELS.get(motor_name, motor_name),
            key=_cortina_visibility_state_key(motor_name),
            help=VARIABLE_FILTER_HELP.get(motor_name, FILTER_HELP_TEXTS['series_visibles'])
        )


def _render_correlacion_series_panel(available_vars, selected_block_code, df_variables_almacen):
    if not available_vars:
        st.info("No hay series disponibles para el rango seleccionado.")
        return []

    with st.expander("Configurar series visibles", expanded=True):
        st.markdown(
            """
            <div class="series-control-card">
                <p class="series-control-kicker">Selector de lectura</p>
                <h3 class="series-control-title">Elige qué señales quieres cruzar en la gráfica</h3>
                <p class="series-control-copy">
                    Mantén visibles las variables ambientales clave y activa las referencias operativas solo cuando ayuden
                    a explicar un cambio de temperatura, humedad, radiación o gramos de agua.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown('<p class="series-toolbar-label">Acciones rápidas</p>', unsafe_allow_html=True)
        action_col, clear_col, external_col, ideal_col = st.columns([0.22, 0.22, 0.34, 0.22], vertical_alignment="center")
        with action_col:
            if st.button("Seleccionar todas", key="correlacion_select_all", width="stretch"):
                _reset_correlacion_selector(available_vars)
        with clear_col:
            if st.button("Quitar todas", key="correlacion_clear_all", width="stretch"):
                for option in available_vars:
                    st.session_state[_selector_state_key(option)] = False
                st.session_state['variables_correlacion'] = []
        with external_col:
            st.checkbox(
                "Comparar con Estación externa",
                key="comparar_con_almacen",
                disabled=selected_block_code == 'ALMACEN' or df_variables_almacen.empty,
                help=FILTER_HELP_TEXTS['comparar_almacen']
            )
        with ideal_col:
            st.checkbox(
                "Aperturas ideales",
                key="mostrar_aperturas_ideales",
                help=FILTER_HELP_TEXTS['aperturas_ideales']
            )

        st.markdown('<div class="series-toolbar-spacer"></div>', unsafe_allow_html=True)
        st.markdown('<p class="analysis-note"><strong>Variables ambientales y operativas disponibles</strong></p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="series-chip-note">Activa solo las señales que realmente aporten lectura al cruce. Así la gráfica respira mejor y se vuelve más clara.</p>',
            unsafe_allow_html=True
        )
        option_columns = st.columns(min(4, max(1, len(available_vars))))
        for idx, option in enumerate(available_vars):
            state_key = _selector_state_key(option)
            if state_key not in st.session_state:
                st.session_state[state_key] = True
            with option_columns[idx % len(option_columns)]:
                st.checkbox(
                    VARIABLE_SELECTOR_LABELS.get(option, VARIABLE_LABELS.get(option, option)),
                    key=state_key,
                    help=VARIABLE_FILTER_HELP.get(option, FILTER_HELP_TEXTS['series_visibles'])
                )

    return _get_selected_correlacion_vars(available_vars)


def _analysis_block_state_key(block_code):
    safe_code = re.sub(r'[^a-z0-9]+', '_', str(block_code).lower()).strip('_')
    return f'bloques_analisis_{safe_code}'


def _reset_analysis_block_selector(block_codes):
    st.session_state['bloques_analisis'] = block_codes.copy()
    for block_code in block_codes:
        st.session_state[_analysis_block_state_key(block_code)] = True


def _get_selected_analysis_blocks(block_codes):
    selected_blocks = [block_code for block_code in block_codes if st.session_state.get(_analysis_block_state_key(block_code), True)]
    st.session_state['bloques_analisis'] = selected_blocks
    return selected_blocks


def _get_block_modification(block_name):
    block_code = _extract_block_code(block_name)
    return BLOCK_MODIFICATIONS.get(block_code) if block_code else None


def _get_block_ventilation_rows(block_name):
    block_code = _extract_block_code(block_name)
    if not block_code:
        return []
    return BLOCK_VENTILATION_DATA.get(block_code, [])


def _get_block_ventilation_row(block_name, expected_row_key):
    for row in _get_block_ventilation_rows(block_name):
        row_key = _build_normalized_text_key(row.get('label', ''))
        if row_key == expected_row_key:
            return row
    return None


def _get_motor_area_reference(block_name, motor_name):
    motor_key = _normalize_cortina_name(motor_name)
    reference_config = MOTOR_AREA_REFERENCE.get(motor_key)
    if not reference_config:
        return None

    row = _get_block_ventilation_row(block_name, reference_config['row_key'])
    if not row:
        return None

    real_value = row.get('real')
    ideal_value = row.get('ideal')
    if real_value is None or pd.isna(real_value):
        return None

    return {
        'real_max_area': float(real_value) / float(reference_config['divisor']),
        'ideal_max_area': (
            float(ideal_value) / float(reference_config['divisor'])
            if ideal_value is not None and not pd.isna(ideal_value)
            else None
        )
    }


def _get_culatas_area_reference(block_name):
    row = _get_block_ventilation_row(block_name, 'ventilacion culatas')
    if not row:
        return None

    real_value = row.get('real')
    if real_value is None or pd.isna(real_value):
        return None

    return float(real_value)


def _build_culatas_state_text(open_percent, block_name=None):
    percent_value = _normalize_percent_value(open_percent)
    if percent_value is None:
        return 'Sin información disponible'

    if percent_value <= 0:
        return 'Culatas cerradas'

    max_area = _get_culatas_area_reference(block_name)
    if max_area is None:
        return 'Culatas abiertas'

    open_area = max_area * percent_value / 100.0
    area_text = _format_area_value(open_area)
    percent_text = _format_summary_number(percent_value, 0)
    return f'Culatas abiertas - {area_text} m2 abiertos ({percent_text}%)'


def _convert_cortina_profile_to_area(df_state, real_max_area, ideal_max_area=None):
    if df_state.empty:
        return df_state

    df_area = df_state.copy()
    apertura_pct = pd.to_numeric(df_area['Apertura'], errors='coerce')
    df_area['Apertura_m2'] = apertura_pct * float(real_max_area) / 100.0
    if ideal_max_area is not None:
        df_area['Apertura_ideal_m2'] = apertura_pct * float(ideal_max_area) / 100.0
    else:
        df_area['Apertura_ideal_m2'] = pd.NA

    detail_values = []
    for detail in df_area['Detalle'].fillna(''):
        detail_text = str(detail).strip()
        if detail_text:
            detail_values.append(detail_text.replace(' | ', ' - '))
        else:
            detail_values.append('')

    df_area['DetalleGrafico'] = detail_values
    apertura_ideal_series = pd.to_numeric(df_area['Apertura_ideal_m2'], errors='coerce')
    brecha_ideal_series = pd.to_numeric(df_area['Apertura_m2'], errors='coerce') - apertura_ideal_series
    df_area['ResumenIdealTexto'] = [
        (
            f'Ideal: {_format_area_value(ideal_value)} m2 | Brecha: {_format_area_value(gap_value)} m2'
            if not pd.isna(ideal_value) and not pd.isna(gap_value) else
            'Ideal: Sin dato'
        )
        for ideal_value, gap_value in zip(apertura_ideal_series, brecha_ideal_series)
    ]
    return df_area


def _format_area_value(value):
    if value is None or pd.isna(value):
        return 'No aplica'

    numeric_value = round(float(value), 2)
    if abs(numeric_value - round(numeric_value)) < 1e-6:
        decimals = 0
    elif abs(numeric_value - round(numeric_value, 1)) < 1e-6:
        decimals = 1
    else:
        decimals = 2

    return _format_summary_number(numeric_value, decimals)


def _extract_block_code(block_name):
    if not block_name:
        return None
    match = re.search(r'(\d+)', str(block_name))
    return match.group(1) if match else None


def _extract_block_identifier(block_name):
    block_code = _extract_block_code(block_name)
    if block_code:
        return block_code

    normalized_key = _build_normalized_text_key(block_name)
    if 'almacen' in normalized_key:
        return 'ALMACEN'

    return None


def _sort_block_names(block_names):
    def sort_key(name):
        text = str(name)
        normalized = _build_normalized_text_key(text)
        if 'almacen' in normalized:
            return (0, 0, text)

        match = re.search(r'(\d+)', text)
        if match:
            return (1, int(match.group(1)), text)

        return (2, float('inf'), text)

    return sorted(block_names, key=sort_key)


def _get_finca_for_block(block_name):
    normalized_key = _build_normalized_text_key(block_name)
    if 'marley' in normalized_key or 'marly' in normalized_key:
        return 'Marly'

    block_identifier = _extract_block_identifier(block_name)
    if block_identifier and block_identifier in BLOCK_FARMS:
        return BLOCK_FARMS[block_identifier]

    return 'La Ponderosa'


def _get_block_options(df_variables_all, df_cortinas_all, selected_finca=None):
    variable_map = {}
    cortina_map = {}

    if not df_variables_all.empty and 'Bloque' in df_variables_all.columns:
        for block_name in sorted(df_variables_all['Bloque'].dropna().unique()):
            if selected_finca and _get_finca_for_block(block_name) != selected_finca:
                continue
            block_identifier = _extract_block_identifier(block_name)
            if block_identifier:
                variable_map[block_identifier] = block_name

    if not df_cortinas_all.empty and 'Bloque' in df_cortinas_all.columns:
        for block_name in sorted(df_cortinas_all['Bloque'].dropna().unique()):
            if selected_finca and _get_finca_for_block(block_name) != selected_finca:
                continue
            block_identifier = _extract_block_identifier(block_name)
            if block_identifier:
                cortina_map[block_identifier] = block_name

    block_codes = _sort_block_names(list(variable_map.keys()))
    return block_codes, variable_map, cortina_map


def _add_day_breaks_to_series(serie, value_col):
    if serie.empty or 'DateTime' not in serie.columns:
        return serie

    serie = serie.sort_values('DateTime').reset_index(drop=True)
    if serie['DateTime'].dt.date.nunique() <= 1:
        return serie

    rows = []
    previous_date = None

    for _, row in serie.iterrows():
        current_date = row['DateTime'].date()
        if previous_date is not None and current_date != previous_date:
            rows.append({'DateTime': row['DateTime'], value_col: None})
        rows.append({'DateTime': row['DateTime'], value_col: row[value_col]})
        previous_date = current_date

    return pd.DataFrame(rows)


def _resolve_plot_resample_rule(total_days, total_points):
    if total_points <= 1200 and total_days <= 3:
        return None
    if total_points <= 2500 and total_days <= 7:
        return None
    if total_days <= 7:
        return '30min'
    if total_days <= 21:
        return '1h'
    if total_days <= 60:
        return '3h'
    return '6h'


def _prepare_sensor_series_for_plot(serie, value_col, multi_day_view=False):
    if serie.empty or 'DateTime' not in serie.columns or value_col not in serie.columns:
        return serie, None

    working = (
        serie[['DateTime', value_col]]
        .dropna(subset=['DateTime', value_col])
        .sort_values('DateTime')
        .copy()
    )
    if working.empty:
        return working, None

    if not multi_day_view:
        return working, None

    total_points = len(working)
    min_dt = pd.Timestamp(working['DateTime'].min())
    max_dt = pd.Timestamp(working['DateTime'].max())
    total_days = max(((max_dt - min_dt).total_seconds() / 86400.0) + 1, 1)
    resample_rule = _resolve_plot_resample_rule(total_days, total_points)

    if not resample_rule:
        return _add_day_breaks_to_series(working, value_col), None

    try:
        resampled = (
            working.set_index('DateTime')[[value_col]]
            .resample(resample_rule)
            .mean()
            .dropna()
            .reset_index()
        )
    except ValueError:
        return _add_day_breaks_to_series(working, value_col), None
    if resampled.empty:
        return _add_day_breaks_to_series(working, value_col), None

    return _add_day_breaks_to_series(resampled, value_col), {
        'rule': resample_rule,
        'original_points': total_points,
        'display_points': len(resampled)
    }


def _normalize_percent_value(value):
    if pd.isna(value):
        return None
    return max(0.0, min(100.0, float(value)))


def _normalize_cortina_name(value):
    if pd.isna(value):
        return None

    normalized_key = _build_normalized_text_key(value)
    normalized_key = re.sub(r'\s+', ' ', normalized_key).strip()
    cortina_name_map = {
        'frente 1': 'FRENTE 1',
        'frente 2': 'FRENTE 2',
        'puerta 1': 'PUERTA 1',
        'puerta 2': 'PUERTA 2'
    }
    return cortina_name_map.get(normalized_key, str(value).strip())


def _build_cortina_apertura_profile(df_cortinas, elemento, config):
    elemento_col = config['element_col']
    apertura_col = config['open_time_col']
    apertura_pct_col = config['open_pct_col']
    duracion_apertura_col = config['open_duration_col']
    cierre_col = config['close_time_col']
    cierre_pct_col = config['close_pct_col']
    duracion_cierre_col = config['close_duration_col']

    if elemento_col not in df_cortinas.columns:
        return pd.DataFrame()

    elemento_normalizado = _normalize_cortina_name(elemento)
    elementos_normalizados = df_cortinas[elemento_col].apply(_normalize_cortina_name)
    datos_elem = df_cortinas[elementos_normalizados == elemento_normalizado].copy()
    if datos_elem.empty or 'Fecha' not in datos_elem.columns:
        return pd.DataFrame()

    datos_elem = datos_elem.sort_values(['Fecha', apertura_col, cierre_col], na_position='last').reset_index(drop=True)
    fechas_elem = [fecha for fecha in datos_elem['Fecha'].dropna().drop_duplicates().tolist()]
    profile = []

    for day_index, fecha_dia in enumerate(fechas_elem):
        datos_dia = datos_elem[datos_elem['Fecha'] == fecha_dia].copy()
        if datos_dia.empty:
            continue

        if day_index > 0:
            profile.append({
                'Hora': datetime.combine(fecha_dia, datetime.min.time()),
                'Apertura': None,
                'Evento': 'Cambio de día',
                'Detalle': ''
            })

        inicio_dia = datetime.combine(fecha_dia, datetime.min.time())
        fin_dia = datetime.combine(fecha_dia, datetime.max.time().replace(microsecond=0))
        current_level = 0.0
        profile.append({
            'Hora': inicio_dia,
            'Apertura': current_level,
            'Evento': 'Inicio del día',
            'Detalle': 'Estado inicial: 0% abierto'
        })

        for _, evt in datos_dia.iterrows():
            apertura_pct = _normalize_percent_value(evt[apertura_pct_col])
            cierre_pct = _normalize_percent_value(evt[cierre_pct_col])
            target_open_level = apertura_pct if apertura_pct is not None else current_level
            target_close_level = 100.0 - cierre_pct if cierre_pct is not None else current_level

            if pd.notna(evt[apertura_col]):
                inicio_apertura = datetime.combine(fecha_dia, evt[apertura_col])
                duracion_ap = float(evt[duracion_apertura_col]) if pd.notna(evt[duracion_apertura_col]) else 0.0
                fin_apertura = inicio_apertura + timedelta(minutes=duracion_ap)
                profile.append({
                    'Hora': inicio_apertura,
                    'Apertura': current_level,
                    'Evento': 'Inicio Apertura',
                    'Detalle': f"Objetivo: {target_open_level:.0f}% abierto | Duración apertura: {duracion_ap:.0f} min"
                })
                profile.append({
                    'Hora': fin_apertura,
                    'Apertura': target_open_level,
                    'Evento': 'Fin Apertura',
                    'Detalle': f"Nivel alcanzado: {target_open_level:.0f}% abierto | Inicio: {inicio_apertura.strftime('%H:%M')} | Fin: {fin_apertura.strftime('%H:%M')}"
                })
                current_level = target_open_level

            if pd.notna(evt[cierre_col]):
                inicio_cierre = datetime.combine(fecha_dia, evt[cierre_col])
                duracion_ci = float(evt[duracion_cierre_col]) if pd.notna(evt[duracion_cierre_col]) else 0.0
                fin_cierre = inicio_cierre + timedelta(minutes=duracion_ci)
                profile.append({
                    'Hora': inicio_cierre,
                    'Apertura': current_level,
                    'Evento': 'Inicio Cierre',
                    'Detalle': f"Cierre: {cierre_pct:.0f}% | Duración cierre: {duracion_ci:.0f} min"
                    if cierre_pct is not None else f"Duración cierre: {duracion_ci:.0f} min"
                })
                profile.append({
                    'Hora': fin_cierre,
                    'Apertura': target_close_level,
                    'Evento': 'Fin Cierre',
                    'Detalle': f"Nivel final: {target_close_level:.0f}% abierto | Inicio: {inicio_cierre.strftime('%H:%M')} | Fin: {fin_cierre.strftime('%H:%M')}"
                })
                current_level = target_close_level

        profile.append({
            'Hora': fin_dia,
            'Apertura': current_level,
            'Evento': 'Fin del día',
            'Detalle': f"Estado final: {current_level:.0f}% abierto"
        })

    return pd.DataFrame(profile).sort_values('Hora').reset_index(drop=True)


def _get_culatas_daily_observation(datos_cortinas, block_label=None):
    if datos_cortinas.empty or 'Culatas %' not in datos_cortinas.columns:
        return None

    valores_culatas = datos_cortinas['Culatas %'].dropna()
    if valores_culatas.empty:
        return None

    ultimo_valor = _normalize_percent_value(valores_culatas.iloc[-1])
    if ultimo_valor is None:
        return None
    return _build_culatas_state_text(ultimo_valor, block_label)


def _get_culatas_observation_by_day(datos_cortinas, block_label=None):
    if (
        datos_cortinas.empty or
        'Fecha' not in datos_cortinas.columns or
        'Culatas %' not in datos_cortinas.columns
    ):
        return []

    observations = []
    datos_ordenados = datos_cortinas.sort_values('Fecha')

    for fecha, datos_dia in datos_ordenados.groupby('Fecha', sort=True):
        valores_culatas = datos_dia['Culatas %'].dropna()
        if valores_culatas.empty:
            state = 'Sin información disponible'
        else:
            ultimo_valor = _normalize_percent_value(valores_culatas.iloc[-1])
            if ultimo_valor is None:
                state = 'Sin información disponible'
            else:
                state = _build_culatas_state_text(ultimo_valor, block_label)

        observations.append({
            'fecha': fecha,
            'state': state
        })

    return observations


def _format_cortina_time(value):
    if pd.isna(value):
        return 'Sin dato'
    if hasattr(value, 'strftime'):
        return value.strftime('%H:%M')
    timestamp = pd.to_datetime(value, errors='coerce')
    if pd.isna(timestamp):
        return str(value)
    return timestamp.strftime('%H:%M')


def _format_cortina_duration(value):
    numeric_value = pd.to_numeric(pd.Series([value]), errors='coerce').iloc[0]
    if pd.isna(numeric_value):
        return 'Sin dato'
    return f"{float(numeric_value):.0f} min"


def _format_cortina_pct(value):
    pct_value = _normalize_percent_value(value)
    if pct_value is None:
        return 'Sin dato'
    return f"{pct_value:.0f}%"


def _build_cortina_operation_rows(datos_cortinas, selected_motors=None):
    if datos_cortinas.empty:
        return pd.DataFrame()

    selected_set = set(selected_motors or [])
    rows = []
    for _, record in datos_cortinas.sort_values('Fecha').iterrows():
        fecha = record.get('Fecha')
        fecha_label = _format_info_day_label(fecha)
        for side_label, config in SIDE_CONFIGS.items():
            motor_name = _normalize_cortina_name(record.get(config['element_col']))
            if not motor_name or (selected_set and motor_name not in selected_set):
                continue

            note_value = record.get(config['note_col'])
            note_text = '' if pd.isna(note_value) else str(note_value).strip()
            if note_text.lower() in {'nan', 'none'}:
                note_text = ''

            rows.append({
                'Fecha': fecha_label,
                'Cortina': VARIABLE_SELECTOR_LABELS.get(motor_name, motor_name),
                'Lado': side_label,
                'Inicio apertura': _format_cortina_time(record.get(config['open_time_col'])),
                'Duración apertura': _format_cortina_duration(record.get(config['open_duration_col'])),
                'Apertura objetivo': _format_cortina_pct(record.get(config['open_pct_col'])),
                'Inicio cierre': _format_cortina_time(record.get(config['close_time_col'])),
                'Duración cierre': _format_cortina_duration(record.get(config['close_duration_col'])),
                'Cierre registrado': _format_cortina_pct(record.get(config['close_pct_col'])),
                'Comentario': note_text or 'Sin comentario'
            })

    return pd.DataFrame(rows)


def _render_cortina_operation_summary(datos_cortinas, selected_motors):
    operation_rows = _build_cortina_operation_rows(datos_cortinas, selected_motors)
    if operation_rows.empty:
        st.info("No hay eventos operativos de apertura o cierre para las cortinas seleccionadas.")
        return

    st.markdown("### Detalle operativo de cortinas")
    _render_chart_explanation(
        "Aperturas y cierres registrados",
        "Esta tabla resume cuándo empezó a abrir o cerrar cada frente o puerta, cuánto duró el movimiento, el porcentaje objetivo y los comentarios registrados en el Excel.",
        accent=BRAND_COLORS['hero']
    )
    _dataframe(operation_rows, hide_index=True)


def _get_available_cortina_vars(datos_cortinas):
    if datos_cortinas.empty:
        return []

    available = []
    for config in SIDE_CONFIGS.values():
        element_col = config['element_col']
        if element_col in datos_cortinas.columns:
            for value in datos_cortinas[element_col].dropna().unique():
                normalized_name = _normalize_cortina_name(value)
                if normalized_name:
                    available.append(normalized_name)
    available_set = set(available)
    ordered_known = [motor for motor in MOTOR_VARIABLES if motor in available_set]
    extras = sorted(available_set - set(MOTOR_VARIABLES))
    return ordered_known + extras


def _get_available_sensor_vars(df_variables):
    if df_variables.empty:
        return []

    sensor_candidates = list(dict.fromkeys([*SENSOR_VARIABLES, 'LUX']))
    return [
        var_name for var_name in sensor_candidates
        if var_name in df_variables.columns and df_variables[var_name].notna().any()
    ]


def _get_available_correlacion_vars(df_variables, datos_cortinas):
    sensor_vars = _get_available_sensor_vars(df_variables)
    if not sensor_vars:
        return []
    motor_vars = _get_available_cortina_vars(datos_cortinas)
    return list(dict.fromkeys(sensor_vars + motor_vars))


def _get_available_variable_dates(df_variables_all, bloque_variables):
    if bloque_variables is None:
        return []

    fechas_variables = df_variables_all.loc[
        df_variables_all['Bloque'].eq(bloque_variables),
        'Fecha_Filtro'
    ].dropna().unique().tolist()
    return sorted(fechas_variables)


def _get_all_variable_dates_for_blocks(df_variables_all, block_names=None):
    if (
        df_variables_all.empty or
        'Fecha_Filtro' not in df_variables_all.columns or
        'Bloque' not in df_variables_all.columns
    ):
        return []

    filtered_df = df_variables_all
    if block_names:
        filtered_df = filtered_df[filtered_df['Bloque'].isin(block_names)]

    fechas_variables = pd.Series(filtered_df['Fecha_Filtro'].dropna().unique()).tolist()
    return sorted(fechas_variables)


def _filter_variables_range(df_variables_all, bloque_variables, fecha_inicio, fecha_fin):
    if (
        df_variables_all.empty or
        'Fecha_Filtro' not in df_variables_all.columns or
        'Bloque' not in df_variables_all.columns or
        bloque_variables is None or
        fecha_inicio is None or
        fecha_fin is None
    ):
        return pd.DataFrame()

    return df_variables_all[
        (df_variables_all['Fecha_Filtro'] >= fecha_inicio) &
        (df_variables_all['Fecha_Filtro'] <= fecha_fin) &
        (df_variables_all['Bloque'] == bloque_variables)
    ].copy()


def _filter_variables_multi_block_range(df_variables_all, fecha_inicio, fecha_fin, bloques=None):
    if (
        df_variables_all.empty or
        'Fecha_Filtro' not in df_variables_all.columns or
        'Bloque' not in df_variables_all.columns or
        fecha_inicio is None or
        fecha_fin is None
    ):
        return pd.DataFrame()

    mask = (
        (df_variables_all['Fecha_Filtro'] >= fecha_inicio) &
        (df_variables_all['Fecha_Filtro'] <= fecha_fin)
    )

    if bloques:
        mask &= df_variables_all['Bloque'].isin(bloques)

    return df_variables_all[mask].copy()

def _render_correlacion_series_panel(available_vars, selected_block_code, df_variables_almacen):
    if not available_vars:
        st.info("No hay series disponibles para el rango seleccionado.")
        return []

    with st.expander("Configurar series visibles", expanded=True):
        st.markdown(
            """
            <div class="series-control-card">
                <p class="series-control-kicker">Selector de lectura</p>
                <h3 class="series-control-title">Elige qué señales quieres cruzar en la gráfica</h3>
                <p class="series-control-copy">
                    Mantén visibles las variables ambientales clave y activa las referencias operativas solo cuando ayuden
                    a explicar un cambio de temperatura, humedad, radiación o gramos de agua.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown('<p class="series-toolbar-label">Acciones rápidas</p>', unsafe_allow_html=True)
        action_col, clear_col, external_col, ideal_col = st.columns([0.22, 0.22, 0.34, 0.22], vertical_alignment="center")
        with action_col:
            if st.button("Seleccionar todas", key="correlacion_select_all", width="stretch"):
                _reset_correlacion_selector(available_vars)
        with clear_col:
            if st.button("Quitar todas", key="correlacion_clear_all", width="stretch"):
                for option in available_vars:
                    st.session_state[_selector_state_key(option)] = False
                st.session_state['variables_correlacion'] = []
        with external_col:
            st.checkbox(
                "Comparar con Estación externa",
                key="comparar_con_almacen",
                disabled=selected_block_code == 'ALMACEN' or df_variables_almacen.empty,
                help=FILTER_HELP_TEXTS['comparar_almacen']
            )
        with ideal_col:
            st.checkbox(
                "Aperturas ideales",
                key="mostrar_aperturas_ideales",
                help=FILTER_HELP_TEXTS['aperturas_ideales']
            )

        st.markdown('<div class="series-toolbar-spacer"></div>', unsafe_allow_html=True)
        st.markdown('<p class="analysis-note"><strong>Variables ambientales y operativas disponibles</strong></p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="series-chip-note">Activa solo las señales que realmente aporten lectura al cruce. Así la gráfica respira mejor y se vuelve más clara.</p>',
            unsafe_allow_html=True
        )
        option_columns = st.columns(min(4, max(1, len(available_vars))))
        for idx, option in enumerate(available_vars):
            state_key = _selector_state_key(option)
            if state_key not in st.session_state:
                st.session_state[state_key] = True
            with option_columns[idx % len(option_columns)]:
                st.checkbox(
                    VARIABLE_SELECTOR_LABELS.get(option, VARIABLE_LABELS.get(option, option)),
                    key=state_key,
                    help=VARIABLE_FILTER_HELP.get(option, FILTER_HELP_TEXTS['series_visibles'])
                )

    return _get_selected_correlacion_vars(available_vars)


def _analysis_block_state_key(block_code):
    safe_code = re.sub(r'[^a-z0-9]+', '_', str(block_code).lower()).strip('_')
    return f'bloques_analisis_{safe_code}'


def _reset_analysis_block_selector(block_codes):
    st.session_state['bloques_analisis'] = block_codes.copy()
    for block_code in block_codes:
        st.session_state[_analysis_block_state_key(block_code)] = True


def _get_selected_analysis_blocks(block_codes):
    selected_blocks = [block_code for block_code in block_codes if st.session_state.get(_analysis_block_state_key(block_code), True)]
    st.session_state['bloques_analisis'] = selected_blocks
    return selected_blocks


def _get_block_modification(block_name):
    block_code = _extract_block_code(block_name)
    return BLOCK_MODIFICATIONS.get(block_code) if block_code else None


def _get_block_ventilation_rows(block_name):
    block_code = _extract_block_code(block_name)
    if not block_code:
        return []
    return BLOCK_VENTILATION_DATA.get(block_code, [])


def _get_block_ventilation_row(block_name, expected_row_key):
    for row in _get_block_ventilation_rows(block_name):
        row_key = _build_normalized_text_key(row.get('label', ''))
        if row_key == expected_row_key:
            return row
    return None


def _get_motor_area_reference(block_name, motor_name):
    motor_key = _normalize_cortina_name(motor_name)
    reference_config = MOTOR_AREA_REFERENCE.get(motor_key)
    if not reference_config:
        return None

    row = _get_block_ventilation_row(block_name, reference_config['row_key'])
    if not row:
        return None

    real_value = row.get('real')
    ideal_value = row.get('ideal')
    if real_value is None or pd.isna(real_value):
        return None

    return {
        'real_max_area': float(real_value) / float(reference_config['divisor']),
        'ideal_max_area': (
            float(ideal_value) / float(reference_config['divisor'])
            if ideal_value is not None and not pd.isna(ideal_value)
            else None
        )
    }


def _get_culatas_area_reference(block_name):
    row = _get_block_ventilation_row(block_name, 'ventilacion culatas')
    if not row:
        return None

    real_value = row.get('real')
    if real_value is None or pd.isna(real_value):
        return None

    return float(real_value)


def _build_culatas_state_text(open_percent, block_name=None):
    percent_value = _normalize_percent_value(open_percent)
    if percent_value is None:
        return 'Sin información disponible'

    if percent_value <= 0:
        return 'Culatas cerradas'

    max_area = _get_culatas_area_reference(block_name)
    if max_area is None:
        return 'Culatas abiertas'

    open_area = max_area * percent_value / 100.0
    area_text = _format_area_value(open_area)
    percent_text = _format_summary_number(percent_value, 0)
    return f'Culatas abiertas - {area_text} m2 abiertos ({percent_text}%)'


def _convert_cortina_profile_to_area(df_state, real_max_area, ideal_max_area=None):
    if df_state.empty:
        return df_state

    df_area = df_state.copy()
    apertura_pct = pd.to_numeric(df_area['Apertura'], errors='coerce')
    df_area['Apertura_m2'] = apertura_pct * float(real_max_area) / 100.0
    if ideal_max_area is not None:
        df_area['Apertura_ideal_m2'] = apertura_pct * float(ideal_max_area) / 100.0
    else:
        df_area['Apertura_ideal_m2'] = pd.NA

    detail_values = []
    for detail in df_area['Detalle'].fillna(''):
        detail_text = str(detail).strip()
        if detail_text:
            detail_values.append(detail_text.replace(' | ', ' - '))
        else:
            detail_values.append('')

    df_area['DetalleGrafico'] = detail_values
    apertura_ideal_series = pd.to_numeric(df_area['Apertura_ideal_m2'], errors='coerce')
    brecha_ideal_series = pd.to_numeric(df_area['Apertura_m2'], errors='coerce') - apertura_ideal_series
    df_area['ResumenIdealTexto'] = [
        (
            f'Ideal: {_format_area_value(ideal_value)} m2 | Brecha: {_format_area_value(gap_value)} m2'
            if not pd.isna(ideal_value) and not pd.isna(gap_value) else
            'Ideal: Sin dato'
        )
        for ideal_value, gap_value in zip(apertura_ideal_series, brecha_ideal_series)
    ]
    return df_area


def _format_area_value(value):
    if value is None or pd.isna(value):
        return 'No aplica'

    numeric_value = round(float(value), 2)
    if abs(numeric_value - round(numeric_value)) < 1e-6:
        decimals = 0
    elif abs(numeric_value - round(numeric_value, 1)) < 1e-6:
        decimals = 1
    else:
        decimals = 2

    return _format_summary_number(numeric_value, decimals)


def _extract_block_code(block_name):
    if not block_name:
        return None
    match = re.search(r'(\d+)', str(block_name))
    return match.group(1) if match else None


def _extract_block_identifier(block_name):
    block_code = _extract_block_code(block_name)
    if block_code:
        return block_code

    normalized_key = _build_normalized_text_key(block_name)
    if 'almacen' in normalized_key:
        return 'ALMACEN'

    return None


def _get_finca_for_block(block_name):
    normalized_key = _build_normalized_text_key(block_name)
    if 'marley' in normalized_key or 'marly' in normalized_key:
        return 'Marly'

    block_identifier = _extract_block_identifier(block_name)
    if block_identifier and block_identifier in BLOCK_FARMS:
        return BLOCK_FARMS[block_identifier]

    return 'La Ponderosa'


def _get_block_options(df_variables_all, df_cortinas_all, selected_finca=None):
    variable_map = {}
    cortina_map = {}

    if not df_variables_all.empty and 'Bloque' in df_variables_all.columns:
        for block_name in sorted(df_variables_all['Bloque'].dropna().unique()):
            if selected_finca and _get_finca_for_block(block_name) != selected_finca:
                continue
            block_identifier = _extract_block_identifier(block_name)
            if block_identifier:
                variable_map[block_identifier] = block_name

    if not df_cortinas_all.empty and 'Bloque' in df_cortinas_all.columns:
        for block_name in sorted(df_cortinas_all['Bloque'].dropna().unique()):
            if selected_finca and _get_finca_for_block(block_name) != selected_finca:
                continue
            block_identifier = _extract_block_identifier(block_name)
            if block_identifier:
                cortina_map[block_identifier] = block_name

    block_codes = _sort_block_names(list(variable_map.keys()))
    return block_codes, variable_map, cortina_map


def _normalize_percent_value(value):
    if pd.isna(value):
        return None
    return max(0.0, min(100.0, float(value)))


def _normalize_cortina_name(value):
    if pd.isna(value):
        return None

    normalized_key = _build_normalized_text_key(value)
    normalized_key = re.sub(r'\s+', ' ', normalized_key).strip()
    cortina_name_map = {
        'frente 1': 'FRENTE 1',
        'frente 2': 'FRENTE 2',
        'puerta 1': 'PUERTA 1',
        'puerta 2': 'PUERTA 2'
    }
    return cortina_name_map.get(normalized_key, str(value).strip())


def _build_cortina_apertura_profile(df_cortinas, elemento, config):
    elemento_col = config['element_col']
    apertura_col = config['open_time_col']
    apertura_pct_col = config['open_pct_col']
    duracion_apertura_col = config['open_duration_col']
    cierre_col = config['close_time_col']
    cierre_pct_col = config['close_pct_col']
    duracion_cierre_col = config['close_duration_col']

    if elemento_col not in df_cortinas.columns:
        return pd.DataFrame()

    elemento_normalizado = _normalize_cortina_name(elemento)
    elementos_normalizados = df_cortinas[elemento_col].apply(_normalize_cortina_name)
    datos_elem = df_cortinas[elementos_normalizados == elemento_normalizado].copy()
    if datos_elem.empty or 'Fecha' not in datos_elem.columns:
        return pd.DataFrame()

    datos_elem = datos_elem.sort_values(['Fecha', apertura_col, cierre_col], na_position='last').reset_index(drop=True)
    fechas_elem = [fecha for fecha in datos_elem['Fecha'].dropna().drop_duplicates().tolist()]
    profile = []

    for day_index, fecha_dia in enumerate(fechas_elem):
        datos_dia = datos_elem[datos_elem['Fecha'] == fecha_dia].copy()
        if datos_dia.empty:
            continue

        if day_index > 0:
            profile.append({
                'Hora': datetime.combine(fecha_dia, datetime.min.time()),
                'Apertura': None,
                'Evento': 'Cambio de día',
                'Detalle': ''
            })

        inicio_dia = datetime.combine(fecha_dia, datetime.min.time())
        fin_dia = datetime.combine(fecha_dia, datetime.max.time().replace(microsecond=0))
        current_level = 0.0
        profile.append({
            'Hora': inicio_dia,
            'Apertura': current_level,
            'Evento': 'Inicio del día',
            'Detalle': 'Estado inicial: 0% abierto'
        })

        for _, evt in datos_dia.iterrows():
            apertura_pct = _normalize_percent_value(evt[apertura_pct_col])
            cierre_pct = _normalize_percent_value(evt[cierre_pct_col])
            target_open_level = apertura_pct if apertura_pct is not None else current_level
            target_close_level = 100.0 - cierre_pct if cierre_pct is not None else current_level

            if pd.notna(evt[apertura_col]):
                inicio_apertura = datetime.combine(fecha_dia, evt[apertura_col])
                duracion_ap = float(evt[duracion_apertura_col]) if pd.notna(evt[duracion_apertura_col]) else 0.0
                fin_apertura = inicio_apertura + timedelta(minutes=duracion_ap)
                profile.append({
                    'Hora': inicio_apertura,
                    'Apertura': current_level,
                    'Evento': 'Inicio Apertura',
                    'Detalle': f"Objetivo: {target_open_level:.0f}% abierto | Duración apertura: {duracion_ap:.0f} min"
                })
                profile.append({
                    'Hora': fin_apertura,
                    'Apertura': target_open_level,
                    'Evento': 'Fin Apertura',
                    'Detalle': f"Nivel alcanzado: {target_open_level:.0f}% abierto | Inicio: {inicio_apertura.strftime('%H:%M')} | Fin: {fin_apertura.strftime('%H:%M')}"
                })
                current_level = target_open_level

            if pd.notna(evt[cierre_col]):
                inicio_cierre = datetime.combine(fecha_dia, evt[cierre_col])
                duracion_ci = float(evt[duracion_cierre_col]) if pd.notna(evt[duracion_cierre_col]) else 0.0
                fin_cierre = inicio_cierre + timedelta(minutes=duracion_ci)
                profile.append({
                    'Hora': inicio_cierre,
                    'Apertura': current_level,
                    'Evento': 'Inicio Cierre',
                    'Detalle': f"Cierre: {cierre_pct:.0f}% | Duración cierre: {duracion_ci:.0f} min"
                    if cierre_pct is not None else f"Duración cierre: {duracion_ci:.0f} min"
                })
                profile.append({
                    'Hora': fin_cierre,
                    'Apertura': target_close_level,
                    'Evento': 'Fin Cierre',
                    'Detalle': f"Nivel final: {target_close_level:.0f}% abierto | Inicio: {inicio_cierre.strftime('%H:%M')} | Fin: {fin_cierre.strftime('%H:%M')}"
                })
                current_level = target_close_level

        profile.append({
            'Hora': fin_dia,
            'Apertura': current_level,
            'Evento': 'Fin del día',
            'Detalle': f"Estado final: {current_level:.0f}% abierto"
        })

    return pd.DataFrame(profile).sort_values('Hora').reset_index(drop=True)


def _get_culatas_daily_observation(datos_cortinas, block_label=None):
    if datos_cortinas.empty or 'Culatas %' not in datos_cortinas.columns:
        return None

    valores_culatas = datos_cortinas['Culatas %'].dropna()
    if valores_culatas.empty:
        return None

    ultimo_valor = _normalize_percent_value(valores_culatas.iloc[-1])
    if ultimo_valor is None:
        return None
    return _build_culatas_state_text(ultimo_valor, block_label)


def _get_culatas_observation_by_day(datos_cortinas, block_label=None):
    if (
        datos_cortinas.empty or
        'Fecha' not in datos_cortinas.columns or
        'Culatas %' not in datos_cortinas.columns
    ):
        return []

    observations = []
    datos_ordenados = datos_cortinas.sort_values('Fecha')

    for fecha, datos_dia in datos_ordenados.groupby('Fecha', sort=True):
        valores_culatas = datos_dia['Culatas %'].dropna()
        if valores_culatas.empty:
            state = 'Sin información disponible'
        else:
            ultimo_valor = _normalize_percent_value(valores_culatas.iloc[-1])
            if ultimo_valor is None:
                state = 'Sin información disponible'
            else:
                state = _build_culatas_state_text(ultimo_valor, block_label)

        observations.append({
            'fecha': fecha,
            'state': state
        })

    return observations


def _format_cortina_time(value):
    if pd.isna(value):
        return 'Sin dato'
    if hasattr(value, 'strftime'):
        return value.strftime('%H:%M')
    timestamp = pd.to_datetime(value, errors='coerce')
    if pd.isna(timestamp):
        return str(value)
    return timestamp.strftime('%H:%M')


def _format_cortina_duration(value):
    numeric_value = pd.to_numeric(pd.Series([value]), errors='coerce').iloc[0]
    if pd.isna(numeric_value):
        return 'Sin dato'
    return f"{float(numeric_value):.0f} min"


def _format_cortina_pct(value):
    pct_value = _normalize_percent_value(value)
    if pct_value is None:
        return 'Sin dato'
    return f"{pct_value:.0f}%"


def _build_cortina_operation_rows(datos_cortinas, selected_motors=None):
    if datos_cortinas.empty:
        return pd.DataFrame()

    selected_set = set(selected_motors or [])
    rows = []
    for _, record in datos_cortinas.sort_values('Fecha').iterrows():
        fecha = record.get('Fecha')
        fecha_label = _format_info_day_label(fecha)
        for side_label, config in SIDE_CONFIGS.items():
            motor_name = _normalize_cortina_name(record.get(config['element_col']))
            if not motor_name or (selected_set and motor_name not in selected_set):
                continue

            note_value = record.get(config['note_col'])
            note_text = '' if pd.isna(note_value) else str(note_value).strip()
            if note_text.lower() in {'nan', 'none'}:
                note_text = ''

            rows.append({
                'Fecha': fecha_label,
                'Cortina': VARIABLE_SELECTOR_LABELS.get(motor_name, motor_name),
                'Lado': side_label,
                'Inicio apertura': _format_cortina_time(record.get(config['open_time_col'])),
                'Duración apertura': _format_cortina_duration(record.get(config['open_duration_col'])),
                'Apertura objetivo': _format_cortina_pct(record.get(config['open_pct_col'])),
                'Inicio cierre': _format_cortina_time(record.get(config['close_time_col'])),
                'Duración cierre': _format_cortina_duration(record.get(config['close_duration_col'])),
                'Cierre registrado': _format_cortina_pct(record.get(config['close_pct_col'])),
                'Comentario': note_text or 'Sin comentario'
            })

    return pd.DataFrame(rows)


def _render_cortina_operation_summary(datos_cortinas, selected_motors):
    operation_rows = _build_cortina_operation_rows(datos_cortinas, selected_motors)
    if operation_rows.empty:
        st.info("No hay eventos operativos de apertura o cierre para las cortinas seleccionadas.")
        return

    st.markdown("### Detalle operativo de cortinas")
    _render_chart_explanation(
        "Aperturas y cierres registrados",
        "Esta tabla resume cuándo empezó a abrir o cerrar cada frente o puerta, cuánto duró el movimiento, el porcentaje objetivo y los comentarios registrados en el Excel.",
        accent=BRAND_COLORS['hero']
    )
    _dataframe(operation_rows, hide_index=True)


def _get_available_cortina_vars(datos_cortinas):
    if datos_cortinas.empty:
        return []

    available = []
    for config in SIDE_CONFIGS.values():
        element_col = config['element_col']
        if element_col in datos_cortinas.columns:
            for value in datos_cortinas[element_col].dropna().unique():
                normalized_name = _normalize_cortina_name(value)
                if normalized_name:
                    available.append(normalized_name)
    available_set = set(available)
    ordered_known = [motor for motor in MOTOR_VARIABLES if motor in available_set]
    extras = sorted(available_set - set(MOTOR_VARIABLES))
    return ordered_known + extras


def _get_available_sensor_vars(df_variables):
    if df_variables.empty:
        return []

    sensor_candidates = list(dict.fromkeys([*SENSOR_VARIABLES, 'LUX']))
    return [
        var_name for var_name in sensor_candidates
        if var_name in df_variables.columns and df_variables[var_name].notna().any()
    ]


def _get_available_correlacion_vars(df_variables, datos_cortinas):
    sensor_vars = _get_available_sensor_vars(df_variables)
    if not sensor_vars:
        return []
    motor_vars = _get_available_cortina_vars(datos_cortinas)
    return list(dict.fromkeys(sensor_vars + motor_vars))


def _get_available_variable_dates(df_variables_all, bloque_variables):
    if bloque_variables is None:
        return []

    fechas_variables = df_variables_all.loc[
        df_variables_all['Bloque'].eq(bloque_variables),
        'Fecha_Filtro'
    ].dropna().unique().tolist()
    return sorted(fechas_variables)


def _get_all_variable_dates_for_blocks(df_variables_all, block_names=None):
    if (
        df_variables_all.empty or
        'Fecha_Filtro' not in df_variables_all.columns or
        'Bloque' not in df_variables_all.columns
    ):
        return []

    filtered_df = df_variables_all
    if block_names:
        filtered_df = filtered_df[filtered_df['Bloque'].isin(block_names)]

    fechas_variables = pd.Series(filtered_df['Fecha_Filtro'].dropna().unique()).tolist()
    return sorted(fechas_variables)


def _filter_variables_range(df_variables_all, bloque_variables, fecha_inicio, fecha_fin):
    if (
        df_variables_all.empty or
        'Fecha_Filtro' not in df_variables_all.columns or
        'Bloque' not in df_variables_all.columns or
        bloque_variables is None or
        fecha_inicio is None or
        fecha_fin is None
    ):
        return pd.DataFrame()

    return df_variables_all[
        (df_variables_all['Fecha_Filtro'] >= fecha_inicio) &
        (df_variables_all['Fecha_Filtro'] <= fecha_fin) &
        (df_variables_all['Bloque'] == bloque_variables)
    ].copy()


def _filter_variables_multi_block_range(df_variables_all, fecha_inicio, fecha_fin, bloques=None):
    if (
        df_variables_all.empty or
        'Fecha_Filtro' not in df_variables_all.columns or
        'Bloque' not in df_variables_all.columns or
        fecha_inicio is None or
        fecha_fin is None
    ):
        return pd.DataFrame()

    mask = (
        (df_variables_all['Fecha_Filtro'] >= fecha_inicio) &
        (df_variables_all['Fecha_Filtro'] <= fecha_fin)
    )

    if bloques:
        mask &= df_variables_all['Bloque'].isin(bloques)

    return df_variables_all[mask].copy()


__all__ = [name for name in globals() if not name.startswith("__")]
