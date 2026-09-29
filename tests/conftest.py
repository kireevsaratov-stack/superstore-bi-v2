import pytest

from superstore.data import load_rates, load_sales


@pytest.fixture(scope='session')
def sales():
    return load_sales()


@pytest.fixture(scope='session')
def rates():
    return load_rates()
