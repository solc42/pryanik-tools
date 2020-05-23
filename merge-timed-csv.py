# -*- coding: <encoding name> -*-
# Принимает на вход два файла.
#
# Первый формата(в кодировке win1251):
#
# Дата;Код<br>фьючерса;Размеры<br>ГО<br>(руб./<br>контракт)
# 03.01.2017;GDH7;6498
# 04.01.2017;GDH7;6594
# 05.01.2017;GDH7;6528
#
# Второй формата:
#
# <TICKER>;<PER>;<DATE>;<TIME>;<OPEN>;<HIGH>;<LOW>;<CLOSE>;<VOL>
# SPFB.GOLD;1;20170103;100000;1158.0000000;1164.1000000;1158.0000000;1162.5000000;738
# SPFB.GOLD;1;20170103;100100;1162.3000000;1162.3000000;1162.0000000;1162.0000000;252
# SPFB.GOLD;1;20170103;100200;1162.1000000;1162.2000000;1161.9000000;1162.1000000;43
#
#
# И строит результат вида:
# <TICKER>;<PER>;<DATE>;<TIME>;<OPEN>;<HIGH>;<LOW>;<CLOSE>;<VOL>;Дата;Код<br>фьючерса;Размеры<br>ГО<br>(руб./<br>контракт)
# SPFB.GOLD;1;20170103;100000;1158.0000000;1164.1000000;1158.0000000;1162.5000000;738;03.01.2017;GDH7;6498
# SPFB.GOLD;1;20170103;100100;1162.3000000;1162.3000000;1162.0000000;1162.0000000;252;03.01.2017;GDH7;6498
# SPFB.GOLD;1;20170103;100200;1162.1000000;1162.2000000;1161.9000000;1162.1000000;43;03.01.2017;GDH7;6498
#
#
# Пример запуска(python версии 3+):
#
# python merge-times-csv.py first_date_file second_time_file
# где
# first_date_file - фалй где разбивка по датам
# second_time_file - файл где разибвка по времени
#

import sys
import csv
import codecs
import datetime

# кодировка входящих файлов чертов win1251
FILE_ENCODING = "cp1251"
RES_FILE = f'res_{datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")}.csv'


def main() -> None:
    if len(sys.argv) != 3:
        print("""Please specify exactly two arguments
Usage: python merge-times-csv.py first_date_file second_time_file""")

    dated_file = sys.argv[1]
    timed_file = sys.argv[2]
    process_timed(timed_file, *load_dated(dated_file))


def load_dated(target_dated_path: str):
    row_by_date = dict()
    with codecs.open(target_dated_path, "r", FILE_ENCODING) as r_f:
        csv_rdr = csv.reader(r_f, delimiter=';', quotechar='"')
        hdr = None
        for row in csv_rdr:
            if not hdr:
                hdr = row
            else:
                row_by_date[datetime.datetime.strptime(row[0], "%d.%m.%Y")] = row
    return row_by_date, hdr


def process_timed(target_timed_path: str, dated_dict: dict, dated_hdr: str) -> None:
    with codecs.open(target_timed_path, "r", FILE_ENCODING) as r_f, \
            open(RES_FILE, "w") as out_f:
        csv_wrtr = csv.writer(out_f, delimiter=';', quotechar='"')
        csv_rdr = csv.reader(r_f, delimiter=';')
        hdr = None
        for row in csv_rdr:
            if not hdr:
                hdr = row
                csv_wrtr.writerow(hdr + dated_hdr)
            else:
                dt = datetime.datetime.strptime(row[2], "%Y%m%d")
                dated_row = dated_dict.get(dt)
                if dated_row is None:
                    raise Exception(f"ERROR: dated_file has no info for date {dated_row}")
                else:
                    csv_wrtr.writerow(row + dated_row)


if __name__ == '__main__':
    main()
