# -*- coding: utf-8 -*-
"""统计模块：词频总表、年度趋势、共词矩阵。"""
import re
from collections import Counter
from pathlib import Path

import csv

YEAR_RE = re.compile(r"(19|20)\d{2}")


def detect_year(filename: str):
    m = YEAR_RE.search(filename)
    return int(m.group(0)) if m else None


def word_freq(corpus, stopwords, topn=100):
    """corpus: [(fname, text), ...] -> Counter(整体词频)"""
    from .segment import segment
    total = Counter()
    for _, text in corpus:
        total.update(segment(text, stopwords))
    return total


def yearly_trend(corpus, stopwords, topn=30):
    """文件名含年份时，输出 {年份: Counter}；否则返回 None。
    每年额外给出行「_当年总词数_」，方便按占比看趋势，避免各年语料量不均。"""
    from .segment import segment
    by_year = {}
    for fname, text in corpus:
        y = detect_year(fname)
        if y is None:
            continue
        by_year.setdefault(y, Counter()).update(segment(text, stopwords))
    if not by_year:
        return None
    years = sorted(by_year)
    top = Counter()
    for c in by_year.values():
        top.update(c)
    words = [w for w, _ in top.most_common(topn)]
    rows = [["词语"] + [str(y) for y in years] + ["合计"]]
    totals = {y: sum(by_year[y].values()) for y in years}
    rows.append(["_当年总词数_"] + [totals[y] for y in years] + [sum(totals.values())])
    for w in words:
        row = [w] + [by_year[y].get(w, 0) for y in years]
        # 每万词频率：消除各年语料量差异
        norm = ["%.2f" % (by_year[y].get(w, 0) / totals[y] * 10000) if totals[y] else "0"
                for y in years]
        row = row + ["(" + n + ")" for n in norm]
        row.append(sum(by_year[y].get(w, 0) for y in years))
        rows.append(row)
    return rows


def cooccurrence_matrix(corpus, stopwords, topn=30):
    """文档级共词矩阵：两个词在同一篇文档同时出现则计数 +1。"""
    from .segment import segment
    counts = Counter()
    for _, text in corpus:
        counts.update(set(segment(text, stopwords)))
    words = [w for w, _ in counts.most_common(topn)]
    n = len(words)
    matrix = [[0] * n for _ in range(n)]
    for _, text in corpus:
        present = set(segment(text, stopwords))
        idx = [i for i, w in enumerate(words) if w in present]
        for a in idx:
            for b in idx:
                if a != b:
                    matrix[a][b] += 1
    header = [""] + words
    rows = [header]
    for i, w in enumerate(words):
        rows.append([w] + [matrix[i][j] for j in range(n)])
    return rows


def save_csv(rows, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)
