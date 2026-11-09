# -*- coding: utf-8 -*-
"""本地可视化界面：textfreq gui 启动后自动打开浏览器。
选路径 → 点开始 → 页面直接看词频图表和趋势，CSV 一键下载。
"""
import html as h
import io
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .cleaner import load_corpus
from .segment import load_stopwords, load_userdict
from .analyze import word_freq, yearly_trend, cooccurrence_matrix, save_csv

ACCENT = "#B5543B"
NAVY = "#4A5B7A"
GREY = "#8B8B93"
BAR = "#9AA3B0"
INK = "#2B2B33"

PAGE_CSS = f"""
body {{ font-family: "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
       background:#FBF9F4; color:{INK}; margin:0; }}
.wrap {{ max-width: 960px; margin: 0 auto; padding: 32px 20px 60px; }}
h1 {{ font-size: 26px; }} h2 {{ font-size: 19px; margin-top: 40px;
     border-left: 4px solid {ACCENT}; padding-left: 10px; }}
input, button {{ font-size: 16px; padding: 9px 12px; border:1px solid #D8D4CA;
                 border-radius:6px; background:#fff; }}
button {{ background:{NAVY}; color:#fff; border:none; cursor:pointer;
          padding: 10px 26px; border-radius:6px; }}
button:hover {{ background:{ACCENT}; }}
.row {{ margin: 14px 0; }} .row label {{ display:block; margin-bottom:5px;
     font-size:14px; color:{GREY}; }} .row input {{ width: 90%; }}
a.dl {{ color:{NAVY}; }} .muted {{ color:{GREY}; font-size:13px; }}
table {{ border-collapse: collapse; font-size: 14px; }}
td, th {{ border:1px solid #E4E0D6; padding: 4px 10px; text-align:right; }}
th {{ background:#F1EDE4; }}
"""


def _esc(s):
    return h.escape(str(s))


def _bar_svg(top_words, top=15, width=880):
    top_words = top_words[:top]
    if not top_words:
        return ""
    maxv = top_words[0][1] * 1.12
    bh, gap = 26, 12
    H = len(top_words) * (bh + gap) + 30
    label_w = 120
    scale = (width - label_w - 60) / maxv
    parts = [f'<svg width="{width}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    for i, (w, c) in enumerate(top_words):
        y = 10 + i * (bh + gap)
        bw = c * scale
        color = ACCENT if i == 0 else (NAVY if i < 3 else BAR)
        parts.append(f'<text x="{label_w-8}" y="{y+bh*0.72}" text-anchor="end" '
                     f'font-size="14" fill="{INK}">{_esc(w)}</text>')
        parts.append(f'<rect x="{label_w}" y="{y}" width="{bw:.1f}" height="{bh}" '
                     f'fill="{color}" rx="3"/>')
        parts.append(f'<text x="{label_w+bw+8:.1f}" y="{y+bh*0.72}" font-size="13" '
                     f'fill="{INK}">{c}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _trend_svg(trend_rows, width=880, height=320):
    if not trend_rows or len(trend_rows[0]) < 3:
        return ""
    years = trend_rows[0][1:-1]
    words = [r[0] for r in trend_rows[1:6]]
    series = {r[0]: r[1:-1] for r in trend_rows[1:6]}
    pad_l, pad_b, pad_t = 70, 36, 16
    W, H = width, height
    ymax = max((max(map(int, v)) for v in series.values()), default=1) or 1
    n = len(years)
    xs = [pad_l + i * (W - pad_l - 30) / max(n - 1, 1) for i in range(n)]
    def yp(v):
        return pad_t + (H - pad_b - pad_t) * (1 - v / ymax)
    colors = [ACCENT, NAVY, "#7A8B6F", "#A8825E", "#8A6FB4"]
    parts = [f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg">']
    for gy in range(0, 5):
        v = ymax * gy / 4
        y = yp(v)
        parts.append(f'<line x1="{pad_l}" y1="{y:.0f}" x2="{W-30}" y2="{y:.0f}" '
                     f'stroke="#E4E0D6"/>')
        parts.append(f'<text x="{pad_l-8}" y="{y+4:.0f}" text-anchor="end" '
                     f'font-size="12" fill="{GREY}">{v:.0f}</text>')
    for yi, (x, yr) in enumerate(zip(xs, years)):
        parts.append(f'<text x="{x:.0f}" y="{H-12}" text-anchor="middle" '
                     f'font-size="13" fill="{GREY}">{_esc(yr)}</text>')
    for k, word in enumerate(words):
        vals = series[word]
        pts = " ".join(f"{x:.0f},{yp(int(v)):.0f}" for x, v in zip(xs, vals))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{colors[k%5]}" '
                     f'stroke-width="2.5"/>')
        for x, v in zip(xs, vals):
            parts.append(f'<circle cx="{x:.0f}" cy="{yp(int(v)):.0f}" r="3.5" '
                         f'fill="{colors[k%5]}"/>')
    # 图例
    lx = pad_l
    for k, word in enumerate(words):
        parts.append(f'<rect x="{lx}" y="4" width="14" height="6" fill="{colors[k%5]}"/>')
        parts.append(f'<text x="{lx+20}" y="11" font-size="13" fill="{INK}">{_esc(word)}</text>')
        lx += 30 + 14 * len(word)
    parts.append("</svg>")
    return "".join(parts)


def _cooc_table(rows, k=10):
    head = rows[0][: k + 1]
    body = [r[: k + 1] for r in rows[1 : k + 1]]
    out = ["<table><tr>"]
    out += [f"<th>{_esc(c)}</th>" for c in head]
    out.append("</tr>")
    for r in body:
        out.append("<tr>")
        for j, c in enumerate(r):
            tag = "th" if j == 0 else "td"
            out.append(f"<{tag}>{_esc(c)}</{tag}>")
        out.append("</tr>")
    out.append("</table>")
    return "".join(out)


FORM_PAGE = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>textfreq · 文科文本词频统计</title><style>{PAGE_CSS}</style></head>
<body><div class="wrap">
<h1>textfreq · 文科文本词频统计</h1>
<p class="muted">把知网导出的 TXT 全放进一个文件夹，填路径、点开始，图表直接出在本页。</p>
<form method="post" action="/run">
  <div class="row"><label>TXT 文件夹路径</label>
    <input name="folder" placeholder="例如 C:\\Users\\me\\Desktop\\知网导出" required></div>
  <div class="row"><label>词频总表收录前多少词</label><input name="top" value="100"></div>
  <div class="row"><label>共词矩阵取前多少高频词</label><input name="cooc_top" value="30"></div>
  <div class="row"><label>额外停用词文件（可选，每行一词）</label><input name="stopwords" placeholder="如 D:\\我的黑名单.txt"></div>
  <div class="row"><label>领域词表文件（可选，专有名词整词识别，每行一词）</label><input name="userdict"></div>
  <p><button type="submit">开始统计</button></p>
</form>
</div></body></html>"""


class Handler(BaseHTTPRequestHandler):
    last_outdir = None

    def _send(self, body, code=200):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.startswith("/dl"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            fname = q.get("f", [""])[0]
            outdir = getattr(Handler, "last_outdir", None)
            if outdir and fname in ("词频总表.csv", "年度趋势.csv", "共词矩阵.csv"):
                fp = Path(outdir) / fname
                if fp.exists():
                    data = fp.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", "text/csv; charset=utf-8")
                    self.send_header("Content-Disposition",
                                     f'attachment; filename="{fname.encode("ascii","ignore").decode() or "export"}"; filename*=UTF-8\'\'{urllib.parse.quote(fname)}')
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
            self._send("文件不存在", 404)
            return
        self._send(FORM_PAGE)

    def log_message(self, *a):
        pass

    def do_POST(self):
        if self.path != "/run":
            self._send("Not found", 404)
            return
        size = int(self.headers.get("Content-Length", 0))
        form = urllib.parse.parse_qs(
            self.rfile.read(size).decode("utf-8"))
        get = lambda k, d="": form.get(k, [d])[0].strip()
        folder, outdir = get("folder"), get("outdir") or None
        try:
            top = int(get("top", "100") or 100)
            cooc_top = int(get("cooc_top", "30") or 30)
        except ValueError:
            top, cooc_top = 100, 30
        corpus = load_corpus(folder)          # 文件夹不存在会在这里报错
        stopwords = load_stopwords(get("stopwords") or None)
        load_userdict(get("userdict") or None)

        freq = word_freq(corpus, stopwords)
        trend = yearly_trend(corpus, stopwords)
        cooc = cooccurrence_matrix(corpus, stopwords, cooc_top)

        outdir_path = Path(outdir or "textfreq_out")
        Handler.last_outdir = outdir_path
        rows = [["排名", "词语", "频次"]] + [
            [i, w, c] for i, (w, c) in enumerate(freq.most_common(top), 1)]
        save_csv(rows, outdir_path / "词频总表.csv")
        if trend:
            save_csv(trend, outdir_path / "年度趋势.csv")
        save_csv(cooc, outdir_path / "共词矩阵.csv")

        msg = ""
        if trend is None:
            msg = '<p class="muted">文件名没带年份（如 2010.txt），所以没生成趋势图。</p>'

        page = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>统计结果 · textfreq</title><style>{PAGE_CSS}</style></head><body><div class="wrap">
<h1>统计结果</h1>
<p class="muted">文件夹：{_esc(folder)}　共 {len(corpus)} 个文件，有效词 {sum(freq.values()):,} 个。</p>
<p><a class="dl" href="/dl?f=词频总表.csv">⬇ 词频总表.csv</a>　
<a class="dl" href="/dl?f=年度趋势.csv">⬇ 年度趋势.csv</a>　
<a class="dl" href="/dl?f=共词矩阵.csv">⬇ 共词矩阵.csv</a>　
（保存在 {_esc(outdir_path.resolve())}）</p>

<h2>高频词 Top {_min(len(freq), 15, top)}</h2>{_bar_svg(freq.most_common(15))}
{msg}
{'' if not trend else '<h2>年度趋势（前 5 个高频词）</h2>' + _trend_svg(trend)}
<h2>共词矩阵预览（前 {min(10, cooc_top)} × {min(10, cooc_top)}）</h2>
{_cooc_table(cooc)}
<p class="muted" style="margin-top:40px"><a class="dl" href="/">← 返回再跑一批</a></p>
</div></body></html>"""
        self._send(page)


def _min(a, b, c):
    return min(a, b, c)


def serve(port=8765):
    for p in range(port, port + 10):
        try:
            server = ThreadingHTTPServer(("127.0.0.1", p), Handler)
            break
        except OSError:
            continue
    url = f"http://127.0.0.1:{p}"
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    print(f"textfreq 界面已启动：{url}  （按 Ctrl+C 退出）")
    server.serve_forever()
