"""Прогноз: учится на полной истории и должен быть точнее наивного «как год назад»."""
import pytest

from superstore.forecast import backtest_last_year, forecast_next_year, monthly_sales


def test_monthly_series_is_contiguous(sales):
    s = monthly_sales(sales)
    assert len(s) == 48
    assert s.index.to_series().diff().dropna().dt.days.between(28, 31).all()


def test_forecast_2018(sales):
    fc = forecast_next_year(sales)
    assert fc.year == 2018 and fc.last_year == 2017
    assert len(fc.values) == 12
    assert fc.total == pytest.approx(904_619, rel=0.02)
    assert 1.1 < fc.total / fc.last_sales < 1.4             # рост, но без +73% как было на 1 году


def test_backtest_beats_naive_baseline(sales):
    bt = backtest_last_year(sales)
    assert bt.year == 2017
    assert bt.mae < bt.naive_mae
    assert abs(bt.total_error) < 10


def test_short_history_is_refused(sales):
    one_year = sales[sales['Year'] == 2017]
    with pytest.raises(ValueError):
        forecast_next_year(one_year)
