"""Расчёты блоков и авто-выводы."""
import pytest

from superstore import analytics as an
from superstore.formatting import format_delta, format_k, plural


def by_years(df, years):
    return df[df['Year'].isin(years)]


def test_kpis_deltas_compare_last_two_selected_years(sales):
    k = an.kpis(sales)
    assert (k.cur_year, k.prev_year) == (2017, 2016)
    assert k.sales == pytest.approx(2_297_200.86, abs=0.01)
    assert k.d_sales == pytest.approx(733_215.26 - 609_205.60, abs=0.1)

    k = an.kpis(by_years(sales, [2014, 2017]))              # годы с разрывом
    assert (k.cur_year, k.prev_year) == (2017, 2014)

    k = an.kpis(by_years(sales, [2016]))                     # один год — без дельт
    assert k.cur_year is None and k.d_sales is None


def test_pareto_is_honest(sales):
    p = an.pareto(sales)
    assert (p.n80, p.n_products, p.n_loss) == (342, 1850, 304)
    assert p.earned + p.burned == pytest.approx(p.net)
    # n80 — ровно первый продукт, на котором набирается 80%
    assert p.curve['Cum %'].iloc[p.n80 - 1] >= 80 > p.curve['Cum %'].iloc[p.n80 - 2]
    text = an.pareto_text(p, '$')
    assert '342 продукта из 1850' in text
    assert 'больше всей итоговой прибыли' in text           # 80% заработанного > итоговой прибыли
    assert '304 продукта в минусе' in text


@pytest.mark.parametrize('years', [[2014], [2015], [2016], [2017], [2014, 2017]])
def test_pareto_on_subsets(sales, years):
    p = an.pareto(by_years(sales, years))
    assert 0 < p.n80 <= p.n_products
    assert len(p.curve) >= 2


def test_discounts_turn_loss_making_from_30(sales):
    disc = an.discounts(sales)
    assert list(disc['Группа'].astype(str)) == an.DISCOUNT_LABELS
    assert '«30%»' in an.discount_text(disc)


def test_category_tree_children_never_exceed_parent(sales):
    # treemap с branchvalues='total' не рисуется, если дети больше родителя
    t = an.category_tree(sales)
    value = dict(zip(t.ids, t.values))
    for parent in set(t.parents) - {''}:
        children = sum(v for v, p in zip(t.values, t.parents) if p == parent)
        assert children <= value[parent] * (1 + 1e-12)


def test_texts_mention_known_facts(sales):
    assert 'Technology' in an.categories_text(sales)
    assert 'Tables' in an.categories_text(sales)
    assert 'California' in an.states_text(an.states(sales))
    cs = an.top_customers(sales)
    assert len(cs) == 20
    assert 'топ-20 клиентов дают 12%' in an.customers_text(cs, sales['Sales'].sum())


def test_states_have_codes(sales):
    assert len(an.states(sales)) == sales['State'].nunique() == 49


@pytest.mark.parametrize('n, word', [(1, 'продукт'), (2, 'продукта'), (5, 'продуктов'),
                                     (11, 'продуктов'), (21, 'продукт'), (22, 'продукта'),
                                     (112, 'продуктов'), (304, 'продукта'), (342, 'продукта')])
def test_plural(n, word):
    assert plural(n, 'продукт', 'продукта', 'продуктов') == word


def test_money_format():
    assert format_k(1_234_567, '$') == '$1,235K'
    assert format_k(950, '$') == '$950'
    assert format_k(-7_000, '$') == '-$7K'                   # минус перед валютой
    assert format_delta(171_000, '$') == '+$171K'
    assert format_delta(-5_000, '₽') == '-₽5K'
