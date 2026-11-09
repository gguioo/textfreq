# -*- coding: utf-8 -*-
"""桌面版界面：双击「启动统计工具」即可使用，全程点鼠标，不用敲命令。

选文件夹 → 点开始 → 表格显示统计结果，CSV 自动保存，可一键打开输出文件夹。
"""
import os
import threading
from pathlib import Path

from .cleaner import load_corpus
from .segment import load_stopwords, load_userdict
from .analyze import word_freq, yearly_trend, cooccurrence_matrix, save_csv


def run_stats(folder, outdir, top=100, cooc_top=30, stopwords=None, userdict=None):
    """纯计算部分：返回 (词频行, 年度趋势行或None, 共词矩阵行)，并写出 CSV。"""
    corpus = load_corpus(folder)
    stop = load_stopwords(stopwords)
    load_userdict(userdict)

    freq = word_freq(corpus, stop)
    rows_freq = [["排名", "词语", "频次"]] + [
        [i, w, c] for i, (w, c) in enumerate(freq.most_common(top), 1)]
    rows_trend = yearly_trend(corpus, stop)
    rows_cooc = cooccurrence_matrix(corpus, stop, cooc_top)

    outdir = Path(outdir)
    save_csv(rows_freq, outdir / "词频总表.csv")
    if rows_trend:
        save_csv(rows_trend, outdir / "年度趋势.csv")
    save_csv(rows_cooc, outdir / "共词矩阵.csv")
    return corpus, rows_freq, rows_trend, rows_cooc


def main():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    class App(tk.Tk):
        def __init__(self):
            super().__init__()
            self.title("textfreq · 文科文本词频统计")
            self.geometry("920x640")
            self._build_form()
            self._build_results()

        # ---------- 表单区 ----------
        def _build_form(self):
            box = ttk.LabelFrame(self, text=" 1. 选择文件与选项 ")
            box.pack(fill="x", padx=12, pady=(12, 6))

            self.v_folder = tk.StringVar()
            self.v_stop = tk.StringVar()
            self.v_dict = tk.StringVar()
            self.v_out = tk.StringVar()
            self.v_top = tk.StringVar(value="100")
            self.v_cooc = tk.StringVar(value="30")

            def add_row(r, label, var, browse=None):
                ttk.Label(box, text=label).grid(row=r, column=0, sticky="e", padx=6, pady=3)
                ttk.Entry(box, textvariable=var, width=62).grid(row=r, column=1, padx=4, pady=3, sticky="we")
                if browse:
                    ttk.Button(box, text="浏览…", command=lambda: self._pick(var, browse)).grid(row=r, column=2, padx=4)

            box.columnconfigure(1, weight=1)
            add_row(0, "TXT 文件夹：", self.v_folder, "dir")
            add_row(1, "输出位置（默认自动）：", self.v_out, "dir")
            add_row(2, "停用词文件（可选）：", self.v_stop, "file")
            add_row(3, "领域词表（可选）：", self.v_dict, "file")
            row4 = ttk.Frame(box); row4.grid(row=4, columnspan=3, pady=4)
            ttk.Label(row4, text="词频收录前：").pack(side="left")
            ttk.Spinbox(row4, from_=10, to=1000, textvariable=self.v_top, width=6).pack(side="left", padx=4)
            ttk.Label(row4, text="共词矩阵取前：").pack(side="left", padx=(12, 0))
            ttk.Spinbox(row4, from_=10, to=100, textvariable=self.v_cooc, width=6).pack(side="left", padx=4)

            bar = ttk.Frame(self); bar.pack(fill="x", padx=12, pady=4)
            self.btn_run = ttk.Button(bar, text=" 2. 开始统计 ", command=self.start)
            self.btn_run.pack(side="left")
            self.btn_open = ttk.Button(bar, text="打开结果文件夹", state="disabled", command=self.open_out)
            self.btn_open.pack(side="left", padx=8)
            self.status = ttk.Label(bar, text="就绪")
            self.status.pack(side="right")

        def _pick(self, var, kind):
            p = filedialog.askdirectory() if kind == "dir" else filedialog.askopenfilename()
            if p:
                var.set(p)

        # ---------- 结果区 ----------
        def _build_results(self):
            nb = self.nb = ttk.Notebook(self)
            nb.pack(fill="both", expand=True, padx=12, pady=8)
            self.tables = {}
            for name in ("词频总表", "年度趋势", "共词矩阵"):
                f = ttk.Frame(nb)
                tv = ttk.Treeview(f, show="headings")
                ys = ttk.Scrollbar(f, orient="vertical", command=tv.yview)
                tv.configure(yscrollcommand=ys.set)
                tv.pack(side="left", fill="both", expand=True); ys.pack(side="right", fill="y")
                nb.add(f, text=name)
                self.tables[name] = tv
            self.outdir = None

        def _fill(self, name, rows, limit=300):
            tv = self.tables[name]
            tv["columns"] = rows[0]
            for i, c in enumerate(rows[0]):
                tv.heading(i, text=c)
                tv.column(i, width=110 if i else 70, anchor="w" if i == 1 else "e")
            tv.delete(*tv.get_children())
            for row in rows[1:limit + 1]:
                tv.insert("", "end", values=row)

        # ---------- 执行 ----------
        def start(self):
            folder = self.v_folder.get().strip()
            if not folder or not Path(folder).is_dir():
                messagebox.showwarning("提示", "请先选择 TXT 所在的文件夹")
                return
            out = self.v_out.get().strip() or str(Path(folder) / "textfreq_out")
            self.outdir = Path(out)
            self.btn_run.config(state="disabled")
            self.status.config(text="统计中…文件多的话稍等一下")
            threading.Thread(target=self._work, daemon=True).start()

        def _work(self):
            try:
                corpus, rf, rt, rc = run_stats(
                    self.v_folder.get().strip(), self.outdir,
                    top=int(self.v_top.get() or 100),
                    cooc_top=int(self.v_cooc.get() or 30),
                    stopwords=self.v_stop.get().strip() or None,
                    userdict=self.v_dict.get().strip() or None)
            except Exception as e:  # 界面上友好报错，不闪退
                self.after(0, lambda: (self.btn_run.config(state="normal"),
                                       self.status.config(text="出错了"),
                                       messagebox.showerror("出错了", f"{e}")))
                return
            def done():
                self._fill("词频总表", rf)
                if rt:
                    self._fill("年度趋势", rt)
                else:
                    self.nb.tab(1, state="disabled")
                self._fill("共词矩阵", rc, limit=30)
                self.btn_run.config(state="normal")
                self.btn_open.config(state="normal")
                n_years = "" if rt else "（文件名没带年份，未生成趋势表）"
                self.status.config(text=f"完成：{len(corpus)} 个文件，结果已保存到 {self.outdir}{n_years}")
            self.after(0, done)

        def open_out(self):
            try:
                os.startfile(self.outdir)  # Windows
            except AttributeError:
                os.system(f'open "{self.outdir}"' if os.uname().sysname == "Darwin"
                          else f'xdg-open "{self.outdir}"')

    App().mainloop()


if __name__ == "__main__":
    main()
