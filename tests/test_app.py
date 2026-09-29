"""Страница целиком (Streamlit AppTest, без браузера): стартует на любых наборах годов."""
import re
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parent.parent / 'app.py')

BLOCKS = ['Продажи и прибыль по месяцам', 'Парето: концентрация прибыли',
          'Топ-15 продуктов по выручке', 'Топ-15 убыточных продуктов', 'Скидки vs Прибыль',
          'Топ-20 клиентов', 'Структура продаж по категориям',
          'География: продажи и прибыль по штатам', 'Прогноз продаж на 2018 год',
          'Бэктестинг: проверка точности', 'Экспорт данных']


def run_app(years=None, rub=False):
    at = AppTest.from_file(APP, default_timeout=60)
    at.run()
    if years is not None:
        at.session_state['years'] = years          # у st.pills нет обёртки в AppTest
    if rub:
        at.toggle[0].set_value(True)
    if years is not None or rub:
        at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def headers(at):
    return [m.value.removeprefix('##### ') for m in at.markdown if m.value.startswith('#####')]


def page_html(at):
    return ' '.join(m.value for m in at.markdown)


@pytest.mark.parametrize('years', [None, [2017], [2014, 2017], [2015, 2016]])
def test_all_blocks_render(years):
    at = run_app(years)
    assert headers(at) == BLOCKS                    # прогноз всегда на 2018 — не зависит от годов
    assert not at.error
    assert not at.warning


def test_empty_selection_asks_for_a_year():
    at = run_app([])
    assert [w.value for w in at.warning] == ['Выберите хотя бы один год.']
    assert headers(at) == []


def test_kpi_note_names_compared_years():
    assert 'Изменения: 2017 к 2016' in page_html(run_app())
    assert 'Изменения: 2017 к 2014' in page_html(run_app([2014, 2017]))
    assert 'Изменения:' not in page_html(run_app([2016]))


def test_rubles_work_offline_and_fast():
    at = run_app(rub=True)
    html = page_html(at)
    assert '₽' in html and '$' not in html.split('Прогноз')[0]
    assert 'по курсу ЦБ на 30.12.2017' in html
    assert not at.warning                           # никаких «API ЦБ недоступен»


def test_captions_escape_dollar_signs():
    # два неэкранированных «$» в одной подписи Streamlit рисует как LaTeX-формулу
    for cap in run_app().caption:
        assert not re.search(r'(?<!\\)\$', cap.value), cap.value
