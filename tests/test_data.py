"""Данные и валюта: то, на чём держатся все остальные цифры."""
import pandas as pd
import pytest

from superstore.data import rate_on, to_excel_bytes, to_rub


def test_dataset_facts(sales):
    # 9994 — это строки заказов; самих заказов 5009
    assert len(sales) == 9994
    assert sales['Order ID'].nunique() == 5009
    assert sales['Customer ID'].nunique() == 793
    assert sorted(sales['Year'].unique()) == [2014, 2015, 2016, 2017]
    assert sales['Sales'].sum() == pytest.approx(2_297_200.86, abs=0.01)
    assert sales['Profit'].sum() == pytest.approx(286_397.02, abs=0.01)


def test_rates_cover_every_order(sales, rates):
    assert rates.index.is_monotonic_increasing and not rates.index.has_duplicates
    assert rates.index[0] < sales['Order Date'].min()
    assert rates.index[-1] >= sales['Order Date'].max() - pd.Timedelta(days=3)
    rate_on(sales['Order Date'], rates)          # не должно быть дат без курса


def test_rate_on_takes_last_known_rate(rates):
    sunday = pd.Timestamp('2017-12-31')
    assert rate_on([sunday], rates)[0] == rates.iloc[-1]
    with pytest.raises(ValueError):
        rate_on([pd.Timestamp('2000-01-01')], rates)


def test_to_rub_uses_historical_rates(sales, rates):
    rub = to_rub(sales, rates)
    assert 'Rate' not in sales.columns                     # исходная таблица не тронута
    assert (rub['Sales'] / sales['Sales']).round(6).equals(rub['Rate'].round(6))
    by_year = rub.groupby('Year')['Rate'].mean()
    assert 32 < by_year[2014] < 45                          # до девальвации
    assert 55 < by_year[2017] < 62
    # никакого «плоского курса 60»: курсы по годам разные
    assert by_year.max() - by_year.min() > 20


def test_excel_export_is_valid_xlsx(sales):
    blob = to_excel_bytes(sales.head(50))
    assert blob[:2] == b'PK'                                # xlsx = zip-архив
