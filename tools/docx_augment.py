# -*- coding: utf-8 -*-
"""
docx_augment - insert new tables and images into an existing .docx without
touching a single character of the existing content.

Design constraints (deliberate, do not "simplify" away):

* ``word/document.xml`` is treated as an opaque byte/character stream. We never
  re-serialise it. We locate the byte offsets of the top-level ``<w:body>``
  children with a quote-aware tag scanner and splice new ``<w:p>`` / ``<w:tbl>``
  markup in at those offsets. Consequence: every existing run, rsid, style ref
  and whitespace byte survives verbatim. ``verify()`` proves it by asserting the
  original ``document.xml`` bytes are a subsequence of the new ones.
* New tables/captions are not invented from scratch: the tool first *inspects*
  the source document and copies the real ``<w:tblPr>``, grid total width, cell
  run properties, header shading and caption ``<w:pPr>`` out of it.
* Images: binary is added to ``word/media/``, a fresh rId is appended to
  ``word/_rels/document.xml.rels``, a ``<Default Extension=.../>`` is added to
  ``[Content_Types].xml`` only when missing, and ``wp:docPr/@id`` continues past
  the highest id already present anywhere in the package.
* Pillow is used for image dimensions when importable; otherwise a built-in
  PNG/JPEG/GIF header parser is used. No hard dependency is added.

Public API
----------
    augment(src_docx, dst_docx, ops)  -> dict
    verify(src_docx, dst_docx)        -> dict

``ops`` is a list of dicts::

    {"type": "table", "anchor": "<verbatim text prefix of a paragraph>",
     "title": "[표 1] ...", "columns": ["A", "B"], "rows": [["1", "2"]],
     # optional: "widths": [2, 1], "occurrence": 0, "after_table": None,
     #           "title_position": "above"|"below", "spacer_after": True,
     #           "page_break_before": False}

    {"type": "image", "anchor": "<verbatim text prefix>",
     "path": r"C:\\...\\photo.jpg", "caption": "[사진 1] ...", "width_cm": 15.0,
     # optional: "occurrence": 0, "after_table": None,
     #           "page_break_before": False}

Each op inserts *after* the anchor paragraph, or after the table that
immediately follows it when the anchor paragraph is that table's caption.
Auto-detection requires both a following ``<w:tbl>`` *and* a caption-looking
anchor (Caption* pStyle, or text opening with ``[표 N]`` / ``[그림 N]`` / ...);
override either way with ``"after_table": True`` / ``False``.

Pagination
----------
Everything inserted is laid out so Word cannot break it in an unreadable way:

* every inserted ``<w:tr>`` carries ``<w:cantSplit/>`` - a row never gets torn
  in half across a page boundary;
* the header row additionally carries ``<w:tblHeader/>`` - it repeats at the
  top of every continuation page;
* a table title placed *above* its table carries ``<w:keepNext/>`` and an image
  paragraph followed by a caption carries ``<w:keepNext/>``, so a caption is
  never orphaned from what it describes; all captions carry ``<w:keepLines/>``;
* ``"page_break_before": true`` forces the block onto a fresh page;
* the anti-merge spacer paragraph is emitted *only* where two ``<w:tbl>``
  elements would otherwise touch - never unconditionally, because a stray empty
  paragraph can flow onto a page of its own and produce a blank page.

These properties are merged into the ``<w:pPr>`` / ``<w:trPr>`` copied from the
source document in correct schema order; nothing copied is discarded.
"""

from __future__ import annotations

import argparse
import copy
import io
import json
import os
import re
import struct
import sys
import zipfile

__all__ = ["augment", "verify", "AugmentError"]

# --------------------------------------------------------------------------
# constants
# --------------------------------------------------------------------------

DOC = "word/document.xml"
RELS = "word/_rels/document.xml.rels"
CTYPES = "[Content_Types].xml"
MEDIA_DIR = "word/media/"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PIC_NS = "http://schemas.openxmlformats.org/drawingml/2006/picture"
IMAGE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"

EMU_PER_CM = 360000

EXT_CONTENT_TYPE = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "tiff": "image/tiff",
    "tif": "image/tiff",
    "emf": "image/x-emf",
    "wmf": "image/x-wmf",
}

# Fallbacks used only when the source document yields nothing to copy.
_FALLBACK_TBLPR = (
    '<w:tblPr><w:tblStyle w:val="TableGrid"/>'
    '<w:tblW w:type="dxa" w:w="9638"/><w:jc w:val="center"/>'
    '<w:tblLook w:firstColumn="1" w:firstRow="1" w:lastColumn="0" w:lastRow="0"'
    ' w:noHBand="0" w:noVBand="1" w:val="04A0"/></w:tblPr>'
)
_FALLBACK_TOTAL_W = 9638
_FALLBACK_HEADER_SHD = '<w:shd w:val="clear" w:fill="1F3A5F"/>'
_FALLBACK_CAPTION_PPR = '<w:pPr><w:jc w:val="center"/></w:pPr>'


class AugmentError(Exception):
    """Raised for anything the caller can fix (bad anchor, missing file, ...)."""


# --------------------------------------------------------------------------
# tiny XML helpers that never reserialise anything
# --------------------------------------------------------------------------

def _esc_text(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _esc_attr(s):
    return _esc_text(s).replace('"', "&quot;")


_ENTITY_RE = re.compile(r"&(#x[0-9A-Fa-f]+|#\d+|amp|lt|gt|quot|apos);")


def _unesc(s):
    def sub(m):
        e = m.group(1)
        if e.startswith("#x"):
            return chr(int(e[2:], 16))
        if e.startswith("#"):
            return chr(int(e[1:]))
        return {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'"}[e]

    return _ENTITY_RE.sub(sub, s)


def _scan_tags(s, start=0, end=None):
    """Yield (open_offset, close_offset, tag_text) for every markup tag.

    Quote-aware, so ``>`` inside an attribute value cannot end a tag early
    (lxml does not escape ``>`` in attributes, so a naive ``[^>]*`` regex is
    genuinely unsafe here). Comments / PIs / CDATA are skipped as units.
    """
    if end is None:
        end = len(s)
    i = start
    n = len(s)
    while True:
        i = s.find("<", i)
        if i < 0 or i >= end:
            return
        if s.startswith("<!--", i):
            j = s.find("-->", i)
            i = (j + 3) if j >= 0 else n
            continue
        if s.startswith("<![CDATA[", i):
            j = s.find("]]>", i)
            i = (j + 3) if j >= 0 else n
            continue
        if s.startswith("<?", i) or s.startswith("<!", i):
            j = s.find(">", i)
            i = (j + 1) if j >= 0 else n
            continue
        j = i + 1
        quote = None
        while j < n:
            c = s[j]
            if quote:
                if c == quote:
                    quote = None
            elif c in "\"'":
                quote = c
            elif c == ">":
                break
            j += 1
        yield i, j + 1, s[i:j + 1]
        i = j + 1


_NAME_RE = re.compile(r"^</?([A-Za-z_][-\w.:]*)")


def _tag_info(tag_text):
    m = _NAME_RE.match(tag_text)
    name = m.group(1) if m else ""
    closing = tag_text.startswith("</")
    selfclose = tag_text.endswith("/>") and not closing
    return name, closing, selfclose


def _top_children(xml):
    """``[(tag_name, raw_xml)]`` for the top-level elements of a fragment."""
    out = []
    depth = 0
    cur_name = None
    cur_start = 0
    for a, b, tag in _scan_tags(xml, 0, len(xml)):
        name, closing, selfclose = _tag_info(tag)
        if selfclose:
            if depth == 0:
                out.append((name, xml[a:b]))
            continue
        if closing:
            depth -= 1
            if depth == 0:
                out.append((cur_name, xml[cur_start:b]))
                cur_name = None
            elif depth < 0:
                raise AugmentError("unbalanced markup in fragment %r" % xml[:80])
        else:
            if depth == 0:
                cur_name = name
                cur_start = a
            depth += 1
    if depth != 0:
        raise AugmentError("unbalanced markup in fragment %r" % xml[:80])
    return out


# ECMA-376 CT_PPrBase/CT_PPr child order. Word rejects a <w:pPr> whose children
# are out of sequence, so anything we merge in has to land in the right slot.
_PPR_ORDER = (
    "w:pStyle", "w:keepNext", "w:keepLines", "w:pageBreakBefore", "w:framePr",
    "w:widowControl", "w:numPr", "w:suppressLineNumbers", "w:pBdr", "w:shd",
    "w:tabs", "w:suppressAutoHyphens", "w:kinsoku", "w:wordWrap",
    "w:overflowPunct", "w:topLinePunct", "w:autoSpaceDE", "w:autoSpaceDN",
    "w:bidi", "w:adjustRightInd", "w:snapToGrid", "w:spacing", "w:ind",
    "w:contextualSpacing", "w:mirrorIndents", "w:suppressOverlap", "w:jc",
    "w:textDirection", "w:textAlignment", "w:textboxTightWrap", "w:outlineLvl",
    "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr", "w:pPrChange",
)
_PPR_INDEX = {n: i for i, n in enumerate(_PPR_ORDER)}

# ECMA-376 CT_TrPrBase child order.
_TRPR_ORDER = (
    "w:cnfStyle", "w:divId", "w:gridBefore", "w:gridAfter", "w:wBefore",
    "w:wAfter", "w:cantSplit", "w:trHeight", "w:tblHeader", "w:tblCellSpacing",
    "w:jc", "w:hidden", "w:ins", "w:del", "w:trPrChange",
)
_TRPR_INDEX = {n: i for i, n in enumerate(_TRPR_ORDER)}

_PR_OPEN_RE = {}


def _merge_props(wrapper, order_index, existing, flags):
    """Merge empty elements ``flags`` into the ``<wrapper>`` element ``existing``.

    ``existing`` may be ``None``/``""`` (a fresh wrapper is built), self-closing
    (``<w:pPr/>``) or a full element copied verbatim out of the source document.
    Children already present are left exactly as they are - including their
    attributes and their relative order - and each flag is spliced into the slot
    the schema demands. A flag already present is not duplicated.
    """
    flags = [f for f in flags if f]
    if not flags:
        return existing or ""
    open_re = _PR_OPEN_RE.get(wrapper)
    if open_re is None:
        open_re = re.compile(r"^\s*<%s(\s[^>]*?)?(/?)>" % re.escape(wrapper), re.S)
        _PR_OPEN_RE[wrapper] = open_re

    attrs, inner = "", ""
    if existing and existing.strip():
        m = open_re.match(existing)
        if not m:
            raise AugmentError("expected a <%s> element, got %r" % (wrapper, existing[:60]))
        attrs = m.group(1) or ""
        if not m.group(2):
            inner = existing[m.end():existing.rindex("</%s>" % wrapper)]

    kids = _top_children(inner)
    present = set(n for n, _ in kids)
    last = len(order_index)
    for flag in flags:
        if flag in present:
            continue
        rank = order_index.get(flag, last)
        pos = 0
        for i, (name, _raw) in enumerate(kids):
            r = order_index.get(name)
            if r is None or r <= rank:
                pos = i + 1
        kids.insert(pos, (flag, "<%s/>" % flag))
        present.add(flag)
    return "<%s%s>%s</%s>" % (wrapper, attrs, "".join(raw for _n, raw in kids), wrapper)


def _ppr_with(ppr, *flags):
    """``<w:pPr>`` with ``flags`` (e.g. ``"w:keepNext"``) merged in, in order."""
    return _merge_props("w:pPr", _PPR_INDEX, ppr, flags)


def _trpr_with(trpr, *flags):
    """``<w:trPr>`` with ``flags`` (e.g. ``"w:cantSplit"``) merged in, in order."""
    return _merge_props("w:trPr", _TRPR_INDEX, trpr, flags)


class Child(object):
    """One top-level child of ``<w:body>``."""

    __slots__ = ("tag", "start", "end", "text")

    def __init__(self, tag, start, end, text):
        self.tag = tag
        self.start = start
        self.end = end
        self.text = text

    def __repr__(self):  # pragma: no cover - debugging aid
        return "Child(%s, %d:%d, %r)" % (self.tag, self.start, self.end, self.text[:40])


_WT_RE = re.compile(r"<w:t(?:\s[^>]*)?>(.*?)</w:t>|<w:t\s*/>", re.S)


def _span_text(xml, start, end):
    out = []
    for m in _WT_RE.finditer(xml, start, end):
        out.append(_unesc(m.group(1)) if m.group(1) is not None else "")
    return "".join(out)


def _body_children(xml):
    """Return (children, body_start, body_end) for ``<w:body>``."""
    m = re.search(r"<w:body(?:\s[^>]*)?>", xml)
    if not m:
        raise AugmentError("no <w:body> found in document.xml")
    body_start = m.end()
    body_end = xml.rindex("</w:body>")

    children = []
    depth = 0
    cur_start = None
    cur_tag = None
    for a, b, tag in _scan_tags(xml, body_start, body_end):
        name, closing, selfclose = _tag_info(tag)
        if selfclose:
            if depth == 0:
                children.append(Child(name, a, b, _span_text(xml, a, b)))
            continue
        if closing:
            depth -= 1
            if depth == 0:
                children.append(Child(cur_tag, cur_start, b, _span_text(xml, cur_start, b)))
                cur_start = None
            elif depth < 0:
                raise AugmentError("unbalanced markup in document.xml near offset %d" % a)
        else:
            if depth == 0:
                cur_start = a
                cur_tag = name
            depth += 1
    if depth != 0:
        raise AugmentError("unbalanced markup in document.xml body")
    return children, body_start, body_end


# --------------------------------------------------------------------------
# template extraction - copy the look of what is already in the document
# --------------------------------------------------------------------------

def _first(pattern, text, default=None, flags=re.S):
    m = re.search(pattern, text, flags)
    return m.group(0) if m else default


def _first_group(pattern, text, default=None, flags=re.S):
    m = re.search(pattern, text, flags)
    return m.group(1) if m else default


class DocTemplate(object):
    """Everything we copy out of the source so new content blends in."""

    def __init__(self, tbl_pr, total_width, header_shd, header_rpr, body_rpr,
                 cell_ppr, caption_ppr, image_ppr, spacer_p):
        self.tbl_pr = tbl_pr
        self.total_width = total_width
        self.header_shd = header_shd
        self.header_rpr = header_rpr
        self.body_rpr = body_rpr
        self.cell_ppr = cell_ppr
        self.caption_ppr = caption_ppr
        self.image_ppr = image_ppr
        self.spacer_p = spacer_p

    def describe(self):
        return {
            "tbl_pr": self.tbl_pr,
            "total_width_dxa": self.total_width,
            "header_shd": self.header_shd,
            "header_rpr": self.header_rpr,
            "body_rpr": self.body_rpr,
            "cell_ppr": self.cell_ppr,
            "caption_ppr": self.caption_ppr,
            "image_ppr": self.image_ppr,
            "spacer_p": self.spacer_p,
        }


def _force_clear_shading(shd_xml):
    """Word renders ``w:val="solid"`` as a *foreground* fill (black text box).
    Only ``clear`` gives the expected background tint."""
    if not shd_xml:
        return _FALLBACK_HEADER_SHD
    return re.sub(r'w:val="[^"]*"', 'w:val="clear"', shd_xml, count=1)


def _extract_template(xml):
    tbl = _first(r"<w:tbl>.*?</w:tbl>", xml)

    tbl_pr = _FALLBACK_TBLPR
    total = _FALLBACK_TOTAL_W
    header_shd = _FALLBACK_HEADER_SHD
    header_rpr = ""
    body_rpr = ""
    cell_ppr = ""

    if tbl:
        tbl_pr = _first(r"<w:tblPr>.*?</w:tblPr>", tbl, _FALLBACK_TBLPR)
        grid = _first_group(r"<w:tblGrid>(.*?)</w:tblGrid>", tbl)
        if grid:
            cols = [int(x) for x in re.findall(r'w:w="(\d+)"', grid)]
            if cols:
                total = sum(cols)
        rows = re.findall(r"<w:tr(?:\s[^>]*)?>.*?</w:tr>", tbl, re.S)
        if rows:
            first_cell = _first(r"<w:tc>.*?</w:tc>", rows[0], "")
            header_shd = _force_clear_shading(_first(r"<w:shd\b[^>]*/>", first_cell))
            header_rpr = _first(r"<w:rPr>.*?</w:rPr>", first_cell, "")
            cell_ppr = _first_group(r"<w:p(?:\s[^>]*)?>\s*(<w:pPr>.*?</w:pPr>)", first_cell, "")
        if len(rows) > 1:
            body_cell = _first(r"<w:tc>.*?</w:tc>", rows[1], "")
            body_rpr = _first(r"<w:rPr>.*?</w:rPr>", body_cell, "")
    if not body_rpr:
        body_rpr = re.sub(r"<w:b/>|<w:color\b[^>]*/>", "", header_rpr)
    if header_rpr and "<w:b/>" not in header_rpr:
        header_rpr = header_rpr.replace("<w:rPr>", "<w:rPr><w:b/>", 1)

    # Caption paragraph properties: prefer a real "[그림 N]" caption.
    caption_ppr = None
    for m in re.finditer(r"\[(?:그림|표|사진|Figure|Table)\s", xml):
        p_start = xml.rfind("<w:p>", 0, m.start())
        p_start2 = xml.rfind("<w:p ", 0, m.start())
        p_start = max(p_start, p_start2)
        if p_start < 0:
            continue
        p_end = xml.find("</w:p>", m.start())
        chunk = xml[p_start:p_end]
        ppr = _first(r"<w:pPr>.*?</w:pPr>", chunk)
        if ppr:
            caption_ppr = ppr
            break
    if not caption_ppr:
        for style in ("Caption2", "Caption"):
            if 'w:val="%s"' % style in xml:
                caption_ppr = ('<w:pPr><w:pStyle w:val="%s"/>'
                               '<w:jc w:val="center"/></w:pPr>' % style)
                break
    if not caption_ppr:
        caption_ppr = _FALLBACK_CAPTION_PPR

    # Paragraph properties used by existing inline images.
    image_ppr = _FALLBACK_CAPTION_PPR
    di = xml.find("<w:drawing>")
    if di >= 0:
        p_start = max(xml.rfind("<w:p>", 0, di), xml.rfind("<w:p ", 0, di))
        if p_start >= 0:
            ppr = _first(r"<w:pPr>.*?</w:pPr>", xml[p_start:di])
            if ppr:
                image_ppr = ppr

    # The empty paragraph these documents put after every table. Reusing it
    # keeps the house spacing AND guarantees two <w:tbl> are never adjacent
    # (Word silently merges consecutive tables into one).
    spacer_p = "<w:p/>"
    m = re.search(r"</w:tbl>(<w:p(?:\s[^>]*)?>.*?</w:p>|<w:p\s*/>)", xml, re.S)
    if m and "<w:t" not in m.group(1):
        spacer_p = m.group(1)

    return DocTemplate(tbl_pr, total, header_shd, header_rpr, body_rpr,
                       cell_ppr, caption_ppr, image_ppr, spacer_p)


# --------------------------------------------------------------------------
# markup builders
# --------------------------------------------------------------------------

def _runs_for(text, rpr):
    """One or more runs; ``\\n`` becomes a real line break inside the cell."""
    text = "" if text is None else str(text)
    lines = text.split("\n")
    parts = []
    for i, line in enumerate(lines):
        br = "<w:br/>" if i else ""
        space = ' xml:space="preserve"' if line != line.strip() else ""
        parts.append("<w:r>%s%s<w:t%s>%s</w:t></w:r>" % (rpr, br, space, _esc_text(line)))
    return "".join(parts)


def _cell(text, width, rpr, ppr, shd=""):
    return (
        "<w:tc><w:tcPr>"
        '<w:tcW w:type="dxa" w:w="%d"/>%s'
        "</w:tcPr>"
        "<w:p>%s%s</w:p>"
        "</w:tc>" % (width, shd, ppr, _runs_for(text, rpr))
    )


def _split_widths(total, ncols, weights=None):
    """DXA widths that sum *exactly* to ``total``."""
    if ncols <= 0:
        raise AugmentError("table needs at least one column")
    if weights:
        if len(weights) != ncols:
            raise AugmentError("widths must have %d entries, got %d" % (ncols, len(weights)))
        s = float(sum(weights))
        if s <= 0:
            raise AugmentError("widths must sum to a positive number")
        widths = [int(total * w / s) for w in weights]
    else:
        widths = [total // ncols] * ncols
    widths[-1] += total - sum(widths)
    return widths


def _build_table(op, tpl, keep_last_row_with_next=False):
    """Return ``(markup, n_rows, n_header_rows)``.

    Pagination properties baked into every generated row:

      ``<w:trPr><w:cantSplit/></w:trPr>``                  every row
      ``<w:trPr><w:cantSplit/><w:tblHeader/></w:trPr>``    the header row

    ``cantSplit`` stops Word tearing a tall cell in half across a page break;
    ``tblHeader`` makes the column headings repeat on every continuation page.
    """
    columns = [str(c) for c in op.get("columns") or []]
    rows = op.get("rows") or []
    if not columns and not rows:
        raise AugmentError("table op needs 'columns' and/or 'rows'")
    ncols = len(columns) if columns else max(len(r) for r in rows)
    widths = _split_widths(tpl.total_width, ncols, op.get("widths"))

    # tblW is normalised to a fixed DXA width equal to the existing tables'
    # grid total, so the new table lines up with them to the twip.
    tbl_pr = tpl.tbl_pr
    tblw = '<w:tblW w:type="dxa" w:w="%d"/>' % tpl.total_width
    if re.search(r"<w:tblW\b[^>]*/>", tbl_pr):
        tbl_pr = re.sub(r"<w:tblW\b[^>]*/>", tblw, tbl_pr, count=1)
    else:
        tbl_pr = tbl_pr.replace("<w:tblPr>", "<w:tblPr>" + tblw, 1)

    header_trpr = _trpr_with("", "w:cantSplit", "w:tblHeader")
    body_trpr = _trpr_with("", "w:cantSplit")
    # A title printed *below* the table must not be orphaned from it; a table
    # itself cannot carry keepNext, so the last row's cell paragraphs do.
    last_ppr = (_ppr_with(tpl.cell_ppr, "w:keepNext")
                if keep_last_row_with_next else tpl.cell_ppr)
    n_rows = len(rows) + (1 if columns else 0)

    out = ["<w:tbl>", tbl_pr, "<w:tblGrid>"]
    out += ['<w:gridCol w:w="%d"/>' % w for w in widths]
    out.append("</w:tblGrid>")

    if columns:
        ppr = last_ppr if (keep_last_row_with_next and not rows) else tpl.cell_ppr
        out.append("<w:tr>" + header_trpr)
        for i, c in enumerate(columns):
            out.append(_cell(c, widths[i], tpl.header_rpr, ppr, tpl.header_shd))
        out.append("</w:tr>")
    for ri, r in enumerate(rows):
        cells = list(r) + [""] * (ncols - len(r))
        ppr = last_ppr if ri == len(rows) - 1 else tpl.cell_ppr
        out.append("<w:tr>" + body_trpr)
        for i in range(ncols):
            out.append(_cell(cells[i], widths[i], tpl.body_rpr, ppr))
        out.append("</w:tr>")
    out.append("</w:tbl>")
    return "".join(out), n_rows, (1 if columns else 0)


def _build_caption(text, tpl, keep_next=False, page_break=False):
    """A caption paragraph.

    ``keepLines`` is always set (a two-line caption must not break in half).
    ``keepNext`` is set when the thing being captioned comes *after* the
    caption - i.e. for a table title printed above its table. The properties
    are merged into the ``<w:pPr>`` copied from a real caption in the source
    document, never substituted for it.
    """
    flags = ["w:keepLines"]
    if keep_next:
        flags.append("w:keepNext")
    if page_break:
        flags.append("w:pageBreakBefore")
    return "<w:p>%s<w:r><w:t%s>%s</w:t></w:r></w:p>" % (
        _ppr_with(tpl.caption_ppr, *flags),
        ' xml:space="preserve"' if text != text.strip() else "",
        _esc_text(text),
    )


def _build_page_break_paragraph():
    """An empty paragraph that starts a new page.

    Only used when there is no title paragraph to hang ``<w:pageBreakBefore/>``
    on. When there is a title, the property goes straight into the title's
    ``<w:pPr>`` so no extra empty paragraph enters the flow.
    """
    return "<w:p><w:pPr><w:pageBreakBefore/></w:pPr></w:p>"


def _build_image_paragraph(rid, doc_pr_id, name, cx, cy, tpl,
                           keep_next=False, page_break=False):
    flags = []
    if keep_next:
        flags.append("w:keepNext")
    if page_break:
        flags.append("w:pageBreakBefore")
    ppr = _ppr_with(tpl.image_ppr, *flags) if flags else tpl.image_ppr
    return (
        "<w:p>%(ppr)s<w:r><w:drawing>"
        '<wp:inline xmlns:a="%(a)s" xmlns:pic="%(pic)s">'
        '<wp:extent cx="%(cx)d" cy="%(cy)d"/>'
        '<wp:docPr id="%(id)d" name="Picture %(id)d" descr="%(name)s"/>'
        '<wp:cNvGraphicFramePr><a:graphicFrameLocks noChangeAspect="1"/></wp:cNvGraphicFramePr>'
        "<a:graphic>"
        '<a:graphicData uri="%(pic)s">'
        "<pic:pic>"
        '<pic:nvPicPr><pic:cNvPr id="0" name="%(name)s"/><pic:cNvPicPr/></pic:nvPicPr>'
        '<pic:blipFill><a:blip r:embed="%(rid)s"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        '<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="%(cx)d" cy="%(cy)d"/></a:xfrm>'
        '<a:prstGeom prst="rect"/></pic:spPr>'
        "</pic:pic></a:graphicData></a:graphic></wp:inline>"
        "</w:drawing></w:r></w:p>"
        % {
            "ppr": ppr,
            "a": A_NS,
            "pic": PIC_NS,
            "cx": cx,
            "cy": cy,
            "id": doc_pr_id,
            "rid": rid,
            "name": _esc_attr(name),
        }
    )


# --------------------------------------------------------------------------
# image dimensions - Pillow if available, otherwise parse the headers
# --------------------------------------------------------------------------

def _png_size(data):
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    if data[12:16] != b"IHDR":
        return None
    w, h = struct.unpack(">II", data[16:24])
    return int(w), int(h)


def _gif_size(data):
    if not data[:6] in (b"GIF87a", b"GIF89a"):
        return None
    w, h = struct.unpack("<HH", data[6:10])
    return int(w), int(h)


_JPEG_SOF = set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}


def _jpeg_size(data):
    """Walk the JPEG marker chain to the first SOFn segment."""
    if not data.startswith(b"\xff\xd8"):
        return None
    i = 2
    n = len(data)
    while i < n - 1:
        if data[i] != 0xFF:
            i += 1  # resync over fill bytes / corrupt padding
            continue
        while i < n and data[i] == 0xFF:
            i += 1
        if i >= n:
            break
        marker = data[i]
        i += 1
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7 or marker == 0x01:
            continue
        if i + 2 > n:
            break
        seglen = struct.unpack(">H", data[i:i + 2])[0]
        if marker in _JPEG_SOF:
            if i + 7 > n:
                break
            h, w = struct.unpack(">HH", data[i + 3:i + 7])
            return int(w), int(h)
        if marker == 0xDA:  # start of scan - no SOF found before image data
            break
        i += seglen
    return None


def _image_size_px(data, path=""):
    try:
        from PIL import Image  # noqa: F401
    except Exception:
        pass
    else:
        try:
            from PIL import Image
            with Image.open(io.BytesIO(data)) as im:
                return int(im.size[0]), int(im.size[1]), "PIL"
        except Exception:
            pass
    for fn in (_png_size, _jpeg_size, _gif_size):
        size = fn(data)
        if size:
            return size[0], size[1], "builtin:" + fn.__name__
    raise AugmentError(
        "cannot determine pixel dimensions of %s (unsupported or corrupt image)" % (path or "<bytes>")
    )


def _emu_from_cm(width_cm, px_w, px_h):
    cx = int(round(float(width_cm) * EMU_PER_CM))
    cy = int(round(cx * (float(px_h) / float(px_w))))
    return max(cx, 1), max(cy, 1)


# --------------------------------------------------------------------------
# package-level edits (rels, content types, media)
# --------------------------------------------------------------------------

def _next_rid(rels_xml):
    used = set(re.findall(r'Id="([^"]+)"', rels_xml))
    n = 1
    for rid in used:
        m = re.fullmatch(r"rId(\d+)", rid)
        if m:
            n = max(n, int(m.group(1)) + 1)
    while ("rId%d" % n) in used:
        n += 1
    return "rId%d" % n


def _add_relationship(rels_xml, rid, target):
    entry = '<Relationship Id="%s" Type="%s" Target="%s"/>' % (rid, IMAGE_REL, _esc_attr(target))
    idx = rels_xml.rindex("</Relationships>")
    return rels_xml[:idx] + entry + rels_xml[idx:]


def _ensure_default_ext(ctypes_xml, ext):
    ext = ext.lower().lstrip(".")
    if re.search(r'<Default\s[^>]*Extension="%s"' % re.escape(ext), ctypes_xml, re.I):
        return ctypes_xml, False
    ct = EXT_CONTENT_TYPE.get(ext)
    if not ct:
        raise AugmentError("unknown image extension %r - add it to EXT_CONTENT_TYPE" % ext)
    entry = '<Default Extension="%s" ContentType="%s"/>' % (ext, ct)
    m = re.search(r"<Types(?:\s[^>]*)?>", ctypes_xml)
    if not m:
        raise AugmentError("malformed [Content_Types].xml")
    return ctypes_xml[:m.end()] + entry + ctypes_xml[m.end():], True


def _next_media_name(existing, ext):
    """imageN.<ext>, N past every existing imageN.* regardless of extension."""
    n = 0
    for name in existing:
        m = re.match(r"^image(\d+)\.", os.path.basename(name), re.I)
        if m:
            n = max(n, int(m.group(1)))
    used = set(existing)
    n += 1
    while ("%simage%d.%s" % (MEDIA_DIR, n, ext)) in used:
        n += 1
    return "%simage%d.%s" % (MEDIA_DIR, n, ext)


def _max_docpr_id(parts):
    best = 0
    for data in parts:
        try:
            text = data.decode("utf-8", "ignore")
        except Exception:
            continue
        for m in re.finditer(r'<wp:docPr\b[^>]*\bid="(\d+)"', text):
            best = max(best, int(m.group(1)))
        for m in re.finditer(r'<pic:cNvPr\b[^>]*\bid="(\d+)"', text):
            best = max(best, int(m.group(1)))
    return best


# --------------------------------------------------------------------------
# anchor resolution
# --------------------------------------------------------------------------

_WS_RE = re.compile(r"\s+")


def _norm(s):
    return _WS_RE.sub(" ", s).strip()


def _find_anchor(children, anchor, occurrence=0):
    want = _norm(anchor)
    if not want:
        raise AugmentError("anchor must be a non-empty text prefix")
    hits = [i for i, c in enumerate(children)
            if c.tag == "w:p" and _norm(c.text).startswith(want)]
    if not hits:
        # any-element containment, then a helpful near-miss report
        loose = [i for i, c in enumerate(children) if want in _norm(c.text)]
        if loose:
            hits = loose
        else:
            near = sorted(
                (c for c in children if c.tag == "w:p" and _norm(c.text)),
                key=lambda c: -_common_prefix_len(_norm(c.text), want),
            )[:3]
            raise AugmentError(
                "anchor not found: %r\nclosest paragraph starts:\n%s"
                % (anchor, "\n".join("  - " + _norm(c.text)[:110] for c in near))
            )
    if occurrence >= len(hits):
        raise AugmentError("anchor %r matched %d paragraph(s); occurrence=%d out of range"
                           % (anchor, len(hits), occurrence))
    return hits[occurrence]


def _common_prefix_len(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


_CAPTION_TEXT_RE = re.compile(r"^\s*[\[(<]\s*(?:표|그림|사진|도표|Table|Figure|Fig\.?|Photo)\b",
                              re.I | re.U)


def _looks_like_caption(xml, child):
    """A caption is a paragraph that either carries a Caption* pStyle or opens
    with a caption marker such as ``[표 3]`` / ``[그림 3]`` / ``[Table 3]``."""
    head = xml[child.start:min(child.end, child.start + 400)]
    if re.search(r'<w:pStyle w:val="[^"]*[Cc]aption[^"]*"/>', head):
        return True
    return bool(_CAPTION_TEXT_RE.match(child.text or ""))


_HARD_BREAK_RE = re.compile(r'<w:br\b[^>]*w:type="page"')


def _is_lone_page_break(xml, child):
    """True for a source paragraph whose whole content is a manual page break.

    These are the documents' section dividers. They are one line tall, so as
    soon as inserted content fills the page they no longer fit: the paragraph
    mark flows onto the next page and *then* its break run fires, leaving a
    completely blank page behind. We cannot touch that paragraph, but we can
    stop it being separated from what we insert in front of it.
    """
    if child.tag != "w:p" or (child.text or "").strip():
        return False
    return bool(_HARD_BREAK_RE.search(xml[child.start:child.end]))


_CELL_P_RE = re.compile(r"<w:p>(<w:pPr(?:\s[^>]*)?(?:/>|>.*?</w:pPr>))?", re.S)


def _keep_next_in_row(tr_markup):
    """``<w:keepNext/>`` on every cell paragraph of one generated ``<w:tr>``."""
    return _CELL_P_RE.sub(
        lambda m: "<w:p>" + _ppr_with(m.group(1) or "", "w:keepNext"), tr_markup)


def _keep_next_on_last_block(markup):
    """Make the final block of ``markup`` inseparable from whatever follows.

    For a paragraph that is ``<w:keepNext/>`` in its ``<w:pPr>``. A table
    cannot carry keepNext itself, so its *last row's* cell paragraphs do - that
    is what keeps a table glued to the block after it.
    """
    kids = _top_children(markup)
    if not kids:
        return markup
    name, raw = kids[-1]

    if name == "w:tbl":
        cut = raw.rfind("<w:tr>")
        if cut < 0:
            return markup
        kids[-1] = (name, raw[:cut] + _keep_next_in_row(raw[cut:]))
        return "".join(r for _n, r in kids)

    if name != "w:p":
        return markup
    m = re.match(r"<w:p(\s[^>]*)?>", raw)
    if not m:
        return markup
    inner = raw[m.end():raw.rindex("</w:p>")]
    pm = re.match(r"\s*<w:pPr(?:\s[^>]*)?(?:/>|>.*?</w:pPr>)", inner, re.S)
    if pm:
        inner = _ppr_with(pm.group(0).strip(), "w:keepNext") + inner[pm.end():]
    else:
        inner = "<w:pPr><w:keepNext/></w:pPr>" + inner
    kids[-1] = ("w:p", "<w:p%s>%s</w:p>" % (m.group(1) or "", inner))
    return "".join(r for _n, r in kids)


def _insert_index(children, idx, after_table, xml=None):
    """Index of the child *after* which new content is spliced.

    ``after_table=None`` (default) auto-detects: only when the anchor paragraph
    reads as a caption *and* a table follows it do we jump past that table.
    A plain body paragraph that happens to precede a table is left alone.
    """
    if after_table is None:
        after_table = (
            idx + 1 < len(children)
            and children[idx + 1].tag == "w:tbl"
            and xml is not None
            and _looks_like_caption(xml, children[idx])
        )
    if after_table:
        if idx + 1 < len(children) and children[idx + 1].tag == "w:tbl":
            return idx + 1
        raise AugmentError("after_table=True but no <w:tbl> follows the anchor paragraph")
    return idx


# --------------------------------------------------------------------------
# main entry point
# --------------------------------------------------------------------------

def augment(src_docx, dst_docx, ops):
    """Copy ``src_docx`` to ``dst_docx`` with ``ops`` inserted.

    Returns a report dict. Raises :class:`AugmentError` on bad input.
    """
    src_docx = os.path.abspath(src_docx)
    dst_docx = os.path.abspath(dst_docx)
    if not os.path.isfile(src_docx):
        raise AugmentError("source not found: %s" % src_docx)
    if os.path.abspath(src_docx) == os.path.abspath(dst_docx):
        raise AugmentError("refusing to write over the source document")
    ops = list(ops or [])

    with zipfile.ZipFile(src_docx, "r") as z:
        names = z.namelist()
        infos = {i.filename: i for i in z.infolist()}
        blobs = {n: z.read(n) for n in names}

    for required in (DOC, RELS, CTYPES):
        if required not in blobs:
            raise AugmentError("%s is missing from %s - not a Word document?" % (required, src_docx))

    doc = blobs[DOC].decode("utf-8")
    rels = blobs[RELS].decode("utf-8")
    ctypes = blobs[CTYPES].decode("utf-8")

    tpl = _extract_template(doc)
    children, _body_start, _body_end = _body_children(doc)

    next_docpr = _max_docpr_id(blobs.values()) + 1
    media_names = [n for n in names if n.startswith(MEDIA_DIR)]
    new_media = {}
    ct_added = []
    report = {
        "src": src_docx,
        "dst": dst_docx,
        "template": tpl.describe(),
        "ops": [],
        "media_added": [],
        "content_types_added": [],
    }

    # (child_index, op_order, markup, report_entry); several ops landing on the
    # same anchor keep their relative order.
    inserts = []
    n_tables = n_rows = n_header_rows = 0

    for order, op in enumerate(ops):
        if not isinstance(op, dict):
            raise AugmentError("op #%d is not a dict" % order)
        kind = op.get("type")
        anchor = op.get("anchor")
        if not anchor:
            raise AugmentError("op #%d has no 'anchor'" % order)
        a_idx = _find_anchor(children, anchor, int(op.get("occurrence", 0) or 0))
        at = _insert_index(children, a_idx, op.get("after_table"), doc)

        if kind == "table":
            title = op.get("title")
            pos = op.get("title_position", "above")
            title_above = bool(title) and pos == "above"
            pbb = bool(op.get("page_break_before"))

            body, nrows, nheader = _build_table(
                op, tpl, keep_last_row_with_next=bool(title) and not title_above)
            n_tables += 1
            n_rows += nrows
            n_header_rows += nheader

            if title_above:
                # keepNext glues the title to the first row of its table.
                markup = _build_caption(title, tpl, keep_next=True,
                                        page_break=pbb) + body
            else:
                lead = _build_page_break_paragraph() if pbb else ""
                cap = _build_caption(title, tpl) if title else ""
                markup = lead + body + cap

            entry = {
                "type": "table", "anchor": anchor, "title": title,
                "anchor_child": a_idx, "insert_after_child": at,
                "insert_after_tag": children[at].tag,
                "cols": len(op.get("columns") or (op.get("rows") or [[]])[0]),
                "rows": len(op.get("rows") or []),
                "table_rows_emitted": nrows, "header_rows_emitted": nheader,
                "title_position": pos if title else None,
                "page_break_before": pbb,
                # filled in below, once neighbours are known
                "spacer_before": False, "spacer_after": False,
            }
            inserts.append((at, order, markup, entry, op.get("spacer_after")))
            report["ops"].append(entry)

        elif kind == "image":
            path = op.get("path")
            if not path or not os.path.isfile(path):
                raise AugmentError("op #%d image path not found: %r" % (order, path))
            with open(path, "rb") as fh:
                data = fh.read()
            ext = os.path.splitext(path)[1].lower().lstrip(".") or "png"
            if ext == "jpg":
                ext = "jpeg"
            px_w, px_h, how = _image_size_px(data, path)
            cx, cy = _emu_from_cm(op.get("width_cm", 15.0), px_w, px_h)

            ctypes, added = _ensure_default_ext(ctypes, ext)
            if added and ext not in ct_added:
                ct_added.append(ext)

            media_name = _next_media_name(list(media_names) + list(new_media), ext)
            new_media[media_name] = data
            media_names.append(media_name)

            rid = _next_rid(rels)
            rels = _add_relationship(rels, rid, media_name[len("word/"):])

            docpr = next_docpr
            next_docpr += 1

            caption = op.get("caption")
            pbb = bool(op.get("page_break_before"))
            # The caption sits *below* the image, so keepNext goes on the image
            # paragraph - that is what stops the two landing on separate pages.
            markup = _build_image_paragraph(
                rid, docpr, os.path.basename(path), cx, cy, tpl,
                keep_next=bool(caption), page_break=pbb)
            if caption:
                markup += _build_caption(caption, tpl)
            entry = {
                "type": "image", "anchor": anchor, "caption": caption,
                "anchor_child": a_idx, "insert_after_child": at,
                "insert_after_tag": children[at].tag,
                "path": os.path.abspath(path), "media": media_name, "rId": rid,
                "docPr_id": docpr, "px": [px_w, px_h], "emu": [cx, cy],
                "cm": [round(cx / EMU_PER_CM, 3), round(cy / EMU_PER_CM, 3)],
                "size_source": how, "page_break_before": pbb,
                "spacer_before": False, "spacer_after": False,
            }
            inserts.append((at, order, markup, entry, op.get("spacer_after")))
            report["ops"].append(entry)
        else:
            raise AugmentError("op #%d: unknown type %r (expected 'table' or 'image')" % (order, kind))

    # ---- splice document.xml (pure insertion, original bytes untouched) ----
    #
    # Word silently merges two <w:tbl> elements that touch, so a paragraph has
    # to separate them. It used to be emitted after *every* inserted table,
    # which left stray empty paragraphs in the flow - one of them flowed onto a
    # page of its own and produced a completely blank page. Now the spacer is
    # emitted only at a boundary where a table really does meet a table: the
    # neighbours are the existing body children on either side of the insertion
    # point plus the other ops landing on the same point.
    inserts.sort(key=lambda t: (t[0], t[1]))
    spacers_emitted = 0
    out = []
    prev = 0
    i = 0
    while i < len(inserts):
        at = inserts[i][0]
        j = i
        while j < len(inserts) and inserts[j][0] == at:
            j += 1
        group = inserts[i:j]
        i = j

        pos = children[at].end
        if pos < prev:
            raise AugmentError("internal: insertion offsets out of order")
        out.append(doc[prev:pos])
        prev = pos

        left_is_tbl = children[at].tag == "w:tbl"
        # If the next existing sibling is a bare page-break paragraph, glue our
        # last paragraph to it so it can never be stranded on a page of its own.
        glue_next = (at + 1 < len(children)
                     and _is_lone_page_break(doc, children[at + 1]))
        for k, (_at, _order, markup, entry, want_spacer) in enumerate(group):
            if glue_next and k == len(group) - 1:
                glued = _keep_next_on_last_block(markup)
                entry["glued_to_page_break"] = glued != markup
                markup = glued
            if left_is_tbl and markup.startswith("<w:tbl>"):
                out.append(tpl.spacer_p)
                spacers_emitted += 1
                entry["spacer_before"] = True
            out.append(markup)
            ends_tbl = markup.rstrip().endswith("</w:tbl>")
            if k + 1 < len(group):
                right_is_tbl = group[k + 1][2].startswith("<w:tbl>")
            else:
                right_is_tbl = (at + 1 < len(children)
                                and children[at + 1].tag == "w:tbl")
            # The anti-merge spacer is mandatory and cannot be opted out of;
            # "spacer_after": true only *adds* one where it is not required.
            need = (ends_tbl and right_is_tbl) or want_spacer is True
            if need:
                out.append(tpl.spacer_p)
                spacers_emitted += 1
                entry["spacer_after"] = True
                left_is_tbl = False
            else:
                left_is_tbl = ends_tbl
    out.append(doc[prev:])
    new_doc = "".join(out)

    blobs[DOC] = new_doc.encode("utf-8")
    blobs[RELS] = rels.encode("utf-8")
    blobs[CTYPES] = ctypes.encode("utf-8")
    blobs.update(new_media)

    report["media_added"] = sorted(new_media)
    report["content_types_added"] = ct_added
    report["doc_bytes"] = {"before": len(doc.encode("utf-8")), "after": len(blobs[DOC])}
    report["pagination"] = {
        "tables_inserted": n_tables,
        "rows_inserted": n_rows,
        "header_rows_inserted": n_header_rows,
        "cant_split_added": new_doc.count("<w:cantSplit/>") - doc.count("<w:cantSplit/>"),
        "tbl_header_added": new_doc.count("<w:tblHeader/>") - doc.count("<w:tblHeader/>"),
        "keep_next_added": new_doc.count("<w:keepNext/>") - doc.count("<w:keepNext/>"),
        "page_break_before_added": (new_doc.count("<w:pageBreakBefore/>")
                                    - doc.count("<w:pageBreakBefore/>")),
        "spacers_emitted": spacers_emitted,
    }
    # Cheap invariants; a mismatch means a builder regressed.
    pg = report["pagination"]
    if pg["cant_split_added"] != n_rows:
        raise AugmentError("internal: %d <w:cantSplit/> for %d inserted rows"
                           % (pg["cant_split_added"], n_rows))
    if pg["tbl_header_added"] != n_header_rows:
        raise AugmentError("internal: %d <w:tblHeader/> for %d header rows"
                           % (pg["tbl_header_added"], n_header_rows))

    # ---- write the package, preserving entry order and compression ----
    out_dir = os.path.dirname(dst_docx)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    order_out = list(names) + [n for n in new_media if n not in names]
    tmp = "%s.%d.tmp" % (dst_docx, os.getpid())
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for n in order_out:
            info = infos.get(n)
            if info is not None:
                zi = copy.copy(info)
                zi.compress_type = info.compress_type
            else:
                zi = zipfile.ZipInfo(n, date_time=(1980, 1, 1, 0, 0, 0))
                zi.compress_type = zipfile.ZIP_DEFLATED
                zi.external_attr = 0o600 << 16
            z.writestr(zi, blobs[n])
    try:
        os.replace(tmp, dst_docx)  # atomic, overwrites on Windows too
    except OSError as exc:
        os.remove(tmp)
        raise AugmentError(
            "cannot write %s (%s) - is it open in Word?" % (dst_docx, exc))
    return report


# --------------------------------------------------------------------------
# verification
# --------------------------------------------------------------------------

def _all_wt(xml_bytes):
    """Every ``<w:t>`` value in document order, via a real XML parse."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml_bytes)
    return [(e.text or "") for e in root.iter("{%s}t" % W_NS)]


def _is_ordered_subsequence(small, big):
    """Greedy two-pointer; greedy is optimal for subsequence testing."""
    it = iter(big)
    for item in small:
        for cand in it:
            if cand == item:
                break
        else:
            return False, item
    return True, None


def verify(src, dst, quiet=False):
    """Assert ``dst`` still contains every original character, in order.

    Checks performed:
      1. both files are valid, non-corrupt zips (``testzip()``)
      2. ``document.xml`` parses as XML
      3. every original ``<w:t>`` value survives, in the original order
      4. the original concatenated text is an ordered subsequence of the new one
      5. the original ``document.xml`` bytes are an ordered subsequence of the
         new bytes - i.e. the edit was a pure insertion, nothing was rewritten
      6. every relationship referenced by ``r:embed`` resolves to a part that
         actually exists in the package
      7. no two ``<w:tbl>`` elements touch (Word would merge them into one) and
         the table count only ever grows
    """
    with zipfile.ZipFile(src) as zs, zipfile.ZipFile(dst) as zd:
        bad = zs.testzip()
        assert bad is None, "source zip corrupt at %s" % bad
        bad = zd.testzip()
        assert bad is None, "output zip corrupt at %s" % bad

        s_doc = zs.read(DOC)
        d_doc = zd.read(DOC)
        s_t = _all_wt(s_doc)
        d_t = _all_wt(d_doc)

        ok, missing = _is_ordered_subsequence(s_t, d_t)
        assert ok, "original <w:t> element lost or reordered: %r" % (missing,)

        s_text = "".join(s_t)
        d_text = "".join(d_t)
        ok, ch = _is_ordered_subsequence(s_text, d_text)
        assert ok, "original character sequence broken at %r" % (ch,)

        ok, b = _is_ordered_subsequence(s_doc, d_doc)
        assert ok, "document.xml was rewritten, not purely inserted into (byte %r)" % (b,)

        d_names = set(zd.namelist())
        import xml.etree.ElementTree as ET
        rels_root = ET.fromstring(zd.read(RELS))
        targets = {r.get("Id"): r.get("Target")
                   for r in rels_root.iter("{%s}Relationship" % PKG_REL_NS)}
        for m in re.finditer(r'r:embed="([^"]+)"', d_doc.decode("utf-8")):
            rid = m.group(1)
            assert rid in targets, "r:embed=%s has no relationship" % rid
            tgt = targets[rid]
            part = tgt if tgt.startswith("word/") else "word/" + tgt.lstrip("/")
            assert part in d_names, "relationship %s -> %s missing from package" % (rid, part)

        ctypes = zd.read(CTYPES).decode("utf-8")
        for n in d_names:
            if n.startswith(MEDIA_DIR):
                ext = os.path.splitext(n)[1].lstrip(".").lower()
                assert re.search(r'<Default\s[^>]*Extension="%s"' % re.escape(ext), ctypes, re.I), \
                    "no <Default Extension=%r> for %s" % (ext, n)

        d_text_xml = d_doc.decode("utf-8")
        merged = re.search(r"</w:tbl>\s*<w:tbl[\s>]", d_text_xml)
        assert merged is None, \
            "two <w:tbl> elements touch at byte %d - Word would merge them" \
            % (merged.start() if merged else -1)

        result = {
            "src": os.path.abspath(src),
            "dst": os.path.abspath(dst),
            "src_wt_elements": len(s_t),
            "dst_wt_elements": len(d_t),
            "src_chars": len(s_text),
            "dst_chars": len(d_text),
            "added_chars": len(d_text) - len(s_text),
            "src_doc_bytes": len(s_doc),
            "dst_doc_bytes": len(d_doc),
            "src_tables": s_doc.count(b"<w:tbl>"),
            "dst_tables": d_doc.count(b"<w:tbl>"),
            "src_drawings": s_doc.count(b"<w:drawing>"),
            "dst_drawings": d_doc.count(b"<w:drawing>"),
            "src_media": sum(1 for n in zs.namelist() if n.startswith(MEDIA_DIR)),
            "dst_media": sum(1 for n in d_names if n.startswith(MEDIA_DIR)),
            "src_rows": len(re.findall(rb"<w:tr[\s>]", s_doc)),
            "dst_rows": len(re.findall(rb"<w:tr[\s>]", d_doc)),
            "src_tbl_header": s_doc.count(b"<w:tblHeader/>"),
            "dst_tbl_header": d_doc.count(b"<w:tblHeader/>"),
            "src_cant_split": s_doc.count(b"<w:cantSplit/>"),
            "dst_cant_split": d_doc.count(b"<w:cantSplit/>"),
            "src_keep_next": s_doc.count(b"<w:keepNext/>"),
            "dst_keep_next": d_doc.count(b"<w:keepNext/>"),
            "text_preserved": True,
        }
        assert result["dst_tables"] >= result["src_tables"], "tables were lost"
        # every inserted table got a repeating header, every inserted row got
        # cantSplit
        assert (result["dst_tbl_header"] - result["src_tbl_header"]) == \
            (result["dst_tables"] - result["src_tables"]), \
            "inserted tables (%d) != added <w:tblHeader/> (%d)" % (
                result["dst_tables"] - result["src_tables"],
                result["dst_tbl_header"] - result["src_tbl_header"])
        assert (result["dst_cant_split"] - result["src_cant_split"]) == \
            (result["dst_rows"] - result["src_rows"]), \
            "inserted rows (%d) != added <w:cantSplit/> (%d)" % (
                result["dst_rows"] - result["src_rows"],
                result["dst_cant_split"] - result["src_cant_split"])

    if not quiet:
        print("verify OK  %s -> %s" % (os.path.basename(src), os.path.basename(dst)))
        print("  text:     %d -> %d chars (+%d), %d -> %d <w:t> elements"
              % (result["src_chars"], result["dst_chars"], result["added_chars"],
                 result["src_wt_elements"], result["dst_wt_elements"]))
        print("  document.xml: %d -> %d bytes (pure insertion verified)"
              % (result["src_doc_bytes"], result["dst_doc_bytes"]))
        print("  tables:   %d -> %d   drawings: %d -> %d   media parts: %d -> %d"
              % (result["src_tables"], result["dst_tables"],
                 result["src_drawings"], result["dst_drawings"],
                 result["src_media"], result["dst_media"]))
        print("  rows:     %d -> %d   tblHeader +%d (= tables inserted %d)"
              "   cantSplit +%d (= rows inserted %d)   keepNext +%d"
              % (result["src_rows"], result["dst_rows"],
                 result["dst_tbl_header"] - result["src_tbl_header"],
                 result["dst_tables"] - result["src_tables"],
                 result["dst_cant_split"] - result["src_cant_split"],
                 result["dst_rows"] - result["src_rows"],
                 result["dst_keep_next"] - result["src_keep_next"]))
    return result


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--ops", required=True,
                    help="path to a JSON file (UTF-8) holding the ops list")
    ap.add_argument("--no-verify", action="store_true")
    args = ap.parse_args(argv)

    with io.open(args.ops, "r", encoding="utf-8") as fh:
        ops = json.load(fh)
    report = augment(args.src, args.dst, ops)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not args.no_verify:
        verify(args.src, args.dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
