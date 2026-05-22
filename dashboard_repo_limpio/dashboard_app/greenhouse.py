from .shared import *

def _filter_cortinas_range(df_cortinas_all, bloque_seleccionado, fecha_inicio, fecha_fin):
    if (
        df_cortinas_all.empty or
        'Fecha' not in df_cortinas_all.columns or
        'Bloque' not in df_cortinas_all.columns or
        bloque_seleccionado is None or
        fecha_inicio is None or
        fecha_fin is None
    ):
        return pd.DataFrame()

    return df_cortinas_all[
        (df_cortinas_all['Bloque'] == bloque_seleccionado) &
        (df_cortinas_all['Fecha'] >= fecha_inicio) &
        (df_cortinas_all['Fecha'] <= fecha_fin)
    ].copy()


def _get_daily_annotations(datos_cortinas):
    if datos_cortinas.empty:
        return []

    annotation_pairs = [
        ('Frente A', 'Anotacion A'),
        ('Puerta B', 'Anotacion B')
    ]
    annotations = []

    for _, row in datos_cortinas.iterrows():
        for label_col, note_col in annotation_pairs:
            note_value = row.get(note_col)
            if pd.isna(note_value):
                continue

            note_text = str(note_value).strip()
            if not note_text or note_text.lower() in {'nan', 'none'}:
                continue

            label_value = row.get(label_col)
            label_text = str(label_value).strip() if pd.notna(label_value) else label_col
            entry = f"{label_text}: {note_text}"
            if entry not in annotations:
                annotations.append(entry)

    return annotations


def _get_annotations_by_day(datos_cortinas):
    if datos_cortinas.empty or 'Fecha' not in datos_cortinas.columns:
        return []

    annotation_pairs = [
        ('Frente A', 'Anotacion A'),
        ('Puerta B', 'Anotacion B')
    ]
    grouped_annotations = []
    datos_ordenados = datos_cortinas.sort_values('Fecha')

    for fecha, datos_dia in datos_ordenados.groupby('Fecha', sort=True):
        entries = []

        for _, row in datos_dia.iterrows():
            for label_col, note_col in annotation_pairs:
                note_value = row.get(note_col)
                if pd.isna(note_value):
                    continue

                note_text = str(note_value).strip()
                if not note_text or note_text.lower() in {'nan', 'none'}:
                    continue

                label_value = row.get(label_col)
                label_text = str(label_value).strip() if pd.notna(label_value) else label_col
                entry = f"{label_text}: {note_text}"
                if entry not in entries:
                    entries.append(entry)

        grouped_annotations.append({
            'fecha': fecha,
            'entries': entries
        })

    return grouped_annotations


def _format_info_day_label(fecha_value):
    timestamp = pd.to_datetime(fecha_value, errors='coerce')
    if pd.isna(timestamp):
        return str(fecha_value)

    weekday = WEEKDAY_ES.get(timestamp.weekday())
    if weekday:
        return f"{weekday} {timestamp.strftime('%d/%m/%Y')}"
    return timestamp.strftime('%d/%m/%Y')


def _get_culatas_state_style(culatas_state):
    culatas_state_lower = str(culatas_state).lower()
    if 'abiertas' in culatas_state_lower:
        return {
            'badge_bg': 'rgba(112, 200, 140, 0.18)',
            'badge_color': '#3C8C57',
            'tag': 'Estado abierto'
        }
    if 'cerradas' in culatas_state_lower:
        return {
            'badge_bg': 'rgba(84, 83, 134, 0.16)',
            'badge_color': BRAND_COLORS['hero'],
            'tag': 'Estado cerrado'
        }
    return {
        'badge_bg': 'rgba(124, 129, 138, 0.16)',
        'badge_color': '#6D727D',
        'tag': 'Sin dato'
    }


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


@st.cache_data(show_spinner="Cargando dashboard y preparando datos...")
def cargar_dashboard_completo(cache_version=DATA_CACHE_VERSION):
    return load_dashboard_data(cache_version)



def _format_analysis_block_table(df):
    if df.empty:
        return df

    formatted = df.copy()
    percent_columns = [
        column_name
        for column_name in formatted.columns
        if "%" in str(column_name)
    ]
    for column_name in percent_columns:
        formatted[column_name] = formatted[column_name].apply(
            lambda value: f"{float(value):.1%}" if pd.notna(value) else "—"
        )
    return formatted


def _format_single_block_detail_table(df):
    if df.empty:
        return pd.DataFrame(columns=["Campo", "Valor"])

    row = df.iloc[0]
    detail_rows = []
    for column_name, value in row.items():
        if pd.isna(value):
            continue
        numeric_value = _safe_float(value) if not isinstance(value, str) else None
        if numeric_value is not None:
            value_text = f"{numeric_value:,.2f}".rstrip("0").rstrip(".")
        else:
            value_text = str(value)
        detail_rows.append({
            "Campo": column_name,
            "Valor": value_text
        })
    return pd.DataFrame(detail_rows)


GREENHOUSE_COLORS = {
    "real": "#3DBB76",
    "gap": "#E7C87A",
    "theoretical": "#6FA8FF",
    "allowed": "#F2A04B",
    "frontal": "#545386",
    "lateral": "#6FBFD6",
    "culatas": "#D77A94",
    "muted": "#D8D2C4",
}


def _safe_float(value):
    if value is None or pd.isna(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_greenhouse_value(value, decimals=1, suffix=""):
    numeric_value = _safe_float(value)
    if numeric_value is None:
        return "Sin datos"
    if decimals == 0:
        formatted_value = f"{numeric_value:,.0f}"
    else:
        formatted_value = f"{numeric_value:,.{decimals}f}"
    return f"{formatted_value}{suffix}"


def _format_greenhouse_percent(value):
    numeric_value = _safe_float(value)
    return f"{numeric_value:.1%}" if numeric_value is not None else "Sin datos"


def _clean_greenhouse_text(value, fallback=""):
    if value is None or pd.isna(value):
        return fallback
    text = str(value).strip()
    return text if text else fallback


def _render_greenhouse_styles():
    st.markdown(
        """
        <style>
        .greenhouse-hero {
            position: relative;
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 1rem;
            align-items: center;
            margin: 0.1rem 0 1.15rem 0;
            padding: 1.18rem 1.25rem;
            border-radius: 8px;
            border: 1px solid rgba(84, 83, 134, 0.18);
            background:
                linear-gradient(120deg, rgba(84,83,134,0.98) 0%, rgba(62,68,98,0.96) 58%, rgba(61,187,118,0.88) 100%);
            box-shadow: 0 18px 42px rgba(38, 43, 59, 0.16);
            overflow: hidden;
        }
        .greenhouse-hero::after {
            content: '';
            position: absolute;
            inset: auto -42px -68px auto;
            width: 210px;
            height: 210px;
            border-radius: 50%;
            border: 34px solid rgba(255,255,255,0.10);
            pointer-events: none;
        }
        .greenhouse-kicker {
            margin: 0 0 0.35rem 0;
            color: rgba(255,255,255,0.72);
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }
        .greenhouse-hero .greenhouse-title {
            margin: 0;
            color: #ffffff !important;
            -webkit-text-fill-color: #ffffff !important;
            font-size: 1.72rem;
            line-height: 1.1;
            font-weight: 900;
            letter-spacing: 0;
            text-shadow: 0 2px 12px rgba(0,0,0,0.28);
        }
        .greenhouse-subtitle {
            max-width: 48rem;
            margin: 0.58rem 0 0 0;
            color: rgba(255,255,255,0.82);
            font-size: 0.96rem;
            line-height: 1.55;
        }
        .greenhouse-hero-badge {
            position: relative;
            z-index: 1;
            min-width: 138px;
            padding: 0.86rem 0.95rem;
            border-radius: 8px;
            border: 1px solid rgba(255,255,255,0.22);
            background: rgba(255,255,255,0.13);
            text-align: center;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.18);
        }
        .greenhouse-hero-badge-label {
            display: block;
            color: rgba(255,255,255,0.72);
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.10em;
            text-transform: uppercase;
        }
        .greenhouse-hero-badge-value {
            display: block;
            margin-top: 0.24rem;
            color: #ffffff;
            font-size: 1.38rem;
            font-weight: 900;
            line-height: 1;
        }
        .greenhouse-section-title {
            margin: 1.05rem 0 0.55rem 0;
            color: var(--elite-graphite);
            font-size: 1.02rem;
            font-weight: 900;
            letter-spacing: 0;
        }
        .greenhouse-flow-grid {
            display: grid;
            grid-template-columns: repeat(5, minmax(0, 1fr));
            gap: 0.72rem;
            margin: 0.62rem 0 1.05rem 0;
        }
        .greenhouse-flow-card {
            position: relative;
            min-height: 138px;
            padding: 0.92rem 0.86rem 0.84rem 0.9rem;
            border-radius: 8px;
            border: 1px solid rgba(84,83,134,0.12);
            background:
                radial-gradient(circle at 92% 10%, rgba(255,255,255,0.95), transparent 32%),
                linear-gradient(180deg, rgba(255,255,255,0.96), rgba(247,244,238,0.88));
            box-shadow: 0 12px 26px rgba(56,58,53,0.075);
            overflow: hidden;
        }
        .greenhouse-flow-card::before {
            content: '';
            position: absolute;
            inset: 0 0 auto 0;
            height: 5px;
            background: var(--greenhouse-accent);
        }
        .greenhouse-flow-step {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 1.86rem;
            height: 1.86rem;
            border-radius: 8px;
            background: color-mix(in srgb, var(--greenhouse-accent) 18%, #ffffff 82%);
            color: var(--elite-graphite);
            font-size: 0.74rem;
            font-weight: 900;
            letter-spacing: 0.04em;
        }
        .greenhouse-flow-title {
            display: block;
            margin-top: 0.58rem;
            color: var(--elite-graphite);
            font-size: 0.86rem;
            font-weight: 900;
            line-height: 1.18;
            text-transform: uppercase;
            letter-spacing: 0.035em;
        }
        .greenhouse-flow-copy {
            display: block;
            margin-top: 0.42rem;
            color: rgba(56,58,53,0.72);
            font-size: 0.79rem;
            line-height: 1.42;
        }
        .greenhouse-divider-note {
            margin: 0.2rem 0 0.9rem 0;
            padding: 0.78rem 0.92rem;
            border-radius: 8px;
            border: 1px dashed rgba(84,83,134,0.22);
            background: rgba(255,255,255,0.64);
            color: rgba(56,58,53,0.74);
            font-size: 0.86rem;
            line-height: 1.48;
        }
        .greenhouse-metric-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.72rem;
            margin: 0.4rem 0 0.85rem 0;
        }
        .greenhouse-metric-card {
            position: relative;
            min-height: 112px;
            padding: 0.92rem 0.92rem 0.82rem 0.92rem;
            border-radius: 8px;
            border: 1px solid rgba(84, 83, 134, 0.12);
            background: linear-gradient(180deg, #ffffff 0%, rgba(255,255,255,0.88) 100%);
            box-shadow: 0 12px 28px rgba(56,58,53,0.08);
            overflow: hidden;
        }
        .greenhouse-metric-card::before {
            content: '';
            position: absolute;
            inset: 0 0 auto 0;
            height: 5px;
            background: var(--greenhouse-accent);
        }
        .greenhouse-metric-card-label {
            display: block;
            color: rgba(56,58,53,0.66);
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 0.06em;
            text-transform: uppercase;
        }
        .greenhouse-metric-card-value {
            display: block;
            margin-top: 0.48rem;
            color: var(--elite-graphite);
            font-size: 1.42rem;
            font-weight: 900;
            line-height: 1.05;
            overflow-wrap: anywhere;
        }
        .greenhouse-metric-card-note {
            display: block;
            margin-top: 0.42rem;
            color: rgba(56,58,53,0.62);
            font-size: 0.78rem;
            line-height: 1.35;
        }
        .greenhouse-insight-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.7rem;
            margin: 0.4rem 0 1rem 0;
        }
        .greenhouse-insight-card {
            padding: 0.9rem 0.95rem;
            border-radius: 8px;
            border: 1px solid rgba(84,83,134,0.12);
            background: linear-gradient(180deg, rgba(255,255,255,0.94), rgba(247,244,238,0.82));
            box-shadow: 0 10px 24px rgba(56,58,53,0.07);
            color: var(--elite-ink);
            font-size: 0.9rem;
            line-height: 1.48;
        }
        .greenhouse-insight-card strong {
            color: var(--elite-hero);
        }
        .greenhouse-reading-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.85rem;
            margin: 0.45rem 0 1rem 0;
        }
        .greenhouse-reading-card {
            position: relative;
            min-height: 118px;
            padding: 1rem 1rem 0.95rem 1.05rem;
            border-radius: 8px;
            border: 1px solid rgba(84,83,134,0.12);
            background: linear-gradient(180deg, rgba(255,255,255,0.96), rgba(247,244,238,0.86));
            box-shadow: 0 12px 28px rgba(56,58,53,0.08);
            overflow: hidden;
        }
        .greenhouse-reading-card::before {
            content: '';
            position: absolute;
            inset: 0 auto 0 0;
            width: 5px;
            background: linear-gradient(180deg, var(--elite-hero), rgba(61,187,118,0.78));
        }
        .greenhouse-reading-card-title {
            display: block;
            color: var(--elite-hero);
            font-size: 0.82rem;
            font-weight: 900;
            letter-spacing: 0.04em;
            text-transform: uppercase;
        }
        .greenhouse-reading-card-body {
            display: block;
            margin-top: 0.48rem;
            color: var(--elite-ink);
            font-size: 0.92rem;
            line-height: 1.48;
        }
        .greenhouse-dictionary-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.82rem;
            margin: 0.65rem 0 1rem 0;
        }
        .greenhouse-dictionary-card {
            padding: 0.95rem 1rem;
            border-radius: 8px;
            border: 1px solid rgba(84,83,134,0.12);
            background: rgba(255,255,255,0.94);
            box-shadow: 0 10px 22px rgba(56,58,53,0.07);
        }
        .greenhouse-dictionary-card-top {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 0.75rem;
            margin-bottom: 0.52rem;
        }
        .greenhouse-dictionary-term {
            color: var(--elite-graphite);
            font-size: 0.96rem;
            font-weight: 900;
            line-height: 1.22;
        }
        .greenhouse-dictionary-unit {
            flex: 0 0 auto;
            padding: 0.2rem 0.46rem;
            border-radius: 8px;
            background: rgba(84,83,134,0.10);
            color: var(--elite-hero);
            font-size: 0.74rem;
            font-weight: 900;
            white-space: nowrap;
        }
        .greenhouse-dictionary-text {
            margin: 0.42rem 0 0 0;
            color: var(--elite-ink);
            font-size: 0.86rem;
            line-height: 1.45;
        }
        .greenhouse-dictionary-source {
            display: inline-flex;
            margin-top: 0.62rem;
            padding: 0.22rem 0.52rem;
            border-radius: 8px;
            background: rgba(61,187,118,0.10);
            color: #2f7652;
            font-size: 0.74rem;
            font-weight: 800;
        }
        @media (max-width: 900px) {
            .greenhouse-hero {
                grid-template-columns: 1fr;
            }
            .greenhouse-hero-badge {
                max-width: 220px;
            }
            .greenhouse-flow-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
            .greenhouse-metric-grid,
            .greenhouse-insight-grid,
            .greenhouse-reading-grid,
            .greenhouse-dictionary-grid {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }
        @media (max-width: 640px) {
            .greenhouse-flow-grid,
            .greenhouse-metric-grid,
            .greenhouse-insight-grid,
            .greenhouse-reading-grid,
            .greenhouse-dictionary-grid {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True
    )


def _render_greenhouse_hero(selected_block_label, selected_summary_df):
    efficiency_text = "Sin datos"
    if not selected_summary_df.empty:
        efficiency_text = _format_greenhouse_percent(selected_summary_df.iloc[0].get("% Real / Máx. Perm."))

    st.markdown(
        f"""
        <div class="greenhouse-hero">
            <div>
                <p class="greenhouse-kicker">Contexto técnico de ventilación</p>
                <h2 class="greenhouse-title">{html.escape(selected_block_label)}</h2>
                <p class="greenhouse-subtitle">
                    Lectura ejecutiva de geometría, capacidad instalada, apertura real y brechas operativas para conectar el comportamiento ambiental con la estructura del invernadero.
                </p>
            </div>
            <div class="greenhouse-hero-badge">
                <span class="greenhouse-hero-badge-label">Uso del máximo</span>
                <span class="greenhouse-hero-badge-value">{html.escape(efficiency_text)}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def _render_greenhouse_metric_grid(title, metrics):
    card_html = []
    for metric in metrics:
        card_html.append(
            (
                f'<div class="greenhouse-metric-card" style="--greenhouse-accent: {metric["accent"]};">'
                f'<span class="greenhouse-metric-card-label">{html.escape(metric["label"])}</span>'
                f'<span class="greenhouse-metric-card-value">{html.escape(metric["value"])}</span>'
                f'<span class="greenhouse-metric-card-note">{html.escape(metric["note"])}</span>'
                '</div>'
            )
        )

    st.markdown(
        f"""
        <div class="greenhouse-section-title">{html.escape(title)}</div>
        <div class="greenhouse-metric-grid">{''.join(card_html)}</div>
        """,
        unsafe_allow_html=True
    )


def _render_greenhouse_flow_cards(title, cards):
    if not cards:
        return

    card_html = []
    for idx, card in enumerate(cards, start=1):
        accent = card.get("accent", BRAND_COLORS["hero"])
        card_html.append(
            (
                f'<div class="greenhouse-flow-card" style="--greenhouse-accent: {accent};">'
                f'<span class="greenhouse-flow-step">{idx:02d}</span>'
                f'<span class="greenhouse-flow-title">{html.escape(card.get("title", ""))}</span>'
                f'<span class="greenhouse-flow-copy">{html.escape(card.get("body", ""))}</span>'
                '</div>'
            )
        )

    st.markdown(
        f"""
        <div class="greenhouse-section-title">{html.escape(title)}</div>
        <div class="greenhouse-flow-grid">{''.join(card_html)}</div>
        """,
        unsafe_allow_html=True
    )


def _render_greenhouse_insight_cards(insights):
    if not insights:
        return

    rows = [
        f'<div class="greenhouse-insight-card"><strong>{idx}.</strong> {html.escape(insight)}</div>'
        for idx, insight in enumerate(insights, start=1)
    ]
    st.markdown(
        f"""
        <div class="greenhouse-section-title">Lectura rápida</div>
        <div class="greenhouse-insight-grid">{''.join(rows)}</div>
        """,
        unsafe_allow_html=True
    )


def _render_greenhouse_reading_cards(title, reading_df, title_col="Indicador", body_col="Interpretacion"):
    if reading_df.empty:
        return

    rows = []
    for _, reading_row in reading_df.iterrows():
        row_title = _clean_greenhouse_text(reading_row.get(title_col, ""))
        row_body = _clean_greenhouse_text(reading_row.get(body_col, ""))
        if not row_title and not row_body:
            continue
        rows.append(
            (
                '<div class="greenhouse-reading-card">'
                f'<span class="greenhouse-reading-card-title">{html.escape(row_title)}</span>'
                f'<span class="greenhouse-reading-card-body">{html.escape(row_body)}</span>'
                '</div>'
            )
        )

    if not rows:
        return

    st.markdown(
        f"""
        <div class="greenhouse-section-title">{html.escape(title)}</div>
        <div class="greenhouse-reading-grid">{''.join(rows)}</div>
        """,
        unsafe_allow_html=True
    )


def _render_greenhouse_dictionary_cards(dictionary_df):
    if dictionary_df.empty:
        st.info("No hay diccionario de variables disponible en el archivo.")
        return

    rows = []
    for _, dictionary_row in dictionary_df.iterrows():
        variable_name = _clean_greenhouse_text(dictionary_row.get("Variable / columna", ""))
        meaning = _clean_greenhouse_text(dictionary_row.get("Qué significa", ""))
        unit = _clean_greenhouse_text(dictionary_row.get("Unidad", ""))
        interpretation = _clean_greenhouse_text(dictionary_row.get("Cómo se interpreta", ""))
        source = _clean_greenhouse_text(dictionary_row.get("Dónde aparece", ""))
        if not variable_name:
            continue
        unit_html = html.escape(unit or "Referencia")
        rows.append(
            (
                '<div class="greenhouse-dictionary-card">'
                '<div class="greenhouse-dictionary-card-top">'
                f'<span class="greenhouse-dictionary-term">{html.escape(variable_name)}</span>'
                f'<span class="greenhouse-dictionary-unit">{unit_html}</span>'
                '</div>'
                f'<p class="greenhouse-dictionary-text">{html.escape(meaning)}</p>'
                f'<p class="greenhouse-dictionary-text"><strong>Lectura:</strong> {html.escape(interpretation)}</p>'
                f'<span class="greenhouse-dictionary-source">{html.escape(source)}</span>'
                '</div>'
            )
        )

    if rows:
        st.markdown(
            f'<div class="greenhouse-dictionary-grid">{"".join(rows)}</div>',
            unsafe_allow_html=True
        )


def _greenhouse_chart_config(file_stem):
    return {
        "displayModeBar": True,
        "displaylogo": False,
        "responsive": True,
        "toImageButtonOptions": {
            "format": "png",
            "filename": file_stem,
            "height": 900,
            "width": 1400,
            "scale": 2,
        },
    }


def _render_greenhouse_chart_panel(fig, title, key, selected_block_label, large_height=680):
    if fig is None:
        return

    file_stem = _build_report_slug("ficha-tecnica", selected_block_label, key)
    chart_config = _greenhouse_chart_config(file_stem)
    _plotly_chart(fig, config=chart_config)


def _build_greenhouse_report_excel_bytes(analysis_data, diagnostic_df=None):
    output = io.BytesIO()
    sheet_definitions = [
        ("Datos generales", analysis_data.get("general", pd.DataFrame())),
        ("Apertura calculada", analysis_data.get("areas", pd.DataFrame())),
        ("Indicadores resumen", analysis_data.get("summary", pd.DataFrame())),
        ("Lectura técnica", analysis_data.get("interpretations", pd.DataFrame())),
        ("Guía rápida", analysis_data.get("guide", pd.DataFrame())),
        ("Gráficas totales", analysis_data.get("chart_totals", pd.DataFrame())),
        ("Gráficas porcentuales", analysis_data.get("chart_ratios", pd.DataFrame())),
        ("Diccionario", analysis_data.get("dictionary", pd.DataFrame())),
    ]
    if isinstance(diagnostic_df, pd.DataFrame) and not diagnostic_df.empty:
        sheet_definitions.append(("Cruce ambiental", diagnostic_df))

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        sheets_written = []
        for sheet_title, frame in sheet_definitions:
            if not isinstance(frame, pd.DataFrame) or frame.empty:
                continue
            sheet_name = _sanitize_excel_sheet_name(sheet_title, sheets_written)
            frame.to_excel(writer, index=False, sheet_name=sheet_name)
            sheets_written.append(sheet_name)

        if not sheets_written:
            fallback_name = _sanitize_excel_sheet_name("Sin datos", sheets_written)
            pd.DataFrame({"Mensaje": ["No hay datos disponibles para exportar."]}).to_excel(
                writer,
                index=False,
                sheet_name=fallback_name
            )

        workbook = writer.book
        try:
            from openpyxl.styles import Alignment, Font, PatternFill

            header_fill = PatternFill("solid", fgColor="545386")
            header_font = Font(color="FFFFFF", bold=True)
            header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        except Exception:
            header_fill = header_font = header_alignment = None

        for worksheet in workbook.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            if header_fill and header_font and header_alignment:
                for cell in worksheet[1]:
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = header_alignment

            for column_cells in worksheet.columns:
                column_letter = column_cells[0].column_letter
                max_length = 0
                for cell in column_cells:
                    value = cell.value
                    if value is None:
                        continue
                    max_length = max(max_length, len(str(value)))
                worksheet.column_dimensions[column_letter].width = min(max(max_length + 2, 12), 42)

    output.seek(0)
    return output.getvalue()


def _render_greenhouse_report_download(analysis_data, selected_block_label, diagnostic_df=None, key_suffix="base"):
    try:
        report_bytes = _build_greenhouse_report_excel_bytes(analysis_data, diagnostic_df=diagnostic_df)
    except Exception as error:
        st.info(f"No fue posible preparar el reporte descargable. Detalle: {error}")
        return

    file_name = f"{_build_report_slug('ficha-tecnica-invernaderos', selected_block_label, key_suffix)}.xlsx"
    st.download_button(
        "Descargar reporte técnico",
        data=report_bytes,
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"download_greenhouse_report_{key_suffix}",
        help="Descarga un Excel con las tablas estructurales, lectura técnica, diccionario y cruce ambiental si está disponible."
    )


def _get_greenhouse_diagnostic_dates(df_variables_all, variable_blocks, window_days=7):
    if (
        df_variables_all.empty or
        "Bloque" not in df_variables_all.columns or
        "Fecha_Filtro" not in df_variables_all.columns or
        not variable_blocks
    ):
        return None, None

    date_series = pd.to_datetime(
        df_variables_all.loc[df_variables_all["Bloque"].isin(variable_blocks), "Fecha_Filtro"],
        errors="coerce"
    ).dropna()
    if date_series.empty:
        return None, None

    end_date = date_series.max().date()
    start_date = end_date - timedelta(days=max(1, int(window_days)) - 1)
    return start_date, end_date


def _classify_greenhouse_diagnostic(row):
    usage = _safe_float(row.get("Uso máximo permitido (%)"))
    temperature = _safe_float(row.get("Temperatura"))
    gap = _safe_float(row.get("Brecha operativa (m²)"))

    if usage is None:
        return "Sin lectura suficiente para priorizar."
    if usage < 85 and temperature is not None and temperature >= 27:
        return "Prioridad alta: menor uso de capacidad con temperatura elevada."
    if usage < 85:
        return "Revisar apertura real y restricciones de cortinas."
    if gap is not None and gap >= 200:
        return "Buena eficiencia relativa, pero con brecha absoluta importante."
    if usage >= 90:
        return "Operación alineada con la capacidad máxima permitida."
    return "Condición intermedia: mantener seguimiento operativo."


def _build_greenhouse_environment_diagnostic(summary_df, df_variables_all, window_days=7):
    empty_meta = {
        "start_date": None,
        "end_date": None,
        "records": 0,
        "mapped_blocks": 0,
    }
    if summary_df.empty or df_variables_all.empty:
        return pd.DataFrame(), empty_meta
    if "Bloque" not in summary_df.columns or "Bloque" not in df_variables_all.columns:
        return pd.DataFrame(), empty_meta

    _, variable_map, _ = _get_block_options(df_variables_all, pd.DataFrame(), selected_finca="La Ponderosa")
    block_lookup = {}
    for block_name in summary_df["Bloque"].dropna().astype(str).tolist():
        block_identifier = _extract_block_identifier(block_name)
        variable_block = variable_map.get(block_identifier)
        if variable_block:
            block_lookup[block_name] = variable_block

    if not block_lookup:
        return pd.DataFrame(), empty_meta

    variable_blocks = list(block_lookup.values())
    start_date, end_date = _get_greenhouse_diagnostic_dates(df_variables_all, variable_blocks, window_days=window_days)
    if start_date is None or end_date is None:
        return pd.DataFrame(), {**empty_meta, "mapped_blocks": len(block_lookup)}

    filtered_df = _filter_variables_multi_block_range(
        df_variables_all,
        start_date,
        end_date,
        bloques=variable_blocks
    )
    sensor_columns = [
        column_name
        for column_name in SENSOR_VARIABLES
        if column_name in filtered_df.columns and filtered_df[column_name].notna().any()
    ]
    if filtered_df.empty or not sensor_columns:
        return pd.DataFrame(), {
            **empty_meta,
            "start_date": start_date,
            "end_date": end_date,
            "mapped_blocks": len(block_lookup),
        }

    aggregate_df = filtered_df.groupby("Bloque", as_index=False)[sensor_columns].mean()
    record_counts = filtered_df.groupby("Bloque").size().reset_index(name="Registros")
    aggregate_df = aggregate_df.merge(record_counts, on="Bloque", how="left")
    reverse_lookup = {variable_block: block_name for block_name, variable_block in block_lookup.items()}
    aggregate_df["Bloque"] = aggregate_df["Bloque"].map(reverse_lookup)
    aggregate_df = aggregate_df.dropna(subset=["Bloque"]).reset_index(drop=True)
    if aggregate_df.empty:
        return pd.DataFrame(), {
            **empty_meta,
            "start_date": start_date,
            "end_date": end_date,
            "mapped_blocks": len(block_lookup),
            "records": int(len(filtered_df)),
        }

    summary_columns = [
        "Bloque",
        "% Real / Teórica",
        "% Real / Máx. Perm.",
        "Brecha Máx-Real (m²)",
        "% Pérdida Operativa",
    ]
    available_summary_columns = [column_name for column_name in summary_columns if column_name in summary_df.columns]
    merged_df = aggregate_df.merge(summary_df[available_summary_columns], on="Bloque", how="left")
    rename_map = {
        "% Real / Teórica": "Uso potencial teórico (%)",
        "% Real / Máx. Perm.": "Uso máximo permitido (%)",
        "Brecha Máx-Real (m²)": "Brecha operativa (m²)",
        "% Pérdida Operativa": "Pérdida operativa (%)",
    }
    merged_df = merged_df.rename(columns=rename_map)
    for column_name in [
        "Uso potencial teórico (%)",
        "Uso máximo permitido (%)",
        "Pérdida operativa (%)",
    ]:
        if column_name in merged_df.columns:
            merged_df[column_name] = pd.to_numeric(merged_df[column_name], errors="coerce") * 100
    if "Brecha operativa (m²)" in merged_df.columns:
        merged_df["Brecha operativa (m²)"] = pd.to_numeric(merged_df["Brecha operativa (m²)"], errors="coerce")

    for column_name in sensor_columns:
        merged_df[column_name] = pd.to_numeric(merged_df[column_name], errors="coerce").round(2)
    merged_df["Lectura operativa"] = merged_df.apply(_classify_greenhouse_diagnostic, axis=1)

    ordered_columns = [
        "Bloque",
        "Registros",
        *sensor_columns,
        "Uso potencial teórico (%)",
        "Uso máximo permitido (%)",
        "Brecha operativa (m²)",
        "Pérdida operativa (%)",
        "Lectura operativa",
    ]
    ordered_columns = [column_name for column_name in ordered_columns if column_name in merged_df.columns]
    merged_df = merged_df[ordered_columns].sort_values("Bloque").reset_index(drop=True)

    return merged_df, {
        "start_date": start_date,
        "end_date": end_date,
        "records": int(len(filtered_df)),
        "mapped_blocks": len(block_lookup),
    }


def _build_greenhouse_environment_scatter(diagnostic_df, metric_column, selected_block_label):
    if diagnostic_df.empty or metric_column not in diagnostic_df.columns:
        return None
    required_columns = ["Bloque", "Uso máximo permitido (%)", "Brecha operativa (m²)"]
    if any(column_name not in diagnostic_df.columns for column_name in required_columns):
        return None

    working_df = diagnostic_df.copy()
    working_df["Uso máximo permitido (%)"] = pd.to_numeric(working_df["Uso máximo permitido (%)"], errors="coerce")
    working_df[metric_column] = pd.to_numeric(working_df[metric_column], errors="coerce")
    working_df["Brecha operativa (m²)"] = pd.to_numeric(working_df["Brecha operativa (m²)"], errors="coerce")
    working_df = working_df.dropna(subset=["Uso máximo permitido (%)", metric_column, "Brecha operativa (m²)"])
    if working_df.empty:
        return None

    gap_min = float(working_df["Brecha operativa (m²)"].min())
    gap_max = float(working_df["Brecha operativa (m²)"].max())
    gap_range = gap_max - gap_min if gap_max != gap_min else 1.0
    marker_sizes = [
        18 + ((float(value) - gap_min) / gap_range) * 30
        for value in working_df["Brecha operativa (m²)"]
    ]
    marker_symbols = [
        "diamond" if str(block_name) == str(selected_block_label) else "circle"
        for block_name in working_df["Bloque"]
    ]

    fig = go.Figure(go.Scatter(
        x=working_df["Uso máximo permitido (%)"],
        y=working_df[metric_column],
        text=working_df["Bloque"],
        customdata=working_df[["Brecha operativa (m²)", "Registros", "Lectura operativa"]],
        mode="markers+text",
        textposition="top center",
        marker=dict(
            size=marker_sizes,
            symbol=marker_symbols,
            color=working_df["Brecha operativa (m²)"],
            colorscale=[
                [0.0, GREENHOUSE_COLORS["real"]],
                [0.55, GREENHOUSE_COLORS["gap"]],
                [1.0, BRAND_COLORS["rose"]],
            ],
            colorbar=dict(title="Brecha m²"),
            line=dict(color="rgba(255,255,255,0.95)", width=2),
            opacity=0.92,
        ),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Uso máximo permitido: %{x:.1f}%<br>"
            f"{VARIABLE_SELECTOR_LABELS.get(metric_column, metric_column)}: "
            f"%{{y:.2f}} {VARIABLE_UNITS.get(metric_column, '')}<br>"
            "Brecha operativa: %{customdata[0]:,.1f} m²<br>"
            "Registros del periodo: %{customdata[1]:,.0f}<br>"
            "%{customdata[2]}<extra></extra>"
        ),
    ))
    fig.update_layout(
        template="plotly_white",
        title=f"Cruce ambiental vs capacidad instalada · {VARIABLE_SELECTOR_LABELS.get(metric_column, metric_column)}",
        xaxis_title="Uso del máximo permitido (%)",
        yaxis_title=VARIABLE_SELECTOR_LABELS.get(metric_column, metric_column),
        height=520,
        margin=dict(l=20, r=20, t=80, b=36),
    )
    fig.update_xaxes(range=[max(0, float(working_df["Uso máximo permitido (%)"].min()) - 5), 105])
    return fig


def _render_greenhouse_environment_tab(summary_df, analysis_data, selected_block_label):
    _render_chart_explanation(
        "Cruce ambiental",
        "Esta lectura conecta la ficha estructural de ventilación con los sensores del periodo más reciente. Sirve para priorizar bloques donde una brecha de apertura podría coincidir con temperatura, humedad, PAR o gramos de agua."
    )

    with _loading_context(True, "Cargando contexto ambiental reciente..."):
        df_variables_all, _ = cargar_dashboard_completo()

    diagnostic_df, diagnostic_meta = _build_greenhouse_environment_diagnostic(summary_df, df_variables_all)
    if diagnostic_df.empty:
        st.info("No se encontró información ambiental suficiente para cruzar con la ficha técnica.")
        return

    period_text = "Periodo no disponible"
    if diagnostic_meta.get("start_date") and diagnostic_meta.get("end_date"):
        period_text = (
            f"{diagnostic_meta['start_date'].strftime('%d/%m/%Y')} - "
            f"{diagnostic_meta['end_date'].strftime('%d/%m/%Y')}"
        )
    st.caption(
        f"Periodo analizado: {period_text}. "
        f"Registros usados: {diagnostic_meta.get('records', 0):,}. "
        f"Bloques conectados: {diagnostic_meta.get('mapped_blocks', 0)}."
    )

    available_metrics = [
        variable_name
        for variable_name in SENSOR_VARIABLES
        if variable_name in diagnostic_df.columns and diagnostic_df[variable_name].notna().any()
    ]
    if not available_metrics:
        st.info("Hay bloques conectados, pero no se detectaron variables ambientales numéricas para graficar.")
        return

    metric_choice = st.selectbox(
        "Variable ambiental para cruzar con capacidad:",
        options=available_metrics,
        format_func=lambda value: VARIABLE_SELECTOR_LABELS.get(value, value),
        key="greenhouse_environment_metric"
    )

    selected_env_df = diagnostic_df[diagnostic_df["Bloque"].astype(str) == str(selected_block_label)].reset_index(drop=True)
    if not selected_env_df.empty:
        selected_env_row = selected_env_df.iloc[0]
        _render_greenhouse_metric_grid(
            "Lectura ambiental del bloque seleccionado",
            [
                {
                    "label": VARIABLE_SELECTOR_LABELS.get(metric_choice, metric_choice),
                    "value": _format_greenhouse_value(
                        selected_env_row.get(metric_choice),
                        2,
                        f" {VARIABLE_UNITS.get(metric_choice, '')}".rstrip()
                    ),
                    "note": "Promedio del periodo reciente",
                    "accent": VARIABLE_COLORS.get(metric_choice, BRAND_COLORS["hero"]),
                },
                {
                    "label": "Uso máximo",
                    "value": _format_greenhouse_value(selected_env_row.get("Uso máximo permitido (%)"), 1, "%"),
                    "note": "Ventilación real frente al máximo permitido",
                    "accent": GREENHOUSE_COLORS["real"],
                },
                {
                    "label": "Brecha operativa",
                    "value": _format_greenhouse_value(selected_env_row.get("Brecha operativa (m²)"), 1, " m²"),
                    "note": "Diferencia entre máximo permitido y real",
                    "accent": GREENHOUSE_COLORS["gap"],
                },
                {
                    "label": "Registros",
                    "value": _format_greenhouse_value(selected_env_row.get("Registros"), 0),
                    "note": "Datos ambientales usados",
                    "accent": BRAND_COLORS["graphite"],
                },
            ]
        )
        st.info(str(selected_env_row.get("Lectura operativa", "Lectura no disponible.")))

    environment_chart = _build_greenhouse_environment_scatter(
        diagnostic_df,
        metric_choice,
        selected_block_label
    )
    _render_greenhouse_chart_panel(
        environment_chart,
        "Cruce ambiental vs capacidad instalada",
        "cruce_ambiental_capacidad",
        selected_block_label,
        large_height=760
    )

    download_col, spacer_col = st.columns([0.28, 0.72])
    with download_col:
        _render_greenhouse_report_download(
            analysis_data,
            selected_block_label,
            diagnostic_df=diagnostic_df,
            key_suffix="cruce_ambiental"
        )
    with spacer_col:
        st.caption("El Excel descargable incluye la ficha técnica completa y la hoja adicional de cruce ambiental.")

    with st.expander("Ver tabla completa del cruce ambiental", expanded=False):
        _dataframe(diagnostic_df, hide_index=True, height=300)


def _build_greenhouse_component_chart(selected_areas_df, selected_block_label):
    if selected_areas_df.empty:
        return None

    row = selected_areas_df.iloc[0]
    components = [
        (
            "Lateral",
            row.get("Área lateral teórica (m²)"),
            row.get("Área lateral máxima permitida (m²)"),
            row.get("Área lateral real (m²)"),
        ),
        (
            "Frontal",
            row.get("Área frontal teórica (m²)"),
            row.get("Área frontal máxima permitida (m²)"),
            row.get("Área frontal real (m²)"),
        ),
        (
            "Culatas",
            row.get("Área culatas teórica (m²)"),
            row.get("Área culatas máxima permitida (m²)"),
            row.get("Área culatas real (m²)"),
        ),
    ]

    chart_df = pd.DataFrame(
        [
            {
                "Componente": component_name,
                "Teórica": _safe_float(theoretical_value) or 0.0,
                "Máx. permitida": _safe_float(max_value) or 0.0,
                "Real": _safe_float(real_value) or 0.0,
            }
            for component_name, theoretical_value, max_value, real_value in components
        ]
    )

    fig = go.Figure()
    series_config = [
        ("Teórica", GREENHOUSE_COLORS["theoretical"]),
        ("Máx. permitida", GREENHOUSE_COLORS["allowed"]),
        ("Real", GREENHOUSE_COLORS["real"]),
    ]
    for series_name, color in series_config:
        fig.add_trace(go.Bar(
            x=chart_df["Componente"],
            y=chart_df[series_name],
            name=series_name,
            marker=dict(color=color, line=dict(color="rgba(56,58,53,0.12)", width=1)),
            text=[f"{value:,.0f}" for value in chart_df[series_name]],
            textposition="outside",
            hovertemplate="%{x}<br>" + series_name + ": %{y:,.2f} m²<extra></extra>"
        ))

    fig.update_layout(
        template="plotly_white",
        barmode="group",
        title=f"Ventilación por componente · {selected_block_label}",
        yaxis_title="Área de ventilación (m²)",
        xaxis_title="",
        legend_title_text="Escenario",
        height=440,
        margin=dict(l=20, r=20, t=70, b=24),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        bargap=0.22,
        bargroupgap=0.08,
    )
    return fig


def _build_greenhouse_efficiency_donut(selected_summary_df, selected_block_label):
    if selected_summary_df.empty:
        return None

    row = selected_summary_df.iloc[0]
    total_real = _safe_float(row.get("Total Real (m²)"))
    total_max = _safe_float(row.get("Total Máx. Perm. (m²)"))
    if total_real is None or total_max is None or total_max <= 0:
        return None

    gap_value = max(total_max - total_real, 0.0)
    fig = go.Figure(go.Pie(
        labels=["Ventilación real", "Brecha operativa"],
        values=[total_real, gap_value],
        hole=0.68,
        marker=dict(
            colors=[GREENHOUSE_COLORS["real"], GREENHOUSE_COLORS["gap"]],
            line=dict(color="rgba(255,255,255,0.96)", width=3),
        ),
        sort=False,
        texttemplate="<b>%{label}</b><br>%{percent}",
        textposition="inside",
        insidetextfont=dict(color="#ffffff", size=12),
        hovertemplate="%{label}<br>%{value:,.2f} m²<extra></extra>"
    ))
    fig.update_layout(
        template="plotly_white",
        title=f"Eficiencia operativa · {selected_block_label}",
        height=390,
        margin=dict(l=20, r=20, t=70, b=38),
        annotations=[dict(
            text=f"{(total_real / total_max):.0%}<br><span style='font-size:12px;'>del máximo</span>",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=18, color="#383A35")
        )],
        uniformtext_minsize=11,
        uniformtext_mode="hide",
        legend=dict(orientation="h", yanchor="bottom", y=-0.16, xanchor="center", x=0.5)
    )
    return fig


def _build_greenhouse_composition_donut(selected_areas_df, selected_block_label):
    if selected_areas_df.empty:
        return None

    row = selected_areas_df.iloc[0]
    composition_rows = [
        ("Lateral", _safe_float(row.get("Área lateral real (m²)")) or 0.0, GREENHOUSE_COLORS["lateral"]),
        ("Frontal", _safe_float(row.get("Área frontal real (m²)")) or 0.0, GREENHOUSE_COLORS["frontal"]),
        ("Culatas", _safe_float(row.get("Área culatas real (m²)")) or 0.0, GREENHOUSE_COLORS["culatas"]),
    ]
    composition_rows = [item for item in composition_rows if item[1] > 0]
    if not composition_rows:
        return None

    total_real = sum(value for _, value, _ in composition_rows)
    fig = go.Figure(go.Pie(
        labels=[label for label, _, _ in composition_rows],
        values=[value for _, value, _ in composition_rows],
        hole=0.62,
        marker=dict(
            colors=[color for _, _, color in composition_rows],
            line=dict(color="rgba(255,255,255,0.96)", width=3),
        ),
        sort=False,
        texttemplate="<b>%{label}</b><br>%{percent}",
        textposition="inside",
        insidetextfont=dict(color="#ffffff", size=12),
        hovertemplate="%{label}<br>%{value:,.2f} m²<extra></extra>"
    ))
    fig.update_layout(
        template="plotly_white",
        title=f"Composición de la ventilación real · {selected_block_label}",
        height=390,
        margin=dict(l=20, r=20, t=70, b=38),
        annotations=[dict(
            text=f"{total_real:,.0f} m²<br><span style='font-size:12px;'>ventilación real</span>",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=18, color="#383A35")
        )],
        uniformtext_minsize=11,
        uniformtext_mode="hide",
        legend=dict(orientation="h", yanchor="bottom", y=-0.16, xanchor="center", x=0.5)
    )
    return fig


def _build_greenhouse_component_progress_chart(selected_areas_df, selected_block_label):
    if selected_areas_df.empty:
        return None

    row = selected_areas_df.iloc[0]
    components = [
        ("Lateral", row.get("Área lateral máxima permitida (m²)"), row.get("Área lateral real (m²)")),
        ("Frontal", row.get("Área frontal máxima permitida (m²)"), row.get("Área frontal real (m²)")),
        ("Culatas", row.get("Área culatas máxima permitida (m²)"), row.get("Área culatas real (m²)")),
    ]
    progress_rows = []
    for component_name, max_value, real_value in components:
        max_numeric = _safe_float(max_value)
        real_numeric = _safe_float(real_value)
        if max_numeric is None or max_numeric <= 0 or real_numeric is None:
            continue
        real_capped = min(real_numeric, max_numeric)
        gap_value = max(max_numeric - real_numeric, 0.0)
        progress_rows.append({
            "Componente": component_name,
            "Real": real_capped,
            "Brecha": gap_value,
            "Cumplimiento": real_numeric / max_numeric,
        })

    if not progress_rows:
        return None

    progress_df = pd.DataFrame(progress_rows)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=progress_df["Componente"],
        x=progress_df["Real"],
        orientation="h",
        name="Real",
        marker=dict(color=GREENHOUSE_COLORS["real"], line=dict(color="rgba(56,58,53,0.10)", width=1)),
        text=[f"{value:.0%}" for value in progress_df["Cumplimiento"]],
        textposition="inside",
        insidetextanchor="middle",
        hovertemplate="%{y}<br>Real: %{x:,.2f} m²<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        y=progress_df["Componente"],
        x=progress_df["Brecha"],
        orientation="h",
        name="Brecha",
        marker=dict(color=GREENHOUSE_COLORS["gap"], line=dict(color="rgba(56,58,53,0.10)", width=1)),
        hovertemplate="%{y}<br>Brecha: %{x:,.2f} m²<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_white",
        title=f"Uso del máximo permitido por componente · {selected_block_label}",
        barmode="stack",
        height=440,
        margin=dict(l=20, r=20, t=70, b=24),
        xaxis_title="Área máxima permitida (m²)",
        yaxis_title="",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def _build_greenhouse_block_ranking_chart(summary_df, selected_block_label):
    if summary_df.empty or "Bloque" not in summary_df.columns or "Total Real (m²)" not in summary_df.columns:
        return None

    ranking_df = summary_df.copy()
    ranking_df["Total Real (m²)"] = pd.to_numeric(ranking_df["Total Real (m²)"], errors="coerce")
    ranking_df = ranking_df.dropna(subset=["Total Real (m²)"]).sort_values("Total Real (m²)", ascending=False)
    if ranking_df.empty:
        return None

    bar_colors = [
        BRAND_COLORS["hero"] if str(block_name) == str(selected_block_label) else "#C9D7E7"
        for block_name in ranking_df["Bloque"]
    ]

    fig = go.Figure(go.Bar(
        x=ranking_df["Total Real (m²)"],
        y=ranking_df["Bloque"],
        orientation="h",
        marker_color=bar_colors,
        text=[f"{value:,.0f} m²" for value in ranking_df["Total Real (m²)"]],
        textposition="outside",
        hovertemplate="%{y}<br>Total real: %{x:,.2f} m²<extra></extra>"
    ))
    fig.update_layout(
        template="plotly_white",
        title="Comparación de ventilación real entre bloques",
        xaxis_title="Total real (m²)",
        yaxis_title="",
        height=420,
        margin=dict(l=20, r=20, t=70, b=24),
        yaxis=dict(autorange="reversed", categoryorder="array", categoryarray=ranking_df["Bloque"].tolist()),
    )
    return fig


def _build_greenhouse_gap_ranking_chart(summary_df, selected_block_label):
    if summary_df.empty or "Bloque" not in summary_df.columns or "Brecha Máx-Real (m²)" not in summary_df.columns:
        return None

    ranking_df = summary_df.copy()
    ranking_df["Brecha Máx-Real (m²)"] = pd.to_numeric(ranking_df["Brecha Máx-Real (m²)"], errors="coerce")
    ranking_df = ranking_df.dropna(subset=["Brecha Máx-Real (m²)"]).sort_values("Brecha Máx-Real (m²)", ascending=False)
    if ranking_df.empty:
        return None

    bar_colors = [
        GREENHOUSE_COLORS["gap"] if str(block_name) == str(selected_block_label) else "#D8D2C4"
        for block_name in ranking_df["Bloque"]
    ]

    fig = go.Figure(go.Bar(
        x=ranking_df["Brecha Máx-Real (m²)"],
        y=ranking_df["Bloque"],
        orientation="h",
        marker=dict(color=bar_colors, line=dict(color="rgba(56,58,53,0.10)", width=1)),
        text=[f"{value:,.0f} m²" for value in ranking_df["Brecha Máx-Real (m²)"]],
        textposition="outside",
        hovertemplate="%{y}<br>Brecha: %{x:,.2f} m²<extra></extra>"
    ))
    fig.update_layout(
        template="plotly_white",
        title="Ranking de brecha operativa por bloque",
        xaxis_title="Brecha máx-real (m²)",
        yaxis_title="",
        height=420,
        margin=dict(l=20, r=20, t=70, b=24),
        yaxis=dict(autorange="reversed", categoryorder="array", categoryarray=ranking_df["Bloque"].tolist()),
    )
    return fig


def _build_greenhouse_performance_heatmap(summary_df, selected_block_label):
    required_columns = [
        "Bloque",
        "% Real / Teórica",
        "% Real / Máx. Perm.",
        "Brecha Máx-Real (m²)",
    ]
    if summary_df.empty or any(column_name not in summary_df.columns for column_name in required_columns):
        return None

    heatmap_df = summary_df[required_columns].copy()
    heatmap_df["% Real / Teórica"] = pd.to_numeric(heatmap_df["% Real / Teórica"], errors="coerce")
    heatmap_df["% Real / Máx. Perm."] = pd.to_numeric(heatmap_df["% Real / Máx. Perm."], errors="coerce")
    heatmap_df["Brecha Máx-Real (m²)"] = pd.to_numeric(heatmap_df["Brecha Máx-Real (m²)"], errors="coerce")
    heatmap_df["Brecha normalizada"] = 1 - (
        heatmap_df["Brecha Máx-Real (m²)"] / heatmap_df["Brecha Máx-Real (m²)"].max()
    )
    heatmap_df = heatmap_df.dropna(subset=["% Real / Teórica", "% Real / Máx. Perm.", "Brecha normalizada"])
    if heatmap_df.empty:
        return None

    metric_labels = ["Real / teórica", "Real / máx.", "Brecha controlada"]
    z_values = heatmap_df[["% Real / Teórica", "% Real / Máx. Perm.", "Brecha normalizada"]].to_numpy()
    text_values = []
    for _, row in heatmap_df.iterrows():
        text_values.append([
            f"{row['% Real / Teórica']:.1%}",
            f"{row['% Real / Máx. Perm.']:.1%}",
            f"{row['Brecha Máx-Real (m²)']:,.0f} m²",
        ])

    fig = go.Figure(go.Heatmap(
        z=z_values,
        x=metric_labels,
        y=heatmap_df["Bloque"],
        text=text_values,
        texttemplate="%{text}",
        colorscale=[
            [0.0, "#D77A94"],
            [0.5, "#E7C87A"],
            [1.0, "#3DBB76"],
        ],
        zmin=0,
        zmax=1,
        colorbar=dict(
            title="Desempeño",
            tickvals=[0, 0.5, 1],
            ticktext=["Bajo", "Medio", "Alto"],
        ),
        hovertemplate="%{y}<br>%{x}: %{text}<extra></extra>",
    ))
    fig.update_layout(
        template="plotly_white",
        title="Heatmap de desempeño técnico",
        height=410,
        margin=dict(l=20, r=20, t=70, b=24),
        xaxis_title="",
        yaxis_title="",
        yaxis=dict(autorange="reversed"),
    )
    return fig


def _build_greenhouse_capacity_slope_chart(summary_df, selected_block_label):
    required_columns = [
        "Bloque",
        "Total Teórica (m²)",
        "Total Máx. Perm. (m²)",
        "Total Real (m²)",
    ]
    if summary_df.empty or any(column_name not in summary_df.columns for column_name in required_columns):
        return None

    working_df = summary_df[required_columns].copy()
    for column_name in required_columns[1:]:
        working_df[column_name] = pd.to_numeric(working_df[column_name], errors="coerce")
    working_df = working_df.dropna(subset=required_columns[1:])
    if working_df.empty:
        return None

    stage_labels = ["Teórica", "Máx. permitida", "Real"]
    stage_columns = ["Total Teórica (m²)", "Total Máx. Perm. (m²)", "Total Real (m²)"]

    fig = go.Figure()
    for _, row in working_df.iterrows():
        is_selected = str(row["Bloque"]) == str(selected_block_label)
        line_color = BRAND_COLORS["hero"] if is_selected else "rgba(84,83,134,0.28)"
        line_width = 4 if is_selected else 2
        marker_size = 11 if is_selected else 8
        fig.add_trace(go.Scatter(
            x=stage_labels,
            y=[row[column_name] for column_name in stage_columns],
            mode="lines+markers+text" if is_selected else "lines+markers",
            name=str(row["Bloque"]),
            line=dict(color=line_color, width=line_width),
            marker=dict(size=marker_size, color=line_color),
            text=[f"{row[column_name]:,.0f}" for column_name in stage_columns] if is_selected else None,
            textposition="top center",
            hovertemplate=f"{row['Bloque']}<br>%{{x}}: %{{y:,.2f}} m²<extra></extra>",
        ))

    fig.update_layout(
        template="plotly_white",
        title="Trayectoria de capacidad: teórica → máxima → real",
        yaxis_title="Área de ventilación (m²)",
        xaxis_title="Etapa de capacidad",
        height=460,
        margin=dict(l=20, r=20, t=70, b=24),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def _build_greenhouse_insights(selected_general_df, selected_areas_df, selected_summary_df):
    insights = []
    if selected_general_df.empty or selected_areas_df.empty or selected_summary_df.empty:
        return insights

    general_row = selected_general_df.iloc[0]
    area_row = selected_areas_df.iloc[0]
    summary_row = selected_summary_df.iloc[0]

    culatas_count = _safe_float(general_row.get("N° Culatas"))
    if culatas_count == 0:
        insights.append("Este bloque no tiene culatas activas en el cálculo, así que su ventilación depende de laterales y frontales.")
    elif culatas_count is not None:
        insights.append(f"El bloque incorpora {int(culatas_count)} culatas consideradas en la capacidad de ventilación.")

    real_vs_theoretical = _safe_float(summary_row.get("% Real / Teórica"))
    if real_vs_theoretical is not None:
        insights.append(f"La ventilación real está en {real_vs_theoretical:.1%} del potencial teórico del bloque.")

    largest_gap = None
    largest_gap_label = None
    for component_name, max_column, real_column in [
        ("lateral", "Área lateral máxima permitida (m²)", "Área lateral real (m²)"),
        ("frontal", "Área frontal máxima permitida (m²)", "Área frontal real (m²)"),
        ("culatas", "Área culatas máxima permitida (m²)", "Área culatas real (m²)"),
    ]:
        max_value = _safe_float(area_row.get(max_column))
        real_value = _safe_float(area_row.get(real_column))
        if max_value is None or real_value is None:
            continue
        gap_value = max_value - real_value
        if largest_gap is None or gap_value > largest_gap:
            largest_gap = gap_value
            largest_gap_label = component_name

    if largest_gap_label is not None:
        insights.append(f"La mayor oportunidad operativa frente al máximo permitido está en la ventilación {largest_gap_label}, con una brecha de {largest_gap:,.1f} m².")

    return insights


@st.cache_data(show_spinner="Cargando análisis estructural de invernaderos...")
def cargar_analisis_invernaderos(ruta_bytes, cache_version=DATA_CACHE_VERSION):
    _ = ruta_bytes
    return load_greenhouse_analysis(cache_version)


def _render_greenhouse_analysis_dashboard():
    analysis_data = cargar_analisis_invernaderos(None)
    general_df = analysis_data["general"]
    areas_df = analysis_data["areas"]
    summary_df = analysis_data["summary"]
    interpretations_df = analysis_data["interpretations"]
    guide_df = analysis_data["guide"]
    chart_totals_df = analysis_data["chart_totals"]
    chart_ratios_df = analysis_data["chart_ratios"]
    dictionary_df = analysis_data["dictionary"]

    available_blocks = []
    for source_df in (summary_df, general_df, areas_df):
        if "Bloque" in source_df.columns:
            available_blocks.extend(source_df["Bloque"].dropna().astype(str).tolist())
    available_blocks = list(dict.fromkeys(available_blocks))

    if not available_blocks:
        st.warning("El archivo de análisis no contiene bloques listos para mostrar.")
        st.stop()

    shared_block_code = st.session_state.get("bloque_compartido")
    default_block_label = next(
        (block_name for block_name in available_blocks if _extract_block_code(block_name) == shared_block_code),
        available_blocks[0]
    )
    if st.session_state.get("greenhouse_analysis_block") not in available_blocks:
        st.session_state["greenhouse_analysis_block"] = default_block_label

    with st.sidebar.expander("Bloque técnico", expanded=True):
        _sidebar_field_label("location", "Bloque analizado")
        selected_block_label = st.selectbox(
            "Seleccionar bloque técnico:",
            options=available_blocks,
            key="greenhouse_analysis_block",
            help="Muestra la ficha estructural y de ventilación calculada para el bloque seleccionado."
        )

    selected_block_code = _extract_block_code(selected_block_label)
    if selected_block_code:
        st.session_state["bloque_compartido"] = selected_block_code

    selected_general_df = (
        general_df[general_df["Bloque"].astype(str) == selected_block_label].reset_index(drop=True)
        if "Bloque" in general_df.columns else pd.DataFrame()
    )
    selected_areas_df = (
        areas_df[areas_df["Bloque"].astype(str) == selected_block_label].reset_index(drop=True)
        if "Bloque" in areas_df.columns else pd.DataFrame()
    )
    selected_summary_df = (
        summary_df[summary_df["Bloque"].astype(str) == selected_block_label].reset_index(drop=True)
        if "Bloque" in summary_df.columns else pd.DataFrame()
    )

    _render_greenhouse_styles()
    _render_greenhouse_hero(selected_block_label, selected_summary_df)

    download_col, download_note_col = st.columns([0.28, 0.72])
    with download_col:
        _render_greenhouse_report_download(analysis_data, selected_block_label, key_suffix="ficha_tecnica")
    with download_note_col:
        st.caption("Reporte listo para auditoría: datos generales, áreas calculadas, indicadores, lectura técnica, guía rápida y diccionario.")

    _render_greenhouse_flow_cards(
        "Ruta de lectura del contexto técnico",
        [
            {
                "title": "Resumen ejecutivo",
                "body": "Decisión rápida: capacidad, brecha, eficiencia y lectura principal del bloque.",
                "accent": BRAND_COLORS["hero"],
            },
            {
                "title": "Componentes",
                "body": "Detalle de geometría, laterales, frontales y culatas para explicar el resultado.",
                "accent": GREENHOUSE_COLORS["real"],
            },
            {
                "title": "Comparativo",
                "body": "Benchmark entre bloques para priorizar dónde revisar primero.",
                "accent": GREENHOUSE_COLORS["gap"],
            },
            {
                "title": "Cruce ambiental",
                "body": "Relación entre estructura de ventilación y comportamiento climático observado.",
                "accent": BRAND_COLORS["sky"],
            },
            {
                "title": "Datos y diccionario",
                "body": "Trazabilidad completa del Excel: tablas fuente, cálculos y definiciones.",
                "accent": BRAND_COLORS["graphite"],
            },
        ]
    )

    tab_exec, tab_components, tab_compare, tab_environment_new, tab_data = st.tabs([
        "1. Resumen ejecutivo",
        "2. Componentes",
        "3. Comparativo",
        "4. Cruce ambiental",
        "5. Datos y diccionario",
    ])

    with tab_exec:
        _render_chart_explanation(
            "Lectura ejecutiva del bloque",
            "Concentra capacidad instalada, uso real y brecha operativa para tomar una decisión rápida antes de entrar al detalle técnico.",
            accent=BRAND_COLORS['hero'],
            kicker='Contexto técnico'
        )

        if not selected_summary_df.empty:
            summary_row = selected_summary_df.iloc[0]
            real_max_ratio = _safe_float(summary_row.get("% Real / Máx. Perm."))
            loss_ratio = max(0.0, 1 - real_max_ratio) if real_max_ratio is not None else None
            _render_greenhouse_metric_grid(
                "Capacidad de ventilación",
                [
                    {"label": "Total teórica", "value": _format_greenhouse_value(summary_row.get("Total Teórica (m²)"), 2, " m²"), "note": "Potencial geométrico calculado", "accent": GREENHOUSE_COLORS["theoretical"]},
                    {"label": "Máx. permitida", "value": _format_greenhouse_value(summary_row.get("Total Máx. Perm. (m²)"), 2, " m²"), "note": "Límite operativo instalado", "accent": GREENHOUSE_COLORS["allowed"]},
                    {"label": "Total real", "value": _format_greenhouse_value(summary_row.get("Total Real (m²)"), 2, " m²"), "note": "Ventilación efectiva disponible", "accent": GREENHOUSE_COLORS["real"]},
                    {"label": "Brecha máx-real", "value": _format_greenhouse_value(summary_row.get("Brecha Máx-Real (m²)"), 2, " m²"), "note": "Oportunidad frente al máximo", "accent": GREENHOUSE_COLORS["gap"]},
                ]
            )
            _render_greenhouse_metric_grid(
                "Indicadores de cumplimiento",
                [
                    {"label": "Real / teórica", "value": _format_greenhouse_percent(summary_row.get("% Real / Teórica")), "note": "Uso del potencial geométrico", "accent": BRAND_COLORS["sky"]},
                    {"label": "Real / máx. permitida", "value": _format_greenhouse_percent(summary_row.get("% Real / Máx. Perm.")), "note": "Uso de la capacidad instalada", "accent": BRAND_COLORS["hero"]},
                    {"label": "Pérdida operativa", "value": _format_greenhouse_percent(loss_ratio), "note": "Brecha relativa al máximo", "accent": BRAND_COLORS["rose"]},
                    {"label": "Bloque evaluado", "value": selected_block_label, "note": "Fuente: Datos por Bloque", "accent": BRAND_COLORS["graphite"]},
                ]
            )

        _render_greenhouse_insight_cards(_build_greenhouse_insights(selected_general_df, selected_areas_df, selected_summary_df))
        exec_left, exec_right = st.columns(2)
        with exec_left:
            _render_greenhouse_chart_panel(_build_greenhouse_efficiency_donut(selected_summary_df, selected_block_label), "Eficiencia operativa", "ejecutivo_eficiencia_operativa", selected_block_label, large_height=620)
        with exec_right:
            _render_greenhouse_chart_panel(_build_greenhouse_composition_donut(selected_areas_df, selected_block_label), "Composición de la ventilación real", "ejecutivo_composicion_ventilacion_real", selected_block_label, large_height=620)

    with tab_components:
        _render_chart_explanation(
            "Componentes estructurales",
            "Separa geometría, ventilación lateral, frontal y culatas para entender de dónde viene la capacidad real del bloque.",
            accent=GREENHOUSE_COLORS["real"],
            kicker='Detalle técnico'
        )
        if not selected_general_df.empty:
            general_row = selected_general_df.iloc[0]
            _render_greenhouse_metric_grid(
                "Geometría del invernadero",
                [
                    {"label": "Cuadros", "value": _format_greenhouse_value(general_row.get("N° Cuadros"), 0), "note": "Módulos estructurales", "accent": GREENHOUSE_COLORS["lateral"]},
                    {"label": "Naves", "value": _format_greenhouse_value(general_row.get("N° Naves"), 0), "note": "Configuración del bloque", "accent": GREENHOUSE_COLORS["frontal"]},
                    {"label": "Culatas", "value": _format_greenhouse_value(general_row.get("N° Culatas"), 0), "note": "Aperturas consideradas", "accent": GREENHOUSE_COLORS["culatas"]},
                    {"label": "Tamaño nave", "value": _format_greenhouse_value(general_row.get("Tamaño de la nave (m)"), 1, " m"), "note": "Medida base de cálculo", "accent": BRAND_COLORS["beige"]},
                ]
            )
        comp_left, comp_right = st.columns(2)
        with comp_left:
            _render_greenhouse_chart_panel(_build_greenhouse_component_chart(selected_areas_df, selected_block_label), "Ventilación por componente", "componentes_ventilacion_por_componente", selected_block_label, large_height=680)
        with comp_right:
            _render_greenhouse_chart_panel(_build_greenhouse_component_progress_chart(selected_areas_df, selected_block_label), "Uso del máximo permitido por componente", "componentes_uso_maximo_por_componente", selected_block_label, large_height=680)
        _render_greenhouse_reading_cards("Guía rápida de lectura", guide_df, title_col="Concepto", body_col="Descripcion")
        detail_left, detail_right = st.columns(2)
        with detail_left:
            with st.expander("Datos generales y aperturas lineales", expanded=False):
                _dataframe(_format_single_block_detail_table(selected_general_df), hide_index=True)
        with detail_right:
            with st.expander("Áreas de ventilación calculadas", expanded=False):
                _dataframe(_format_single_block_detail_table(selected_areas_df), hide_index=True)

    with tab_compare:
        _render_chart_explanation(
            "Comparativo entre bloques",
            "Ubica el bloque seleccionado frente al resto para priorizar brechas, eficiencia relativa y posición técnica.",
            accent=GREENHOUSE_COLORS["gap"],
            kicker='Benchmark técnico'
        )
        diagnostic_left, diagnostic_right = st.columns(2)
        with diagnostic_left:
            _render_greenhouse_chart_panel(_build_greenhouse_performance_heatmap(summary_df, selected_block_label), "Heatmap de desempeño técnico", "comparativo_heatmap_desempeno_tecnico", selected_block_label, large_height=650)
        with diagnostic_right:
            _render_greenhouse_chart_panel(_build_greenhouse_gap_ranking_chart(summary_df, selected_block_label), "Ranking de brecha operativa", "comparativo_ranking_brecha_operativa", selected_block_label, large_height=650)
        _render_greenhouse_chart_panel(_build_greenhouse_capacity_slope_chart(summary_df, selected_block_label), "Trayectoria de capacidad", "comparativo_trayectoria_capacidad", selected_block_label, large_height=680)
        _render_greenhouse_chart_panel(_build_greenhouse_block_ranking_chart(summary_df, selected_block_label), "Comparación de ventilación real entre bloques", "comparativo_ranking_ventilacion_real", selected_block_label, large_height=650)
        with st.expander("Tabla comparativa por bloque", expanded=True):
            _dataframe(_format_analysis_block_table(summary_df), hide_index=True)
        _render_greenhouse_reading_cards("Lectura técnica del archivo", interpretations_df)

    with tab_environment_new:
        _render_greenhouse_environment_tab(summary_df, analysis_data, selected_block_label)

    with tab_data:
        _render_chart_explanation(
            "Base técnica y trazabilidad",
            "Esta pestaña conserva las tablas originales, las bases de gráficas y el diccionario para auditar de dónde sale cada indicador del contexto técnico.",
            accent=BRAND_COLORS["graphite"],
            kicker="Soporte de datos"
        )
        _render_greenhouse_metric_grid(
            "Trazabilidad del archivo",
            [
                {"label": "Bloques técnicos", "value": f"{len(available_blocks):,}", "note": "Bloques detectados en el Excel", "accent": BRAND_COLORS["hero"]},
                {"label": "Datos generales", "value": f"{len(general_df):,}", "note": "Filas de geometría y aperturas", "accent": GREENHOUSE_COLORS["lateral"]},
                {"label": "Áreas calculadas", "value": f"{len(areas_df):,}", "note": "Filas de ventilación en m²", "accent": GREENHOUSE_COLORS["real"]},
                {"label": "Variables definidas", "value": f"{len(dictionary_df):,}", "note": "Conceptos documentados", "accent": GREENHOUSE_COLORS["gap"]},
            ]
        )
        st.markdown(
            """
            <div class="greenhouse-divider-note">
                Usa esta zona como respaldo técnico: primero están las tablas fuente, luego las bases usadas para gráficas comparativas
                y al final el diccionario con el significado operativo de cada variable.
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown("### Tablas fuente del Excel")
        with st.expander("Datos generales de todos los bloques", expanded=False):
            _dataframe(general_df, hide_index=True, height=260)
        with st.expander("Apertura calculada en m² de todos los bloques", expanded=False):
            _dataframe(_format_analysis_block_table(areas_df), hide_index=True, height=280)
        with st.expander("Datos base de gráficas comparativas", expanded=False):
            if not chart_totals_df.empty:
                st.markdown("#### Ventilación por bloque")
                _dataframe(chart_totals_df, hide_index=True)
            if not chart_ratios_df.empty:
                st.markdown("#### Indicadores porcentuales")
                _dataframe(_format_analysis_block_table(chart_ratios_df), hide_index=True)
        st.markdown("### Diccionario de variables")
        _render_greenhouse_dictionary_cards(dictionary_df)
        with st.expander("Ver diccionario en tabla completa", expanded=False):
            _dataframe(dictionary_df, hide_index=True, height=360)

    return

    tab_block, tab_summary, tab_environment, tab_dictionary = st.tabs([
        "Datos por bloque",
        "Resumen comparativo",
        "Cruce ambiental",
        "Diccionario",
    ])

    with tab_block:
        _render_chart_explanation(
            "Datos por bloque",
            "Esta vista resume la geometría del invernadero, la capacidad de ventilación por componente y la posición relativa del bloque seleccionado frente a los demás."
        )

        if not selected_summary_df.empty:
            summary_row = selected_summary_df.iloc[0]
            real_max_ratio = _safe_float(summary_row.get("% Real / Máx. Perm."))
            loss_ratio = max(0.0, 1 - real_max_ratio) if real_max_ratio is not None else None
            _render_greenhouse_metric_grid(
                "Capacidad de ventilación",
                [
                    {
                        "label": "Total teórica",
                        "value": _format_greenhouse_value(summary_row.get("Total Teórica (m²)"), 2, " m²"),
                        "note": "Potencial geométrico calculado",
                        "accent": GREENHOUSE_COLORS["theoretical"],
                    },
                    {
                        "label": "Máx. permitida",
                        "value": _format_greenhouse_value(summary_row.get("Total Máx. Perm. (m²)"), 2, " m²"),
                        "note": "Límite operativo instalado",
                        "accent": GREENHOUSE_COLORS["allowed"],
                    },
                    {
                        "label": "Total real",
                        "value": _format_greenhouse_value(summary_row.get("Total Real (m²)"), 2, " m²"),
                        "note": "Ventilación efectiva disponible",
                        "accent": GREENHOUSE_COLORS["real"],
                    },
                    {
                        "label": "Brecha máx-real",
                        "value": _format_greenhouse_value(summary_row.get("Brecha Máx-Real (m²)"), 2, " m²"),
                        "note": "Oportunidad frente al máximo",
                        "accent": GREENHOUSE_COLORS["gap"],
                    },
                ]
            )
            _render_greenhouse_metric_grid(
                "Indicadores de cumplimiento",
                [
                    {
                        "label": "Real / teórica",
                        "value": _format_greenhouse_percent(summary_row.get("% Real / Teórica")),
                        "note": "Uso del potencial geométrico",
                        "accent": BRAND_COLORS["sky"],
                    },
                    {
                        "label": "Real / máx. permitida",
                        "value": _format_greenhouse_percent(summary_row.get("% Real / Máx. Perm.")),
                        "note": "Uso de la capacidad instalada",
                        "accent": BRAND_COLORS["hero"],
                    },
                    {
                        "label": "Pérdida operativa",
                        "value": _format_greenhouse_percent(loss_ratio),
                        "note": "Brecha relativa al máximo",
                        "accent": BRAND_COLORS["rose"],
                    },
                    {
                        "label": "Bloque evaluado",
                        "value": selected_block_label,
                        "note": "Fuente: Datos por Bloque",
                        "accent": BRAND_COLORS["graphite"],
                    },
                ]
            )

        if not selected_general_df.empty:
            general_row = selected_general_df.iloc[0]
            _render_greenhouse_metric_grid(
                "Geometría del invernadero",
                [
                    {
                        "label": "Cuadros",
                        "value": _format_greenhouse_value(general_row.get("N° Cuadros"), 0),
                        "note": "Módulos estructurales",
                        "accent": GREENHOUSE_COLORS["lateral"],
                    },
                    {
                        "label": "Naves",
                        "value": _format_greenhouse_value(general_row.get("N° Naves"), 0),
                        "note": "Configuración del bloque",
                        "accent": GREENHOUSE_COLORS["frontal"],
                    },
                    {
                        "label": "Culatas",
                        "value": _format_greenhouse_value(general_row.get("N° Culatas"), 0),
                        "note": "Aperturas consideradas",
                        "accent": GREENHOUSE_COLORS["culatas"],
                    },
                    {
                        "label": "Tamaño nave",
                        "value": _format_greenhouse_value(general_row.get("Tamaño de la nave (m)"), 1, " m"),
                        "note": "Medida base de cálculo",
                        "accent": BRAND_COLORS["beige"],
                    },
                ]
            )

        insight_rows = _build_greenhouse_insights(selected_general_df, selected_areas_df, selected_summary_df)
        _render_greenhouse_insight_cards(insight_rows)

        donut_left, donut_right = st.columns(2)
        with donut_left:
            efficiency_donut = _build_greenhouse_efficiency_donut(selected_summary_df, selected_block_label)
            _render_greenhouse_chart_panel(
                efficiency_donut,
                "Eficiencia operativa",
                "eficiencia_operativa",
                selected_block_label,
                large_height=720
            )
        with donut_right:
            composition_donut = _build_greenhouse_composition_donut(selected_areas_df, selected_block_label)
            _render_greenhouse_chart_panel(
                composition_donut,
                "Composición de la ventilación real",
                "composicion_ventilacion_real",
                selected_block_label,
                large_height=720
            )

        chart_left, chart_right = st.columns(2)
        with chart_left:
            component_chart = _build_greenhouse_component_chart(selected_areas_df, selected_block_label)
            _render_greenhouse_chart_panel(
                component_chart,
                "Ventilación por componente",
                "ventilacion_por_componente",
                selected_block_label,
                large_height=760
            )
        with chart_right:
            progress_chart = _build_greenhouse_component_progress_chart(selected_areas_df, selected_block_label)
            _render_greenhouse_chart_panel(
                progress_chart,
                "Uso del máximo permitido por componente",
                "uso_maximo_por_componente",
                selected_block_label,
                large_height=760
            )

        _render_greenhouse_reading_cards("Guía rápida de lectura", guide_df, title_col="Concepto", body_col="Descripcion")

        st.markdown("### Datos completos del Excel")
        with st.expander("Datos generales de todos los bloques", expanded=True):
            _dataframe(general_df, hide_index=True, height=230)
        with st.expander("Apertura calculada en m² de todos los bloques", expanded=True):
            _dataframe(_format_analysis_block_table(areas_df), hide_index=True, height=250)

        detail_left, detail_right = st.columns(2)
        with detail_left:
            with st.expander("Ver datos generales y aperturas lineales", expanded=False):
                _dataframe(_format_single_block_detail_table(selected_general_df), hide_index=True)
        with detail_right:
            with st.expander("Ver áreas de ventilación calculadas", expanded=False):
                _dataframe(_format_single_block_detail_table(selected_areas_df), hide_index=True)

    with tab_summary:
        _render_chart_explanation(
            "Resumen comparativo",
            "Aquí puedes revisar rápidamente cómo se comporta cada bloque frente al resto usando los indicadores globales del archivo."
        )

        diagnostic_left, diagnostic_right = st.columns(2)
        with diagnostic_left:
            heatmap_chart = _build_greenhouse_performance_heatmap(summary_df, selected_block_label)
            _render_greenhouse_chart_panel(
                heatmap_chart,
                "Heatmap de desempeño técnico",
                "heatmap_desempeno_tecnico",
                selected_block_label,
                large_height=720
            )
        with diagnostic_right:
            gap_chart = _build_greenhouse_gap_ranking_chart(summary_df, selected_block_label)
            _render_greenhouse_chart_panel(
                gap_chart,
                "Ranking de brecha operativa",
                "ranking_brecha_operativa",
                selected_block_label,
                large_height=720
            )

        slope_chart = _build_greenhouse_capacity_slope_chart(summary_df, selected_block_label)
        _render_greenhouse_chart_panel(
            slope_chart,
            "Trayectoria de capacidad",
            "trayectoria_capacidad",
            selected_block_label,
            large_height=760
        )

        ranking_chart = _build_greenhouse_block_ranking_chart(summary_df, selected_block_label)
        _render_greenhouse_chart_panel(
            ranking_chart,
            "Comparación de ventilación real entre bloques",
            "ranking_ventilacion_real",
            selected_block_label,
            large_height=720
        )

        st.markdown("### Tabla comparativa por bloque")
        _dataframe(_format_analysis_block_table(summary_df), hide_index=True)

        _render_greenhouse_reading_cards("Lectura técnica del archivo", interpretations_df)

        with st.expander("Datos base de gráficas comparativas del archivo", expanded=False):
            if not chart_totals_df.empty:
                st.markdown("#### Ventilación por bloque")
                _dataframe(chart_totals_df, hide_index=True)
            if not chart_ratios_df.empty:
                st.markdown("#### Indicadores porcentuales")
                _dataframe(_format_analysis_block_table(chart_ratios_df), hide_index=True)

    with tab_environment:
        _render_greenhouse_environment_tab(summary_df, analysis_data, selected_block_label)

    with tab_dictionary:
        st.markdown("### Diccionario de variables")
        _render_greenhouse_dictionary_cards(dictionary_df)
        with st.expander("Ver diccionario en tabla completa", expanded=False):
            _dataframe(dictionary_df, hide_index=True, height=360)


__all__ = [name for name in globals() if not name.startswith("__")]
