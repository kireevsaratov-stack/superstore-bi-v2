"""Plotly-фигуры для блоков дашборда. Без Streamlit: на входе данные, на выходе go.Figure."""
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from .config import (COLOR_FORECAST, COLOR_LAND, COLOR_LOSS, COLOR_ON_BAR, COLOR_PROFIT,
                     COLOR_REF_LINE, COLOR_SALES, COLOR_SALES_FILL, COLOR_ZERO_LINE,
                     DIVERGING_SCALE, GRID, TEMPLATE)
from .formatting import format_k

# горизонтальная легенда под графиком
LEGEND_BELOW = dict(orientation='h', yanchor='top', y=-0.18, xanchor='center', x=0.5)


def _profit_colors(values):
    return [COLOR_PROFIT if v > 0 else COLOR_LOSS for v in values]


# =========================================================
# РЯД 1
# =========================================================
def monthly_chart(m):
    fig = go.Figure(layout=dict(template=TEMPLATE))
    fig.add_trace(go.Scatter(x=m['Order Date'], y=m['Sales'], name='Продажи',
                             fill='tozeroy', line=dict(color=COLOR_SALES, width=2),
                             hovertemplate='%{x}<br>Продажи: %{y:,.0f}<extra></extra>'))
    fig.add_trace(go.Scatter(x=m['Order Date'], y=m['Profit'], name='Прибыль',
                             fill='tozeroy', line=dict(color=COLOR_PROFIT, width=2),
                             hovertemplate='%{x}<br>Прибыль: %{y:,.0f}<extra></extra>'))
    n = len(m)
    step = 1 if n <= 12 else 2 if n <= 24 else 3 if n <= 36 else 4
    ticks = [m['Order Date'].iloc[i] for i in range(0, n, step)]
    fig.update_layout(height=360, hovermode='x unified', margin=dict(l=0, r=0, t=10, b=30),
                      xaxis=dict(tickmode='array', tickvals=ticks, ticktext=ticks, gridcolor=GRID),
                      yaxis=dict(gridcolor=GRID), legend=LEGEND_BELOW)
    return fig


def pareto_chart(p):
    # Накопительная кривая концентрации до 80% — читается на любой ширине.
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=p.curve['N'], y=p.curve['Cum %'], mode='lines', fill='tozeroy',
                             line=dict(width=3, color=COLOR_SALES), fillcolor=COLOR_SALES_FILL,
                             hovertemplate='Продукт #%{x}<br>накоплено %{y:.0f}% '
                                           'заработанной прибыли<extra></extra>'))
    fig.add_hline(y=80, line_dash='dash', opacity=.6, line_color=COLOR_REF_LINE,
                  annotation_text='80% заработанной прибыли', annotation_position='top left')
    fig.update_layout(template=TEMPLATE, height=360, margin=dict(l=0, r=0, t=10, b=0),
                      showlegend=False,
                      xaxis=dict(title=f'Топ-{p.n80} продуктов по прибыли', showgrid=False),
                      yaxis=dict(title='Накопленная прибыль', range=[0, 85], ticksuffix='%',
                                 gridcolor=GRID))
    return fig


# =========================================================
# РЯД 2
# =========================================================
def top_products_chart(t, currency):
    fig = px.bar(t, x='Sales', y='Label', orientation='h', template=TEMPLATE,
                 color_discrete_sequence=[COLOR_SALES], labels={'Sales': 'Продажи', 'Label': ''})
    fig.update_traces(text=t['Sales'].apply(lambda x: format_k(x, currency)),
                      textposition='inside', textfont=dict(size=11, color=COLOR_ON_BAR),
                      hovertemplate='%{customdata}<br>%{x:,.0f}<extra></extra>',
                      customdata=t['Product Name'])
    fig.update_layout(yaxis={'categoryorder': 'total ascending', 'automargin': True,
                             'tickfont': dict(size=10)},
                      xaxis=dict(range=[0, t['Sales'].max() * 1.15]),
                      height=360, margin=dict(l=0, r=0, t=10, b=0))
    return fig


def top_losses_chart(t, currency):
    fig = px.bar(t, x='Profit', y='Label', orientation='h', template=TEMPLATE,
                 color_discrete_sequence=[COLOR_LOSS], labels={'Profit': 'Прибыль', 'Label': ''})
    fig.update_traces(text=t['Profit'].apply(lambda x: format_k(x, currency)),
                      textposition='auto', textfont=dict(size=11),
                      hovertemplate='%{customdata}<br>%{x:,.0f}<extra></extra>',
                      customdata=t['Product Name'])
    fig.update_layout(yaxis={'categoryorder': 'total descending', 'automargin': True,
                             'tickfont': dict(size=10), 'side': 'right'},
                      xaxis=dict(range=[t['Profit'].min() * 1.15, 0]),
                      height=360, margin=dict(l=5, r=10, t=10, b=0))
    return fig


# =========================================================
# РЯД 3
# =========================================================
def discount_chart(disc):
    fig = go.Figure()
    fig.add_trace(go.Bar(x=disc['Группа'], y=disc['Рент. %'],
                         marker_color=_profit_colors(disc['Рент. %']),
                         text=disc['Рент. %'].apply(lambda x: f'{x:+.0f}%'),
                         textposition='outside',
                         hovertemplate='Скидка %{x}<br>Рентабельность %{y:.1f}%<extra></extra>'))
    fig.add_hline(y=0, line_dash='dash', line_color=COLOR_ZERO_LINE, opacity=.5)
    fig.update_layout(template=TEMPLATE, height=360, margin=dict(l=0, r=0, t=10, b=0),
                      xaxis=dict(title='Размер скидки'),
                      yaxis=dict(title='Рентабельность', ticksuffix='%'))
    return fig


def customers_chart(cs, currency):
    fig = go.Figure(go.Bar(y=cs['Name'], x=cs['Sales'], orientation='h',
                           marker_color=_profit_colors(cs['Profit']),
                           text=cs['Sales'].apply(lambda x: format_k(x, currency)),
                           textposition='outside', textfont=dict(size=11),
                           hovertemplate='%{y}<br>Выручка %{x:,.0f}<extra></extra>'))
    fig.update_layout(template=TEMPLATE, yaxis={'categoryorder': 'total ascending'},
                      height=360, showlegend=False, margin=dict(l=0, r=0, t=10, b=0),
                      xaxis=dict(range=[0, cs['Sales'].max() * 1.18]))
    return fig


# =========================================================
# РЯД 4
# =========================================================
def category_treemap(tree, currency):
    lim = max(abs(min(tree.margins)), abs(max(tree.margins))) or 1
    money = f'{currency}%{{value:,.0f}}'
    fig = go.Figure(go.Treemap(
        ids=tree.ids, labels=tree.labels, parents=tree.parents, values=tree.values,
        branchvalues='total',
        marker=dict(colors=tree.margins, cmin=-lim, cmid=0, cmax=lim,
                    colorscale=DIVERGING_SCALE,
                    colorbar=dict(title='Маржа %', orientation='h', yanchor='top', y=-0.02,
                                  xanchor='center', x=0.5, thickness=12, len=0.7)),
        customdata=np.column_stack([tree.profits, tree.margins]),
        texttemplate=f'%{{label}}<br>{money}',
        hovertemplate=(f'%{{label}}<br>Выручка {money}<br>Прибыль {currency}%{{customdata[0]:,.0f}}'
                       '<br>Маржа %{customdata[1]:.0f}%<extra></extra>'),
        textfont=dict(size=12), tiling=dict(pad=2)))
    fig.update_layout(template=TEMPLATE, height=420, margin=dict(l=0, r=0, t=10, b=10))
    return fig


def states_bars(geo, currency, n=15):
    top = geo.nlargest(n, 'Sales')
    fig = go.Figure(go.Bar(
        y=top['State'], x=top['Sales'], orientation='h', marker_color=_profit_colors(top['Profit']),
        text=top['Sales'].apply(lambda x: format_k(x, currency)),
        textposition='outside', textfont=dict(size=11), customdata=top['Profit'],
        hovertemplate='%{y}<br>Выручка %{x:,.0f}<br>Прибыль %{customdata:,.0f}<extra></extra>'))
    fig.update_layout(template=TEMPLATE, yaxis={'categoryorder': 'total ascending'},
                      height=420, showlegend=False, margin=dict(l=0, r=0, t=10, b=0),
                      xaxis=dict(range=[0, top['Sales'].max() * 1.18]))
    return fig


def states_bubbles(geo):
    limit = max(abs(geo['Profit'].min()), abs(geo['Profit'].max())) or 1
    fig = px.scatter_geo(
        geo, locations='Code', locationmode='USA-states', size='Sales', color='Profit',
        scope='usa', size_max=26, color_continuous_scale=DIVERGING_SCALE,
        range_color=[-limit, limit], hover_name='State',
        hover_data={'Code': False, 'Sales': ':,.0f', 'Profit': ':,.0f'},
        labels={'Profit': 'Прибыль', 'Sales': 'Выручка'})
    fig.update_layout(height=420, margin=dict(l=0, r=0, t=0, b=0),
                      coloraxis_colorbar=dict(title='Прибыль', orientation='h', yanchor='top', y=0,
                                              xanchor='center', x=0.5, thickness=12, len=0.7))
    fig.update_geos(fitbounds='locations', visible=True, showland=True,
                    landcolor=COLOR_LAND, subunitcolor=COLOR_ZERO_LINE, showsubunits=True)
    return fig


# =========================================================
# РЯД 5: прогноз (k — множитель валюты: 1 для $, курс для ₽)
# =========================================================
def forecast_chart(fc, k=1.0):
    fig = go.Figure(layout=dict(template=TEMPLATE))
    fig.add_trace(go.Scatter(x=fc.history.index, y=fc.history.to_numpy() * k,
                             mode='lines+markers', name='История',
                             line=dict(color=COLOR_PROFIT, width=2)))
    fig.add_trace(go.Scatter(x=fc.dates, y=fc.values * k, mode='lines', name='Прогноз',
                             line=dict(color=COLOR_FORECAST, width=2, dash='dot')))
    fig.update_layout(height=360, hovermode='x unified', margin=dict(l=0, r=0, t=10, b=30),
                      legend=LEGEND_BELOW)
    return fig


def backtest_chart(bt, k=1.0):
    fig = go.Figure(layout=dict(template=TEMPLATE))
    fig.add_trace(go.Scatter(x=bt.dates, y=bt.actual * k, mode='lines+markers', name='Факт',
                             line=dict(color=COLOR_PROFIT, width=2)))
    fig.add_trace(go.Scatter(x=bt.dates, y=bt.predicted * k, mode='lines+markers', name='Прогноз',
                             line=dict(color=COLOR_FORECAST, width=2, dash='dash')))
    fig.update_layout(height=320, hovermode='x unified', margin=dict(l=0, r=0, t=10, b=30),
                      legend=dict(LEGEND_BELOW, y=-0.2))
    return fig
