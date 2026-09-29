"""Прогноз выручки на следующий год (Holt-Winters) и проверка точности. Без Streamlit.

Модель всегда учится на ПОЛНОЙ истории: на выбранных годах она врала
(1 год → 12 точек и «сезон» 6 мес; годы с разрывом → дыры, заполненные нулями).
Считаем в долларах — валюте бизнеса; в рубли переводит app.py.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

SEASON = 12          # сезонность — год
HORIZON = 12         # прогноз на 12 месяцев
MIN_MONTHS = 2 * SEASON


def monthly_sales(df):
    """Непрерывный помесячный ряд выручки (индекс — первое число месяца)."""
    s = df.groupby(df['Order Date'].dt.to_period('M'))['Sales'].sum()
    s = s.reindex(pd.period_range(s.index.min(), s.index.max(), freq='M'), fill_value=0.0)
    s.index = s.index.to_timestamp()
    return s.astype(float)


def _holt_winters(values):
    model = ExponentialSmoothing(values, seasonal_periods=SEASON,
                                 trend='add', seasonal='add').fit()
    return np.asarray(model.forecast(HORIZON))


@dataclass
class Forecast:
    year: int                 # прогнозируемый год
    history: pd.Series        # факт по месяцам
    dates: pd.DatetimeIndex   # месяцы прогноза
    values: np.ndarray        # прогноз по месяцам
    total: float              # прогноз выручки за год
    margin: float             # историческая маржа (доля) → прогноз прибыли
    aov: float                # средний чек → прогноз заказов
    last_year: int
    last_sales: float
    last_profit: float
    last_orders: int

    @property
    def profit(self):
        return self.total * self.margin

    @property
    def orders(self):
        return self.total / self.aov


def forecast_next_year(df):
    s = monthly_sales(df)
    if len(s) < MIN_MONTHS:
        raise ValueError(f'Для прогноза нужно ≥ {MIN_MONTHS} месяцев истории, есть {len(s)}')
    values = _holt_winters(s.to_numpy())
    dates = pd.date_range(s.index[-1] + pd.DateOffset(months=1), periods=HORIZON, freq='MS')

    last_year = int(df['Year'].max())
    last = df[df['Year'] == last_year]
    return Forecast(
        year=dates[0].year, history=s, dates=dates, values=values, total=float(values.sum()),
        margin=df['Profit'].sum() / df['Sales'].sum(),
        aov=df['Sales'].sum() / df['Order ID'].nunique(),
        last_year=last_year, last_sales=float(last['Sales'].sum()),
        last_profit=float(last['Profit'].sum()), last_orders=int(last['Order ID'].nunique()))


@dataclass
class Backtest:
    year: int                 # проверочный год (последний в данных)
    dates: pd.DatetimeIndex
    actual: np.ndarray
    predicted: np.ndarray     # модель, обученная без последнего года
    mae: float                # средняя ошибка по месяцам, в деньгах
    mape: float               # средняя ошибка по месяцам, %
    total_error: float        # ошибка годовой суммы, %
    naive_mae: float          # ошибка наивного прогноза «как год назад»

    @property
    def gain_vs_naive(self):
        """На сколько процентов модель точнее наивного прогноза (по MAE)."""
        return (1 - self.mae / self.naive_mae) * 100


def backtest_last_year(df):
    """Учим модель без последних 12 месяцев и сравниваем прогноз с фактом."""
    s = monthly_sales(df)
    if len(s) < MIN_MONTHS + HORIZON:
        raise ValueError('Для проверки точности нужно ≥ 36 месяцев истории')
    train, test = s.iloc[:-HORIZON], s.iloc[-HORIZON:]
    actual = test.to_numpy()
    predicted = _holt_winters(train.to_numpy())
    naive = train.iloc[-HORIZON:].to_numpy()
    with np.errstate(divide='ignore', invalid='ignore'):
        mape = np.nanmean(np.abs((actual - predicted) / np.where(actual == 0, np.nan, actual))) * 100
    return Backtest(
        year=test.index[0].year, dates=test.index, actual=actual, predicted=predicted,
        mae=float(np.mean(np.abs(actual - predicted))), mape=float(mape),
        total_error=float((predicted.sum() / actual.sum() - 1) * 100),
        naive_mae=float(np.mean(np.abs(actual - naive))))
