"""Read articles from a Wikipedia XML dump, strip markup, split sentences."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent       # src/wikipedia_utils.py → repo root
WIKIPEDIA_DUMP_PATH = Path(
    os.environ.get("WIKIPEDIA_DUMP_PATH", str(PROJECT_ROOT / "data" / "wikipedia_dump.xml"))
)

_PAGE = re.compile(rb"<page>(.*?)</page>", flags=re.DOTALL)
_TITLE = re.compile(rb"<title>(.*?)</title>")
_TEXT = re.compile(rb"<text[^>]*>(.*?)</text>", flags=re.DOTALL)


def read_articles(
    dump_path: Path = WIKIPEDIA_DUMP_PATH,
    n: int = 1000,
    max_bytes: int = 50_000_000,
) -> list[tuple[str, bytes]]:
    """Yield (title, raw_body) for the first `n` non-redirect, non-namespace articles."""
    if not dump_path.exists():
        raise FileNotFoundError(
            f"Wikipedia dump not found at {dump_path}. "
            f"Set WIKIPEDIA_DUMP_PATH env var."
        )
    articles: list[tuple[str, bytes]] = []
    with open(dump_path, "rb") as fh:
        buf = b""
        bytes_read = 0
        while len(articles) < n and bytes_read < max_bytes:
            chunk = fh.read(1 << 22)
            if not chunk:
                break
            buf += chunk
            bytes_read += len(chunk)
            last_end = 0
            for m in _PAGE.finditer(buf):
                last_end = m.end()
                title_m = _TITLE.search(m.group(1))
                text_m = _TEXT.search(m.group(1))
                if not (title_m and text_m):
                    continue
                title = title_m.group(1).decode("latin1", errors="replace")
                raw = text_m.group(1)
                if raw.lstrip()[:32].lower().startswith(b"#redirect"):
                    continue
                if ":" in title.split(" ", 1)[0]:
                    continue
                articles.append((title, raw))
                if len(articles) >= n:
                    break
            buf = buf[last_end:]
    return articles


_TEMPLATE_BLOCK = re.compile(rb"\{\{[^{}]*\}\}")
_REF_BLOCK = re.compile(rb"<ref[^>]*>.*?</ref>", flags=re.DOTALL)
_HTML_TAG = re.compile(rb"<[^>]+>")
_WIKILINK_PIPE = re.compile(rb"\[\[([^\]|]+)\|([^\]]+)\]\]")
_WIKILINK_PLAIN = re.compile(rb"\[\[([^\]]+)\]\]")
_TABLE_BLOCK = re.compile(rb"\{\|.*?\|\}", flags=re.DOTALL)
_HEADING = re.compile(rb"^==+.*?==+$", flags=re.MULTILINE)
_LIST_LINE = re.compile(rb"^[*#:].*$", flags=re.MULTILINE)
_HTML_ENTITY = re.compile(rb"&(?:[a-z]+|#\d+);")
_BOLD = re.compile(rb"'''+")
_ITALIC = re.compile(rb"''")


def strip_markup(raw: bytes) -> str:
    """Strip MediaWiki markup, return prose as a unicode string."""
    s = raw
    for _ in range(2):
        s = _TEMPLATE_BLOCK.sub(b" ", s)
    s = _REF_BLOCK.sub(b" ", s)
    s = _TABLE_BLOCK.sub(b" ", s)
    s = _HEADING.sub(b" ", s)
    s = _LIST_LINE.sub(b" ", s)
    s = _WIKILINK_PIPE.sub(rb"\2", s)
    s = _WIKILINK_PLAIN.sub(rb"\1", s)
    s = _HTML_TAG.sub(b" ", s)
    s = _BOLD.sub(b"", s)
    s = _ITALIC.sub(b"", s)
    s = _HTML_ENTITY.sub(b" ", s)
    s = re.sub(rb"\s+", b" ", s).strip()
    return s.decode("latin1", errors="replace")


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'])")


def split_sentences(text: str, min_chars: int = 15, max_chars: int = 600) -> list[str]:
    """Split prose into sentences; drop very short and very long fragments."""
    return [
        p.strip()
        for p in _SENTENCE_SPLIT.split(text)
        if min_chars <= len(p.strip()) <= max_chars
    ]
