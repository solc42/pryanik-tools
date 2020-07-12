# -*- coding: utf-8 -*-
#
# adhoc script for tricky best matched rows extraction.
#

from typing import List, Tuple
import argparse
import csv
import codecs
import datetime
import json
import collections


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--config', required=True, help="Path to config file")
    parser.add_argument('-l', '--lead-file', required=True, help="'First'/'Leading' file")
    parser.add_argument('-f', '--following-file', required=True, help="'Second'/'Following' file")
    parser.add_argument('-e', '--encoding', required=False, default="cp1251", help="Input files encoding. Default = 'cp1251'")
    parser.add_argument('-d', '--delimiter', required=False, default=";", help="Delimiter for csv (in/out). Default = ';'")
    parser.add_argument('-o', '--output-result', required=False,
                        default=f'res_{datetime.datetime.now().strftime("%Y-%m-%d_%H_%M_%S")}.csv',
                        help="File path to save results. Default ~= res_<current_time>.csv"
                        )
    args = parser.parse_args()
    print(f"Launched with args: {args}")
    config = load_cfg(args.config)
    print(f"Launched with config: {config}")

    cv_rows_lead = load_cvrows(args.lead_file, config, args.encoding, args.delimiter)
    cv_rows_fol = load_cvrows(args.following_file, config, args.encoding, args.delimiter)
    res = find_top_matching(cv_rows_lead, cv_rows_fol, config)
    save_res(res, args.output_result, args.delimiter)


def load_cfg(file_path):
    with open(file_path, "r") as cfg_file:
        return json.load(cfg_file)


class CVRow:
    def __init__(self, coeffs: dict, fields: dict):
        self.__coeffs = {k: float(v) for k, v in coeffs.items() if len(v) > 0}
        self.__base_fields = {k: float(v) for k, v in fields.items() if len(v) > 0}

    def __str__(self):
        return f"[f={self.__base_fields}, c={self.__coeffs}]"

    @property
    def base_fields(self) -> dict:
        return self.__base_fields

    @property
    def coeffs(self) -> dict:
        return self.__coeffs


class SimilarityCheck:
    def __init__(self, l_row: CVRow, f_row: CVRow, check_stats: dict, is_similar: bool):
        self.__l_row = l_row
        self.__f_row = f_row
        self.__check_stats = check_stats
        self.__is_similar = is_similar

    def __str__(self):
        return f"[\n l_row={self.__l_row},\n f_row={self.__f_row},\n cs={self.check_stats},\n similar={self.__is_similar}\n]"

    @property
    def l_row(self) -> CVRow:
        return self.__l_row

    @property
    def f_row(self) -> CVRow:
        return self.__f_row

    @property
    def check_stats(self) -> dict:
        return self.__check_stats

    @property
    def is_similar(self) -> bool:
        return self.__is_similar


def find_top_matching(leading_rows: List[CVRow], fol_rows: List[CVRow], config: dict) -> List[SimilarityCheck]:
    similar_results = list(
        filter(
            lambda sc: sc.is_similar,
            [check_similarity(lr, fr, config) for lr in leading_rows for fr in fol_rows]
        )
    )
    similar_results.sort(key=lambda sc: similar_sort_key(sc, config["baseSortingField"]), reverse=True)
    return similar_results[:config["resultRowsToShow"]]


def similar_sort_key(sc: SimilarityCheck, sort_field_name: str) -> Tuple:
    return sc.l_row.base_fields[sort_field_name], sc.f_row.base_fields[sort_field_name]


# метод грязноват, но так как весь скрипт adhoc то некритично
def check_similarity(l_row: CVRow, f_row: CVRow, config: dict) -> SimilarityCheck:
    """
    проверка 'близости' двух записей.
    'близки' - если для значений одноименных коэффициентов значения близки с учетом потенциально
     заданных пороговых значений в конфиге.
    """
    coeff_thresholds = config["coeffConf"]
    base_thresholds = config["baseConf"]
    check_stats = {"Similar_Fields": []}
    is_similar = False

    for f_l, v_l in l_row.coeffs.items():
        opts = get_coeff_options(coeff_thresholds, f_l)
        max_range_value = opts["maxRangeValue"]
        equality_th_pct = opts["equalityThPctIncl"]
        low_th = opts.get("lowerBoundIncl")
        up_th = opts.get("upperBoundIncl")

        check_stats.update(
            {
                f"{f_l}__max_val": max_range_value,
                f"{f_l}__eq_th_pct": equality_th_pct,
                f"{f_l}__low_th": low_th,
                f"{f_l}__up_th": up_th
            }
        )

        v_f = f_row.coeffs.get(f_l)
        if v_f is None:
            raise Exception(f"Failed to find coeff '{f_l}' in 'second' data set")

        # дельта расходится меньше чем пороговое значение в процентах
        if (v_l - v_f) / max_range_value <= equality_th_pct:
            check_stats["Similar_Fields"].append(f_l)
            is_similar = True
            # тут не выходим, чтобы сдампить опции сравнения по всем коэффициентам

    # также сдампим фильтры по базовым полям которые есть в выдаче
    for f_l in l_row.base_fields.keys():

        if f_l in base_thresholds:
            check_stats.update(
                {
                    f"{f_l}__low_th": base_thresholds[f_l].get("lowerBoundIncl"),
                    f"{f_l}__up_th": base_thresholds[f_l].get("upperBoundIncl")
                }
            )

    return SimilarityCheck(l_row, f_row, check_stats, is_similar)


def get_coeff_options(thresholds: dict, coeff_name: str) -> dict:
    options = {"maxRangeValue": 100, "equalityThPctIncl": 0}
    if coeff_name in thresholds:
        options.update(thresholds[coeff_name])

    return options


def build_cv_row(row: collections.OrderedDict, config: dict) -> CVRow:
    coeffs = extract_coefffs(row, config)
    fields = extract_base_fields(row, config)
    return CVRow(coeffs, fields)


def extract_base_fields(row: collections.OrderedDict, config: dict) -> dict:
    """взять основные поля, на основе опции в конфиге"""
    return dict([
        (f, v) for f, v in row.items()
        if f in config["baseFields"]
    ])


def extract_coefffs(row: collections.OrderedDict, config: dict) -> dict:
    """взять коэффициенты, располагающиеся ПОСЛЕ колонки-разделителя(имя задано в конфиге)"""
    idx = find_sep_position(row, config["coeffsSeparatorField"])
    return dict(list(row.items())[idx + 1:])


def is_acceptable_by_value_th(row: CVRow, base_thresholds: dict, coeff_thresholds: dict) -> bool:
    """фильтр записей, на основе потенциально заданных пороговых значений"""
    for f, v in row.base_fields.items():
        if f in base_thresholds:
            lower_bound_incl = base_thresholds[f].get("lowerBoundIncl")
            if lower_bound_incl is not None and v < lower_bound_incl:
                return False
            upper_bound_incl = base_thresholds[f].get("upperBoundIncl")
            if upper_bound_incl is not None and v > upper_bound_incl:
                return False

    for f, v in row.coeffs.items():
        if f in coeff_thresholds:
            lower_bound_incl = coeff_thresholds[f].get("lowerBoundIncl")
            if lower_bound_incl is not None and v < lower_bound_incl:
                return False
            upper_bound_incl = coeff_thresholds[f].get("upperBoundIncl")
            if upper_bound_incl is not None and v > upper_bound_incl:
                return False

    return True


def find_sep_position(hdr_row: collections.OrderedDict, coeff_separator_field) -> int:
    for idx, f in enumerate(hdr_row.keys(), start=0):
        if f == coeff_separator_field:
            return idx
    raise Exception(f"Failed to find separator field '{coeff_separator_field}'")


def load_cvrows(file: str, config: dict, enc: str, csv_delimiter: str) -> List[CVRow]:
    with codecs.open(file, "r", enc) as r_f:
        cv_rows = list(filter(
            lambda r: is_acceptable_by_value_th(r, config["baseConf"], config["coeffConf"]),
            [
                build_cv_row(row, config)
                for row in csv.DictReader(r_f, quotechar='"', delimiter=csv_delimiter)
            ]
        ))

        sort_field = config["baseSortingField"]
        rows_to_analyze = config["topRowsToAnalyze"]
        cv_rows.sort(key=lambda r: r.base_fields[sort_field], reverse=True)
        return cv_rows[:rows_to_analyze]


def save_res(checks: List[SimilarityCheck], res_file_name: str, delimiter: str) -> None:
    print(f"Saving result to: {res_file_name}")
    with open(res_file_name, "w") as out_f:
        csv_wrtr = csv.writer(out_f, delimiter=delimiter, quotechar='"', lineterminator='\n')
        for idx, sc in enumerate(checks, start=1):
            (l_base_hdr, l_base_values) = list(zip(*sc.l_row.base_fields.items()))
            (l_coeff_hdr, l_coeff_values) = list(zip(*sc.l_row.coeffs.items()))
            (meta_hdr, meta_values) = list(zip(*sc.check_stats.items()))

            csv_wrtr.writerow([f"Пара #{idx}. Результат из 'первого' файла"])
            csv_wrtr.writerow(list(l_base_hdr + l_coeff_hdr + meta_hdr))
            csv_wrtr.writerow(list(l_base_values + l_coeff_values + meta_values))

            csv_wrtr.writerow([f"Пара #{idx}. Результат из 'второго' файла"])
            (f_base_hdr, f_base_values) = list(zip(*sc.f_row.base_fields.items()))
            (f_coeff_hdr, f_coeff_values) = list(zip(*sc.f_row.coeffs.items()))
            csv_wrtr.writerow(list(f_base_hdr + f_coeff_hdr))
            csv_wrtr.writerow(list(f_base_values + f_coeff_values))

            csv_wrtr.writerow([""])


if __name__ == '__main__':
    main()
