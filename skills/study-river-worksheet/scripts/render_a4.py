#!/usr/bin/env python3
"""Render agent-authored worksheet data. No network, LLM, or station catalog.

Runtime dependency: ReportLab 4+ (not installed automatically).
All dimensions below are millimetres; text sizes are points.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import re
import sys
import tempfile
import unicodedata
from fractions import Fraction
from pathlib import Path

try:
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
except ImportError:
    raise SystemExit('ReportLab is unavailable. Use a host with ReportLab; no PDF was generated.')

FONT_PATH = Path(__file__).resolve().parents[1] / 'assets/fonts/KleeOne-SemiBold.ttf'
FONT = 'StudyRiverKlee'
WIDTH, HEIGHT, LEFT, RIGHT = 210, 297, 12, 198
BODY_TOP, BODY_BOTTOM = 45, 277
VERSION = '0.3.1'
# Paper never names a grade, age, or target learner (the same sheet works for anyone).
AUDIENCE = re.compile(r'[小中高]学?[校生]?\s*[0-9０-９一二三四五六](?:\s*年|(?![0-9０-９]))|[0-9０-９一二三四五六]\s*年生|[0-9０-９]+\s*[歳才]|'
                      r'中学|高校|小学|幼児|園児|キッズ|子ども|こども|大人|シニア|'
                      r'\b(?:grade|year|age)\s*[0-9]+|\bages?\s+[0-9]|\b(?:kids?|children|adults?|seniors?|'
                      r'kindergarten|preschool)\b|\bpara\s+(?:niños|adultos)|\b(?:grado|curso)\s*[0-9]+', re.I)
# Fixed paper labels only; subject matter comes from the worksheet data.
LABELS = {
    'ja': dict(name='なまえ', date='ひづけ', answers='こたえ・れい', remainder='あまり'),
    'en': dict(name='Name', date='Date', answers='Answer key / examples', remainder='R'),
    'es': dict(name='Nombre', date='Fecha', answers='Respuestas / ejemplos', remainder='R'),
}
DEFAULT_INSTRUCTIONS = {
    'en': {'word_trace': 'Trace the light letters, then write them in the empty boxes.',
           'kanji_trace': 'Look at the model, trace it, then write it in the empty boxes.',
           'qa': 'Write your answers in the spaces below.',
           'arithmetic': 'Solve each problem.'},
    'es': {'word_trace': 'Repasa las letras claras y luego escríbelas en las casillas vacías.',
           'kanji_trace': 'Mira el modelo, repásalo y luego escríbelo en las casillas vacías.',
           'qa': 'Escribe tus respuestas en los espacios.',
           'arithmetic': 'Resuelve cada operación.'},
}
# Vertical (筆算) arithmetic: two columns per row, digits sit on a shared column pitch.
CELL_W = (RIGHT - LEFT) / 2
PITCH, DIGIT = 9.7, 8.5
TRACE_KINDS = ('word_trace', 'kanji_trace')
SMALL_KANA = set('ぁぃぅぇぉっゃゅょゎゕゖァィゥェォッャュョヮヵヶ')


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


def is_kana(c):
    return '\u3041' <= c <= '\u3096' or '\u30a1' <= c <= '\u30fa' or c == 'ー'


def is_kanji(c):
    return '\u4e00' <= c <= '\u9fff' or c in '々〆'


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
    tokens = re.findall(r'[A-Za-z0-9_]+(?:[\x27’-][A-Za-z0-9_]+)*|.', value)
    lines, line = [], ''
    for token in tokens:
        if measure(token, size) > width:
            fail('An unbreakable word is wider than the text column')
        if line and measure(line + token, size) > width:
            lines.append(line.rstrip())
            line = token.lstrip()
        else:
            line += token
    if line:
        lines.append(line.rstrip())
    return lines


def fraction_string(value):
    return str(value.numerator) if value.denominator == 1 else str(value)


def validate(raw):
    keys(raw, ['schema_version', 'kind', 'title', 'instructions', 'locale', 'items',
               'answer_key', 'layout', 'sources'], 'worksheet')
    if raw.get('schema_version') != '1.0':
        fail('schema_version must be 1.0')
    kind = raw.get('kind')
    if kind not in ('word_trace', 'kanji_trace', 'qa', 'arithmetic'):
        fail('kind must be word_trace, kanji_trace, qa, or arithmetic')
    locale = raw.get('locale', 'ja')
    if locale not in LABELS:
        fail('locale must be ja, en, or es')
    doc = dict(raw, locale=locale)
    doc['title'] = text(raw.get('title'), 'title', 80)
    vertical_trace = kind in TRACE_KINDS and (raw.get('layout') or {}).get('direction') != 'horizontal'
    vertical_trace = vertical_trace if isinstance(raw.get('layout', {}), dict) else False
    default = {'word_trace': 'うすい もじを なぞって、' + ('となりの' if vertical_trace else 'したの')
               + ' ますに かきましょう。',
               'kanji_trace': 'てほんを みて なぞり、あいている ますに かきましょう。',
               'qa': 'こたえを かきましょう。', 'arithmetic': 'けいさんを しましょう。'}
    fallback = default[kind] if locale == 'ja' else DEFAULT_INSTRUCTIONS[locale][kind]
    doc['instructions'] = text(raw.get('instructions', fallback), 'instructions', 160)
    for field in ('title', 'instructions'):
        found = AUDIENCE.search(doc[field])
        if found:
            fail(f'{field} names a grade, age, or target learner ("{found.group()}"). Paper stays '
                 'neutral: describe the content instead (e.g. 英語 基礎問題), and mention the level only in chat.')
    answer_key = raw.get('answer_key', kind not in TRACE_KINDS)
    if type(answer_key) is not bool:
        fail('answer_key must be boolean')
    if kind in TRACE_KINDS and answer_key:
        fail(f'{kind} has a model on the worksheet and does not use an answer key')
    doc['answer_key'] = answer_key
    layout = raw.get('layout', {})
    keys(layout, {'word_trace': ['max_pages', 'box_mm', 'direction'],
                  'kanji_trace': ['max_pages', 'box_mm', 'direction'],
                  'arithmetic': ['max_pages', 'format']}.get(kind, ['max_pages']), 'layout')
    doc['layout'] = {'max_pages': integer(layout.get('max_pages', 1), 'max_pages', 1, 20)}
    if kind in TRACE_KINDS:
        low, default_box = (12, 16) if kind == 'word_trace' else (16, 20)
        box = layout.get('box_mm', default_box)
        if type(box) not in (int, float) or not math.isfinite(box) or not low <= box <= 22:
            fail(f'box_mm must be a finite number from {low} to 22')
        doc['layout']['box_mm'] = box
    if kind in TRACE_KINDS:
        # Japanese handwriting practice is written top to bottom by default.
        direction = layout.get('direction', 'vertical')
        if direction not in ('vertical', 'horizontal'):
            fail('layout.direction must be vertical or horizontal')
        doc['layout']['direction'] = direction
    if kind == 'arithmetic':
        form = layout.get('format', 'horizontal')
        if form not in ('horizontal', 'vertical'):
            fail('layout.format must be horizontal or vertical')
        doc['layout']['format'] = form
    vertical = doc['layout'].get('format') == 'vertical'
    items = raw.get('items')
    if not isinstance(items, list) or not 1 <= len(items) <= 200:
        fail('items must contain 1..200 entries')
    normalized, seen = [], set()
    for i, item in enumerate(items, 1):
        fields = {'word_trace': ['id', 'text', 'label'],
                  'kanji_trace': ['id', 'char', 'reading'],
                  'qa': ['id', 'prompt', 'answer', 'answer_lines', 'note'],
                  'arithmetic': ['id', 'a', 'b', 'op', 'answer', 'remainder']}[kind]
        keys(item, fields, f'item {i}')
        ident = text(item.get('id'), f'item {i}.id', 40)
        if ident in seen:
            fail(f'Duplicate item id: {ident}')
        seen.add(ident)
        obj = dict(item, id=ident)
        if kind == 'word_trace':
            obj['text'] = text(item.get('text'), f'{ident}.text', 30)
            if not all(is_kana(c) or is_kanji(c) for c in obj['text']):
                fail(f'{ident}: word_trace supports hiragana/katakana, ー, and kanji only')
            obj['label'] = text(item.get('label', obj['text']), f'{ident}.label', 60)
        elif kind == 'kanji_trace':
            obj['char'] = text(item.get('char'), f'{ident}.char', 1)
            if not (is_kanji(obj['char']) or is_kana(obj['char'])):
                fail(f'{ident}: char must be one kanji or kana character')
            if 'reading' in item:
                obj['reading'] = text(item['reading'], f'{ident}.reading', 30)
        elif kind == 'qa':
            obj['prompt'] = text(item.get('prompt'), f'{ident}.prompt')
            obj['answer'] = text(item.get('answer'), f'{ident}.answer')
            obj['answer_lines'] = integer(item.get('answer_lines', 1), 'answer_lines', 1, 4)
            if 'note' in item:
                obj['note'] = text(item['note'], f'{ident}.note')
        else:
            for name in ('a', 'b'):
                obj[name] = integer(item.get(name), f'{ident}.{name}', -9999, 9999)
            a, b, op = obj['a'], obj['b'], item.get('op')
            if op not in ('add', 'sub', 'mul', 'div'):
                fail(f'{ident}: unsupported arithmetic operation')
            if op == 'div' and b == 0:
                fail(f'{ident}: division by zero')
            supplied = text(item.get('answer'), f'{ident}.answer', 40)
            if vertical:
                if a < 0 or b < 0:
                    fail(f'{ident}: vertical layout supports non-negative integers only')
                if op == 'sub' and a < b:
                    fail(f'{ident}: vertical subtraction needs a >= b')
                if not re.fullmatch(r'\d+', supplied):
                    fail(f'{ident}: answer must be a non-negative integer string')
                if op == 'div':
                    expected, rest = divmod(a, b)
                    given = integer(item.get('remainder', 0), f'{ident}.remainder', 0, 9999)
                    if (int(supplied), given) != (expected, rest):
                        fail(f'{ident}: incorrect answer; expected {expected} remainder {rest}')
                    obj['remainder'] = rest
                else:
                    if 'remainder' in item:
                        fail(f'{ident}: remainder is only for division')
                    expected = {'add': a + b, 'sub': a - b, 'mul': a * b}[op]
                    if int(supplied) != expected:
                        fail(f'{ident}: incorrect answer; expected {expected}')
                obj['answer'] = str(expected)
            else:
                if 'remainder' in item:
                    fail(f'{ident}: remainder is only for vertical division')
                expected = {'add': lambda: Fraction(a + b), 'sub': lambda: Fraction(a - b),
                            'mul': lambda: Fraction(a * b), 'div': lambda: Fraction(a, b)}[op]()
                if not re.fullmatch(r'-?\d+(?:/[1-9]\d*)?', supplied):
                    fail(f'{ident}: answer must be an integer or fraction string')
                if Fraction(supplied) != expected:
                    fail(f'{ident}: incorrect answer; expected {fraction_string(expected)}')
                obj['answer'] = fraction_string(expected)
        normalized.append(obj)
    doc['items'] = normalized
    sources = raw.get('sources', [])
    if not isinstance(sources, list) or len(sources) > 30:
        fail('sources must be a list with at most 30 entries')
    for source in sources:
        keys(source, ['title', 'url', 'checked_on'], 'source')
        for field in ('title', 'url', 'checked_on'):
            text(source.get(field), f'source.{field}', 1000)
        if not source['url'].startswith('https://'):
            fail('source.url must use https://')
    doc['sources'] = sources
    return doc


def prepare(raw):
    doc = validate(raw)
    load_font()
    if measure(doc['title'], 18) > RIGHT - LEFT:
        fail('Title too wide; shorten it without reducing the writing area')
    instructions = wrap(doc['instructions'], 10, RIGHT - LEFT)
    if len(instructions) > 2:
        fail('Instructions must fit within two lines')
    kind = doc['kind']
    if kind in TRACE_KINDS and doc['layout']['direction'] == 'vertical':
        planner = plan_kanji_columns if kind == 'kanji_trace' else plan_word_columns
        return (*planner(doc), instructions)
    vertical = doc['layout'].get('format') == 'vertical'
    # One remainder field style per sheet, so its presence does not hint at individual answers.
    show_remainder = any(i.get('remainder') for i in doc['items'])
    entries = []
    for number, item in enumerate(doc['items'], 1):
        if kind == 'word_trace':
            box = doc['layout']['box_mm']
            if len(item['text']) * box > RIGHT - LEFT - 8:
                fail(f'{item["id"]}: word too wide for {box}mm boxes; choose a supported size explicitly')
            glyphs(item['text'])
            model = item['text'] if item['label'] == item['text'] else f'{item["label"]}   {item["text"]}'
            heading = f'{number}. {model}'
            if measure(heading, 10) > RIGHT - LEFT:
                fail(f'{item["id"]}: label too wide')
            height = 2 * box + 11
            detail = {'heading': heading}
        elif kind == 'kanji_trace':
            box = doc['layout']['box_mm']
            glyphs(item['char'])
            heading = f'{number}. {item["reading"]}' if item.get('reading') else f'{number}.'
            if measure(heading, 10) > RIGHT - LEFT:
                fail(f'{item["id"]}: reading too wide')
            height = box + 9  # 20mm boxes: eight characters per page
            detail = {'heading': heading, 'cells': int((RIGHT - LEFT - 8) // box)}
        elif kind == 'qa':
            prompts = wrap(item['prompt'], 12, RIGHT - LEFT - 10)
            answers = wrap(item['answer'], 11, RIGHT - LEFT - 10)
            notes = wrap(item['note'], 9, RIGHT - LEFT - 10) if item.get('note') else []
            # Reserve the greater of problem/answer heights, so matching pages stay aligned.
            height = len(prompts) * 6 + max(item['answer_lines'] * 9,
                                           len(answers) * 6 + len(notes) * 5) + 7
            detail = dict(prompts=prompts, answers=answers, notes=notes)
        elif vertical:
            height, width = vertical_plan(item)
            if width > CELL_W - 4:
                fail(f'{item["id"]}: numbers too wide for vertical layout; use smaller numbers '
                     'or the horizontal format')
            detail = dict(remainder_field=show_remainder)
        else:
            def operand(n):
                return f'({n})' if n < 0 else str(n)
            symbol = {'add': '＋', 'sub': '−', 'mul': '×', 'div': '÷'}[item['op']]
            prompt = f'{operand(item["a"])} {symbol} {operand(item["b"])} ＝'
            if measure(prompt + '  ' + item['answer'], 14) > RIGHT - LEFT - 10:
                fail(f'{item["id"]}: arithmetic expression too wide')
            height, detail = 11, dict(prompt=prompt)
        if height > BODY_BOTTOM - BODY_TOP:
            fail(f'{item["id"]}: item exceeds one page')
        entries.append((number, item, height, detail))
    step = 2 if vertical else 1
    page_items, pages, y = [], [], BODY_TOP
    for start in range(0, len(entries), step):
        row = entries[start:start + step]
        height = max(e[2] for e in row)
        if y + height > BODY_BOTTOM:
            pages.append(page_items)
            page_items, y = [], BODY_TOP
        for col, (number, item, _, detail) in enumerate(row):
            page_items.append(dict(number=number, item=item, y=y, x=LEFT + col * CELL_W,
                                   height=height, **detail))
        y += height
    pages.append(page_items)
    if len(pages) > doc['layout']['max_pages']:
        fail(f'{len(pages)} problem pages needed, max_pages={doc["layout"]["max_pages"]}. '
             'Keep requested content; ask which page/count constraint to change.')
    return doc, pages, instructions


def plan_kanji_columns(doc):
    """Japanese practice-notebook order: one character per column, columns right to left."""
    box = doc['layout']['box_mm']
    cols = int((RIGHT - LEFT) // box)
    rows = int((BODY_BOTTOM - BODY_TOP - 6) // box)
    grid_right = (LEFT + RIGHT) / 2 + cols * box / 2
    pages = []
    for number, item in enumerate(doc['items'], 1):
        glyphs(item['char'])
        reading = item.get('reading', '')
        if reading and measure(reading, 7) > box - 1:
            fail(f'{item["id"]}: reading too wide for a {box}mm column; shorten it or use larger boxes')
        index = (number - 1) % cols
        if index == 0:
            pages.append([])
        pages[-1].append(dict(number=number, item=item, y=BODY_TOP, rows=rows,
                              x=grid_right - (index + 1) * box))
    return check_pages(doc, pages)


def plan_word_columns(doc):
    """Each word: a tracing column, then an empty column to its left; words run right to left."""
    box = doc['layout']['box_mm']
    pair = 2 * box + 3
    per_page = int((RIGHT - LEFT + 3) // pair)
    rows = int((BODY_BOTTOM - BODY_TOP - 6) // box)
    grid_right = (LEFT + RIGHT) / 2 + (per_page * pair - 3) / 2
    pages = []
    for number, item in enumerate(doc['items'], 1):
        glyphs(item['text'])
        if len(item['text']) > rows:
            fail(f'{item["id"]}: word too long for {box}mm boxes ({rows} per column); '
                 'choose a supported size explicitly')
        heading = f'{number}.' if item['label'] == item['text'] else f'{number}. {item["label"]}'
        if measure(heading, 8) > 2 * box:
            fail(f'{item["id"]}: label too wide for the column pair; shorten it or use larger boxes')
        index = (number - 1) % per_page
        if index == 0:
            pages.append([])
        pages[-1].append(dict(number=number, item=item, y=BODY_TOP, heading=heading,
                              x=grid_right - index * pair - box))
    return check_pages(doc, pages)


def check_pages(doc, pages):
    if len(pages) > doc['layout']['max_pages']:
        fail(f'{len(pages)} problem pages needed, max_pages={doc["layout"]["max_pages"]}. '
             'Keep requested content; ask which page/count constraint to change.')
    return doc, pages


def vertical_plan(item):
    """Height and width (mm) of one 筆算 cell; columns are counted in PITCH units."""
    a, b, op, answer = str(item['a']), str(item['b']), item['op'], item['answer']
    if op == 'div':
        return 50, len(a) * PITCH + measure(b, 18) + 22
    cols = max(len(a), len(b), len(answer))
    height = 38
    if op == 'mul' and item['b'] > 9:
        cols = max([cols] + [len(str(item['a'] * int(d))) + k for k, d in enumerate(reversed(b))])
        height = 40 + 9.5 * len(b)
    return height, (cols + 1) * PITCH + 12


def put(c, x, y, value, size=11, gray=0):
    glyphs(value)
    c.setFont(FONT, size)
    c.setFillGray(gray)
    c.drawString(x * mm, (HEIGHT - y) * mm, value)


def line(c, x1, y1, x2, y2, gray=0.65, thickness=0.25):
    c.setStrokeGray(gray)
    c.setLineWidth(thickness * mm)
    c.line(x1 * mm, (HEIGHT - y1) * mm, x2 * mm, (HEIGHT - y2) * mm)


def cell(c, char, xx, y, box, gray=None, vertical=False):
    """One writing box with a dashed cross guide; gray=None leaves it empty.

    vertical=True uses tategaki forms: ー turns upright and small kana sit top-right.
    """
    c.setStrokeGray(0.55)
    c.setLineWidth(0.25 * mm)
    c.rect(xx * mm, (HEIGHT - y - box) * mm, box * mm, box * mm)
    c.setDash(1 * mm, 1.2 * mm)
    line(c, xx + box / 2, y, xx + box / 2, y + box, 0.8, 0.15)
    line(c, xx, y + box / 2, xx + box, y + box / 2, 0.8, 0.15)
    c.setDash()
    if gray is not None:
        size = box * mm * 0.77
        char_w = measure(char, size)
        # Font metrics align all kana to the same baseline, including small kana.
        ascent, descent = pdfmetrics.getAscentDescent(FONT, size)
        baseline = y + box / 2 + (ascent + descent) / (2 * mm)
        x0 = xx + (box - char_w) / 2
        if vertical and char == 'ー':
            c.saveState()
            c.translate((xx + box / 2) * mm, (HEIGHT - y - box / 2) * mm)
            c.rotate(-90)
            c.scale(-1, 1)  # mirror so the stroke reads like the vertical form
            put_at_origin(c, char, size, gray, char_w, (ascent + descent) / 2)
            c.restoreState()
            return
        if vertical and char in SMALL_KANA:
            shift = box * 0.14
            x0, baseline = x0 + shift, baseline - shift
        put(c, x0, baseline, char, size, gray)


def put_at_origin(c, char, size, gray, width_mm, mid):
    """Draw a glyph centred on the current origin (points; used under a transform)."""
    c.setFont(FONT, size)
    c.setFillGray(gray)
    c.drawString(-width_mm * mm / 2, -mid, char)


def grid(c, value, x, y, box, trace):
    for i, char in enumerate(value):
        cell(c, char, x + i * box, y, box, 0.7 if trace else None)


def digits(c, value, right, baseline, size=18, shift=0):
    """Digits centred on the column grid; column 0 (ones) ends at `right`."""
    for i, ch in enumerate(reversed(str(value))):
        centre = right - (i + shift + 0.5) * PITCH
        put(c, centre - measure(ch, size) / 2, baseline, ch, size)


def boxes(c, count, right, top, shift=0, value=None):
    c.setStrokeGray(0.55)
    c.setLineWidth(0.25 * mm)
    for i in range(count):
        bx = right - (i + shift + 1) * PITCH + (PITCH - DIGIT) / 2
        c.rect(bx * mm, (HEIGHT - top - DIGIT) * mm, DIGIT * mm, DIGIT * mm)
    if value is not None:
        digits(c, value, right, top + DIGIT - 1.8, 16, shift)


def draw_vertical(c, b, locale, answers):
    x, y, item = b['x'], b['y'], b['item']
    a, n, op, answer = item['a'], item['b'], item['op'], item['answer']
    shown = answer if answers else None
    right = x + CELL_W - 10
    put(c, x, y + 6, f'{b["number"]}.', 10)
    if op == 'div':
        base = y + 22
        digits(c, a, right, base)
        bracket = right - len(str(a)) * PITCH - 1
        line(c, bracket, y + 14, right + 1, y + 14, 0, 0.35)
        line(c, bracket, y + 14, bracket - 3, base + 1.5, 0, 0.35)
        put(c, bracket - 4.5 - measure(str(n), 18), base, str(n), 18)
        boxes(c, len(answer), right, y + 3.5, value=shown)
        # y+24..y+42 stays empty for the working.
        if b['remainder_field']:
            label = LABELS[locale]['remainder']
            lx = right - 12 - measure(label, 9) - 2
            put(c, lx, y + 46.5, label, 9, 0.3)
            line(c, right - 12, y + 47.5, right, y + 47.5, 0, 0.3)
            if answers:
                rem = str(item['remainder'])
                put(c, right - 6 - measure(rem, 13) / 2, y + 46.5, rem, 13)
        return
    digits(c, a, right, y + 10)
    digits(c, n, right, y + 19)
    width = max(len(str(a)), len(str(n)))
    symbol = {'add': '＋', 'sub': '−', 'mul': '×'}[op]
    put(c, right - (width + 0.5) * PITCH - measure(symbol, 16) / 2, y + 19, symbol, 16)
    rule = right - (vertical_plan(item)[1] - 12) - 1
    line(c, rule, y + 22, right + 1, y + 22, 0, 0.35)
    top = y + 24.5
    if op == 'mul' and n > 9:
        for k, d in enumerate(reversed(str(n))):
            partial = a * int(d)
            boxes(c, len(str(partial)), right, y + 24 + k * 9.5, k, partial if answers else None)
        second = y + 24 + len(str(n)) * 9.5 + 0.5
        line(c, rule, second, right + 1, second, 0, 0.35)
        top = second + 2
    boxes(c, len(answer), right, top, value=shown)


def make_pdf(doc, pages, instructions, ident, answers=False):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=(WIDTH * mm, HEIGHT * mm), invariant=1, pageCompression=1)
    c.setTitle(doc['title'] + (' - Answer key' if answers else ''))
    c.setAuthor('Study River')
    c.setCreator('Study River worksheet renderer ' + VERSION)
    for page_no, blocks in enumerate(pages, 1):
        put(c, LEFT, 19, doc['title'], 18)
        if answers:
            put(c, LEFT, 28, LABELS[doc['locale']]['answers'], 11)
        else:
            put(c, LEFT, 28, LABELS[doc['locale']]['name'], 10)
            line(c, 27, 29, 119, 29)
            put(c, 132, 28, LABELS[doc['locale']]['date'], 10)
            line(c, 147, 29, RIGHT, 29)
        for n, s in enumerate(instructions):
            put(c, LEFT, 36 + n * 4.5, s, 10)
        line(c, LEFT, 41.5, RIGHT, 41.5, 0.3)
        for b in blocks:
            y, item, number = b['y'], b['item'], b['number']
            if doc['kind'] == 'word_trace' and doc['layout']['direction'] == 'vertical':
                box = doc['layout']['box_mm']
                put(c, b['x'] - box, y + 4, b['heading'], 8)
                for r, char in enumerate(item['text']):
                    cell(c, char, b['x'], y + 6 + r * box, box, 0.7, True)
                    cell(c, char, b['x'] - box, y + 6 + r * box, box, None)
            elif doc['kind'] == 'word_trace':
                box = doc['layout']['box_mm']
                put(c, LEFT, y + 4, b['heading'], 10)
                grid(c, item['text'], LEFT + 8, y + 7, box, True)
                grid(c, item['text'], LEFT + 8, y + 7 + box, box, False)
            elif doc['kind'] == 'kanji_trace' and doc['layout']['direction'] == 'vertical':
                box = doc['layout']['box_mm']
                reading = item.get('reading')
                if reading:
                    put(c, b['x'] + (box - measure(reading, 7)) / 2, y + 4, reading, 7, 0.3)
                for r in range(b['rows']):
                    # Row 0: black model; 1-3: light tracing; the rest: empty practice boxes.
                    gray = 0 if r == 0 else 0.7 if r <= 3 else None
                    cell(c, item['char'], b['x'], y + 6 + r * box, box, gray, True)
            elif doc['kind'] == 'kanji_trace':
                box = doc['layout']['box_mm']
                put(c, LEFT, y + 4, b['heading'], 10)
                for i in range(b['cells']):
                    # Column 0: black model; 1-3: light tracing; the rest: empty practice boxes.
                    gray = 0 if i == 0 else 0.7 if i <= 3 else None
                    cell(c, item['char'], LEFT + 8 + i * box, y + 6, box, gray)
            elif doc['kind'] == 'qa':
                put(c, LEFT, y + 5, f'{number}.', 10)
                for n, prompt in enumerate(b['prompts']):
                    put(c, LEFT + 10, y + 5 + n * 6, prompt, 12)
                after = y + len(b['prompts']) * 6
                if answers:
                    for n, answer in enumerate(b['answers']):
                        put(c, LEFT + 10, after + 5 + n * 6, answer, 11)
                    for n, note in enumerate(b['notes']):
                        put(c, LEFT + 10, after + len(b['answers']) * 6 + 5 + n * 5, note, 9, 0.3)
                else:
                    for n in range(item['answer_lines']):
                        line(c, LEFT + 10, after + 7 + n * 9, RIGHT, after + 7 + n * 9)
            elif doc['layout'].get('format') == 'vertical':
                draw_vertical(c, b, doc['locale'], answers)
            else:
                put(c, LEFT, y + 6, f'{number}.', 10)
                put(c, LEFT + 10, y + 6, b['prompt'], 14)
                x = LEFT + 10 + measure(b['prompt'], 14) + 4
                if answers:
                    put(c, x, y + 6, item['answer'], 14)
                else:
                    line(c, x, y + 7, min(x + 30, RIGHT), y + 7)
        line(c, LEFT, 281, RIGHT, 281, 0.65, 0.2)
        put(c, LEFT, 286, 'Study River | eidendo.co.jp/studyriver/', 8, 0.3)
        put(c, 147, 286, f'{ident} | {page_no}/{len(pages)}', 7, 0.3)
        c.showPage()
    c.save()
    return buffer.getvalue()


def render(raw, out_dir):
    # Generate all bytes before touching output paths. Validation cannot leave a partial PDF.
    doc, pages, instructions = prepare(raw)
    snapshot = json.dumps(doc, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    ident = hashlib.sha256(snapshot.encode()).hexdigest()[:10]
    files = {'worksheet.pdf': make_pdf(doc, pages, instructions, ident)}
    if doc['answer_key']:
        files['answer-key.pdf'] = make_pdf(doc, pages, instructions, ident, True)
    report = {'renderer_version': VERSION, 'worksheet_id': ident,
              'problem_pages': len(pages), 'answer_pages': len(pages) if doc['answer_key'] else 0,
              'item_count': len(doc['items']), 'font_sha256': hashlib.sha256(FONT_PATH.read_bytes()).hexdigest(),
              'content_validation': 'exact_arithmetic' if doc['kind'] == 'arithmetic'
              else 'structure_only; facts and linguistic correctness require author review',
              'pdf_sha256': {k: hashlib.sha256(v).hexdigest() for k, v in files.items()}}
    files['worksheet.json'] = (json.dumps(doc, ensure_ascii=False, indent=2) + '\n').encode()
    files['report.json'] = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode()
    out_dir = Path(out_dir)
    # One dedicated run directory avoids stale answers from an earlier generation.
    if out_dir.exists() and any(out_dir.iterdir()):
        fail('Output directory is not empty. Use a new directory to preserve previous worksheets.')
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        with tempfile.NamedTemporaryFile(dir=out_dir, delete=False) as temp:
            temp.write(data)
            tmp = Path(temp.name)
        try:
            os.replace(tmp, out_dir / name)
        finally:
            tmp.unlink(missing_ok=True)
    return dict(report, files=[str(out_dir / name) for name in files])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', nargs='?', type=Path)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--check', action='store_true', help='Validate and plan without writing PDFs')
    parser.add_argument('--probe', action='store_true', help='Check runtime and bundled font')
    args = parser.parse_args()
    try:
        if args.probe:
            load_font()
            glyphs('Study River とうきょう しんじゅく なまえ 漢字 あまり ＋−×÷')
            print(json.dumps({'ready': True, 'renderer_version': VERSION}))
            return
        if not args.input or (not args.check and not args.output_dir):
            parser.error('input and --output-dir are required (or use --check/--probe)')
        if args.input.stat().st_size > 1_000_000:
            fail('Input JSON exceeds 1 MB')
        raw = json.loads(args.input.read_text(encoding='utf-8'))
        if args.check:
            doc, pages, _ = prepare(raw)
            result = {'valid': True, 'problem_pages': len(pages), 'item_count': len(doc['items'])}
        else:
            result = render(raw, args.output_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (WorksheetError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)


if __name__ == '__main__':
    main()
