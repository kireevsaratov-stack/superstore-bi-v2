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
    page_title="Superstore BI Pro",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

def format_currency(value, currency):
    return f"{currency}{value:,.0f}"

# =========================================================
# EXCHANGE RATES
# =========================================================
@st.cache_data(ttl=86400, show_spinner="Загрузка курсов валют...")
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
    df['Quarter'] = df['Order Date'].dt.quarter
    df['Weekday'] = df['Order Date'].dt.day_name()
    df['Processing Days'] = (df['Ship Date'] - df['Order Date']).dt.days
    df['Margin %'] = np.where(df['Sales'] != 0, (df['Profit'] / df['Sales']) * 100, 0).round(1)

    # ABC Analysis (A = топ-30 по прибыли, C = убыточные, B = остальные)
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
# SIDEBAR
# =========================================================
with st.sidebar:
    st.title("🎛️ Фильтры")
    show_rub = st.toggle("🇷🇺 RUB", value=False)
    currency = '₽' if show_rub else '$'

    st.subheader("📅 Период")
    min_date = df_raw['Order Date'].min().date()
    max_date = df_raw['Order Date'].max().date()
    date_range = st.date_input("Диапазон", [min_date, max_date], min_value=min_date, max_value=max_date)

    st.subheader("🌍 География")
    regions = ['Все'] + sorted(df_raw['Region'].unique())
    selected_region = st.selectbox('Регион', regions)
    states = ['Все'] + sorted(df_raw['State'].unique())
    if selected_region != 'Все':
        states = ['Все'] + sorted(df_raw[df_raw['Region'] == selected_region]['State'].unique())
    selected_state = st.selectbox('Штат', states)

    st.subheader("🏷️ Категория")
    categories = ['Все'] + sorted(df_raw['Category'].unique())
    selected_category = st.selectbox('Категория', categories)

    plotly_template = 'plotly'
    st.markdown('---')
    st.caption(f"Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M')}")

# =========================================================
# FILTERS
# =========================================================
df = df_raw.copy()
if len(date_range) == 2:
    df = df[(df['Order Date'].dt.date >= date_range[0]) & (df['Order Date'].dt.date <= date_range[1])]
if selected_region != 'Все':
    df = df[df['Region'] == selected_region]
if selected_state != 'Все':
    df = df[df['State'] == selected_state]
if selected_category != 'Все':
    df = df[df['Category'] == selected_category]
if show_rub:
    df = convert_to_rub(df, rates)

if df.empty:
    st.warning('Нет данных для выбранных фильтров.')
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
# monthly для графиков
# =========================================================
monthly = df.groupby(df['Order Date'].dt.to_period('M')).agg({'Sales': 'sum', 'Profit': 'sum'}).reset_index()
monthly['Order Date'] = monthly['Order Date'].astype(str)

# =========================================================
# TABS
# =========================================================
tab1, tab2, tab3, tab4 = st.tabs([
    '📊 Обзор', '📦 Продукты и клиенты', '🔮 Прогноз', '💾 Экспорт'
])

# =========================================================
# TAB 1: ОБЗОР
# =========================================================
with tab1:
    st.title('📊 Общий обзор')

    # KPI метрики
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.metric('💰 Продажи', format_currency(sales_sum, currency))
    with c2:
        st.metric('📈 Прибыль', format_currency(profit_sum, currency), f'{margin:.1f}%')
    with c3:
        st.metric('📦 Заказы', f'{orders:,}')
    with c4:
        st.metric('👥 Клиенты', f'{customers:,}')
    with c5:
        st.metric('🏷️ Ср. скидка', f'{avg_discount:.1f}%')
    with c6:
        st.metric('🚚 Доставка', f'{avg_delivery:.1f} дн.')

    # Ряд 1: Продажи и прибыль + Пирог
    col1, col2 = st.columns(2)

    with col1:
        st.subheader('Продажи и Прибыль по месяцам')
        fig = go.Figure(layout=dict(template=plotly_template))
        fig.add_trace(go.Scatter(x=monthly['Order Date'], y=monthly['Sales'], name='Продажи', fill='tozeroy'))
        fig.add_trace(go.Scatter(x=monthly['Order Date'], y=monthly['Profit'], name='Прибыль', fill='tozeroy'))
        fig.update_layout(
            hovermode='x unified',
            height=400,
            legend=dict(orientation='h', yanchor='top', y=1.15, xanchor='center', x=0.5)
        )
        st.plotly_chart(fig, width='stretch')

    with col2:
        st.subheader('Продажи и прибыль по категориям')
        cat_tab1, cat_tab2 = st.tabs(['🍩 Donut', '☀️ Sunburst'])

        with cat_tab1:
            cat_data = df.groupby('Category').agg(Sales=('Sales', 'sum'), Profit=('Profit', 'sum')).reset_index()
            fig = go.Figure()
            fig.add_trace(go.Pie(
                labels=cat_data['Category'], values=cat_data['Sales'],
                hole=0.5, textinfo='label+percent+value',
                texttemplate='%{label}<br>%{percent:.1%}<br>' + currency + '%{value:,.0f}',
                marker=dict(colors=px.colors.qualitative.Pastel[:3], line=dict(color='white', width=4)),
                pull=[0.05, 0.05, 0.05], textfont=dict(size=13),
                hovertemplate='<b>%{label}</b><br>Продажи: ' + currency + '%{value:,.0f}<br>Доля: %{percent:.1%}<br>Прибыль: %{customdata:,.0f}<extra></extra>',
                customdata=cat_data['Profit']
            ))
            fig.update_layout(height=400, template=plotly_template)
            st.plotly_chart(fig, width='stretch')

        with cat_tab2:
            sunburst_data = df.groupby(['Category', 'Sub-Category']).agg(
                Sales=('Sales', 'sum'), Profit=('Profit', 'sum')
            ).reset_index()
            fig = px.sunburst(sunburst_data, path=['Category', 'Sub-Category'],
                              values='Sales', color='Profit', template=plotly_template,
                              color_continuous_scale=['red', 'yellow', 'green'],
                              hover_data={'Sales': f':{currency},.0f', 'Profit': f':{currency},.0f'})
            fig.update_layout(height=400)
            st.plotly_chart(fig, width='stretch')

    st.markdown('---')

    # Ряд 2: Сезонность + Гео
    col1, col2 = st.columns(2)

    with col1:
        st.subheader('📈 Сезонность продаж')
        seas_tab1, seas_tab2 = st.tabs(['🔥 Heatmap', '🎯 Polar'])

        with seas_tab1:
            heatmap_data = df.pivot_table(values='Sales', index='Month', columns='Year', aggfunc='sum')
            heatmap_data.index = [MONTH_NAMES[m] for m in heatmap_data.index]
            fig = px.imshow(heatmap_data, aspect='auto', color_continuous_scale='Blues', template=plotly_template)
            fig.update_traces(text=[[f"{currency}{val:,.0f}" for val in row] for row in heatmap_data.values],
                              texttemplate="%{text}", textfont=dict(size=11))
            fig.update_xaxes(side='top', title='Год', tickformat='d', dtick=1)
            fig.update_layout(coloraxis_showscale=False, height=450, margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig, width='stretch')

        with seas_tab2:
            monthly_sales = df.groupby('Month').agg({'Sales': 'sum', 'Profit': 'sum'}).reset_index()
            monthly_sales['Month Name'] = monthly_sales['Month'].map(MONTH_NAMES)
            fig = px.line_polar(monthly_sales, r='Sales', theta='Month Name', line_close=True,
                                template=plotly_template, color_discrete_sequence=['#636EFA'])
            fig.update_layout(height=400)
            st.plotly_chart(fig, width='stretch')

    with col2:
        st.subheader('🗺️ География продаж')
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
                            color_continuous_scale='Blues',
                            labels={'Sales': f'Продажи ({currency})'},
                            hover_name='State',
                            hover_data={'Profit': f':{currency},.0f', 'Sales': f':{currency},.0f'})
        fig.update_layout(coloraxis_showscale=False, height=450, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, width='stretch')

# =========================================================
# TAB 2: ПРОДУКТЫ И КЛИЕНТЫ
# =========================================================
with tab2:
    st.title('📦 Продукты и клиенты')

    # ABC-анализ
    st.subheader('📊 ABC-анализ продуктов')
    abc_data = df.groupby('ABC').agg(
        Products=('Product Name', 'nunique'), Sales=('Sales', 'sum'), Profit=('Profit', 'sum')
    ).reindex(['A - Золото', 'B - Середняки', 'C - Балласт']).fillna(0)

    c1, c2, c3 = st.columns(3)
    for col, (abc, emoji) in zip([c1, c2, c3], [('A - Золото', '🥇'), ('B - Середняки', '🥈'), ('C - Балласт', '🥉')]):
        with col:
            val = abc_data.loc[abc, 'Products']
            profit_val = abc_data.loc[abc, 'Profit']
            if profit_val < 0:
                st.metric(f"{emoji} {abc}", f"{val:.0f} продуктов",
                          delta=f"Убыток: {currency}{profit_val:,.0f}", delta_color="inverse")
            else:
                st.metric(f"{emoji} {abc}", f"{val:.0f} продуктов",
                          delta=f"Прибыль: {currency}{profit_val:,.0f}", delta_color="normal")

    st.markdown('---')

    # Топ-10 продуктов + Топ-10 убыточных
    col1, col2 = st.columns(2)

    with col1:
        st.subheader('🏆 Топ-10 продуктов')
        top10 = df.groupby('Product Name')['Sales'].sum().nlargest(10).reset_index()
        fig = px.bar(top10, x='Sales', y='Product Name', orientation='h',
                     template=plotly_template, color='Sales', color_continuous_scale='Blues', text_auto='.2s')
        fig.update_layout(yaxis={'categoryorder': 'total ascending'},
                          xaxis=dict(range=[0, top10['Sales'].max() * 1.1]),
                          coloraxis_showscale=False, height=400)
        st.plotly_chart(fig, width='stretch')

    with col2:
        st.subheader('💀 Топ-10 убыточных')
        loss10 = df.groupby('Product Name')['Profit'].sum().nsmallest(10).reset_index()
        fig = px.bar(loss10, x='Profit', y='Product Name', orientation='h',
                     template=plotly_template, color='Profit',
                     color_continuous_scale='Reds_r', text_auto='.2s')
        fig.update_layout(yaxis={'categoryorder': 'total descending'},
                          xaxis=dict(range=[loss10['Profit'].min() * 1.1, 0]),
                          coloraxis_showscale=False, height=400)
        st.plotly_chart(fig, width='stretch')

    st.markdown('---')

    # Скидки vs Прибыль + Топ-20 клиентов
    col1, col2 = st.columns(2)

    with col1:
        st.subheader('🔥 Скидки vs Прибыль')
        df_plot = df.copy()
        df_plot['Discount Level'] = pd.cut(df_plot['Discount'], bins=[-0.01, 0.05, 0.2, 0.5, 1],
                                           labels=['Без скидки', '0-5%', '5-20%', '20%+'])
        fig = px.scatter(df_plot, x='Discount', y='Profit', color='Profit',
                         template=plotly_template, opacity=0.7, size_max=12,
                         color_continuous_scale=['red', 'yellow', 'green'],
                         hover_data=['Product Name', 'Sales', 'Discount'])
        fig.update_traces(selector=dict(mode='markers'), marker=dict(size=25, coloraxis='coloraxis'))
        fig.add_hline(y=0, line_dash="dash", line_color="black", opacity=0.5)
        fig.update_layout(height=500, xaxis=dict(title='Скидка (%)', tickformat='.0%', range=[-0.05, 0.85]),
                          yaxis=dict(title=f'Прибыль ({currency})'), margin=dict(l=20, r=20, t=30, b=30),
                          coloraxis_showscale=False, template=plotly_template)
        st.plotly_chart(fig, width='stretch')

    with col2:
        st.subheader('👥 Топ-20 клиентов')
        customer_stats = df.groupby('Customer ID').agg(
            Customer_Name=('Customer Name', 'first'), Total_Sales=('Sales', 'sum'),
            Total_Profit=('Profit', 'sum'), Orders=('Order ID', 'nunique')
        ).reset_index()
        top_cust = customer_stats.nlargest(20, 'Total_Sales')
        fig = px.bar(top_cust, x='Total_Sales', y='Customer_Name', orientation='h',
                     color='Total_Profit', template=plotly_template,
                     color_continuous_scale=['red', 'yellow', 'green'])
        fig.update_traces(text=top_cust['Total_Sales'].apply(lambda x: f'{x:,.0f}'), textposition='outside', textfont=dict(size=11))
        fig.update_layout(yaxis={'categoryorder': 'total ascending'}, height=500, margin=dict(l=20, r=20, t=30, b=30),
                          coloraxis_showscale=False)
        st.plotly_chart(fig, width='stretch')

# =========================================================
# TAB 3: ПРОГНОЗ
# =========================================================
with tab3:
    st.title('🔮 Прогноз продаж на год')

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
        forecast_avg_sales = forecast_values.mean()
        avg_margin_pct = (df['Profit'].sum() / df['Sales'].sum() * 100) if df['Sales'].sum() > 0 else 10
        profit_margin = avg_margin_pct / 100
        forecast_profit = forecast_sales * profit_margin
        forecast_avg_profit = forecast_avg_sales * profit_margin
        avg_check = df['Sales'].sum() / df['Order ID'].nunique() if df['Order ID'].nunique() > 0 else 500
        forecast_orders = forecast_sales / avg_check
        forecast_avg_orders = forecast_avg_sales / avg_check

        last_year = monthly_values[-12:].sum()
        last_year_profit = last_year * profit_margin
        last_year_orders = last_year / avg_check

        sales_delta_pct = (forecast_sales / last_year - 1) * 100
        profit_delta_pct = (forecast_profit / last_year_profit - 1) * 100
        orders_delta_pct = (forecast_orders / last_year_orders - 1) * 100

        st.subheader('📊 Сравнение год к году')
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown('### 💰 Выручка')
            st.metric('За год (прогноз)', format_currency(forecast_sales, currency), delta=f'{sales_delta_pct:+.1f}%')
            st.metric('Средняя в месяц', format_currency(forecast_avg_sales, currency))
            st.caption(f'Предыдущий год: {currency}{last_year:,.0f}')
        with col2:
            st.markdown('### 📈 Прибыль')
            st.metric('За год (прогноз)', format_currency(forecast_profit, currency), delta=f'{profit_delta_pct:+.1f}%')
            st.metric('Средняя в месяц', format_currency(forecast_avg_profit, currency))
            st.caption(f'Предыдущий год: {currency}{last_year_profit:,.0f}')
        with col3:
            st.markdown('### 📦 Заказы')
            st.metric('За год (прогноз)', f'{forecast_orders:,.0f}', delta=f'{orders_delta_pct:+.1f}%')
            st.metric('Среднее в месяц', f'{forecast_avg_orders:,.0f}')
            st.caption(f'Предыдущий год: {last_year_orders:,.0f}')

        st.markdown('---')
        st.subheader('📈 История + Прогноз')
        fig = go.Figure(layout=dict(template=plotly_template))
        fig.add_trace(go.Scatter(x=future_dates, y=forecast_values, mode='lines', name='Прогноз', line=dict(color='#FFA500', width=2)))
        fig.add_trace(go.Scatter(x=pd.to_datetime(monthly_prophet['Order Date']), y=monthly_values, mode='markers+lines', name='История', line=dict(color='#00CC96', width=2)))
        fig.update_layout(height=500, hovermode='x unified', legend=dict(orientation='h', yanchor='top', y=1.15, xanchor='center', x=0.5))
        st.plotly_chart(fig, width='stretch')

        # Бэктестинг
        st.markdown('---')
        st.subheader('🎯 Бэктестинг: проверка точности')

        train = monthly_values[:-12]
        test = monthly_values[-12:]
        model_backtest = ExponentialSmoothing(train, seasonal_periods=12, trend='add', seasonal='add').fit()
        forecast_backtest = model_backtest.forecast(12)

        mae = np.mean(np.abs(test - forecast_backtest))
        mape = np.mean(np.abs((test - forecast_backtest) / test)) * 100

        test_dates = pd.to_datetime(monthly_prophet['Order Date'].iloc[-12:])
        fig_bt = go.Figure(layout=dict(template=plotly_template))
        fig_bt.add_trace(go.Scatter(x=test_dates, y=test, mode='lines+markers', name='Факт', line=dict(color='#00CC96', width=2)))
        fig_bt.add_trace(go.Scatter(x=test_dates, y=forecast_backtest, mode='lines+markers', name='Прогноз', line=dict(color='#FFA500', width=2, dash='dash')))
        fig_bt.update_layout(height=350, hovermode='x unified', title='Проверка на 2017 году: факт vs прогноз',
                             legend=dict(orientation='h', yanchor='top', y=1.15, xanchor='center', x=0.5))
        st.plotly_chart(fig_bt, width='stretch')

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric('📊 Средняя ошибка (MAE)', f'{currency}{mae:,.0f}')
        with col2:
            st.metric('📈 Точность (MAPE)', f'{100 - mape:.1f}%', delta=f'±{mape:.1f}%')
        with col3:
            quality = 'Отличная' if mape < 10 else 'Хорошая' if mape < 20 else 'Средняя' if mape < 30 else 'Низкая'
            st.metric('🏆 Качество модели', quality)

        st.caption(f'MAPE: {mape:.1f}% — чем меньше, тем точнее')

        st.markdown('---')
        st.markdown("""
        ### 📘 О прогнозе
        **Как работает модель:** Holt-Winters Exponential Smoothing (statsmodels). Учитывает тренд и сезонность (12 месяцев).
        **Ограничения:** Чем дальше прогноз — тем выше неопределённость. Модель не учитывает внешние факторы (акции, кризисы).
        **Использование:** Для бюджетирования — нижняя граница, для целей — верхняя.
        """)

    except Exception as e:
        st.error(f'Ошибка прогноза: {e}')

# =========================================================
# TAB 4: ЭКСПОРТ
# =========================================================
with tab4:
    st.title('💾 Экспорт')

    col1, col2 = st.columns(2)
    with col1:
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button('📥 Скачать CSV', csv, 'superstore_filtered.csv', 'text/csv')
    with col2:
        try:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Superstore', index=False)
            excel_data = output.getvalue()
            st.download_button('📥 Excel', excel_data, 'superstore_filtered.xlsx',
                               'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        except:
            st.warning('Excel недоступен')

    st.markdown('---')
    st.subheader('📋 Информация о данных')

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric('📊 Строк', f'{len(df):,}')
    with col2:
        st.metric('📋 Столбцов', f'{len(df.columns)}')
    with col3:
        st.metric('📦 Заказов', f'{df["Order ID"].nunique():,}')
    with col4:
        st.metric('👥 Клиентов', f'{df["Customer ID"].nunique():,}')
    with col5:
        st.metric('📦 Продуктов', f'{df["Product Name"].nunique():,}')
    with col6:
        st.metric('🏙️ Городов', f'{df["City"].nunique():,}')

    date_min = df['Order Date'].min().strftime('%d.%m.%Y')
    date_max = df['Order Date'].max().strftime('%d.%m.%Y')
    st.caption(f'📅 Период данных: {date_min} — {date_max}')

    nulls = df.isnull().sum().sum()
    if nulls > 0:
        st.warning(f'⚠️ Пропусков в данных: {nulls}')
    else:
        st.success('✅ Пропусков в данных нет')

    st.markdown('---')
    st.subheader('📋 Все данные')
    st.dataframe(df, width='stretch', height=500)