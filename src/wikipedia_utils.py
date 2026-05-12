"""Read articles from a Wikipedia XML dump, strip markup, split sentences.

The dump is parsed by streaming the file in 4 MB chunks and matching
<page>…</page> blocks with a regex — full XML parsing would be
prohibitively expensive on the multi-gigabyte enwiki dumps. We accept
some quirks (encoding fallbacks, occasional truncated entities) in
exchange for being able to process 1,000 articles in a few seconds
without dependencies."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# Ensure stdout can carry the Latin-1/UTF-8 mix that comes out of the
# dump. Failures here are benign on platforms that already do this.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# Resolve from src/wikipedia_utils.py to the repo root; the default
# dump path lives next to the source tree so the demos can find it
# without environment configuration.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WIKIPEDIA_DUMP_PATH = Path(
    os.environ.get("WIKIPEDIA_DUMP_PATH", str(PROJECT_ROOT / "data" / "wikipedia_dump.xml"))
)

# Regex over bytes — much cheaper than decoding the whole dump to text
# before parsing. DOTALL lets <page>…</page> span newlines.
_PAGE = re.compile(rb"<page>(.*?)</page>", flags=re.DOTALL)
_TITLE = re.compile(rb"<title>(.*?)</title>")
_TEXT = re.compile(rb"<text[^>]*>(.*?)</text>", flags=re.DOTALL)


def read_articles(
    dump_path: Path = WIKIPEDIA_DUMP_PATH,
    n: int = 1000,
    max_bytes: int = 50_000_000,
) -> list[tuple[str, bytes]]:
    """Yield (title, raw_body) for the first `n` non-redirect, non-namespace articles.

    Streams the file in 4 MB chunks rather than loading it whole — the
    enwiki dump is tens of gigabytes. `max_bytes` caps total bytes read
    so a misconfigured path can't accidentally chew through the disk."""
    if not dump_path.exists():
        raise FileNotFoundError(
            f"Wikipedia dump not found at {dump_path}. "
            f"Set WIKIPEDIA_DUMP_PATH env var."
        )
    articles: list[tuple[str, bytes]] = []
    with open(dump_path, "rb") as fh:
        # `buf` accumulates unparsed bytes across chunks so a <page>
        # tag that straddles a chunk boundary still matches.
        buf = b""
        bytes_read = 0
        while len(articles) < n and bytes_read < max_bytes:
            chunk = fh.read(1 << 22)                # 4 MB
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
                # latin1 decode never raises and round-trips bytes;
                # most Wikipedia titles are ASCII so artefacts are rare.
                title = title_m.group(1).decode("latin1", errors="replace")
                raw = text_m.group(1)
                # Skip redirect stubs: "#REDIRECT [[Other Page]]" pages
                # have no real prose to extract from.
                if raw.lstrip()[:32].lower().startswith(b"#redirect"):
                    continue
                # Skip namespace pages (Talk:, Wikipedia:, File:, etc.).
                # Real articles never have a colon in the first word.
                if ":" in title.split(" ", 1)[0]:
                    continue
                articles.append((title, raw))
                if len(articles) >= n:
                    break
            # Drop everything we've parsed; keep the unparsed tail so a
            # mid-tag chunk boundary doesn't lose a page.
            buf = buf[last_end:]
    return articles


# Markup patterns. All operate over bytes for speed; ordering inside
# strip_markup matters because some substitutions undo others if
# applied out of order (e.g. wikilinks must be unwrapped before the
# generic <html> tag stripper would eat the surrounding brackets).
_TEMPLATE_BLOCK = re.compile(rb"\{\{[^{}]*\}\}")    # {{infobox …}}
_REF_BLOCK = re.compile(rb"<ref[^>]*>.*?</ref>", flags=re.DOTALL)
_HTML_TAG = re.compile(rb"<[^>]+>")
_WIKILINK_PIPE = re.compile(rb"\[\[([^\]|]+)\|([^\]]+)\]\]")     # [[Target|Display]]
_WIKILINK_PLAIN = re.compile(rb"\[\[([^\]]+)\]\]")               # [[Target]]
_TABLE_BLOCK = re.compile(rb"\{\|.*?\|\}", flags=re.DOTALL)
_HEADING = re.compile(rb"^==+.*?==+$", flags=re.MULTILINE)
_LIST_LINE = re.compile(rb"^[*#:].*$", flags=re.MULTILINE)
_HTML_ENTITY = re.compile(rb"&(?:[a-z]+|#\d+);")
_BOLD = re.compile(rb"'''+")
_ITALIC = re.compile(rb"''")


def strip_markup(raw: bytes) -> str:
    """Strip MediaWiki markup, return prose as a unicode string."""
    s = raw
    # Two passes over template blocks to handle one level of nesting —
    # {{a|{{b|x}}}} resolves only after the inner template is removed.
    # Deeper nesting is rare and would need a proper parser.
    for _ in range(2):
        s = _TEMPLATE_BLOCK.sub(b" ", s)
    s = _REF_BLOCK.sub(b" ", s)
    s = _TABLE_BLOCK.sub(b" ", s)
    s = _HEADING.sub(b" ", s)
    s = _LIST_LINE.sub(b" ", s)
    # Pipe wikilinks first ([[Target|Display]] → Display) so the plain
    # form ([[Target]] → Target) doesn't strip the wrong half.
    s = _WIKILINK_PIPE.sub(rb"\2", s)
    s = _WIKILINK_PLAIN.sub(rb"\1", s)
    s = _HTML_TAG.sub(b" ", s)
    s = _BOLD.sub(b"", s)
    s = _ITALIC.sub(b"", s)
    s = _HTML_ENTITY.sub(b" ", s)
    # Collapse runs of whitespace introduced by all the substitutions.
    s = re.sub(rb"\s+", b" ", s).strip()
    return s.decode("latin1", errors="replace")


# Sentence boundary heuristic: split on .?! followed by whitespace and
# a capital/quote. Misses some edge cases (abbreviations, ellipses)
# but works well enough for the extractor's purposes.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'])")


def split_sentences(text: str, min_chars: int = 15, max_chars: int = 600) -> list[str]:
    """Split prose into sentences; drop very short and very long fragments.

    Length filtering drops two failure modes: very short fragments
    (headings that survived markup stripping, list bullets) and very
    long fragments (paragraphs the splitter couldn't break, usually
    because of unusual punctuation). Both produce poor extractor
    output."""
    return [
        p.strip()
        for p in _SENTENCE_SPLIT.split(text)
        if min_chars <= len(p.strip()) <= max_chars
    ]
