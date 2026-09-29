"""Загрузка данных, пересчёт валюты и экспорт. Без Streamlit — кэширует app.py."""
from io import BytesIO

import pandas as pd

from .config import RATES_CSV, SALES_CSV


def load_sales(path=SALES_CSV):
    """Читает CSV Superstore и добавляет служебные колонки (год, месяц, дни обработки)."""
    df = pd.read_csv(path, encoding='latin1')
    df['Order Date'] = pd.to_datetime(df['Order Date'], format='%m/%d/%Y')
    df['Ship Date'] = pd.to_datetime(df['Ship Date'], format='%m/%d/%Y')
    df['Year'] = df['Order Date'].dt.year
    df['Month'] = df['Order Date'].dt.month
    df['Processing Days'] = (df['Ship Date'] - df['Order Date']).dt.days
    return df


def load_rates(path=RATES_CSV):
    """Дневные курсы ЦБ: Series «дата → рублей за доллар», по возрастанию даты."""
    rates = pd.read_csv(path, parse_dates=['date'])
    return rates.set_index('date')['usd_rub'].sort_index()


def rate_on(dates, rates):
    """Курс ЦБ, действовавший на каждую дату (последний установленный — на выходных тоже)."""
    pos = rates.index.searchsorted(pd.DatetimeIndex(dates), side='right') - 1
    if (pos < 0).any():
        raise ValueError('Есть даты раньше первого курса в файле — обновите data/usd_rub_cbr.csv')
    return rates.to_numpy()[pos]


def to_rub(df, rates):
    """Копия таблицы с Sales/Profit в рублях по курсу на дату заказа + колонка Rate."""
    out = df.copy()
    out['Rate'] = rate_on(out['Order Date'], rates)
    out['Sales'] = out['Sales'] * out['Rate']
    out['Profit'] = out['Profit'] * out['Rate']
    return out


def to_csv_bytes(df):
    return df.to_csv(index=False).encode('utf-8')


def to_excel_bytes(df):
    """Excel собирается ~2–3 с, поэтому app.py вызывает это только по нажатию кнопки."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as w:
        df.to_excel(w, sheet_name='Superstore', index=False)
    return buf.getvalue()
