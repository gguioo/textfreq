# -*- coding: utf-8 -*-
"""命令行入口：textfreq run <文件夹> -o 输出目录"""
import argparse
from pathlib import Path

from .cleaner import load_corpus
from .segment import load_stopwords, load_userdict
from .analyze import word_freq, yearly_trend, cooccurrence_matrix, save_csv
from .stats import (doc_freq_map, dispersion, keywords_ll,
                    collocations, diversity)
from collections import Counter


def run_all(folder, outdir, top=100, cooc_top=30,
            stopwords=None, userdict=None, reference=None,
            window=5, min_count=4, ref_top=100):
    """跑完整统计并写出全部 CSV，返回各表内容（供桌面版复用）。"""
    corpus = load_corpus(folder)
    stop = load_stopwords(stopwords)
    load_userdict(userdict)

    freq = word_freq(corpus, stop)
    doc_counters = doc_freq_map(corpus, stop)

    # 词频总表：附跨文档分布度（Juilland's D）
    freq_rows = [["排名", "词语", "频次", "分布度D(0~1)"]]
    for i, (w, c) in enumerate(freq.most_common(top), 1):
        dp = dispersion(doc_counters, w)
        freq_rows.append([i, w, c, "%.3f" % dp if dp is not None else ""])

    trend = yearly_trend(corpus, stop)
    cooc = cooccurrence_matrix(corpus, stop, cooc_top)

    outdir = Path(outdir)
    save_csv(freq_rows, outdir / "词频总表.csv")
    if trend:
        save_csv(trend, outdir / "年度趋势.csv")
    save_csv(cooc, outdir / "共词矩阵.csv")

    # 搭配强度（互信息 + t 分数）
    from .segment import segment
    doc_tokens = [segment(text, stop) for _, text in corpus]
    targets = [w for w, _ in freq.most_common(30)]
    coll = collocations(doc_tokens, freq, targets, window=window,
                        min_count=min_count, topn=200)
    save_csv([["目标词", "搭配词", "共现次数", "互信息MI", "t分数"]] + coll,
             outdir / "搭配表.csv")

    # 词汇丰富度
    by_year = {}
    for (fname, _), toks in zip(corpus, doc_tokens):
        from .analyze import detect_year
        y = detect_year(fname)
        if y is not None:
            by_year.setdefault(y, Counter()).update(toks)
    div = diversity(by_year)
    if div:
        save_csv(div, outdir / "词汇多样性.csv")

    # 关键词检验（需要参照语料）
    kw = None
    if reference:
        ref_corpus = load_corpus(reference)
        ref_freq = word_freq(ref_corpus, stop)
        kw = keywords_ll(freq, ref_freq, min_freq=5, topn=100)
        save_csv([["关键词", "本文库频次", "参照库频次", "对数似然LL", "方向"]] + kw,
                 outdir / "关键词.csv")

    return corpus, freq_rows, trend, cooc, coll, div, kw


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="textfreq",
        description="文科文本批量词频统计工具箱：TXT 清洗→分词→词频/趋势/共词/搭配/关键词")
    sub = ap.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="对文件夹内全部 TXT 跑完整统计")
    run.add_argument("folder", help="存放 TXT 的文件夹路径")
    run.add_argument("-o", "--outdir", default="textfreq_out", help="输出目录")
    run.add_argument("--top", type=int, default=100, help="词频总表收录前 N 词")
    run.add_argument("--cooc-top", type=int, default=30, help="共词矩阵取前 N 高频词")
    run.add_argument("--stopwords", help="自定义停用词文件（每行一词）")
    run.add_argument("--userdict", help="自定义领域词表（每行一词）")
    run.add_argument("--reference", help="参照语料文件夹：做关键词显著性检验（LL）")
    run.add_argument("--window", type=int, default=5, help="搭配统计窗口宽度（默认左右各5词）")
    run.add_argument("--min-count", type=int, default=4, help="搭配最低共现次数（默认4）")

    args = ap.parse_args(argv)

    print(f"[1/6] 读入并清洗文件…")
    corpus, freq_rows, trend, cooc, coll, div, kw = run_all(
        args.folder, args.outdir, top=args.top, cooc_top=args.cooc_top,
        stopwords=args.stopwords, userdict=args.userdict,
        reference=args.reference, window=args.window, min_count=args.min_count)
    print(f"[2/6] 共 {len(corpus)} 个文件")
    print(f"[3/6] 词频总表（含分布度）→ 词频总表.csv")
    print(f"[4/6] 搭配表（互信息/t分数）→ 搭配表.csv")
    print(f"[5/6] 词汇多样性 → 词汇多样性.csv" if div else "[5/6] 无分年数据，跳过多样的分年行")
    if kw:
        print(f"[6/6] 关键词检验（LL）→ 关键词.csv")
    else:
        print(f"[6/6] 未提供 --reference 参照语料，跳过关键词检验")
    if trend:
        print(f"年度趋势（含每万词频率）→ 年度趋势.csv")
    print(f"输出完成 → {Path(args.outdir).resolve()}")

    print("\nTop 10：")
    for row in freq_rows[1:11]:
        print(f"  {row[1]}\t{row[2]}")


if __name__ == "__main__":
    main()
