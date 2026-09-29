"""Расчёты для блоков дашборда и тексты авто-выводов. Без Streamlit.

Каждая функция получает уже отфильтрованную таблицу (выбранные годы, нужная валюта),
поэтому все выводы пересчитываются при смене годов и валюты.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import STATE_CODES
from .formatting import format_k, plural, truncate


def _ratio_pct(num, den):
    """num / den * 100, а при den == 0 — 0 (без предупреждений о делении на ноль)."""
    return (num / den.where(den != 0) * 100).fillna(0)


# =========================================================
# KPI + ДЕЛЬТЫ (последний выбранный год vs предпоследний)
# =========================================================
@dataclass
class Kpis:
    sales: float
    profit: float
    orders: int
    customers: int
    cur_year: int | None = None      # дельты считаются «cur_year к prev_year»
    prev_year: int | None = None
    d_sales: float | None = None
    d_profit: float | None = None
    d_orders: int | None = None
    d_customers: int | None = None


def kpis(df):
    k = Kpis(sales=df['Sales'].sum(), profit=df['Profit'].sum(),
             orders=df['Order ID'].nunique(), customers=df['Customer ID'].nunique())
    years = sorted(df['Year'].unique())
    if len(years) >= 2:
        cur = df[df['Year'] == years[-1]]
        prev = df[df['Year'] == years[-2]]
        k.cur_year, k.prev_year = int(years[-1]), int(years[-2])
        k.d_sales = cur['Sales'].sum() - prev['Sales'].sum()
        k.d_profit = cur['Profit'].sum() - prev['Profit'].sum()
        k.d_orders = cur['Order ID'].nunique() - prev['Order ID'].nunique()
        k.d_customers = cur['Customer ID'].nunique() - prev['Customer ID'].nunique()
    return k


# =========================================================
# РЯД 1: продажи по месяцам + Парето
# =========================================================
def monthly(df):
    m = df.groupby(df['Order Date'].dt.to_period('M')).agg(
        Sales=('Sales', 'sum'), Profit=('Profit', 'sum')).reset_index()
    m['Order Date'] = m['Order Date'].astype(str)
    return m


@dataclass
class Pareto:
    curve: pd.DataFrame   # N, Cum % — кривая до точки, где набирается 80%
    n80: int              # сколько прибыльных продуктов дают 80% заработанной прибыли
    n_products: int
    n_loss: int           # убыточные и нулевые продукты
    earned: float         # «заработанная» прибыль: сумма по прибыльным продуктам
    burned: float         # убыток убыточных продуктов (отрицательное число)
    net: float            # итоговая прибыль = earned + burned


def pareto(df):
    # Парето считаем только по прибыльным продуктам: отрицательная прибыль
    # искажает накопительный процент.
    prod = df.groupby('Product Name')['Profit'].sum().sort_values(ascending=False)
    pos = prod[prod > 0]
    cum = (pos.cumsum() / pos.sum() * 100).to_numpy() if len(pos) else np.array([])
    # первый продукт, на котором накопленная доля достигает 80%
    n80 = min(int(np.searchsorted(cum, 80)) + 1, len(pos)) if len(pos) else 0
    curve = pd.DataFrame({'N': np.arange(1, len(pos) + 1), 'Cum %': cum}).head(max(n80, 2))
    return Pareto(curve=curve, n80=n80, n_products=len(prod), n_loss=int((prod <= 0).sum()),
                  earned=float(pos.sum()), burned=float(prod[prod <= 0].sum()),
                  net=float(prod.sum()))


def pareto_text(p, currency):
    if not p.n80:
        return '**Вывод:** прибыльных продуктов за выбранный период нет.'
    share = p.n80 / p.n_products * 100
    target = p.earned * 0.8
    txt = (f'**Вывод:** {p.n80} {plural(p.n80, "продукт", "продукта", "продуктов")} '
           f'из {p.n_products} (≈{share:.0f}%) приносят 80% заработанной прибыли — '
           f'{format_k(target, currency)}')
    if target > p.net:
        txt += f', это больше всей итоговой прибыли ({format_k(p.net, currency)})'
    txt += '.'
    if p.n_loss:
        txt += (f' Ещё {p.n_loss} {plural(p.n_loss, "продукт", "продукта", "продуктов")} '
                f'в минусе и съедают {format_k(-p.burned, currency)}.')
    return txt


# =========================================================
# РЯД 2: топ-15 по выручке + топ-15 убыточных
# =========================================================
def top_products(df, n=15):
    t = df.groupby('Product Name')['Sales'].sum().nlargest(n).reset_index()
    t['Label'] = t['Product Name'].apply(truncate)
    return t


def top_losses(df, n=15):
    t = df.groupby('Product Name')['Profit'].sum().nsmallest(n).reset_index()
    t['Label'] = t['Product Name'].apply(truncate)
    return t


# =========================================================
# РЯД 3: скидки + топ-20 клиентов
# =========================================================
DISCOUNT_BINS = [-0.01, 0, .10, .20, .30, .40, .50, .60, .80]
DISCOUNT_LABELS = ['0%', '10%', '20%', '30%', '40%', '50%', '60%', '70%+']


def discounts(df):
    groups = pd.cut(df['Discount'], bins=DISCOUNT_BINS, labels=DISCOUNT_LABELS,
                    include_lowest=True)
    disc = df.assign(Группа=groups).groupby('Группа', observed=False).agg(
        Sales=('Sales', 'sum'), Profit=('Profit', 'sum'),
        Orders=('Order ID', 'nunique')).reset_index()
    disc['Рент. %'] = _ratio_pct(disc['Profit'], disc['Sales'])
    return disc


def discount_text(disc):
    neg = disc[disc['Рент. %'] < 0]['Группа']
    if len(neg):
        return (f'**Вывод:** скидки от «{neg.iloc[0]}» делают заказы убыточными — '
                f'ограничение глубоких скидок быстрее всего поднимет прибыль.')
    return '**Вывод:** даже при больших скидках заказы остаются прибыльными.'


def top_customers(df, n=20):
    return df.groupby('Customer ID').agg(
        Name=('Customer Name', 'first'), Sales=('Sales', 'sum'),
        Profit=('Profit', 'sum')).reset_index().nlargest(n, 'Sales')


def customers_text(cs, total_sales):
    share = cs['Sales'].sum() / total_sales * 100 if total_sales else 0
    n_loss = int((cs['Profit'] < 0).sum())
    if n_loss:
        return (f'**Вывод:** топ-20 клиентов дают {share:.0f}% выручки; '
                f'из них {n_loss} убыточны (красные) — стоит пересмотреть условия.')
    return f'**Вывод:** топ-20 клиентов дают {share:.0f}% выручки, и все они прибыльны.'


# =========================================================
# РЯД 4: структура (treemap) + география
# =========================================================
@dataclass
class CategoryTree:
    ids: list
    labels: list
    parents: list
    values: list    # выручка
    profits: list
    margins: list   # маржа, %


def category_tree(df):
    cats = df.groupby('Category').agg(S=('Sales', 'sum'), P=('Profit', 'sum')).reset_index()
    subs = df.groupby(['Category', 'Sub-Category']).agg(
        S=('Sales', 'sum'), P=('Profit', 'sum')).reset_index().rename(columns={'Sub-Category': 'Sub'})

    def margin(p, s):
        return p / s * 100 if s else 0

    t = CategoryTree([], [], [], [], [], [])

    def add(node_id, label, parent, s, p):
        t.ids.append(node_id); t.labels.append(label); t.parents.append(parent)
        t.values.append(s); t.profits.append(p); t.margins.append(margin(p, s))

    add('Все', 'Все', '', cats['S'].sum(), cats['P'].sum())
    for r in cats.itertuples():
        add(r.Category, r.Category, 'Все', r.S, r.P)
    for r in subs.itertuples():
        add(f'{r.Category}/{r.Sub}', r.Sub, r.Category, r.S, r.P)
    return t


def categories_text(df):
    cats = df.groupby('Category').agg(S=('Sales', 'sum'), P=('Profit', 'sum'))
    if cats.empty:
        return None
    cats['M'] = _ratio_pct(cats['P'], cats['S'])
    subs = df.groupby('Sub-Category')['Profit'].sum()
    losers = subs[subs < 0].sort_values().index.tolist()
    best, low = cats['P'].idxmax(), cats['M'].idxmin()
    if losers:
        return (f'**Вывод:** больше всего прибыли даёт «{best}», '
                f'а у «{low}» маржа всего {cats.loc[low, "M"]:.0f}% — '
                f'её тянут вниз убыточные подкатегории: {", ".join(losers[:3])}.')
    return f'**Вывод:** больше всего прибыли даёт «{best}»; убыточных подкатегорий нет.'


def states(df):
    geo = df.groupby('State').agg(Sales=('Sales', 'sum'), Profit=('Profit', 'sum')).reset_index()
    geo['Code'] = geo['State'].map(STATE_CODES)
    return geo.dropna(subset=['Code'])


def states_text(geo):
    best = geo.loc[geo['Profit'].idxmax(), 'State']
    loss_big = geo[geo['Profit'] < 0].nlargest(3, 'Sales')['State'].tolist()
    if loss_big:
        return (f'**Вывод:** больше всего прибыли приносит {best}; '
                f'при этом {", ".join(loss_big)} дают большие продажи, но убыточны.')
    return f'**Вывод:** больше всего прибыли приносит {best}; убыточных штатов нет.'
