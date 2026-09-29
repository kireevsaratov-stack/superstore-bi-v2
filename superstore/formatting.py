"""Форматирование чисел и слов для подписей."""


def format_k(value, currency=''):
    """1234567 -> '$1,235K', 950 -> '$950', -5000 -> '-$5K'."""
    sign = '-' if value < 0 else ''
    value = abs(value)
    if value >= 1000:
        return f'{sign}{currency}{value / 1000:,.0f}K'
    return f'{sign}{currency}{value:,.0f}'


def format_delta(value, currency=''):
    """Дельта со знаком: '+$171K' / '-$5K' (st.metric красит по ведущему минусу)."""
    return ('+' if value >= 0 else '') + format_k(value, currency)


def plural(n, one, few, many):
    """Склонение по числу: plural(342, 'продукт', 'продукта', 'продуктов') -> 'продукта'."""
    n = abs(int(n))
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def truncate(s, n=25):
    return s if len(s) <= n else s[:n] + '…'
