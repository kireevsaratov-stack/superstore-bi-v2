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
    .main-subtitle { font-size: 14px; color: #6b7280; margin-bottom: 20px; }

    .year-summary { display: flex; gap: 40px; flex-wrap: wrap; margin: 16px 0; }
    .year-stat { text-align: center; }
    .year-stat .value { font-size: 42px; font-weight: 400; color: #1a1a1a; }    
    .year-stat .label { font-size: 12px; color: #6b7280; text-transform: uppercase; }

    .top-bar {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 16px 24px;
        margin-bottom: 20px;
    }

    /* Тонкие светлые рамки */
    .st-key-plot1, .st-key-plot2, .st-key-plot3, .st-key-plot4,
    .st-key-plot5, .st-key-plot6, .st-key-plot7, .st-key-plot8,
    .st-key-plot9, .st-key-plot10, .st-key-plot11, .st-key-plot12 {
        border: 1px solid #e5e7eb !important;
        border-radius: 10px !important;
        padding: 16px !important;
        margin-bottom: 12px !important;
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
    pp = df.groupby('Product Name')['Profit'].sum().sort_values(ascending=False)
    loss = pp <= 0
    top30 = pp[pp > 0].head(30)
    abc = pd.Series('B - Середняки', index=pp.index)
    abc[top30.index] = 'A - Золото'
    abc[loss] = 'C - Балласт'
    df['ABC'] = df['Product Name'].map(abc)
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
st.markdown('<div class="main-header">Superstore Sales</div>', unsafe_allow_html=True)

# =========================================================
# TOP BAR
# =========================================================

c1, c2 = st.columns([3, 1])
with c1:
    st.markdown("**Compare different years**")
    years = st.pills("Years to compare", options=sorted(df_raw['Year'].unique()),
                     default=sorted(df_raw['Year'].unique()), selection_mode="multi", key="y",
                     label_visibility="collapsed")
with c2:
    show_rub = st.toggle("🇷🇺 RUB", value=False)


df = df_raw.copy()
if years: df = df[df['Year'].isin(years)]
currency = '₽' if show_rub else '$'
if show_rub: df = convert_to_rub(df, rates)
if df.empty: st.warning('Нет данных.'), st.stop()

sales_sum = df['Sales'].sum();
profit_sum = df['Profit'].sum()
orders = df['Order ID'].nunique();
customers = df['Customer ID'].nunique()

# =========================================================
# YEAR SUMMARY (как в demo: заголовок → цифра → динамика)
# =========================================================
# Считаем динамику к предыдущему году
if len(years) >= 2:
    # Берём последние два выбранных года
    selected_sorted = sorted(years)
    current_year = selected_sorted[-1]
    prev_year = selected_sorted[-2]

    df_prev = df_raw[df_raw['Year'] == prev_year]
    if show_rub: df_prev = convert_to_rub(df_prev, rates)
    prev_sales = df_prev['Sales'].sum()
    prev_profit = df_prev['Profit'].sum()
    prev_orders = df_prev['Order ID'].nunique()
    prev_customers = df_prev['Customer ID'].nunique()

    sales_delta = sales_sum - prev_sales
    profit_delta = profit_sum - prev_profit
    orders_delta = orders - prev_orders
    customers_delta = customers - prev_customers
else:
    sales_delta = profit_delta = orders_delta = customers_delta = 0


def delta_html(value, currency=''):
    if len(years) < 2:
        return ''  # ← не показываем дельту если выбран 1 год
    if value > 0:
        color = '#22c55e'
        bg = '#f0fdf4'
        arrow = '↑'
        sign = '+'
    elif value < 0:
        color = '#ef4444'
        bg = '#fef2f2'
        arrow = '↓'
        sign = ''
    else:
        return ''  # ← не показываем если 0

    formatted = format_k(abs(value), currency) if abs(value) >= 1000 else f'{currency}{abs(value):,.0f}'
    return f'<span style="color:{color};background:{bg};padding:2px 8px;border-radius:4px;font-size:13px;">{arrow} {sign}{formatted}</span>'


st.markdown(f"""
<div class="year-summary">
    <div class="year-stat">
        <div class="label">Total Sales</div>
        <div class="value">{format_k(sales_sum, currency)}</div>
        {delta_html(sales_delta, currency) if len(years) >= 2 else ''}
    </div>
    <div class="year-stat">
        <div class="label">Total Profit</div>
        <div class="value">{format_k(profit_sum, currency)}</div>
        {delta_html(profit_delta, currency) if len(years) >= 2 else ''}
    </div>
    <div class="year-stat">
        <div class="label">Orders</div>
        <div class="value">{orders:,}</div>
        {delta_html(orders_delta) if len(years) >= 2 else ''}
    </div>
    <div class="year-stat">
        <div class="label">Customers</div>
        <div class="value">{customers:,}</div>
        {delta_html(customers_delta) if len(years) >= 2 else ''}
    </div>
</div>
""", unsafe_allow_html=True)

# =========================================================
# monthly
# =========================================================
monthly = df.groupby(df['Order Date'].dt.to_period('M')).agg({'Sales': 'sum', 'Profit': 'sum'}).reset_index()
monthly['Order Date'] = monthly['Order Date'].astype(str)
plotly_template = 'plotly'
plotly_config = {'staticPlot': True, 'responsive': True, 'displayModeBar': False, 'displaylogo': False}

# =========================================================
# РЯД 1
# =========================================================
col1, col2 = st.columns(2)
with col1:
    with st.container(border=True, key="plot1"):
        st.markdown(f"""
        <div class="year-summary">
            <div class="year-stat">
                <div class="label">Total Sales</div>
                <div class="value">{format_k(sales_sum, currency)}</div>
                {delta_html(sales_delta, currency) if len(years) >= 2 else ''}
            </div>
            <div class="year-stat">
                <div class="label">Total Profit</div>
                <div class="value">{format_k(profit_sum, currency)}</div>
                {delta_html(profit_delta, currency) if len(years) >= 2 else ''}
            </div>
            <div class="year-stat">
                <div class="label">Orders</div>
                <div class="value">{orders:,}</div>
                {delta_html(orders_delta) if len(years) >= 2 else ''}
            </div>
            <div class="year-stat">
                <div class="label">Customers</div>
                <div class="value">{customers:,}</div>
                {delta_html(customers_delta) if len(years) >= 2 else ''}
            </div>
        </div>
        """, unsafe_allow_html=True)
with col2:
    with st.container(border=True, key="plot2"):
        st.markdown('##### Sales distribution')
        cat = df.groupby('Category').agg(Sales=('Sales', 'sum')).reset_index()
        fig = go.Figure()
        fig.add_trace(go.Pie(
            labels=cat['Category'], values=cat['Sales'],
            hole=0.6,
            textinfo='label+percent',
            texttemplate='%{label}<br>%{percent:.1%}',
            marker=dict(colors=px.colors.qualitative.Pastel[:3], line=dict(color='white', width=2)),
            textfont=dict(size=14),
            sort=False
        ))
        fig.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20), showlegend=False)
        st.plotly_chart(fig, width='stretch', config=plotly_config)

# =========================================================
# РЯД 2: Сезонность + Гео
# =========================================================
col1, col2 = st.columns(2)
with col1:
    with st.container(border=True, key="plot3"):
        st.markdown('##### Сезонность')
        hd = df.pivot_table(values='Sales', index='Month', columns='Year', aggfunc='sum')
        hd.index = [MONTH_NAMES[m] for m in hd.index]
        fig = px.imshow(hd, aspect='auto', color_continuous_scale='Blues', template=plotly_template)
        fig.update_traces(text=[[f"{currency}{v:,.0f}" for v in r] for r in hd.values], texttemplate="%{text}",
                          textfont=dict(size=11))
        fig.update_xaxes(side='top', title='', tickformat='d', dtick=1)
        fig.update_layout(coloraxis_showscale=False, height=400, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, width='stretch', config=plotly_config)
with col2:
    with st.container(border=True, key="plot4"):
        st.markdown('##### География')
        abbr = {'Alabama': 'AL', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA', 'Colorado': 'CO',
                'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL', 'Georgia': 'GA', 'Idaho': 'ID',
                'Illinois': 'IL', 'Indiana': 'IN', 'Iowa': 'IA', 'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA',
                'Maine': 'ME', 'Maryland': 'MD', 'Massachusetts': 'MA', 'Michigan': 'MI', 'Minnesota': 'MN',
                'Mississippi': 'MS', 'Missouri': 'MO', 'Montana': 'MT', 'Nebraska': 'NE', 'Nevada': 'NV',
                'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC',
                'North Dakota': 'ND', 'Ohio': 'OH', 'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA',
                'Rhode Island': 'RI', 'South Carolina': 'SC', 'South Dakota': 'SD', 'Tennessee': 'TN', 'Texas': 'TX',
                'Utah': 'UT', 'Vermont': 'VT', 'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV',
                'Wisconsin': 'WI', 'Wyoming': 'WY', 'District of Columbia': 'DC'}
        sd = df.groupby('State').agg({'Sales': 'sum', 'Profit': 'sum'}).reset_index()
        sd['Code'] = sd['State'].map(abbr)
        fig = px.choropleth(sd, locations='Code', locationmode='USA-states', color='Sales', scope='usa',
                            template=plotly_template, color_continuous_scale='Blues', hover_name='State')
        fig.update_layout(coloraxis_showscale=False, height=400, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, width='stretch', config=plotly_config)

# =========================================================
# РЯД 3: Топ-10 + Топ-10 убыточных
# =========================================================
col1, col2 = st.columns(2)
with col1:
    with st.container(border=True, key="plot5"):
        st.markdown('##### Топ-10 продуктов')
        t10 = df.groupby('Product Name')['Sales'].sum().nlargest(10).reset_index()
        fig = px.bar(t10, x='Sales', y='Product Name', orientation='h', template=plotly_template, color='Sales',
                     color_continuous_scale='Blues', text_auto='.2s')
        fig.update_layout(yaxis={'categoryorder': 'total ascending'}, xaxis=dict(range=[0, t10['Sales'].max() * 1.1]),
                          coloraxis_showscale=False, height=400, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, width='stretch', config=plotly_config)
with col2:
    with st.container(border=True, key="plot6"):
        st.markdown('##### Топ-10 убыточных')
        l10 = df.groupby('Product Name')['Profit'].sum().nsmallest(10).reset_index()
        fig = px.bar(l10, x='Profit', y='Product Name', orientation='h', template=plotly_template, color='Profit',
                     color_continuous_scale='Reds_r', text_auto='.2s')
        fig.update_layout(yaxis={'categoryorder': 'total descending'}, xaxis=dict(range=[l10['Profit'].min() * 1.1, 0]),
                          coloraxis_showscale=False, height=400, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, width='stretch', config=plotly_config)

# =========================================================
# РЯД 4: Скидки + Топ-20
# =========================================================
col1, col2 = st.columns(2)
with col1:
    with st.container(border=True, key="plot7"):
        st.markdown('##### Скидки vs Прибыль')
        dp = df.copy()
        dp['DL'] = pd.cut(dp['Discount'], bins=[-0.01, 0.05, 0.2, 0.5, 1],
                          labels=['Без скидки', '0-5%', '5-20%', '20%+'])
        fig = px.scatter(dp, x='Discount', y='Profit', color='Profit', template=plotly_template, opacity=0.7,
                         color_continuous_scale=['red', 'yellow', 'green'])
        fig.update_traces(selector=dict(mode='markers'), marker=dict(size=15, coloraxis='coloraxis'))
        fig.add_hline(y=0, line_dash="dash", line_color="black", opacity=0.5)
        fig.update_layout(height=400, xaxis=dict(title='Скидка (%)', tickformat='.0%', range=[-0.05, 0.85]),
                          yaxis=dict(title=f'Прибыль ({currency})'), coloraxis_showscale=False,
                          margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, width='stretch', config=plotly_config)
with col2:
    with st.container(border=True, key="plot8"):
        st.markdown('##### Топ-20 клиентов')
        cs = df.groupby('Customer ID').agg(Customer_Name=('Customer Name', 'first'), Total_Sales=('Sales', 'sum'),
                                           Total_Profit=('Profit', 'sum'), Orders=('Order ID', 'nunique')).reset_index()
        tc = cs.nlargest(20, 'Total_Sales')
        fig = px.bar(tc, x='Total_Sales', y='Customer_Name', orientation='h', color='Total_Profit',
                     template=plotly_template, color_continuous_scale=['red', 'yellow', 'green'])
        fig.update_traces(text=tc['Total_Sales'].apply(lambda x: f'{x:,.0f}'), textposition='outside',
                          textfont=dict(size=11))
        fig.update_layout(yaxis={'categoryorder': 'total ascending'}, height=400, coloraxis_showscale=False,
                          margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, width='stretch', config=plotly_config)

# =========================================================
# РЯД 5: ABC + Sunburst
# =========================================================
col1, col2 = st.columns(2)
with col1:
    with st.container(border=True, key="plot9"):
        st.markdown('##### ABC-анализ')
        ad = df.groupby('ABC').agg(Products=('Product Name', 'nunique'), Sales=('Sales', 'sum'),
                                   Profit=('Profit', 'sum')).reindex(
            ['A - Золото', 'B - Середняки', 'C - Балласт']).fillna(0)
        fig = px.bar(ad, x=ad.index, y='Products', color='Profit', template=plotly_template,
                     color_continuous_scale=['red', 'yellow', 'green'], text_auto=True)
        fig.update_layout(height=400, coloraxis_showscale=False, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, width='stretch', config=plotly_config)
with col2:
    with st.container(border=True, key="plot10"):
        st.markdown('##### Категории и подкатегории')
        sd = df.groupby(['Category', 'Sub-Category']).agg(Sales=('Sales', 'sum'),
                                                          Profit=('Profit', 'sum')).reset_index()
        fig = px.sunburst(sd, path=['Category', 'Sub-Category'], values='Sales', color='Profit',
                          template=plotly_template, color_continuous_scale=['red', 'yellow', 'green'])
        fig.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, width='stretch', config=plotly_config)

# =========================================================
# РЯД 6: ПРОГНОЗ + БЭКТЕСТИНГ
# =========================================================
with st.container(border=True, key="plot11"):
    st.markdown('##### Прогноз продаж')
    try:
        from statsmodels.tsa.holtwinters import ExponentialSmoothing

        mp = df.groupby(df['Order Date'].dt.to_period('M'))['Sales'].sum().reset_index()
        mp['Order Date'] = mp['Order Date'].astype(str)
        mv = mp['Sales'].values.astype(float)
        model = ExponentialSmoothing(mv, seasonal_periods=12, trend='add', seasonal='add').fit()
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
        fig.add_trace(go.Scatter(x=pd.to_datetime(mp['Order Date']), y=mv, mode='markers+lines', name='История',
                                 line=dict(color='#00CC96', width=2)))
        fig.update_layout(height=400, hovermode='x unified', margin=dict(l=20, r=20, t=20, b=30),
                          legend=dict(orientation='h', yanchor='top', y=-0.2, xanchor='center', x=0.5))
        st.plotly_chart(fig, width='stretch', config=plotly_config)

        # Бэктестинг
        st.markdown('##### Бэктестинг: проверка точности')
        train, test = mv[:-12], mv[-12:]
        mb = ExponentialSmoothing(train, seasonal_periods=12, trend='add', seasonal='add').fit()
        fb = mb.forecast(12)
        mae = np.mean(np.abs(test - fb))
        mape = np.mean(np.abs((test - fb) / test)) * 100
        td = pd.to_datetime(mp['Order Date'].iloc[-12:])

        fig_bt = go.Figure(layout=dict(template=plotly_template))
        fig_bt.add_trace(
            go.Scatter(x=td, y=test, mode='lines+markers', name='Факт', line=dict(color='#00CC96', width=2)))
        fig_bt.add_trace(go.Scatter(x=td, y=fb, mode='lines+markers', name='Прогноз',
                                    line=dict(color='#FFA500', width=2, dash='dash')))
        fig_bt.update_layout(height=350, hovermode='x unified', margin=dict(l=20, r=20, t=20, b=30),
                             legend=dict(orientation='h', yanchor='top', y=-0.2, xanchor='center', x=0.5))
        st.plotly_chart(fig_bt, width='stretch', config=plotly_config)
        st.caption(f'MAE: {format_k(mae, currency)} | MAPE: {mape:.1f}%')
    except Exception as e:
        st.error(f'Ошибка: {e}')

# =========================================================
# РЯД 7: ЭКСПОРТ
# =========================================================
with st.container(border=True, key="plot12"):
    st.markdown('##### Экспорт')
    c1, c2 = st.columns(2)
    with c1:
        st.download_button('📥 CSV', df.to_csv(index=False).encode('utf-8'), 'superstore_filtered.csv', 'text/csv')
    with c2:
        try:
            o = BytesIO()
            with pd.ExcelWriter(o, engine='openpyxl') as w:
                df.to_excel(w, sheet_name='Superstore', index=False)
            st.download_button('📥 Excel', o.getvalue(), 'superstore_filtered.xlsx',
                               'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        except:
            st.warning('Excel недоступен')
    st.caption(
        f'Строк: {len(df):,} | Заказов: {df["Order ID"].nunique():,} | Клиентов: {df["Customer ID"].nunique():,} | Продуктов: {df["Product Name"].nunique():,}')