"""Superstore BI — дашборд анализа продаж (Streamlit).

Здесь только раскладка страницы: расчёты — superstore/analytics.py и forecast.py,
графики — superstore/charts.py, оформление — superstore/ui.py.
Streamlit выполняет этот файл сверху вниз при каждом действии пользователя,
поэтому всё тяжёлое закэшировано (@st.cache_data) или вынесено в кнопки.
"""
from functools import partial

import streamlit as st

from superstore import analytics as an
from superstore import charts, ui
from superstore.config import CURRENCY_SIGN, PLOTLY_CONFIG
from superstore.data import load_rates, load_sales, to_csv_bytes, to_excel_bytes, to_rub
from superstore.forecast import backtest_last_year, forecast_next_year
from superstore.formatting import format_delta, format_k

# =========================================================
# КОНФИГ СТРАНИЦЫ
# =========================================================
st.set_page_config(
    page_title='Анализ продаж · Superstore',
    page_icon='📊',
    layout='wide',
    initial_sidebar_state='collapsed',
)
ui.inject_css()


def show(fig):
    st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)


# =========================================================
# ДАННЫЕ (кэш: CSV и курсы читаются один раз на валюту)
# =========================================================
@st.cache_data(show_spinner=False)
def get_sales(currency):
    """Вся таблица в нужной валюте. Рубли — по курсу ЦБ на дату заказа (файл, без сети)."""
    df = load_sales()
    return to_rub(df, load_rates()) if currency == 'RUB' else df


@st.cache_data(show_spinner=False)
def get_forecast():
    """Прогноз и бэктест — всегда по полной истории в долларах (от выбора годов не зависят)."""
    df = load_sales()
    return forecast_next_year(df), backtest_last_year(df)


@st.cache_data(show_spinner=False)
def last_rate():
    rates = load_rates()
    return rates.index[-1], float(rates.iloc[-1])


# =========================================================
# ШАПКА + ПАНЕЛЬ УПРАВЛЕНИЯ
# =========================================================
ui.header('Анализ продаж', 'Superstore · 2014–2017')

all_years = sorted(int(y) for y in get_sales('USD')['Year'].unique())
c1, c2 = st.columns([3, 1])
with c1:
    st.markdown('**Годы для сравнения**')
    years = st.pills('Годы', options=all_years, default=all_years,
                     selection_mode='multi', key='years', label_visibility='collapsed')
with c2:
    show_rub = st.toggle('🇷🇺 В рублях', value=False)

currency_code = 'RUB' if show_rub else 'USD'
currency = CURRENCY_SIGN[currency_code]

if not years:
    st.warning('Выберите хотя бы один год.')
    st.stop()
data = get_sales(currency_code)
df = data[data['Year'].isin(years)]          # рабочая таблица: выбранные годы, нужная валюта
if df.empty:
    st.warning('Нет данных за выбранные годы.')
    st.stop()

# =========================================================
# KPI + ДЕЛЬТЫ (последний выбранный год к предпоследнему)
# =========================================================
ui.kpi_row(an.kpis(df), currency)

# =========================================================
# РЯД 1: продажи/прибыль по месяцам + Парето
# =========================================================
col1, col2 = st.columns(2)
with col1, ui.card('monthly', 'Продажи и прибыль по месяцам'):
    show(charts.monthly_chart(an.monthly(df)))

with col2, ui.card('pareto', 'Парето: концентрация прибыли'):
    p = an.pareto(df)
    show(charts.pareto_chart(p))
    ui.caption(an.pareto_text(p, currency))

# =========================================================
# РЯД 2: топ-15 по выручке + топ-15 убыточных
# =========================================================
col1, col2 = st.columns(2)
with col1, ui.card('top-sales', 'Топ-15 продуктов по выручке'):
    show(charts.top_products_chart(an.top_products(df), currency))

with col2, ui.card('top-losses', 'Топ-15 убыточных продуктов'):
    show(charts.top_losses_chart(an.top_losses(df), currency))

# =========================================================
# РЯД 3: скидки vs прибыль + топ-20 клиентов
# =========================================================
col1, col2 = st.columns(2)
with col1, ui.card('discounts', 'Скидки vs Прибыль'):
    disc = an.discounts(df)
    tab_chart, tab_table = st.tabs(['График', 'Таблица'])
    with tab_chart:
        show(charts.discount_chart(disc))
        ui.caption(an.discount_text(disc))
    with tab_table:
        table = disc.assign(
            Sales=disc['Sales'].apply(lambda x: format_k(x, currency)),
            Profit=disc['Profit'].apply(lambda x: format_k(x, currency)),
            **{'Рент. %': disc['Рент. %'].apply(lambda x: f'{x:+.1f}%')},
        ).rename(columns={'Sales': 'Выручка', 'Profit': 'Прибыль', 'Orders': 'Заказов'})
        st.dataframe(table, width='stretch', hide_index=True)

with col2, ui.card('customers', 'Топ-20 клиентов'):
    cs = an.top_customers(df)
    show(charts.customers_chart(cs, currency))
    ui.caption(an.customers_text(cs, df['Sales'].sum()))

# =========================================================
# РЯД 4: структура (treemap) + география (бары / пузыри)
# =========================================================
col1, col2 = st.columns(2)
with col1, ui.card('categories', 'Структура продаж по категориям'):
    show(charts.category_treemap(an.category_tree(df), currency))
    ui.caption('Площадь — выручка, цвет — маржа % (красный = убыток). '
               'На компьютере клик по категории раскрывает её подкатегории.')
    ui.caption(an.categories_text(df))

with col2, ui.card('geo', 'География: продажи и прибыль по штатам'):
    geo = an.states(df)
    if geo.empty:
        st.info('Нет данных по штатам для выбранных фильтров.')
    else:
        tab_bar, tab_bub = st.tabs(['Бары', 'Пузыри'])
        with tab_bar:   # основная вкладка, удобна на смартфоне
            show(charts.states_bars(geo, currency))
            ui.caption('Длина — выручка, цвет — прибыль (зелёный) или убыток (красный). Топ-15 штатов.')
        with tab_bub:   # пузырьковая карта: размер = выручка, цвет = прибыль
            show(charts.states_bubbles(geo))
            ui.caption('Размер круга — выручка, цвет — прибыль (красный — убыток).')
        ui.caption(an.states_text(geo))

# =========================================================
# РЯД 5: ПРОГНОЗ + БЭКТЕСТИНГ (по полной истории, в $; для ₽ — по последнему курсу)
# =========================================================
fc, bt = get_forecast()
rate_date, rate = last_rate()
k = rate if currency_code == 'RUB' else 1.0

with ui.card('forecast', f'Прогноз продаж на {fc.year} год'):
    k1, k2, k3 = st.columns(3)
    k1.metric('Прогноз выручки', format_k(fc.total * k, currency),
              delta=format_delta((fc.total - fc.last_sales) * k, currency))
    k2.metric('Прогноз прибыли', format_k(fc.profit * k, currency),
              delta=format_delta((fc.profit - fc.last_profit) * k, currency))
    k3.metric('Прогноз заказов', f'{fc.orders:,.0f}',
              delta=f'{fc.orders - fc.last_orders:+,.0f}')
    show(charts.forecast_chart(fc, k))

    rub_note = (f' Суммы в рублях — по курсу ЦБ на {rate_date:%d.%m.%Y} ({rate:.2f} ₽/$).'
                if currency_code == 'RUB' else '')
    ui.info_box(
        f'<b>📘 Как работает прогноз:</b> модель <b>Holt-Winters</b> раскладывает историю на '
        f'тренд, сезонность и уровень и продлевает её на 12 месяцев ({fc.year} год). '
        f'Модель всегда учится на всей истории {fc.history.index[0].year}–{fc.last_year} — '
        f'выбор годов выше на прогноз не влияет. Дельты — к {fc.last_year} году. '
        f'Чем дальше горизонт — тем выше неопределённость; внешние факторы не учитываются.'
        f'{rub_note}')

    st.markdown('##### Бэктестинг: проверка точности')
    show(charts.backtest_chart(bt, k))
    ui.caption(f'Модель обучена без {bt.year} года и сравнена с фактом. '
               f'MAE: {format_k(bt.mae * k, currency)} · MAPE: {bt.mape:.1f}% '
               f'(средняя ошибка по месяцам) · ошибка годовой суммы: {bt.total_error:+.1f}%.')
    ui.caption(f'Для сравнения: наивный прогноз «как год назад» ошибается в среднем на '
               f'{format_k(bt.naive_mae * k, currency)} в месяц — модель точнее на '
               f'{bt.gain_vs_naive:.0f}%.')

# =========================================================
# РЯД 6: ЭКСПОРТ (файлы собираются только по нажатию кнопки)
# =========================================================
with ui.card('export', 'Экспорт данных'):
    e1, e2 = st.columns(2)
    e1.download_button('📥 Скачать CSV', data=partial(to_csv_bytes, df),
                       file_name='superstore_filtered.csv', mime='text/csv',
                       on_click='ignore', width='stretch')
    e2.download_button('📥 Скачать Excel', data=partial(to_excel_bytes, df),
                       file_name='superstore_filtered.xlsx',
                       mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                       on_click='ignore', width='stretch')
    ui.caption(f'Строк: {len(df):,} · Заказов: {df["Order ID"].nunique():,} · '
               f'Клиентов: {df["Customer ID"].nunique():,} · '
               f'Продуктов: {df["Product Name"].nunique():,}')
    st.dataframe(df, width='stretch', height=420)
