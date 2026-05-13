import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import numpy as np
from io import BytesIO
from datetime import datetime, timedelta

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(page_title="BI Data analysis", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

# =========================================================
# CSS
# =========================================================
st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    }
    [data-testid="stSidebar"] { display: none !important; }
    .main .block-container { max-width: 1200px; padding-top: 20px; }

    .main-header { font-size: 42px; font-weight: 400; color: #1a1a1a; margin-bottom: 8px; }

    .year-summary { display: flex; gap: 40px; flex-wrap: wrap; margin: 16px 0 24px 0; }

    @media (max-width: 768px) {
        .year-stat {
            width: 100% !important;
            text-align: left !important;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #e5e7eb;
        }
        .year-stat .value { font-size: 28px !important; }
        .year-stat .label { font-size: 14px !important; }
    }
    .year-stat { text-align: center; }
    .year-stat .value { font-size: 42px; font-weight: 400; color: #1a1a1a; }    
    .year-stat .label { font-size: 12px; color: #6b7280; text-transform: uppercase; }

    /* Тонкие разделители вместо рамок */
    .st-key-plot1, .st-key-plot2, .st-key-plot3, .st-key-plot4,
    .st-key-plot5, .st-key-plot6, .st-key-plot7, .st-key-plot8,
    .st-key-plot9, .st-key-plot10, .st-key-plot11, .st-key-plot12 {
        border: none !important;
        border-bottom: 1px solid #e5e7eb !important;
        border-radius: 0 !important;
        padding: 12px 8px !important;
        margin-bottom: 0 !important;
    }
    /* Принудительная светлая тема для всех */
    [data-testid="stAppViewContainer"] {
        background-color: #ffffff !important;
        color: #1a1a1a !important;
    }
    [data-testid="stHeader"] {
        background-color: #ffffff !important;
    }
    [data-testid="stToolbar"] {
        background-color: #ffffff !important;
    }
    h3, h5 { font-size: 14px; font-weight: 600; color: #1a1a1a; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# CONSTANTS
# =========================================================
MONTH_NAMES = {
    1: 'Янв', 2: 'Фев', 3: 'Мар', 4: 'Апр', 5: 'Май', 6: 'Июн',
    7: 'Июл', 8: 'Авг', 9: 'Сен', 10: 'Окт', 11: 'Ноя', 12: 'Дек'
}

def safe_div(a, b): return a / b if b not in [0, None, np.nan] else 0

def format_k(value, currency):
    if abs(value) >= 1000: return f"{currency}{value / 1000:,.0f}K"
    return f"{currency}{value:,.0f}"

# =========================================================
# EXCHANGE RATES
# =========================================================
@st.cache_data(ttl=86400, show_spinner="Загрузка курсов...")
def get_exchange_rates():
    rates = {}
    for year in [2014, 2015, 2016, 2017]:
        for month in [1, 4, 7, 10]:
            url = f"https://www.cbr-xml-daily.ru/archive/{year}-{month:02d}-01/daily_json.js"
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    rates[f"{year}-{month:02d}-01"] = resp.json()['Valute']['USD']['Value']
            except:
                pass
    return rates

@st.cache_data(show_spinner=False)
def load_data():
    df = pd.read_csv('Sample - Superstore.csv', encoding='latin1')
    df['Order Date'] = pd.to_datetime(df['Order Date'])
    df['Ship Date'] = pd.to_datetime(df['Ship Date'])
    df['Year'] = df['Order Date'].dt.year
    df['Month'] = df['Order Date'].dt.month
    df['Month Name'] = df['Month'].map(MONTH_NAMES)
    df['Processing Days'] = (df['Ship Date'] - df['Order Date']).dt.days
    df['Margin %'] = np.where(df['Sales'] != 0, (df['Profit'] / df['Sales']) * 100, 0).round(1)
    return df

def convert_to_rub(df, rates):
    t = df.copy()
    t['Month_Key'] = t['Order Date'].dt.strftime('%Y-%m-01')
    t['Rate'] = t['Month_Key'].map(rates).fillna(np.mean(list(rates.values())) if rates else 60)
    t['Sales'] *= t['Rate']
    t['Profit'] *= t['Rate']
    return t

rates = get_exchange_rates()
df_raw = load_data()

# =========================================================
# HEADER
# =========================================================
st.markdown('<div class="main-header">Анализ продаж</div>', unsafe_allow_html=True)

# =========================================================
# TOP BAR
# =========================================================
c1, c2 = st.columns([3, 1])
with c1:
    st.markdown("**Сравнение по годам**")
    years = st.pills("Годы для сравнения", options=sorted(df_raw['Year'].unique()),
                     default=sorted(df_raw['Year'].unique()), selection_mode="multi", key="y",
                     label_visibility="collapsed")
with c2:
    show_rub = st.toggle("🇷🇺 RUB", value=False)

df = df_raw.copy()
if years: df = df[df['Year'].isin(years)]
currency = '₽' if show_rub else '$'
if show_rub: df = convert_to_rub(df, rates)
if df.empty: st.warning('Нет данных.'), st.stop()

sales_sum = df['Sales'].sum()
profit_sum = df['Profit'].sum()
orders = df['Order ID'].nunique()
customers = df['Customer ID'].nunique()

# =========================================================
# YEAR SUMMARY
# =========================================================
sales_delta = profit_delta = orders_delta = customers_delta = 0

if len(years) >= 2:
    selected_sorted = sorted(years)
    current_year = selected_sorted[-1]
    prev_year = selected_sorted[-2]
    df_prev = df_raw[df_raw['Year'] == prev_year]
    if show_rub: df_prev = convert_to_rub(df_prev, rates)
    if len(df_prev) > 0:
        prev_sales = df_prev['Sales'].sum()
        prev_profit = df_prev['Profit'].sum()
        prev_orders = df_prev['Order ID'].nunique()
        prev_customers = df_prev['Customer ID'].nunique()
        sales_delta = sales_sum - prev_sales
        profit_delta = profit_sum - prev_profit
        orders_delta = orders - prev_orders
        customers_delta = customers - prev_customers

def delta_html(value, currency='$'):
    if len(years) < 2: return ''
    if value > 0: color, bg, arrow, sign = '#22c55e', '#f0fdf4', '↑', '+'
    elif value < 0: color, bg, arrow, sign = '#ef4444', '#fef2f2', '↓', ''
    else: return ''
    formatted = format_k(abs(value), currency) if abs(value) >= 1000 else f'{currency}{abs(value):,.0f}'
    return f'<span style="color:{color};background:{bg};padding:2px 8px;border-radius:4px;font-size:13px;">{arrow} {sign}{formatted}</span>'

html_parts = ['<div class="year-summary">']
for label, val, d, cur in [
    ('Выручка', format_k(sales_sum, currency), sales_delta, currency),
    ('Прибыль', format_k(profit_sum, currency), profit_delta, currency),
    ('Заказы', f'{orders:,}', orders_delta, ''),
    ('Клиенты', f'{customers:,}', customers_delta, '')
]:
    html_parts.append(f'<div class="year-stat"><div class="label">{label}</div><div class="value">{val}</div>')
    delta = delta_html(d, cur)
    if delta: html_parts.append(delta)
    html_parts.append('</div>')
html_parts.append('</div>')
st.markdown('\n'.join(html_parts), unsafe_allow_html=True)

# =========================================================
# monthly
# =========================================================
monthly = df.groupby(df['Order Date'].dt.to_period('M')).agg({'Sales': 'sum', 'Profit': 'sum'}).reset_index()
monthly['Order Date'] = monthly['Order Date'].astype(str)
plotly_template = 'plotly'
plotly_config = {'staticPlot': True, 'responsive': True, 'displayModeBar': False, 'displaylogo': False}

# =========================================================
# РЯД 1: Продажи/Прибыль + Структура продаж
# =========================================================
col1, col2 = st.columns(2)
with col1:
    with st.container(border=True, key="plot1"):
        st.markdown('##### Продажи и прибыль по месяцам')
        fig = go.Figure(layout=dict(template=plotly_template))
        fig.add_trace(go.Scatter(x=monthly['Order Date'], y=monthly['Sales'], name='Продажи', fill='tozeroy', line=dict(color='#1a56db')))
        fig.add_trace(go.Scatter(x=monthly['Order Date'], y=monthly['Profit'], name='Прибыль', fill='tozeroy', line=dict(color='#00CC96')))
        total_months = len(monthly)
        tick_spacing = 1 if total_months <= 12 else 2 if total_months <= 24 else 3 if total_months <= 36 else 4
        tick_indices = list(range(0, total_months, tick_spacing))
        tick_texts = [monthly['Order Date'].iloc[i] for i in tick_indices]
        tick_vals = [monthly['Order Date'].iloc[i] for i in tick_indices]
        fig.update_layout(
            height=400, hovermode='x unified', margin=dict(l=0, r=0, t=20, b=30),
            xaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)', tickmode='array', tickvals=tick_vals, ticktext=tick_texts),
            yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.1)'),
            legend=dict(orientation='h', yanchor='top', y=-0.2, xanchor='center', x=0.5)
        )
        st.plotly_chart(fig, width='stretch', config=plotly_config)
        st.caption('Цветовая дифференциация по прибыльности категорий')

with col2:
    with st.container(border=True, key="plot2"):
        st.markdown('##### Структура продаж по категориям')
        sd = df.groupby(['Category', 'Sub-Category']).agg(Sales=('Sales', 'sum'), Profit=('Profit', 'sum')).reset_index()
        fig = px.sunburst(sd, path=['Category', 'Sub-Category'], values='Sales', color='Profit',
                          template=plotly_template, color_continuous_scale=[[0, '#EF553B'], [0.5, '#fecaca'], [0.5, '#bbf7d0'], [1, '#00CC96']],
                          range_color=[sd['Profit'].min(), sd['Profit'].max()], maxdepth=2)
        fig.update_traces(textinfo='label+percent parent', textfont=dict(size=12))
        fig.update_layout(height=400, margin=dict(l=0, r=0, t=20, b=0), showlegend=False, coloraxis_showscale=False)
        st.plotly_chart(fig, width='stretch', config=plotly_config)
        st.caption('Цветовая дифференциация по прибыльности категорий')

# =========================================================
# РЯД 2: Сезонность + Pareto
# =========================================================
col1, col2 = st.columns(2)
with col1:
    with st.container(border=True, key="plot3"):
        st.markdown('##### Сезонность')
        hd = df.pivot_table(values='Sales', index='Month', columns='Year', aggfunc='sum')
        hd.index = [MONTH_NAMES[m] for m in hd.index]
        fig = px.imshow(hd, aspect='auto', color_continuous_scale=[[0, '#e8f0ff'], [1, '#1a56db']], template=plotly_template)
        fig.update_traces(text=[[f"{currency}{v/1000:,.0f}K" for v in r] for r in hd.values], texttemplate="%{text}", textfont=dict(size=11))
        fig.update_xaxes(side='top', title='Год', tickformat='d', dtick=1)
        fig.update_layout(height=400, margin=dict(l=0, r=0, t=20, b=0), coloraxis_showscale=True,
                          coloraxis_colorbar=dict(title='Продажи', orientation='h', yanchor='bottom', y=-0.3, xanchor='center', x=0.5, len=0.8))
        st.plotly_chart(fig, width='stretch', config=plotly_config)

with col2:
    with st.container(border=True, key="plot9"):
        st.markdown('##### Парето: концентрация прибыли')
        pareto = df.groupby('Product Name')['Profit'].sum().sort_values(ascending=False).reset_index()
        total_profit = pareto['Profit'].sum()
        pareto['Cumsum %'] = pareto['Profit'].cumsum() / total_profit * 100
        pareto['N'] = range(1, len(pareto) + 1)
        products_80 = (pareto['Cumsum %'] <= 80).sum()
        pareto_short = pareto.head(products_80)
        loss = pareto[pareto['Profit'] <= 0]

        fig = go.Figure()
        fig.add_trace(go.Bar(x=pareto_short['N'], y=pareto_short['Profit'], name='Прибыль',
                             marker_color=['#22c55e' if x > 0 else '#ef4444' for x in pareto_short['Profit']],
                             hovertemplate='Продукт #%{x}<br>Прибыль: %{y:,.0f}<extra></extra>'))
        fig.add_trace(go.Scatter(x=pareto_short['N'], y=pareto_short['Cumsum %'], mode='lines',
                                 name='Накопительно %', yaxis='y2', line=dict(width=3, color='#636EFA')))
        fig.add_hline(y=80, line_dash="dash", opacity=0.5, line_color="gray", yref='y2')
        fig.update_layout(template=plotly_template, height=400, margin=dict(l=0, r=0, t=20, b=0),
                          xaxis=dict(title=f'Продукты (первые {products_80} из {len(pareto)})', showgrid=False),
                          yaxis=dict(title='Прибыль', showgrid=False),
                          yaxis2=dict(title='Накопительный %', overlaying='y', side='right', range=[0, 100],
                                     tickmode='linear', tick0=0, dtick=20, showgrid=False),
                          legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1), bargap=0.3)
        st.plotly_chart(fig, width='stretch', config=plotly_config)

        c1, c2, c3 = st.columns(3)
        c1.metric('Всего продуктов', f'{len(pareto)}')
        c2.metric(f'Дают 80% прибыли', f'{products_80}')
        c3.metric('Убыточных продуктов', f'{len(loss)}')

# =========================================================
# РЯД 3: Топ-10 + Топ-10 убыточных
# =========================================================
col1, col2 = st.columns(2)
with col1:
    with st.container(border=True, key="plot5"):
        st.markdown('##### Топ-10 продуктов по выручке')
        t10 = df.groupby('Product Name')['Sales'].sum().nlargest(10).reset_index()
        t10['Product Name'] = t10['Product Name'].apply(lambda x: x[:20] + '...' if len(x) > 20 else x)
        fig = px.bar(t10, x='Sales', y='Product Name', orientation='h', template=plotly_template,
                     color='Sales', color_continuous_scale=[[0, '#e8f0ff'], [1, '#1a56db']],
                     labels={'Sales': 'Продажи', 'Product Name': ''})
        fig.update_traces(text=t10['Sales'].apply(lambda x: f'{format_k(x, currency)}'), textposition='outside', textfont=dict(size=11))
        fig.update_layout(
            yaxis={'categoryorder': 'total ascending', 'automargin': True, 'tickfont': dict(size=10)},
            xaxis=dict(range=[0, t10['Sales'].max() * 1.15]),
            coloraxis_showscale=False,
            height=400,
            margin=dict(l=5, r=10, t=20, b=0)
        )
        st.plotly_chart(fig, width='stretch', config=plotly_config)

with col2:
    with st.container(border=True, key="plot6"):
        st.markdown('##### Топ-10 убыточных продуктов')
        l10 = df.groupby('Product Name')['Profit'].sum().nsmallest(10).reset_index()
        l10['Product Name'] = l10['Product Name'].apply(lambda x: x[:20] + '...' if len(x) > 20 else x)
        fig = px.bar(l10, x='Profit', y='Product Name', orientation='h', template=plotly_template,
                     color_discrete_sequence=['#EF553B'] * 10,
                     labels={'Profit': 'Прибыль', 'Product Name': ''})
        fig.update_traces(text=l10['Profit'].apply(lambda x: f'-{format_k(abs(x), currency)}'), textposition='outside', textfont=dict(size=11))
        fig.update_layout(
            yaxis={'categoryorder': 'total descending', 'automargin': True, 'tickfont': dict(size=10)},
            xaxis=dict(range=[l10['Profit'].min() * 1.15, 0], tickmode='array',
                       tickvals=[-8000, -6000, -4000, -2000, 0], ticktext=['-8K', '-6K', '-4K', '-2K', '0']),
            coloraxis_showscale=False,
            height=400,
            margin=dict(l=5, r=10, t=20, b=0)
        )
        st.plotly_chart(fig, width='stretch', config=plotly_config)

# =========================================================
# РЯД 4: Скидки + Топ-20
# =========================================================
col1, col2 = st.columns(2)
with col1:
    with st.container(border=True, key="plot7"):
        st.markdown('##### Скидки vs Прибыль')
        dp = df.copy()
        disc_tab1, disc_tab2 = st.tabs(['График', 'Таблица'])
        with disc_tab1:
            dp['Скидка группа'] = pd.cut(dp['Discount'], bins=[-0.01, 0.00, 0.20, 0.40, 0.60, 0.80],
                                         labels=['0%', '0–20%', '20–40%', '40–60%', '60–80%'], include_lowest=True)
            avg_line = dp.groupby('Скидка группа', observed=False).agg(Sales=('Sales', 'sum'), Profit=('Profit', 'sum'), Orders=('Order ID', 'nunique')).reset_index()
            avg_line['Рентабельность %'] = avg_line['Profit'] / avg_line['Sales'] * 100
            colors_line = ['#00CC96' if x > 0 else '#EF553B' for x in avg_line['Рентабельность %']]
            fig = go.Figure()
            fig.add_trace(go.Bar(x=avg_line['Скидка группа'], y=avg_line['Рентабельность %'], marker_color=colors_line,
                                 text=avg_line['Рентабельность %'].apply(lambda x: f'{x:+.1f}%'), textposition='outside'))
            fig.add_hline(y=0, line_dash="dash", line_color="#d1d5db", opacity=0.4)
            fig.update_layout(height=400, xaxis=dict(title='Размер скидки'), yaxis=dict(title='Прибыль %', ticksuffix='%'),
                              margin=dict(l=0, r=0, t=20, b=0), template=plotly_template)
            st.plotly_chart(fig, width='stretch', config=plotly_config)
            st.caption('С ростом скидки рентабельность падает. Группы 20–40% и выше — убыточны.')
        with disc_tab2:
            dp['Скидка группа'] = pd.cut(dp['Discount'], bins=[-0.01, 0.00, 0.20, 0.40, 0.60, 0.80],
                                         labels=['0%', '0–20%', '20–40%', '40–60%', '60–80%'], include_lowest=True)
            table_data = dp.groupby('Скидка группа', observed=False).agg(Выручка=('Sales', 'sum'), Прибыль=('Profit', 'sum'), Заказов=('Order ID', 'nunique')).reset_index()
            table_data['Рентабельность %'] = table_data['Прибыль'] / table_data['Выручка'] * 100
            table_data['Выручка'] = table_data['Выручка'].apply(lambda x: format_k(x, currency))
            table_data['Прибыль'] = table_data['Прибыль'].apply(lambda x: format_k(x, currency))
            table_data['Рентабельность %'] = table_data['Рентабельность %'].apply(lambda x: f'{x:+.1f}%')
            st.markdown("<style>.st-key-plot7 table td, .st-key-plot7 table th {text-align:center!important;}</style>", unsafe_allow_html=True)
            st.dataframe(table_data, use_container_width=True, hide_index=True)

with col2:
    with st.container(border=True, key="plot8"):
        st.markdown('##### Топ-20 клиентов')
        cs = df.groupby('Customer ID').agg(Customer_Name=('Customer Name', 'first'), Total_Sales=('Sales', 'sum'),
                                           Total_Profit=('Profit', 'sum'), Orders=('Order ID', 'nunique')).reset_index()
        tc = cs.nlargest(20, 'Total_Sales')
        colors = ['#00CC96' if x > 0 else '#EF553B' for x in tc['Total_Profit']]
        fig = go.Figure()
        fig.add_trace(go.Bar(y=tc['Customer_Name'], x=tc['Total_Sales'], orientation='h', marker_color=colors,
                             text=tc['Total_Sales'].apply(lambda x: f'{format_k(x, currency)}'), textposition='outside', textfont=dict(size=11)))
        fig.update_layout(yaxis={'categoryorder': 'total ascending'}, height=400, showlegend=False,
                          margin=dict(l=0, r=0, t=20, b=0), xaxis=dict(range=[0, tc['Total_Sales'].max() * 1.15]), template=plotly_template)
        st.plotly_chart(fig, width='stretch', config=plotly_config)
        st.caption('Красным — покупатели с отрицательной прибылью (убыток)')

# =========================================================
# РЯД 5: ПРОГНОЗ + БЭКТЕСТИНГ
# =========================================================
with st.container(border=True, key="plot11"):
    st.markdown('##### Прогноз продаж на 2018 год')
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing
        mp = df.groupby(df['Order Date'].dt.to_period('M'))['Sales'].sum().reset_index()
        mp['Order Date'] = mp['Order Date'].astype(str)
        mv = mp['Sales'].values.astype(float)
        n_months = len(mv)
        sp = 12 if n_months >= 24 else 6 if n_months >= 12 else 3 if n_months >= 6 else 1
        model = ExponentialSmoothing(mv, seasonal_periods=sp, trend='add', seasonal='add').fit()
        fv = model.forecast(12)
        ld = pd.to_datetime(mp['Order Date'].iloc[-1])
        fd = pd.date_range(start=ld + pd.DateOffset(months=1), periods=12, freq='MS')
        fs = fv.sum()
        am = (df['Profit'].sum() / df['Sales'].sum() * 100) if df['Sales'].sum() > 0 else 10
        fp = fs * am / 100
        ac = df['Sales'].sum() / df['Order ID'].nunique() if df['Order ID'].nunique() > 0 else 500
        fo = fs / ac
        c1, c2, c3 = st.columns(3)
        c1.metric('Прогноз выручки', format_k(fs, currency))
        c2.metric('Прогноз прибыли', format_k(fp, currency))
        c3.metric('Прогноз заказов', f'{fo:,.0f}')
        fig = go.Figure(layout=dict(template=plotly_template))
        fig.add_trace(go.Scatter(x=fd, y=fv, mode='lines', name='Прогноз', line=dict(color='#FFA500', width=2)))
        fig.add_trace(go.Scatter(x=pd.to_datetime(mp['Order Date']), y=mv, mode='markers+lines', name='История', line=dict(color='#00CC96', width=2)))
        fig.update_layout(height=400, hovermode='x unified', margin=dict(l=0, r=0, t=20, b=30),
                          legend=dict(orientation='h', yanchor='top', y=-0.2, xanchor='center', x=0.5))
        st.plotly_chart(fig, width='stretch', config=plotly_config)
        st.markdown("""<div style="font-size:13px; color:#475569; line-height:1.7; margin-top:12px;">
        <b>📘 Как работает прогноз:</b><br><br>
        • Используется модель <b>Holt-Winters Exponential Smoothing</b> — статистический метод прогнозирования временных рядов.<br><br>
        • Модель раскладывает историю продаж на три компонента: <b>тренд</b>, <b>сезонность</b> и <b>уровень</b>.<br><br>
        • Обучается на данных за выбранные годы и предсказывает на 12 месяцев вперёд — на 2018 год.<br><br>
        • Чем дальше горизонт прогноза — тем выше неопределённость. Модель не учитывает внешние факторы.<br><br>
        • Рекомендуется обновлять прогноз ежемесячно.
        </div>""", unsafe_allow_html=True)
        if len(mv) >= 24:
            st.markdown('##### Бэктестинг: проверка точности')
            train, test = mv[:-12], mv[-12:]
            sp_bt = 12 if len(train) >= 24 else 6 if len(train) >= 12 else 3
            mb = ExponentialSmoothing(train, seasonal_periods=sp_bt, trend='add', seasonal='add').fit()
            fb = mb.forecast(12)
            mae = np.mean(np.abs(test - fb))
            mape = np.mean(np.abs((test - fb) / test)) * 100
            td = pd.to_datetime(mp['Order Date'].iloc[-12:])
            fig_bt = go.Figure(layout=dict(template=plotly_template))
            fig_bt.add_trace(go.Scatter(x=td, y=test, mode='lines+markers', name='Факт', line=dict(color='#00CC96', width=2)))
            fig_bt.add_trace(go.Scatter(x=td, y=fb, mode='lines+markers', name='Прогноз', line=dict(color='#FFA500', width=2, dash='dash')))
            fig_bt.update_layout(height=350, hovermode='x unified', margin=dict(l=0, r=0, t=20, b=30),
                                 legend=dict(orientation='h', yanchor='top', y=-0.2, xanchor='center', x=0.5))
            st.plotly_chart(fig_bt, width='stretch', config=plotly_config)
            st.caption(f'MAE: {format_k(mae, currency)} | MAPE: {mape:.1f}%')
            st.caption('Бэктестинг проверяет точность модели: обучаем на прошлых периодах и сравниваем прогноз с реальными данными.')
        else:
            st.info('Для бэктестинга необходимо минимум 24 месяца данных. Выберите больше годов.')
    except Exception as e:
        st.error(f'Ошибка: {e}')

# =========================================================
# РЯД 6: ЭКСПОРТ
# =========================================================
with st.container(border=True, key="plot12"):
    st.markdown('##### Экспорт')
    c1, c2 = st.columns(2)
    with c1:
        st.download_button('📥 CSV', df.to_csv(index=False).encode('utf-8'), 'superstore_filtered.csv', 'text/csv')
    with c2:
        try:
            o = BytesIO()
            with pd.ExcelWriter(o, engine='openpyxl') as w: df.to_excel(w, sheet_name='Superstore', index=False)
            st.download_button('📥 Excel', o.getvalue(), 'superstore_filtered.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        except: st.warning('Excel недоступен')
    st.caption(f'Строк: {len(df):,} | Заказов: {df["Order ID"].nunique():,} | Клиентов: {df["Customer ID"].nunique():,} | Продуктов: {df["Product Name"].nunique():,}')
    st.dataframe(df, use_container_width=True, height=500)