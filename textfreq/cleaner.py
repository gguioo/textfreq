# -*- coding: utf-8 -*-
"""文本清洗：读取 TXT（自动识别常见编码），去除页眉页脚与常见噪音行。"""
import re
from pathlib import Path

# 常见中文文献噪音行特征（页眉页脚、页码、重复站点信息等）
_NOISE_PATTERNS = [
    re.compile(r"^[-—·\s\d]{1,12}$"),                 # 纯页码/分隔符
    re.compile(r"第?\s*\d+\s*页(共\s*\d+\s*页)?"),     # 第 x 页 共 x 页
    re.compile(r"^\d+\s*/\s*\d+$"),                    # 1/5
    re.compile(r"^\s*\d{1,4}\s*$"),
    re.compile(r"(下载|扫码|二维码|关注|订阅|微信|公众号|APP|App)"),
    re.compile(r"(维普|知网|万方|龙源|CNKI|http[s]?://\S+)"),
    re.compile(r"^(总第|卷|期|Vol|No)[:：\s]*\S{0,10}$"),
    re.compile(r"^[\s\u3000]+$"),
]

ENCODE_ORDER = ("utf-8", "gb18030", "utf-16", "big5")


def read_txt(path) -> str:
    """按常见编码顺序尝试读取，返回纯文本。"""
    data = Path(path).read_bytes()
    for enc in ENCODE_ORDER:
        try:
            return data.decode(enc)
        except (UnicodeDecodeError, ValueError):
            continue
    return data.decode("utf-8", errors="ignore")


def clean_text(text: str) -> str:
    """逐行去除噪音行，压缩空白。"""
    kept = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            kept.append("")
            continue
        if any(p.search(line) for p in _NOISE_PATTERNS):
            continue
        kept.append(line)
    cleaned = "\n".join(kept)
    cleaned = re.sub(r"[ \t\u3000]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def load_corpus(folder: str, suffix: str = ".txt"):
    """读取文件夹内全部 TXT，返回 [(文件名, 清洗后文本), ...]。"""
    folder = Path(folder)
    files = sorted(p for p in folder.iterdir()
                   if p.suffix.lower() == suffix.lower() and p.is_file())
    if not files:
        raise FileNotFoundError(f"{folder} 下没有找到 {suffix} 文件")
    return [(p.name, clean_text(read_txt(p))) for p in files]
