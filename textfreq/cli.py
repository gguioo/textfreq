# -*- coding: utf-8 -*-
"""命令行入口：textfreq run <文件夹> -o 输出目录"""
import argparse
from pathlib import Path

from .cleaner import load_corpus
from .segment import load_stopwords, load_userdict
from .analyze import word_freq, yearly_trend, cooccurrence_matrix, save_csv


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="textfreq",
        description="文科文本批量词频统计工具箱：TXT 清洗→分词→词频/年度趋势/共词矩阵")
    sub = ap.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="对文件夹内全部 TXT 跑完整统计")
    run.add_argument("folder", help="存放 TXT 的文件夹路径")
    run.add_argument("-o", "--outdir", default="textfreq_out", help="输出目录")
    run.add_argument("--top", type=int, default=100, help="词频总表收录前 N 词")
    run.add_argument("--cooc-top", type=int, default=30, help="共词矩阵取前 N 高频词")
    run.add_argument("--stopwords", help="自定义停用词文件（每行一词）")
    run.add_argument("--userdict", help="自定义领域词表（每行一词，可带词频词性）")

    args = ap.parse_args(argv)

    corpus = load_corpus(args.folder)
    print(f"[1/4] 读入并清洗 {len(corpus)} 个文件")
    stopwords = load_stopwords(args.stopwords)
    load_userdict(args.userdict)

    freq = word_freq(corpus, stopwords)
    print(f"[2/4] 分词完成，共 {sum(freq.values())} 个有效词，去重 {len(freq)} 词")

    outdir = Path(args.outdir)
    rows = [["排名", "词语", "频次"]] + [
        [i, w, c] for i, (w, c) in enumerate(freq.most_common(args.top), 1)]
    save_csv(rows, outdir / "词频总表.csv")

    trend = yearly_trend(corpus, stopwords)
    if trend:
        save_csv(trend, outdir / "年度趋势.csv")
        print("[3/4] 检测到文件名含年份，已输出年度趋势")
    else:
        print("[3/4] 文件名未检测到年份，跳过年度趋势")

    cooc = cooccurrence_matrix(corpus, stopwords, topn=args.cooc_top)
    save_csv(cooc, outdir / "共词矩阵.csv")
    print(f"[4/4] 输出完成 → {outdir.resolve()}")
    print("\nTop 10：")
    for w, c in freq.most_common(10):
        print(f"  {w}\t{c}")


if __name__ == "__main__":
    main()
