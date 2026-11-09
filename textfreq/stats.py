# -*- coding: utf-8 -*-
"""现代语料统计模块：关键词检验、搭配强度、词汇丰富度、跨文档分布度。"""
import math
import re
from collections import Counter

YEAR_RE = re.compile(r"(19|20)\d{2}")


def detect_year(filename: str):
    m = YEAR_RE.search(filename)
    return int(m.group(0)) if m else None


def word_freq(corpus, stopwords, topn=100):
    from .segment import segment
    total = Counter()
    for _, text in corpus:
        total.update(segment(text, stopwords))
    return total


def doc_freq_map(corpus, stopwords):
    """每个文档的词频列表，供分布度等计算复用。"""
    from .segment import segment
    return [Counter(segment(text, stopwords)) for _, text in corpus]


def dispersion(doc_counters, word):
    """Juilland's D：1 - 标准差/均值，取值 0~1，越接近 1 跨文档分布越均匀。"""
    n = len(doc_counters)
    if n < 2:
        return None
    xs = [c.get(word, 0) for c in doc_counters]
    mean = sum(xs) / n
    if mean == 0:
        return None
    var = sum((x - mean) ** 2 for x in xs) / n
    return max(0.0, 1 - math.sqrt(var) / mean)


def keywords_ll(target_freq, ref_freq, min_freq=5, topn=100):
    """对数似然（Log-Likelihood）关键词检验：找出在目标语料中显著超频的词。
    正值 = 目标语料中显著偏多；负值 = 显著偏少。按 |LL| 排序。
    """
    n1 = sum(target_freq.values())
    n2 = sum(ref_freq.values())
    if not n1 or not n2:
        return []
    rows = []
    for w, f1 in target_freq.items():
        if f1 < min_freq:
            continue
        f2 = ref_freq.get(w, 0)
        # 合并期望频率
        e1 = n1 * (f1 + f2) / (n1 + n2)
        e2 = n2 * (f1 + f2) / (n1 + n2)
        ll = 0.0
        if f1 > 0:
            ll += f1 * math.log(f1 / e1)
        if f2 > 0:
            ll += f2 * math.log(f2 / e2)
        ll *= 2
        direction = "超频" if f1 / n1 > f2 / n2 else "偏少"
        rows.append([w, f1, f2, round(ll, 2), direction])
    rows.sort(key=lambda r: -abs(r[3]))
    return rows[:topn]


def collocations(doc_tokens, node_freq, targets, window=5, min_count=4, topn=200):
    """窗口内共现搭配：互信息 MI 和 t 分数衡量搭配强度。"""
    total_tokens = sum(node_freq.values())
    assoc = {w: Counter() for w in targets}
    for toks in doc_tokens:
        for i, t in enumerate(toks):
            if t not in assoc:
                continue
            for j in range(max(0, i - window), min(len(toks), i + window + 1)):
                if j != i:
                    assoc[t][toks[j]] += 1
    rows = []
    seen = set()
    for node, counter in assoc.items():
        fn = node_freq[node]
        for col, o in counter.most_common():
            if o < min_count:
                continue
            if col in assoc and (col, node) in seen:
                continue  # 对称配对只保留一个方向
            seen.add((node, col))
            fc = node_freq[col]
            # MI：共现次数与随机共现期望之比的对数，越大越"铁"
            mi = math.log2((o * total_tokens) / (fn * fc)) if fn and fc else 0.0
            # t 分数：样本量充足时更稳健，突出高频搭配
            expected = fn * fc / total_tokens
            t_score = (o - expected) / math.sqrt(o)
            rows.append([node, col, o, round(mi, 2), round(t_score, 2)])
    rows.sort(key=lambda r: -r[4])
    return rows[:topn]


def diversity(year_tokens):
    """词汇丰富度：TTR / STTR（每千词窗口）/ Guiraud / 奇次词占比，总体+分年。"""
    def metrics(counter):
        total = sum(counter.values())
        if not total:
            return None
        types = len(counter)
        ttr = types / total
        hapax = sum(1 for v in counter.values() if v == 1)
        guiraud = types / math.sqrt(total)
        # STTR：按 1000 词切块求 TTR 均值
        toks = list(counter.elements())
        chunks = [Counter(toks[i:i + 1000]) for i in range(0, len(toks) - 999, 1000)]
        sttr = (sum(len(c) for c in chunks) / len(chunks) / 1000) if chunks else ttr
        return [total, types, round(ttr, 4), round(sttr, 4),
                round(guiraud, 2), round(hapax / total, 4)]
    rows = [["范围", "总词数", "不同词数", "TTR", "STTR", "Guiraud", "奇次词占比"]]
    overall = Counter()
    for c in year_tokens.values():
        overall.update(c)
    m = metrics(overall)
    if m:
        rows.append(["全部"] + m)
    for y in sorted(year_tokens):
        m = metrics(year_tokens[y])
        if m:
            rows.append([str(y)] + m)
    return rows if len(rows) > 1 else None
