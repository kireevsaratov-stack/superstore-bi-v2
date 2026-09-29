"""Константы проекта: пути, цвета, настройки графиков."""
from pathlib import Path

# =========================================================
# ПУТИ (от папки проекта, а не от текущей папки запуска)
# =========================================================
ROOT = Path(__file__).resolve().parent.parent
SALES_CSV = ROOT / 'data' / 'Sample - Superstore.csv'
RATES_CSV = ROOT / 'data' / 'usd_rub_cbr.csv'   # курсы ЦБ, см. scripts/fetch_cbr_rates.py

# =========================================================
# ЦВЕТА — брать только отсюда
# =========================================================
COLOR_SALES = '#1a56db'      # продажи (синий)
COLOR_PROFIT = '#16a34a'     # прибыль (зелёный)
COLOR_LOSS = '#ef4444'       # убыток (красный)
COLOR_FORECAST = '#f59e0b'   # прогноз (оранжевый)
COLOR_NEUTRAL = '#f1f5f9'    # середина шкалы «убыток → прибыль»
COLOR_ZERO_LINE = '#d1d5db'  # нулевая линия, границы штатов
COLOR_REF_LINE = 'gray'      # линия-ориентир (80% на Парето)
COLOR_LAND = '#f3f4f6'       # суша на карте
COLOR_ON_BAR = 'white'       # подписи внутри столбцов
COLOR_SALES_FILL = 'rgba(26,86,219,0.08)'
GRID = 'rgba(120,120,120,.12)'

# шкала «убыток → ноль → прибыль» для treemap и карты
DIVERGING_SCALE = [[0, COLOR_LOSS], [0.5, COLOR_NEUTRAL], [1, COLOR_PROFIT]]

# =========================================================
# PLOTLY
# =========================================================
# Подсказки при наведении включены, панель инструментов скрыта.
PLOTLY_CONFIG = {'displayModeBar': False, 'responsive': True, 'displaylogo': False}
TEMPLATE = 'plotly_white'

# =========================================================
# ВАЛЮТЫ
# =========================================================
CURRENCY_SIGN = {'USD': '$', 'RUB': '₽'}

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
