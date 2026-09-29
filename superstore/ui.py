"""Оформление страницы: CSS, KPI-строка, карточки-блоки. Единственный модуль пакета со Streamlit."""
from contextlib import contextmanager

import streamlit as st

from .config import COLOR_LOSS, COLOR_PROFIT
from .formatting import format_k

# =========================================================
# CSS — мобильный приоритет + лёгкая визуальная отделка.
# Тему фиксирует .streamlit/config.toml, поэтому здесь
# НЕ воюем через !important с тёмной темой.
# Карточки-блоки — контейнеры с ключом card-* (класс st-key-card-*).
# =========================================================
CSS = """
<style>
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
    }
    [data-testid="stSidebar"] { display: none; }

    .app-title { font-size: 34px; font-weight: 600; color: #0f172a; margin: 0 0 2px 0; }
    .app-sub   { font-size: 14px; color: #64748b; margin: 0 0 18px 0; }

    /* KPI-строка */
    .kpi-row { display: flex; gap: 28px; flex-wrap: wrap; margin: 10px 0 22px 0; }
    .kpi { min-width: 120px; }
    .kpi .label { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: .04em; }
    .kpi .value { font-size: 34px; font-weight: 600; color: #0f172a; line-height: 1.1; }
    .kpi .delta { font-size: 13px; padding: 1px 8px; border-radius: 6px; display: inline-block; margin-top: 2px; }
    .kpi-note  { font-size: 12px; color: #64748b; margin: -14px 0 18px 0; }

    /* тонкие разделители вместо тяжёлых рамок у графиков */
    [class*="st-key-card-"] {
        border: 1px solid #eef1f5;
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 4px;
        background: #ffffff;
    }
    h5 { font-size: 14px; font-weight: 600; color: #0f172a; margin-bottom: 6px; }

    /* ---------- МОБИЛЬНАЯ ВЕРСИЯ ---------- */
    @media (max-width: 768px) {
        .app-title { font-size: 26px; }
        .app-sub   { font-size: 13px; }

        /* KPI в две колонки: компактно и читаемо на телефоне */
        .kpi-row { gap: 0; }
        .kpi {
            width: 50%; box-sizing: border-box;
            padding: 8px 4px; border-bottom: 1px solid #f1f5f9;
        }
        .kpi .value { font-size: 24px; }
        .kpi-note  { margin-top: -12px; }

        [class*="st-key-card-"] { padding: 10px 10px; }

        /* На телефоне графики статичны: касания не двигают/зумят график,
           а прокручивают страницу. На десктопе (шире 768px) интерактив остаётся. */
        [data-testid="stPlotlyChart"] { pointer-events: none; }
    }
</style>
"""

DELTA_STYLE = {True: (COLOR_PROFIT, '#f0fdf4', '↑'), False: (COLOR_LOSS, '#fef2f2', '↓')}


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def header(title, subtitle):
    st.markdown(f'<div class="app-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="app-sub">{subtitle}</div>', unsafe_allow_html=True)


def delta_badge(value, currency=''):
    if value is None or value == 0:
        return ''
    color, bg, arrow = DELTA_STYLE[value > 0]
    txt = format_k(abs(value), currency)
    return (f'<span class="delta" style="color:{color};background:{bg};">'
            f'{arrow} {"+" if value > 0 else ""}{txt}</span>')


def kpi_row(k, currency):
    items = [
        ('Выручка', format_k(k.sales, currency), delta_badge(k.d_sales, currency)),
        ('Прибыль', format_k(k.profit, currency), delta_badge(k.d_profit, currency)),
        ('Заказы', f'{k.orders:,}', delta_badge(k.d_orders)),
        ('Клиенты', f'{k.customers:,}', delta_badge(k.d_customers)),
    ]
    html = '<div class="kpi-row">'
    for label, value, badge in items:
        html += (f'<div class="kpi"><div class="label">{label}</div>'
                 f'<div class="value">{value}</div>{badge}</div>')
    html += '</div>'
    if k.cur_year:
        html += f'<div class="kpi-note">Изменения: {k.cur_year} к {k.prev_year}</div>'
    st.markdown(html, unsafe_allow_html=True)


def caption(text):
    """st.caption с экранированным $: два «$» в одной строке Streamlit рендерит как формулу."""
    if text:
        st.caption(text.replace('$', r'\$'))


@contextmanager
def card(key, title=None):
    """Блок-карточка с заголовком: with card('pareto', 'Парето'): ..."""
    with st.container(border=True, key=f'card-{key}'):
        if title:
            st.markdown(f'##### {title}')
        yield


def info_box(html):
    st.markdown(f'<div style="font-size:13px;color:#475569;line-height:1.7;margin-top:8px;">'
                f'{html}</div>', unsafe_allow_html=True)
