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
st.set_page_config(
    page_title="Superstore BI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# =========================================================
# CSS
# =========================================================
st.markdown("""
<style>
    /* Системный шрифт */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    }

    /* Убираем сайдбар */
    [data-testid="stSidebar"] { display: none !important; }

    /* Основной контент */
    .main .block-container {
        max-width: 1200px;
        padding-top: 20px;
    }

    /* Карточки */
    .graph-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    .graph-card h3, .graph-card .stSubheader {
        margin-top: 0;
    }

    /* Верхняя панель */
    .top-bar {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 16px 24px;
        margin-bottom: 20px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
    }

    /* KPI */
    .kpi-card {
        background: white;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 14px 16px;
        text-align: center;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
    }

    .kpi-value {
        font-size: 22px;
        font-weight: 700;
        color: #1a1a1a;
        margin: 4px 0;
    }

    .kpi-label {
        font-size: 11px;
        font-weight: 500;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* Pills (кнопки годов) */
    .st-key-years .stMultiSelect {
        background: transparent;
    }
</style>
""", unsafe_allow_html=True)

# =========================================================
# CONSTANTS
# =========================================================
MONTH_NAMES = {
    1: 'Янв', 2: 'Фев', 3: 'Мар', 4: 'Апр',
    5: 'Май', 6: 'Июн', 7: 'Июл', 8: 'Авг',
    9: 'Сен', 10: 'Окт', 11: 'Ноя', 12: 'Дек'
}


# =========================================================
# HELPERS
# =========================================================
def safe_div(a, b):
    return a / b if b not in [0, None, np.nan] else 0


def format_k(value, currency):
    if abs(value) >= 1000:
        return f"{currency}{value / 1000:,.0f}K"
    return f"{currency}{value:,.0f}"


# =========================================================
# EXCHANGE RATES
# =========================================================
@st.cache_data(ttl=86400, show_spinner="Загрузка курсов...")
def get_exchange_rates():
    rates = {}
    for year in [2014, 2015, 2016, 2017]:
        for month in [1, 4, 7, 10]:
            date_str = f"{year}-{month:02d}-01"
            url = f"https://www.cbr-xml-daily.ru/archive/{date_str}/daily_json.js"
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    rates[date_str] = data['Valute']['USD']['Value']
            except:
                pass
    return rates


# =========================================================
# DATA LOADING
# =========================================================
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

    product_profit = df.groupby('Product Name')['Profit'].sum().sort_values(ascending=False)
    loss_mask = product_profit <= 0
    top30 = product_profit[product_profit > 0].head(30)
    abc_series = pd.Series('B - Середняки', index=product_profit.index)
    abc_series[top30.index] = 'A - Золото'
    abc_series[loss_mask] = 'C - Балласт'
    df['ABC'] = df['Product Name'].map(abc_series)

    return df


# =========================================================
# CURRENCY CONVERSION
# =========================================================
def convert_to_rub(df, rates):
    temp_df = df.copy()
    temp_df['Month_Key'] = temp_df['Order Date'].dt.strftime('%Y-%m-01')
    temp_df['Rate'] = temp_df['Month_Key'].map(rates)
    avg_rate = np.mean(list(rates.values())) if rates else 60
    temp_df['Rate'] = temp_df['Rate'].fillna(avg_rate)
    temp_df['Sales'] = temp_df['Sales'] * temp_df['Rate']
    temp_df['Profit'] = temp_df['Profit'] * temp_df['Rate']
    return temp_df


# =========================================================
# LOAD
# =========================================================
rates = get_exchange_rates()
df_raw = load_data()

# =========================================================
# TOP BAR
# =========================================================
st.markdown('<div class="top-bar">', unsafe_allow_html=True)

col1, col2, col3 = st.columns([2, 3, 1])

with col1:
    st.markdown("**📊 Superstore BI**")

with col2:
    all_years = sorted(df_raw['Year'].unique())
    years = st.pills("Годы", options=all_years, default=all_years, selection_mode="multi", key="years",
                     label_visibility="collapsed")

with col3:
    show_rub = st.toggle("🇷🇺 RUB", value=False)

st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# FILTERS
# =========================================================
df = df_raw.copy()
if years:
    df = df[df['Year'].isin(years)]

currency = '₽' if show_rub else '$'
if show_rub:
    df = convert_to_rub(df, rates)

if df.empty:
    st.warning('Нет данных для выбранных годов.')
    st.stop()

# =========================================================
# KPI
# =========================================================
sales_sum = df['Sales'].sum()
profit_sum = df['Profit'].sum()
margin = safe_div(profit_sum, sales_sum) * 100
orders = df['Order ID'].nunique()
customers = df['Customer ID'].nunique()
avg_discount = df['Discount'].mean() * 100
avg_delivery = df['Processing Days'].mean()

# =========================================================
# KPI ROW
# =========================================================
kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)

for col, label, value in [
    (kpi1, '💰 Выручка', format_k(sales_sum, currency)),
    (kpi2, '📈 Прибыль', format_k(profit_sum, currency)),
    (kpi3, '📦 Заказы', f'{orders:,}'),
    (kpi4, '👥 Клиенты', f'{customers:,}'),
    (kpi5, '🏷️ Скидка', f'{avg_discount:.1f}%'),
    (kpi6, '🚚 Доставка', f'{avg_delivery:.1f} дн')
]:
    with col:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
        </div>
        """, unsafe_allow_html=True)

# =========================================================
# monthly
# =========================================================
monthly = df.groupby(df['Order Date'].dt.to_period('M')).agg({'Sales': 'sum', 'Profit': 'sum'}).reset_index()
monthly['Order Date'] = monthly['Order Date'].astype(str)

plotly_template = 'plotly'

# =========================================================
# ОБЗОР
# =========================================================
st.markdown('<div class="graph-card">', unsafe_allow_html=True)
st.subheader('Продажи и Прибыль по месяцам')
fig = go.Figure(layout=dict(template=plotly_template))
fig.add_trace(go.Scatter(x=monthly['Order Date'], y=monthly['Sales'], name='Продажи', fill='tozeroy'))
fig.add_trace(go.Scatter(x=monthly['Order Date'], y=monthly['Profit'], name='Прибыль', fill='tozeroy'))
fig.update_layout(height=400, hovermode='x unified', margin=dict(l=20, r=20, t=20, b=30),
                  legend=dict(orientation='h', yanchor='top', y=-0.2, xanchor='center', x=0.5))
st.plotly_chart(fig, width='stretch', config={'responsive': True})
st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# ПРОДАЖИ ПО КАТЕГОРИЯМ + СЕЗОННОСТЬ
# =========================================================
col1, col2 = st.columns(2)

with col1:
    st.markdown('<div class="graph-card">', unsafe_allow_html=True)
    st.subheader('Продажи по категориям')
    cat_data = df.groupby('Category').agg(Sales=('Sales', 'sum'), Profit=('Profit', 'sum')).reset_index()
    fig = go.Figure()
    fig.add_trace(go.Pie(
        labels=cat_data['Category'], values=cat_data['Sales'], hole=0.5,
        texttemplate='%{label}<br>%{percent:.1%}<br>' + currency + '%{value:,.0f}',
        marker=dict(colors=px.colors.qualitative.Pastel[:3], line=dict(color='white', width=4)),
        textfont=dict(size=13)
    ))
    fig.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, width='stretch', config={'responsive': True})
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="graph-card">', unsafe_allow_html=True)
    st.subheader('📈 Сезонность')
    heatmap_data = df.pivot_table(values='Sales', index='Month', columns='Year', aggfunc='sum')
    heatmap_data.index = [MONTH_NAMES[m] for m in heatmap_data.index]
    fig = px.imshow(heatmap_data, aspect='auto', color_continuous_scale='Blues', template=plotly_template)
    fig.update_traces(text=[[f"{currency}{val:,.0f}" for val in row] for row in heatmap_data.values],
                      texttemplate="%{text}", textfont=dict(size=11))
    fig.update_xaxes(side='top', title='', tickformat='d', dtick=1)
    fig.update_layout(coloraxis_showscale=False, height=350, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, width='stretch', config={'responsive': True})
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# ГЕОГРАФИЯ + ТОП-10
# =========================================================
col1, col2 = st.columns(2)

with col1:
    st.markdown('<div class="graph-card">', unsafe_allow_html=True)
    st.subheader('🗺️ География')
    state_abbr = {
        'Alabama': 'AL', 'Arizona': 'AZ', 'Arkansas': 'AR', 'California': 'CA',
        'Colorado': 'CO', 'Connecticut': 'CT', 'Delaware': 'DE', 'Florida': 'FL',
        'Georgia': 'GA', 'Idaho': 'ID', 'Illinois': 'IL', 'Indiana': 'IN',
        'Iowa': 'IA', 'Kansas': 'KS', 'Kentucky': 'KY', 'Louisiana': 'LA',
        'Maine': 'ME', 'Maryland': 'MD', 'Massachusetts': 'MA', 'Michigan': 'MI',
        'Minnesota': 'MN', 'Mississippi': 'MS', 'Missouri': 'MO', 'Montana': 'MT',
        'Nebraska': 'NE', 'Nevada': 'NV', 'New Hampshire': 'NH', 'New Jersey': 'NJ',
        'New Mexico': 'NM', 'New York': 'NY', 'North Carolina': 'NC', 'North Dakota': 'ND',
        'Ohio': 'OH', 'Oklahoma': 'OK', 'Oregon': 'OR', 'Pennsylvania': 'PA',
        'Rhode Island': 'RI', 'South Carolina': 'SC', 'South Dakota': 'SD',
        'Tennessee': 'TN', 'Texas': 'TX', 'Utah': 'UT', 'Vermont': 'VT',
        'Virginia': 'VA', 'Washington': 'WA', 'West Virginia': 'WV', 'Wisconsin': 'WI',
        'Wyoming': 'WY', 'District of Columbia': 'DC'
    }
    state_data = df.groupby('State').agg({'Sales': 'sum', 'Profit': 'sum'}).reset_index()
    state_data['State Code'] = state_data['State'].map(state_abbr)
    fig = px.choropleth(state_data, locations='State Code', locationmode='USA-states',
                        color='Sales', scope='usa', template=plotly_template,
                        color_continuous_scale='Blues', hover_name='State')
    fig.update_layout(coloraxis_showscale=False, height=350, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, width='stretch', config={'responsive': True})
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="graph-card">', unsafe_allow_html=True)
    st.subheader('🏆 Топ-10 продуктов')
    top10 = df.groupby('Product Name')['Sales'].sum().nlargest(10).reset_index()
    fig = px.bar(top10, x='Sales', y='Product Name', orientation='h',
                 template=plotly_template, color='Sales', color_continuous_scale='Blues', text_auto='.2s')
    fig.update_layout(yaxis={'categoryorder': 'total ascending'},
                      xaxis=dict(range=[0, top10['Sales'].max() * 1.1]),
                      coloraxis_showscale=False, height=350, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, width='stretch', config={'responsive': True})
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# СКИДКИ + ТОП-20
# =========================================================
col1, col2 = st.columns(2)

with col1:
    st.markdown('<div class="graph-card">', unsafe_allow_html=True)
    st.subheader('🔥 Скидки vs Прибыль')
    df_plot = df.copy()
    df_plot['Discount Level'] = pd.cut(df_plot['Discount'], bins=[-0.01, 0.05, 0.2, 0.5, 1],
                                       labels=['Без скидки', '0-5%', '5-20%', '20%+'])
    fig = px.scatter(df_plot, x='Discount', y='Profit', color='Profit',
                     template=plotly_template, opacity=0.7, size_max=12,
                     color_continuous_scale=['red', 'yellow', 'green'])
    fig.update_traces(selector=dict(mode='markers'), marker=dict(size=18, coloraxis='coloraxis'))
    fig.add_hline(y=0, line_dash="dash", line_color="black", opacity=0.5)
    fig.update_layout(height=350, xaxis=dict(title='Скидка (%)', tickformat='.0%', range=[-0.05, 0.85]),
                      yaxis=dict(title=f'Прибыль ({currency})'),
                      coloraxis_showscale=False, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, width='stretch', config={'responsive': True})
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="graph-card">', unsafe_allow_html=True)
    st.subheader('👥 Топ-20 клиентов')
    customer_stats = df.groupby('Customer ID').agg(
        Customer_Name=('Customer Name', 'first'), Total_Sales=('Sales', 'sum'),
        Total_Profit=('Profit', 'sum'), Orders=('Order ID', 'nunique')
    ).reset_index()
    top_cust = customer_stats.nlargest(20, 'Total_Sales')
    fig = px.bar(top_cust, x='Total_Sales', y='Customer_Name', orientation='h',
                 color='Total_Profit', template=plotly_template,
                 color_continuous_scale=['red', 'yellow', 'green'])
    fig.update_traces(text=top_cust['Total_Sales'].apply(lambda x: f'{x:,.0f}'), textposition='outside',
                      textfont=dict(size=11))
    fig.update_layout(yaxis={'categoryorder': 'total ascending'}, height=350,
                      coloraxis_showscale=False, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, width='stretch', config={'responsive': True})
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# ABC + SUNBURST
# =========================================================
col1, col2 = st.columns(2)

with col1:
    st.markdown('<div class="graph-card">', unsafe_allow_html=True)
    st.subheader('📊 ABC-анализ')
    abc_data = df.groupby('ABC').agg(Products=('Product Name', 'nunique'), Sales=('Sales', 'sum'),
                                     Profit=('Profit', 'sum')).reindex(
        ['A - Золото', 'B - Середняки', 'C - Балласт']).fillna(0)
    fig = px.bar(abc_data, x=abc_data.index, y='Products', color='Profit',
                 template=plotly_template, color_continuous_scale=['red', 'yellow', 'green'],
                 text_auto=True, labels={'Products': 'Кол-во', 'index': ''})
    fig.update_layout(height=350, coloraxis_showscale=False, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, width='stretch', config={'responsive': True})
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="graph-card">', unsafe_allow_html=True)
    st.subheader('☀️ Категории и подкатегории')
    sunburst_data = df.groupby(['Category', 'Sub-Category']).agg(Sales=('Sales', 'sum'),
                                                                 Profit=('Profit', 'sum')).reset_index()
    fig = px.sunburst(sunburst_data, path=['Category', 'Sub-Category'], values='Sales', color='Profit',
                      template=plotly_template, color_continuous_scale=['red', 'yellow', 'green'])
    fig.update_layout(height=350, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, width='stretch', config={'responsive': True})
    st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# ПРОГНОЗ
# =========================================================
st.markdown('<div class="graph-card">', unsafe_allow_html=True)
st.subheader('🔮 Прогноз продаж')

try:
    from statsmodels.tsa.holtwinters import ExponentialSmoothing

    monthly_prophet = df.groupby(df['Order Date'].dt.to_period('M'))['Sales'].sum().reset_index()
    monthly_prophet['Order Date'] = monthly_prophet['Order Date'].astype(str)
    monthly_values = monthly_prophet['Sales'].values.astype(float)

    model = ExponentialSmoothing(monthly_values, seasonal_periods=12, trend='add', seasonal='add').fit()
    forecast_values = model.forecast(12)

    last_date = pd.to_datetime(monthly_prophet['Order Date'].iloc[-1])
    future_dates = pd.date_range(start=last_date + pd.DateOffset(months=1), periods=12, freq='MS')

    forecast_sales = forecast_values.sum()
    avg_margin_pct = (df['Profit'].sum() / df['Sales'].sum() * 100) if df['Sales'].sum() > 0 else 10
    profit_margin = avg_margin_pct / 100
    forecast_profit = forecast_sales * profit_margin
    avg_check = df['Sales'].sum() / df['Order ID'].nunique() if df['Order ID'].nunique() > 0 else 500
    forecast_orders = forecast_sales / avg_check

    c1, c2, c3 = st.columns(3)
    c1.metric('💰 Выручка (прогноз)', format_k(forecast_sales, currency))
    c2.metric('📈 Прибыль (прогноз)', format_k(forecast_profit, currency))
    c3.metric('📦 Заказы (прогноз)', f'{forecast_orders:,.0f}')

    fig = go.Figure(layout=dict(template=plotly_template))
    fig.add_trace(go.Scatter(x=future_dates, y=forecast_values, mode='lines', name='Прогноз',
                             line=dict(color='#FFA500', width=2)))
    fig.add_trace(go.Scatter(x=pd.to_datetime(monthly_prophet['Order Date']), y=monthly_values, mode='markers+lines',
                             name='История', line=dict(color='#00CC96', width=2)))
    fig.update_layout(height=400, hovermode='x unified', margin=dict(l=20, r=20, t=20, b=30),
                      legend=dict(orientation='h', yanchor='top', y=-0.2, xanchor='center', x=0.5))
    st.plotly_chart(fig, width='stretch', config={'responsive': True})
except Exception as e:
    st.error(f'Ошибка: {e}')

st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# ЭКСПОРТ
# =========================================================
st.markdown('<div class="graph-card">', unsafe_allow_html=True)
st.subheader('💾 Экспорт')

c1, c2 = st.columns(2)
with c1:
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button('📥 CSV', csv, 'superstore_filtered.csv', 'text/csv')
with c2:
    try:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Superstore', index=False)
        st.download_button('📥 Excel', output.getvalue(), 'superstore_filtered.xlsx',
                           'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except:
        st.warning('Excel недоступен')

st.caption(f'Строк: {len(df):,} | Заказов: {df["Order ID"].nunique():,} | Клиентов: {df["Customer ID"].nunique():,}')
st.markdown('</div>', unsafe_allow_html=True)