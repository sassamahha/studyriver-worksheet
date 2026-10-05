"""Shared page geometry, validation helpers, and drawing primitives.

All dimensions are millimetres from the top-left corner; text sizes are points.
Paper colours are black and light gray (home monochrome printing); only bundled pictures are in colour.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

try:
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
except ImportError:
    raise SystemExit('ReportLab is unavailable. Use a host with ReportLab; no PDF was generated.')

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
FONT_PATH = ASSETS / 'fonts/KleeOne-SemiBold.ttf'
FONT = 'StudyRiverKlee'
WIDTH, HEIGHT, LEFT, RIGHT = 210, 297, 12, 198
BODY_TOP, BODY_BOTTOM = 45, 277
BODY_W = RIGHT - LEFT
VERSION = '0.4.1'
# Paper never names a grade, age, or target learner (the same sheet works for anyone).
AUDIENCE = re.compile(r'[小中高]学?[校生]?\s*[0-9０-９一二三四五六](?:\s*年|(?![0-9０-９]))|[0-9０-９一二三四五六]\s*年生|[0-9０-９]+\s*[歳才]|'
                      r'中学|高校|小学|幼児|園児|キッズ|子ども|こども|大人|シニア|'
                      r'\b(?:grade|year|age)\s*[0-9]+|\bages?\s+[0-9]|\b(?:kids?|children|adults?|seniors?|'
                      r'kindergarten|preschool)\b|\bpara\s+(?:niños|adultos)|\b(?:grado|curso)\s*[0-9]+', re.I)
# Fixed paper labels only; subject matter comes from the worksheet data.
LABELS = {
    'ja': dict(name='なまえ', date='ひづけ', answers='こたえ・れい', remainder='あまり',
               time='よんだ時間', minutes='分', seconds='秒', times='よんだ回数'),
    'en': dict(name='Name', date='Date', answers='Answer key / examples', remainder='R',
               time='Time', minutes='min', seconds='s', times='Times read'),
    'es': dict(name='Nombre', date='Fecha', answers='Respuestas / ejemplos', remainder='R',
               time='Tiempo', minutes='min', seconds='s', times='Veces leído'),
}
SMALL_KANA = set('ぁぃぅぇぉっゃゅょゎゕゖァィゥェォッャュョヮヵヶ')
LIGHT = 0.7  # tracing gray


class WorksheetError(ValueError):
    pass


def fail(message):
    raise WorksheetError(message)


def keys(obj, allowed, where):
    if not isinstance(obj, dict):
        fail(f'{where}: expected an object')
    extra = set(obj) - set(allowed)
    if extra:
        fail(f'{where}: unsupported fields {sorted(extra)}')


def text(value, where, limit=500):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        fail(f'{where}: expected nonempty text, at most {limit} characters')
    value = unicodedata.normalize('NFC', value)
    if any(unicodedata.category(c).startswith('C') for c in value):
        fail(f'{where}: control characters and multiline strings are unsupported')
    return value


def integer(value, where, low, high):
    if type(value) is not int or not low <= value <= high:
        fail(f'{where}: expected integer {low}..{high}')
    return value


def choice(value, where, options):
    if value not in options:
        fail(f'{where} must be one of: {", ".join(options)}')
    return value


def neutral(value, where):
    """Reject paper text that names a grade, age, or target learner."""
    found = AUDIENCE.search(value)
    if found:
        fail(f'{where} names a grade, age, or target learner ("{found.group()}"). Paper stays '
             'neutral: describe the content instead (e.g. 英語 基礎問題), and mention the level only in chat.')
    return value


def is_kana(c):
    return 'ぁ' <= c <= 'ゖ' or 'ァ' <= c <= 'ヺ' or c == 'ー'


def is_kanji(c):
    return '一' <= c <= '鿿' or c in '々〆'


def load_font():
    if FONT not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT, str(FONT_PATH)))


def glyphs(value):
    cmap = pdfmetrics.getFont(FONT).face.charToGlyph
    missing = sorted({c for c in value if c != ' ' and not cmap.get(ord(c))})
    if missing:
        fail(f'Font cannot display: {" ".join(missing)}. Choose supported text or a verified font.')


def measure(value, size):
    glyphs(value)
    return pdfmetrics.stringWidth(value, FONT, size) / mm


def wrap(value, size, width):
    """Keep Latin words together; allow kana/kanji character boundaries."""
    tokens = re.findall(r'[A-Za-zÀ-ÿ0-9_]+(?:[\x27’-][A-Za-zÀ-ÿ0-9_]+)*|.', value)
    lines, line_ = [], ''
    for token in tokens:
        if measure(token, size) > width:
            fail('An unbreakable word is wider than the text column')
        if line_ and measure(line_ + token, size) > width:
            lines.append(line_.rstrip())
            line_ = token.lstrip()
        else:
            line_ += token
    if line_:
        lines.append(line_.rstrip())
    return lines


def put(c, x, y, value, size=11, gray=0):
    glyphs(value)
    c.setFont(FONT, size)
    c.setFillGray(gray)
    c.drawString(x * mm, (HEIGHT - y) * mm, value)


def put_center(c, x, y, value, size=11, gray=0):
    put(c, x - measure(value, size) / 2, y, value, size, gray)


def put_right(c, x, y, value, size=11, gray=0):
    put(c, x - measure(value, size), y, value, size, gray)


def line(c, x1, y1, x2, y2, gray=0.65, thickness=0.25):
    c.setStrokeGray(gray)
    c.setLineWidth(thickness * mm)
    c.line(x1 * mm, (HEIGHT - y1) * mm, x2 * mm, (HEIGHT - y2) * mm)


def rect(c, x, y, w, h, gray=0.55, thickness=0.25, fill=None):
    c.setStrokeGray(gray)
    c.setLineWidth(thickness * mm)
    if fill is not None:
        c.setFillGray(fill)
    c.rect(x * mm, (HEIGHT - y - h) * mm, w * mm, h * mm, stroke=1, fill=0 if fill is None else 1)


def dashed(c, x1, y1, x2, y2, gray=0.75, thickness=0.15):
    c.setDash(1 * mm, 1.2 * mm)
    line(c, x1, y1, x2, y2, gray, thickness)
    c.setDash()


def baseline_for(box_top, box, size):
    """Baseline (mm) that centres a full-height glyph of `size` points in a box."""
    ascent, descent = pdfmetrics.getAscentDescent(FONT, size)
    return box_top + box / 2 + (ascent + descent) / (2 * mm)


def cell(c, char, xx, y, box, gray=None, vertical=False):
    """One writing box with a dashed cross guide; gray=None leaves it empty.

    vertical=True uses tategaki forms: ー turns upright and small kana sit top-right.
    """
    rect(c, xx, y, box, box)
    dashed(c, xx + box / 2, y, xx + box / 2, y + box, 0.8)
    dashed(c, xx, y + box / 2, xx + box, y + box / 2, 0.8)
    if gray is not None:
        glyph_in_box(c, char, xx, y, box, gray, vertical)


def glyph_in_box(c, char, xx, y, box, gray, vertical=False, scale=0.77):
    size = box * mm * scale
    char_w = measure(char, size)
    ascent, descent = pdfmetrics.getAscentDescent(FONT, size)
    baseline = y + box / 2 + (ascent + descent) / (2 * mm)
    x0 = xx + (box - char_w) / 2
    if vertical and char in ROTATE:
        c.saveState()
        c.translate((xx + box / 2) * mm, (HEIGHT - y - box / 2) * mm)
        c.rotate(-90)
        if char == 'ー':
            c.scale(-1, 1)  # mirror so the stroke reads like the vertical form
        c.setFont(FONT, size)
        c.setFillGray(gray)
        c.drawString(-char_w * mm / 2, -(ascent + descent) / 2, char)
        c.restoreState()
        return
    if vertical:
        char = VERTICAL_FORMS.get(char, char)
        char_w = measure(char, size)
        x0 = xx + (box - char_w) / 2
        if char in SMALL_KANA:
            shift = box * 0.14
            x0, baseline = x0 + shift, baseline - shift
    put(c, x0, baseline, char, size, gray)


# Tategaki: Unicode vertical presentation forms where the font has them; others rotate.
VERTICAL_FORMS = {'、': '︑', '。': '︒', '「': '﹁', '」': '﹂', '『': '﹃', '』': '﹄', '（': '︵', '）': '︶',
                  '(': '︵', ')': '︶', '【': '︻', '】': '︼', '…': '︙', '‥': '︰', '―': '︱', '！': '！', '？': '？'}
ROTATE = set('ー〜～−－-')


def footer(c, ident, page_no, pages):
    line(c, LEFT, 281, RIGHT, 281, 0.65, 0.2)
    put(c, LEFT, 286, 'Study River | eidendo.co.jp/studyriver/', 8, 0.3)
    put(c, 147, 286, f'{ident} | {page_no}/{pages}', 7, 0.3)


class Kind:
    """A worksheet kind implemented outside the original four (see render_a4.validate).

    Subclasses define item fields, layout fields, validation, page planning, and drawing.
    Pages are lists of block dicts; blocks must contain everything draw() needs.
    """
    name = ''
    item_fields: tuple = ()
    layout_fields: tuple = ('max_pages',)
    extra_fields: tuple = ()          # additional top-level document fields
    answer_key_default = True
    answer_key_allowed = True
    min_items = 1
    validation = 'structure_only; facts and linguistic correctness require author review'
    instructions = {'ja': '', 'en': '', 'es': ''}

    def wants_key(self, doc):
        return self.answer_key_default

    def allows_key(self, doc):
        return self.answer_key_allowed

    def layout(self, raw, doc):
        return {}

    def document(self, raw, doc):
        """Validate extra top-level fields into doc."""

    def item(self, raw, ident, doc):
        raise NotImplementedError

    def plan(self, doc):
        raise NotImplementedError

    def draw(self, c, doc, block, answers):
        raise NotImplementedError


def paginate(doc, entries, top=BODY_TOP, bottom=BODY_BOTTOM):
    """Stack (height, block) entries down the page; returns pages of blocks with y set."""
    pages, page, y = [], [], top
    for height, block in entries:
        if height > bottom - top:
            fail(f'{block.get("id", "item")}: item exceeds one page')
        if y + height > bottom and page:
            pages.append(page)
            page, y = [], top
        page.append(dict(block, y=y, height=height))
        y += height
    pages.append(page)
    return check_pages(doc, pages)


def check_pages(doc, pages):
    if len(pages) > doc['layout']['max_pages']:
        fail(f'{len(pages)} problem pages needed, max_pages={doc["layout"]["max_pages"]}. '
             'Keep requested content; ask which page/count constraint to change.')
    return pages
