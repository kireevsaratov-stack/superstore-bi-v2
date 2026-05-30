import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
from io import BytesIO

# =========================================================
# КОНФИГ СТРАНИЦЫ
# =========================================================
st.set_page_config(
    page_title="Анализ продаж · Superstore",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =========================================================
# CSS — мобильный приоритет + лёгкая визуальная отделка
# Тему фиксирует .streamlit/config.toml, поэтому здесь
# больше НЕ воюем через !important с тёмной темой.
# =========================================================
st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
    }
    [data-testid="stSidebar"] { display: none; }
    .main .block-container { max-width: 1200px; padding-top: 14px; padding-bottom: 40px; }

    .app-title { font-size: 34px; font-weight: 600; color: #0f172a; margin: 0 0 2px 0; }
    .app-sub   { font-size: 14px; color: #64748b; margin: 0 0 18px 0; }

    /* KPI-строка */
    .kpi-row { display: flex; gap: 28px; flex-wrap: wrap; margin: 10px 0 22px 0; }
    .kpi { min-width: 120px; }
    .kpi .label { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: .04em; }
    .kpi .value { font-size: 34px; font-weight: 600; color: #0f172a; line-height: 1.1; }
    .kpi .delta { font-size: 13px; padding: 1px 8px; border-radius: 6px; display: inline-block; margin-top: 2px; }

    /* тонкие разделители вместо тяжёлых рамок у графиков */
    .st-key-plot1,.st-key-plot2,.st-key-plot3,.st-key-plot4,.st-key-plot5,
    .st-key-plot6,.st-key-plot7,.st-key-plot8,.st-key-plot9,.st-key-plot10,
    .st-key-plot11,.st-key-plot12 {
        border: 1px solid #eef1f5;
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 4px;
        background: #ffffff;
    }
    h5 { font-size: 14px; font-weight: 600; color: #0f172a; margin-bottom: 6px; }

    /* ---------- МОБИЛЬНАЯ ВЕРСИЯ ---------- */
    @media (max-width: 768px) {
        .main .block-container { padding-left: 10px; padding-right: 10px; }
        .app-title { font-size: 26px; }
        .app-sub   { font-size: 13px; }

        /* KPI в две колонки: компактно и читаемо на телефоне */
        .kpi-row { gap: 0; }
        .kpi {
            width: 50%; box-sizing: border-box;
            padding: 8px 4px; border-bottom: 1px solid #f1f5f9;
        }
        .kpi .value { font-size: 24px; }

        .st-key-plot1,.st-key-plot2,.st-key-plot3,.st-key-plot4,.st-key-plot5,
        .st-key-plot6,.st-key-plot7,.st-key-plot8,.st-key-plot11,.st-key-plot12 {
            padding: 10px 10px;
        }

        /* На телефоне графики статичны: касания не двигают/зумят график,
           а прокручивают страницу. На десктопе (шире 768px) интерактив остаётся. */
        [data-testid="stPlotlyChart"] { pointer-events: none; }
    }
</style>
""", unsafe_allow_html=True)

# =========================================================
# КОНСТАНТЫ И ХЕЛПЕРЫ
# =========================================================
MONTH_NAMES = {1:'Янв',2:'Фев',3:'Мар',4:'Апр',5:'Май',6:'Июн',
               7:'Июл',8:'Авг',9:'Сен',10:'Окт',11:'Ноя',12:'Дек'}

COLOR_SALES  = '#1a56db'   # продажи (синий)
COLOR_PROFIT = '#16a34a'   # прибыль (зелёный)
COLOR_LOSS   = '#ef4444'   # убыток (красный)

# Конфиг Plotly: подсказки (hover) ВКЛЮЧЕНЫ (убрали staticPlot=True),
# панель инструментов скрыта.
PLOTLY_CONFIG = {'displayModeBar': False, 'responsive': True, 'displaylogo': False}
TEMPLATE = 'plotly_white'

# Названия штатов -> двухбуквенные коды (для карты)
STATE_CODES = {
    'Alabama': 'AL', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA', 'Colorado': 'CO',
    'Connecticut': 'CT', 'Delaware': 'DE', 'District of Columbia': 'DC', 'Florida': 'FL',
    'Georgia': 'GA', 'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS',
    'Kentucky': 'KY', 'Louisiana': 'LA', 'Maine': 'ME', 'Maryland': 'MD', 'Massachusetts': 'MA',
    'Michigan': 'MI', 'Minnesota': 'MN', 'Mississippi': 'MS', 'Missouri': 'MO', 'Montana': 'MT',
    'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM',
    'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK',
    'Oregon': 'OR', 'Pennsylvania': 'PA', 'Rhode Island': 'RI', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT',
    'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV', 'Wisconsin': 'WI', 'Wyoming': 'WY',
}

def format_k(value, currency=''):
    """1234567 -> '$1,235K', 950 -> '$950'."""
    if abs(value) >= 1000:
        return f"{currency}{value/1000:,.0f}K"
    return f"{currency}{value:,.0f}"

# =========================================================
# ЗАГРУЗКА ДАННЫХ (кэш — читаем CSV один раз)
# =========================================================
@st.cache_data(show_spinner=False)
def load_data():
    # Файл лежит рядом с app.py. Пробуем оба распространённых имени.
    for name in ['Sample - Superstore.csv', 'Sample__Superstore.csv', 'Sample_Superstore.csv']:
        try:
            df = pd.read_csv(name, encoding='latin1')
            break
        except FileNotFoundError:
            continue
    else:
        raise FileNotFoundError("CSV не найден. Положи 'Sample - Superstore.csv' рядом с app.py")

    df['Order Date'] = pd.to_datetime(df['Order Date'], format='%m/%d/%Y')
    df['Ship Date']  = pd.to_datetime(df['Ship Date'],  format='%m/%d/%Y')
    df['Year']  = df['Order Date'].dt.year
    df['Month'] = df['Order Date'].dt.month
    df['Processing Days'] = (df['Ship Date'] - df['Order Date']).dt.days
    return df

# =========================================================
# КУРСЫ ВАЛЮТ (исторические — кэш бессрочный)
# Берём все 12 месяцев, а не 4, чтобы конвертация была честной.
# =========================================================
@st.cache_data(show_spinner="Загрузка курсов ЦБ...")
def get_exchange_rates():
    rates = {}
    for year in [2014, 2015, 2016, 2017]:
        for month in range(1, 13):
            url = f"https://www.cbr-xml-daily.ru/archive/{year}-{month:02d}-01/daily_json.js"
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    rates[f"{year}-{month:02d}-01"] = resp.json()['Valute']['USD']['Value']
            except requests.RequestException:
                continue
    return rates

# =========================================================
# ПОДГОТОВКА ДАННЫХ В НУЖНОЙ ВАЛЮТЕ (кэш по значению show_rub)
# Конвертация выполняется РОВНО ОДИН РАЗ на всю таблицу,
# а не по нескольку раз на каждый рерёан.
# =========================================================
@st.cache_data(show_spinner=False)
def prepare_df(show_rub: bool):
    df = load_data().copy()
    if not show_rub:
        return df, True            # (данные, курс_ок)
    rates = get_exchange_rates()
    rate_ok = len(rates) > 0
    fallback = float(np.mean(list(rates.values()))) if rate_ok else 60.0
    key = df['Order Date'].dt.strftime('%Y-%m-01')
    df['Rate'] = key.map(rates).fillna(fallback)
    df['Sales']  = df['Sales']  * df['Rate']
    df['Profit'] = df['Profit'] * df['Rate']
    return df, rate_ok

# =========================================================
# ШАПКА
# =========================================================
st.markdown('<div class="app-title">Анализ продаж</div>', unsafe_allow_html=True)
st.markdown('<div class="app-sub">Superstore · 2014–2017</div>', unsafe_allow_html=True)

# =========================================================
# ПАНЕЛЬ УПРАВЛЕНИЯ
# =========================================================
all_years = sorted(load_data()['Year'].unique())

c1, c2 = st.columns([3, 1])
with c1:
    st.markdown("**Годы для сравнения**")
    years = st.pills("Годы", options=all_years, default=all_years,
                     selection_mode="multi", key="years", label_visibility="collapsed")
with c2:
    show_rub = st.toggle("🇷🇺 В рублях", value=False)

currency = '₽' if show_rub else '$'

# Готовим данные в нужной валюте (кэш)
df_cur, rate_ok = prepare_df(show_rub)
if show_rub and not rate_ok:
    st.warning("API ЦБ недоступен — рублёвые суммы рассчитаны по приблизительному курсу.")

df_filtered = df_cur                                  # без фильтра по году (нужно для дельт)
if not years:
    st.warning("Выберите хотя бы один год.")
    st.stop()
df = df_filtered[df_filtered['Year'].isin(years)]     # рабочий датафрейм
if df.empty:
    st.warning("Нет данных за выбранные годы.")
    st.stop()

# =========================================================
# KPI + ДЕЛЬТЫ (последний выбранный год vs предпоследний)
# =========================================================
sales_sum  = df['Sales'].sum()
profit_sum = df['Profit'].sum()
orders     = df['Order ID'].nunique()
customers  = df['Customer ID'].nunique()

sales_delta = profit_delta = orders_delta = customers_delta = None
years_sorted = sorted(years)
if len(years_sorted) >= 2:
    cy, py = years_sorted[-1], years_sorted[-2]
    dcur = df[df['Year'] == cy]
    dprev = df_filtered[df_filtered['Year'] == py]   # уже в нужной валюте, те же фильтры
    if len(dcur) and len(dprev):
        sales_delta     = dcur['Sales'].sum()      - dprev['Sales'].sum()
        profit_delta    = dcur['Profit'].sum()     - dprev['Profit'].sum()
        orders_delta    = dcur['Order ID'].nunique()    - dprev['Order ID'].nunique()
        customers_delta = dcur['Customer ID'].nunique() - dprev['Customer ID'].nunique()

def delta_badge(value, currency=''):
    if value is None or value == 0:
        return ''
    if value > 0:
        color, bg, arrow, sign = '#16a34a', '#f0fdf4', '↑', '+'
    else:
        color, bg, arrow, sign = '#ef4444', '#fef2f2', '↓', ''
    txt = format_k(abs(value), currency) if abs(value) >= 1000 else f'{currency}{abs(value):,.0f}'
    return f'<span class="delta" style="color:{color};background:{bg};">{arrow} {sign}{txt}</span>'

kpi_items = [
    ('Выручка', format_k(sales_sum, currency),  delta_badge(sales_delta, currency)),
    ('Прибыль', format_k(profit_sum, currency), delta_badge(profit_delta, currency)),
    ('Заказы',  f'{orders:,}',                  delta_badge(orders_delta)),
    ('Клиенты', f'{customers:,}',               delta_badge(customers_delta)),
]
html = '<div class="kpi-row">'
for label, value, badge in kpi_items:
    html += f'<div class="kpi"><div class="label">{label}</div><div class="value">{value}</div>{badge}</div>'
html += '</div>'
st.markdown(html, unsafe_allow_html=True)

# месячная агрегация для нескольких графиков
monthly = df.groupby(df['Order Date'].dt.to_period('M')).agg(
    Sales=('Sales', 'sum'), Profit=('Profit', 'sum')).reset_index()
monthly['Order Date'] = monthly['Order Date'].astype(str)

# =========================================================
# РЯД 1: Продажи/Прибыль по месяцам + Парето
# =========================================================
col1, col2 = st.columns(2)
with col1:
    with st.container(border=True, key="plot1"):
        st.markdown('##### Продажи и прибыль по месяцам')
        fig = go.Figure(layout=dict(template=TEMPLATE))
        fig.add_trace(go.Scatter(x=monthly['Order Date'], y=monthly['Sales'], name='Продажи',
                                 fill='tozeroy', line=dict(color=COLOR_SALES, width=2),
                                 hovertemplate='%{x}<br>Продажи: %{y:,.0f}<extra></extra>'))
        fig.add_trace(go.Scatter(x=monthly['Order Date'], y=monthly['Profit'], name='Прибыль',
                                 fill='tozeroy', line=dict(color=COLOR_PROFIT, width=2),
                                 hovertemplate='%{x}<br>Прибыль: %{y:,.0f}<extra></extra>'))
        n = len(monthly)
        step = 1 if n <= 12 else 2 if n <= 24 else 3 if n <= 36 else 4
        ticks = [monthly['Order Date'].iloc[i] for i in range(0, n, step)]
        fig.update_layout(height=360, hovermode='x unified', margin=dict(l=0, r=0, t=10, b=30),
                          xaxis=dict(tickmode='array', tickvals=ticks, ticktext=ticks,
                                     gridcolor='rgba(120,120,120,.15)'),
                          yaxis=dict(gridcolor='rgba(120,120,120,.1)'),
                          legend=dict(orientation='h', yanchor='top', y=-0.18, xanchor='center', x=0.5))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

with col2:
    with st.container(border=True, key="plot4"):
        st.markdown('##### Парето: концентрация прибыли')
        prod = df.groupby('Product Name')['Profit'].sum().sort_values(ascending=False).reset_index()
        pos = prod[prod['Profit'] > 0].copy()
        pos['Cum %'] = pos['Profit'].cumsum() / pos['Profit'].sum() * 100
        pos['N'] = range(1, len(pos) + 1)
        n80 = int((pos['Cum %'] <= 80).sum())
        loss = int((prod['Profit'] <= 0).sum())
        # Обрезаем кривую по точке выхода на 80% — без длинного плоского хвоста.
        head = pos.head(max(n80 + 1, 2))

        # Вариант А: накопительная кривая концентрации до 80% (читается на любой ширине).
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=head['N'], y=head['Cum %'], mode='lines', fill='tozeroy',
                                 line=dict(width=3, color=COLOR_SALES),
                                 fillcolor='rgba(26,86,219,0.08)',
                                 hovertemplate='Продукт #%{x}<br>накоплено %{y:.0f}% прибыли<extra></extra>'))
        fig.add_hline(y=80, line_dash='dash', opacity=.6, line_color='gray',
                      annotation_text='80% прибыли', annotation_position='top left')
        fig.update_layout(template=TEMPLATE, height=360, margin=dict(l=0, r=0, t=10, b=0),
                          showlegend=False,
                          xaxis=dict(title=f'Топ-{n80} продуктов (дают 80% прибыли)', showgrid=False),
                          yaxis=dict(title='Накопленная прибыль', range=[0, 85], ticksuffix='%',
                                     gridcolor='rgba(120,120,120,.12)'))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        _pct = n80 / len(prod) * 100 if len(prod) else 0
        st.caption(f"**Вывод:** {n80} продуктов из {len(prod)} (≈{_pct:.0f}%) дают 80% прибыли, "
                   f"при этом {loss} — убыточны.")

# =========================================================
# РЯД 2: Топ-15 по выручке + Топ-15 убыточных
# =========================================================
def truncate(s, n=25):
    return s if len(s) <= n else s[:n] + '…'

col1, col2 = st.columns(2)
with col1:
    with st.container(border=True, key="plot5"):
        st.markdown('##### Топ-15 продуктов по выручке')
        t = df.groupby('Product Name')['Sales'].sum().nlargest(15).reset_index()
        t['Label'] = t['Product Name'].apply(truncate)
        fig = px.bar(t, x='Sales', y='Label', orientation='h', template=TEMPLATE,
                     color_discrete_sequence=[COLOR_SALES], labels={'Sales': 'Продажи', 'Label': ''})
        fig.update_traces(text=t['Sales'].apply(lambda x: format_k(x, currency)),
                          textposition='inside', textfont=dict(size=11, color='white'),
                          hovertemplate='%{customdata}<br>%{x:,.0f}<extra></extra>',
                          customdata=t['Product Name'])
        fig.update_layout(yaxis={'categoryorder': 'total ascending', 'automargin': True,
                                 'tickfont': dict(size=10)},
                          xaxis=dict(range=[0, t['Sales'].max() * 1.15]),
                          height=360, margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

with col2:
    with st.container(border=True, key="plot6"):
        st.markdown('##### Топ-15 убыточных продуктов')
        l = df.groupby('Product Name')['Profit'].sum().nsmallest(15).reset_index()
        l['Label'] = l['Product Name'].apply(truncate)
        fig = px.bar(l, x='Profit', y='Label', orientation='h', template=TEMPLATE,
                     color_discrete_sequence=[COLOR_LOSS], labels={'Profit': 'Прибыль', 'Label': ''})
        fig.update_traces(text=l['Profit'].apply(lambda x: format_k(x, currency)),
                          textposition='auto', textfont=dict(size=11),
                          hovertemplate='%{customdata}<br>%{x:,.0f}<extra></extra>',
                          customdata=l['Product Name'])
        fig.update_layout(yaxis={'categoryorder': 'total descending', 'automargin': True,
                                 'tickfont': dict(size=10), 'side': 'right'},
                          xaxis=dict(range=[l['Profit'].min() * 1.15, 0]),
                          height=360, margin=dict(l=5, r=10, t=10, b=0))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

# =========================================================
# РЯД 3: Скидки vs Прибыль (без дублирования) + Топ-20 клиентов
# =========================================================
col1, col2 = st.columns(2)
with col1:
    with st.container(border=True, key="plot7"):
        st.markdown('##### Скидки vs Прибыль')
        # Группировку считаем ОДИН раз и переиспользуем в обеих вкладках.
        dp = df.copy()
        dp['Группа'] = pd.cut(dp['Discount'],
                              bins=[-0.01, 0, .10, .20, .30, .40, .50, .60, .80],
                              labels=['0%', '10%', '20%', '30%', '40%', '50%', '60%', '70%+'],
                              include_lowest=True)
        disc = dp.groupby('Группа', observed=False).agg(
            Sales=('Sales', 'sum'), Profit=('Profit', 'sum'),
            Orders=('Order ID', 'nunique')).reset_index()
        disc['Рент. %'] = np.where(disc['Sales'] != 0, disc['Profit'] / disc['Sales'] * 100, 0)

        tab_chart, tab_table = st.tabs(['График', 'Таблица'])
        with tab_chart:
            colors = [COLOR_PROFIT if x > 0 else COLOR_LOSS for x in disc['Рент. %']]
            fig = go.Figure()
            fig.add_trace(go.Bar(x=disc['Группа'], y=disc['Рент. %'], marker_color=colors,
                                 text=disc['Рент. %'].apply(lambda x: f'{x:+.0f}%'),
                                 textposition='outside',
                                 hovertemplate='Скидка %{x}<br>Рентабельность %{y:.1f}%<extra></extra>'))
            fig.add_hline(y=0, line_dash="dash", line_color="#d1d5db", opacity=.5)
            fig.update_layout(template=TEMPLATE, height=360, margin=dict(l=0, r=0, t=10, b=0),
                              xaxis=dict(title='Размер скидки'),
                              yaxis=dict(title='Рентабельность', ticksuffix='%'))
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
            # авто-вывод
            _neg = disc[disc['Рент. %'] < 0]['Группа']
            if len(_neg):
                st.caption(f"**Вывод:** скидки от «{_neg.iloc[0]}» делают заказы убыточными — "
                           f"ограничение глубоких скидок быстрее всего поднимет прибыль.")
            else:
                st.caption("**Вывод:** даже при больших скидках заказы остаются прибыльными.")
        with tab_table:
            show = disc.copy()
            show['Sales']  = show['Sales'].apply(lambda x: format_k(x, currency))
            show['Profit'] = show['Profit'].apply(lambda x: format_k(x, currency))
            show['Рент. %'] = show['Рент. %'].apply(lambda x: f'{x:+.1f}%')
            show = show.rename(columns={'Sales': 'Выручка', 'Profit': 'Прибыль', 'Orders': 'Заказов'})
            st.dataframe(show, use_container_width=True, hide_index=True)

with col2:
    with st.container(border=True, key="plot8"):
        st.markdown('##### Топ-20 клиентов')
        cs = df.groupby('Customer ID').agg(
            Name=('Customer Name', 'first'), Sales=('Sales', 'sum'),
            Profit=('Profit', 'sum')).reset_index().nlargest(20, 'Sales')
        colors = [COLOR_PROFIT if x > 0 else COLOR_LOSS for x in cs['Profit']]
        fig = go.Figure(go.Bar(y=cs['Name'], x=cs['Sales'], orientation='h', marker_color=colors,
                               text=cs['Sales'].apply(lambda x: format_k(x, currency)),
                               textposition='outside', textfont=dict(size=11),
                               hovertemplate='%{y}<br>Выручка %{x:,.0f}<extra></extra>'))
        fig.update_layout(template=TEMPLATE, yaxis={'categoryorder': 'total ascending'},
                          height=360, showlegend=False, margin=dict(l=0, r=0, t=10, b=0),
                          xaxis=dict(range=[0, cs['Sales'].max() * 1.18]))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        # авто-вывод
        _total_sales = df['Sales'].sum()
        _share = cs['Sales'].sum() / _total_sales * 100 if _total_sales else 0
        _nloss = int((cs['Profit'] < 0).sum())
        if _nloss:
            st.caption(f"**Вывод:** топ-20 клиентов дают {_share:.0f}% выручки; "
                       f"из них {_nloss} убыточны (красные) — стоит пересмотреть условия.")
        else:
            st.caption(f"**Вывод:** топ-20 клиентов дают {_share:.0f}% выручки, и все они прибыльны.")

# =========================================================
# РЯД 4: СТРУКТУРА (treemap) + ГЕОГРАФИЯ (бары + пузыри) — в одной строке
# =========================================================
col1, col2 = st.columns(2)
with col1:
    with st.container(border=True, key="plot2"):
        st.markdown('##### Структура продаж по категориям')
        _c = df.groupby('Category').agg(S=('Sales', 'sum'), P=('Profit', 'sum')).reset_index()
        _s = df.groupby(['Category', 'Sub-Category']).agg(
            S=('Sales', 'sum'), P=('Profit', 'sum')).reset_index().rename(columns={'Sub-Category': 'Sub'})

        ids, labels, parents, values, profits, margins = [], [], [], [], [], []
        root_s, root_p = _c['S'].sum(), _c['P'].sum()
        ids.append('Все'); labels.append('Все'); parents.append(''); values.append(root_s)
        profits.append(root_p); margins.append(root_p / root_s * 100 if root_s else 0)
        for r in _c.itertuples():
            ids.append(r.Category); labels.append(r.Category); parents.append('Все')
            values.append(r.S); profits.append(r.P); margins.append(r.P / r.S * 100 if r.S else 0)
        for r in _s.itertuples():
            ids.append(f'{r.Category}/{r.Sub}'); labels.append(r.Sub); parents.append(r.Category)
            values.append(r.S); profits.append(r.P); margins.append(r.P / r.S * 100 if r.S else 0)

        lim = max(abs(min(margins)), abs(max(margins))) or 1
        fig = go.Figure(go.Treemap(
            ids=ids, labels=labels, parents=parents, values=values, branchvalues='total',
            marker=dict(colors=margins, cmin=-lim, cmid=0, cmax=lim,
                        colorscale=[[0, COLOR_LOSS], [0.5, '#f1f5f9'], [1, COLOR_PROFIT]],
                        colorbar=dict(title='Маржа %', orientation='h', yanchor='top', y=-0.02,
                                      xanchor='center', x=0.5, thickness=12, len=0.7)),
            customdata=np.column_stack([profits, margins]),
            texttemplate='%{label}<br>%{value:$,.0f}',
            hovertemplate='%{label}<br>Выручка %{value:$,.0f}<br>Прибыль '
                          '%{customdata[0]:$,.0f}<br>Маржа %{customdata[1]:.0f}%<extra></extra>',
            textfont=dict(size=12), tiling=dict(pad=2)))
        fig.update_layout(template=TEMPLATE, height=420, margin=dict(l=0, r=0, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        st.caption('Площадь — выручка, цвет — маржа % (красный = убыток). Тап по категории — детализация.')
        # авто-вывод
        _cm = _c.set_index('Category')
        _cm['M'] = _cm['P'] / _cm['S'] * 100
        _sub = df.groupby('Sub-Category')['Profit'].sum()
        _losers = _sub[_sub < 0].sort_values().index.tolist()
        if len(_cm):
            _best = _cm['P'].idxmax()
            _lowm = _cm['M'].idxmin()
            if _losers:
                st.caption(f"**Вывод:** больше всего прибыли даёт «{_best}», "
                           f"а у «{_lowm}» маржа всего {_cm.loc[_lowm, 'M']:.0f}% — "
                           f"её тянут вниз убыточные подкатегории: {', '.join(_losers[:3])}.")
            else:
                st.caption(f"**Вывод:** больше всего прибыли даёт «{_best}»; убыточных подкатегорий нет.")

with col2:
    with st.container(border=True, key="plot9"):
        st.markdown('##### География: продажи и прибыль по штатам')
        geo = df.groupby('State').agg(Sales=('Sales', 'sum'), Profit=('Profit', 'sum')).reset_index()
        geo['Code'] = geo['State'].map(STATE_CODES)
        geo = geo.dropna(subset=['Code'])

        if geo.empty:
            st.info('Нет данных по штатам для выбранных фильтров.')
        else:
            limit = max(abs(geo['Profit'].min()), abs(geo['Profit'].max())) or 1
            tab_bar, tab_bub = st.tabs(['Бары', 'Пузыри'])

            # --- Вкладка 1: горизонтальные бары (основная, удобна на смартфоне) ---
            with tab_bar:
                top = geo.nlargest(15, 'Sales').copy()
                colors = [COLOR_PROFIT if p > 0 else COLOR_LOSS for p in top['Profit']]
                fig = go.Figure(go.Bar(
                    y=top['State'], x=top['Sales'], orientation='h', marker_color=colors,
                    text=top['Sales'].apply(lambda x: format_k(x, currency)),
                    textposition='outside', textfont=dict(size=11),
                    customdata=top['Profit'],
                    hovertemplate='%{y}<br>Выручка %{x:,.0f}<br>Прибыль %{customdata:,.0f}<extra></extra>'))
                fig.update_layout(template=TEMPLATE, yaxis={'categoryorder': 'total ascending'},
                                  height=420, showlegend=False, margin=dict(l=0, r=0, t=10, b=0),
                                  xaxis=dict(range=[0, top['Sales'].max() * 1.18]))
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
                st.caption('Длина — выручка, цвет — прибыль (зелёный) или убыток (красный). Топ-15 штатов.')

            # --- Вкладка 2: пузырьковая карта (размер = выручка, цвет = прибыль) ---
            with tab_bub:
                fig = px.scatter_geo(
                    geo, locations='Code', locationmode='USA-states',
                    size='Sales', color='Profit', scope='usa', size_max=26,
                    color_continuous_scale=[[0, COLOR_LOSS], [0.5, '#f1f5f9'], [1, COLOR_PROFIT]],
                    range_color=[-limit, limit], hover_name='State',
                    hover_data={'Code': False, 'Sales': ':,.0f', 'Profit': ':,.0f'},
                    labels={'Profit': 'Прибыль', 'Sales': 'Выручка'})
                fig.update_layout(height=420, margin=dict(l=0, r=0, t=0, b=0),
                                  coloraxis_colorbar=dict(title='Прибыль', orientation='h',
                                                          yanchor='top', y=0, xanchor='center', x=0.5,
                                                          thickness=12, len=0.7))
                fig.update_geos(fitbounds='locations', visible=True, showland=True,
                                landcolor='#f3f4f6', subunitcolor='#d1d5db', showsubunits=True)
                st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
                st.caption('Размер круга — выручка, цвет — прибыль (красный — убыток).')

            # авто-вывод (общий для блока)
            _best = geo.loc[geo['Profit'].idxmax(), 'State']
            _loss_big = geo[geo['Profit'] < 0].nlargest(3, 'Sales')['State'].tolist()
            if _loss_big:
                st.caption(f"**Вывод:** больше всего прибыли приносит {_best}; "
                           f"при этом {', '.join(_loss_big)} дают большие продажи, но убыточны.")
            else:
                st.caption(f"**Вывод:** больше всего прибыли приносит {_best}; убыточных штатов нет.")

# =========================================================
# РЯД 5: ПРОГНОЗ (динамический год) + БЭКТЕСТИНГ
# =========================================================
with st.container(border=True, key="plot11"):
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        # Строим НЕПРЕРЫВНЫЙ месячный ряд (важно при несмежных годах)
        s = df.groupby(df['Order Date'].dt.to_period('M'))['Sales'].sum()
        full_idx = pd.period_range(s.index.min(), s.index.max(), freq='M')
        gaps = len(full_idx) - len(s)
        s = s.reindex(full_idx, fill_value=0)
        mv = s.values.astype(float)
        n = len(mv)

        forecast_year = (s.index.max() + 1).year
        st.markdown(f'##### Прогноз продаж на {forecast_year} год')
        if gaps > 0:
            st.warning(f'Выбранные годы идут с разрывами — {gaps} мес. без данных заполнены нулями, '
                       'прогноз может быть неточным.')

        if n < 6:
            st.info('Недостаточно данных для прогноза (нужно ≥ 6 месяцев).')
        else:
            sp = 12 if n >= 24 else 6 if n >= 12 else 3
            model = ExponentialSmoothing(mv, seasonal_periods=sp, trend='add', seasonal='add').fit()
            fv = model.forecast(12)
            fd = pd.date_range(s.index.max().to_timestamp() + pd.DateOffset(months=1),
                               periods=12, freq='MS')

            fs = float(fv.sum())
            margin = (df['Profit'].sum() / df['Sales'].sum() * 100) if df['Sales'].sum() else 10
            fp = fs * margin / 100
            aov = df['Sales'].sum() / df['Order ID'].nunique() if df['Order ID'].nunique() else 500
            fo = fs / aov

            # сравнение с последним фактическим годом
            last_y = int(df['Year'].max())
            d_last = df[df['Year'] == last_y]
            d_s = (fs - d_last['Sales'].sum()) if len(d_last) else None
            d_p = (fp - d_last['Profit'].sum()) if len(d_last) else None
            d_o = (fo - d_last['Order ID'].nunique()) if len(d_last) else None

            k1, k2, k3 = st.columns(3)
            k1.metric('Прогноз выручки', format_k(fs, currency),
                      delta=format_k(d_s, currency) if d_s is not None else None)
            k2.metric('Прогноз прибыли', format_k(fp, currency),
                      delta=format_k(d_p, currency) if d_p is not None else None)
            k3.metric('Прогноз заказов', f'{fo:,.0f}',
                      delta=f'{d_o:+,.0f}' if d_o is not None else None)

            fig = go.Figure(layout=dict(template=TEMPLATE))
            fig.add_trace(go.Scatter(x=s.index.to_timestamp(), y=mv, mode='lines+markers',
                                     name='История', line=dict(color=COLOR_PROFIT, width=2)))
            fig.add_trace(go.Scatter(x=fd, y=fv, mode='lines', name='Прогноз',
                                     line=dict(color='#f59e0b', width=2, dash='dot')))
            fig.update_layout(height=360, hovermode='x unified', margin=dict(l=0, r=0, t=10, b=30),
                              legend=dict(orientation='h', yanchor='top', y=-0.18,
                                          xanchor='center', x=0.5))
            st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)

            st.markdown(f"""<div style="font-size:13px;color:#475569;line-height:1.7;margin-top:8px;">
            <b>📘 Как работает прогноз:</b> модель <b>Holt-Winters</b> раскладывает историю на
            тренд, сезонность и уровень и продлевает её на 12 месяцев ({forecast_year} год).
            Чем дальше горизонт — тем выше неопределённость; внешние факторы не учитываются.
            </div>""", unsafe_allow_html=True)

            # Бэктестинг
            if n >= 24:
                st.markdown('##### Бэктестинг: проверка точности')
                train, test = mv[:-12], mv[-12:]
                sp_bt = 12 if len(train) >= 24 else 6 if len(train) >= 12 else 3
                mb = ExponentialSmoothing(train, seasonal_periods=sp_bt,
                                          trend='add', seasonal='add').fit()
                fb = mb.forecast(12)
                mae = np.mean(np.abs(test - fb))
                with np.errstate(divide='ignore', invalid='ignore'):
                    mape_arr = np.abs((test - fb) / np.where(test == 0, np.nan, test))
                mape = np.nanmean(mape_arr) * 100
                td = s.index[-12:].to_timestamp()
                figb = go.Figure(layout=dict(template=TEMPLATE))
                figb.add_trace(go.Scatter(x=td, y=test, mode='lines+markers', name='Факт',
                                          line=dict(color=COLOR_PROFIT, width=2)))
                figb.add_trace(go.Scatter(x=td, y=fb, mode='lines+markers', name='Прогноз',
                                          line=dict(color='#f59e0b', width=2, dash='dash')))
                figb.update_layout(height=320, hovermode='x unified', margin=dict(l=0, r=0, t=10, b=30),
                                   legend=dict(orientation='h', yanchor='top', y=-0.2,
                                               xanchor='center', x=0.5))
                st.plotly_chart(figb, use_container_width=True, config=PLOTLY_CONFIG)
                st.caption(f'MAE: {format_k(mae, currency)} · MAPE: {mape:.1f}% '
                           '(средняя ошибка прогноза)')
            else:
                st.info('Для бэктестинга нужно ≥ 24 месяцев. Выберите больше лет.')
    except ImportError:
        st.error('Не установлен statsmodels. Добавьте его в requirements.txt')
    except Exception as e:
        st.error(f'Не удалось построить прогноз: {e}')

# =========================================================
# РЯД 6: ЭКСПОРТ
# =========================================================
with st.container(border=True, key="plot12"):
    st.markdown('##### Экспорт данных')
    e1, e2 = st.columns(2)
    with e1:
        st.download_button('📥 Скачать CSV', df.to_csv(index=False).encode('utf-8'),
                           'superstore_filtered.csv', 'text/csv', use_container_width=True)
    with e2:
        try:
            buf = BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as w:
                df.to_excel(w, sheet_name='Superstore', index=False)
            st.download_button('📥 Скачать Excel', buf.getvalue(), 'superstore_filtered.xlsx',
                               'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                               use_container_width=True)
        except Exception:
            st.warning('Excel недоступен (нет openpyxl)')
    st.caption(f'Строк: {len(df):,} · Заказов: {df["Order ID"].nunique():,} · '
               f'Клиентов: {df["Customer ID"].nunique():,} · Продуктов: {df["Product Name"].nunique():,}')
    st.dataframe(df, use_container_width=True, height=420)
