"""Скачивает официальные курсы ЦБ РФ (USD → RUB) и сохраняет в data/usd_rub_cbr.csv.

Запускать вручную, один раз: исторические курсы не меняются, поэтому
приложение читает готовый файл и в сеть не ходит.

    .venv/bin/python scripts/fetch_cbr_rates.py

Источник — официальный API ЦБ (XML_dynamic), R01235 = доллар США.
Период берётся с запасом до начала данных (первый заказ 03.01.2014),
чтобы у каждого заказа был курс «на дату или раньше».
"""
import csv
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.request import urlopen

URL = ('https://www.cbr.ru/scripts/XML_dynamic.asp'
       '?date_req1=01/12/2013&date_req2=31/12/2017&VAL_NM_RQ=R01235')
OUT = Path(__file__).resolve().parent.parent / 'data' / 'usd_rub_cbr.csv'


def main():
    with urlopen(URL, timeout=30) as resp:
        root = ET.fromstring(resp.read())

    rows = []
    for rec in root.findall('Record'):
        day, month, year = rec.get('Date').split('.')
        nominal = int(rec.find('Nominal').text)
        value = float(rec.find('Value').text.replace(',', '.'))
        rows.append((f'{year}-{month}-{day}', round(value / nominal, 4)))
    rows.sort()

    with OUT.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['date', 'usd_rub'])
        writer.writerows(rows)
    print(f'{len(rows)} курсов: {rows[0][0]} … {rows[-1][0]} → {OUT}')


if __name__ == '__main__':
    main()
