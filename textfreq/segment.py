# -*- coding: utf-8 -*-
"""中文分词与词项过滤：jieba 分词 + 内置停用词 + 自定义词表/黑名单。"""
import re
from pathlib import Path

import jieba

_STOPWORD_FILE = Path(__file__).parent / "stopwords.txt"

# 过滤规则：单字、纯数字、数字字母混合串、标点符号
_PUNCT = re.compile(r"^[\W_]+$", re.UNICODE)
_ALNUM_MIX = re.compile(r"^[0-9a-zA-Z%．.\-]+$")


def _read_wordlist(path):
    stop = set()
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # 同一行也允许空格/顿号分隔多个词
        stop |= {w for w in re.split(r"[\s,，、]+", line) if w}
    return stop


def load_stopwords(extra=None):
    stop = set()
    if _STOPWORD_FILE.exists():
        stop |= _read_wordlist(_STOPWORD_FILE)
    if extra and Path(extra).exists():
        stop |= _read_wordlist(extra)
    return stop


def load_userdict(userdict=None):
    if userdict and Path(userdict).exists():
        jieba.load_userdict(str(userdict))


def is_valid_token(token: str, stopwords: set) -> bool:
    t = token.strip()
    if len(t) < 2:                 # 丢单字（可按需放宽）
        return False
    if _PUNCT.match(t) or _ALNUM_MIX.match(t):
        return False
    if t in stopwords:
        return False
    return True


def segment(text: str, stopwords: set):
    return [w for w in jieba.cut(text) if is_valid_token(w, stopwords)]
