"""Synthetic PDF builders shared by the tests (no binary fixtures)."""

from types import SimpleNamespace

import pymupdf


def make_doc(lines, pitch=14.0, size=11.0, x=72.0, y0=100.0, fontname="helv"):
    doc = pymupdf.open()
    page = doc.new_page()
    for i, text in enumerate(lines):
        page.insert_text((x, y0 + i * pitch), text, fontsize=size, fontname=fontname)
    return doc


def words_of(page, **kw):
    return page.get_text("words", **kw)


def res(entity_type, text, value, score=0.85):
    """Presidio-like result for the first occurrence of `value` in `text`."""
    start = text.index(value)
    return SimpleNamespace(
        entity_type=entity_type, start=start, end=start + len(value), score=score
    )


def fake_words(text):
    """`get_text("words")`-style tuples for plain text (one block)."""
    out = []
    y = 0.0
    for li, line in enumerate(text.split("\n")):
        x = 10.0
        for wi, w in enumerate(line.split()):
            out.append((x, y, x + 6 * len(w), y + 12, w, 0, li, wi))
            x += 6 * len(w) + 4
        y += 14
    return out
