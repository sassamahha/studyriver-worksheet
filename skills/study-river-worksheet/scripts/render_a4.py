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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reportlab.lib.units import mm  # noqa: E402
from reportlab.pdfbase import pdfmetrics  # noqa: E402
from reportlab.pdfgen import canvas  # noqa: E402

from core import (BODY_BOTTOM, BODY_TOP, FONT, FONT_PATH, HEIGHT, LABELS, LEFT, RIGHT,  # noqa: E402
                  VERSION, WIDTH, WorksheetError, cell, check_pages, fail, footer, glyphs, integer,
                  is_kana, is_kanji, keys, line, load_font, measure, neutral, put, text, wrap)
import kinds_language  # noqa: E402
import kinds_math  # noqa: E402
import kinds_puzzle  # noqa: E402

KINDS = {k.name: k for k in (*kinds_language.KINDS, *kinds_math.KINDS, *kinds_puzzle.KINDS)}
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


def fraction_string(value):
    return str(value.numerator) if value.denominator == 1 else str(value)


NUMBER = re.compile(r'-?\d{1,5}(?:\.\d{1,4})?')


def operand(value, where):
    """Integer, or a decimal string such as "3.25" (exact; never a binary float)."""
    if type(value) is int:
        return integer(value, where, -9999, 9999)
    if isinstance(value, str) and NUMBER.fullmatch(value):
        return value if '.' in value else integer(int(value), where, -9999, 9999)
    fail(f'{where}: expected an integer -9999..9999 or a decimal string like "3.25"')


def decimal_string(value):
    """Exact decimal text for a terminating Fraction, without trailing zeros."""
    for places in range(0, 9):
        scaled = value * 10 ** places
        if scaled.denominator == 1:
            n = abs(scaled.numerator)
            whole, frac = divmod(n, 10 ** places)
            sign = '-' if value < 0 else ''
            return sign + str(whole) + (f'.{frac:0{places}d}' if places else '')
    return None


def places(value):
    return len(value.split('.')[1]) if isinstance(value, str) and '.' in value else 0


def validate(raw):
    load_font()
    kind = raw.get('kind') if isinstance(raw, dict) else None
    spec = KINDS.get(kind)
    keys(raw, ['schema_version', 'kind', 'title', 'instructions', 'locale', 'items',
               'answer_key', 'layout', 'sources', *(spec.extra_fields if spec else ())], 'worksheet')
    if raw.get('schema_version') != '1.0':
        fail('schema_version must be 1.0')
    if kind not in ('word_trace', 'kanji_trace', 'qa', 'arithmetic', *KINDS):
        fail('kind must be one of: ' + ', '.join(('word_trace', 'kanji_trace', 'qa', 'arithmetic', *KINDS)))
    locale = raw.get('locale', 'ja')
    if locale not in LABELS:
        fail('locale must be ja, en, or es')
    doc = dict(raw, locale=locale)
    doc['title'] = text(raw.get('title'), 'title', 80)
    layout = raw.get('layout', {})
    keys(layout, spec.layout_fields if spec else
         {'word_trace': ['max_pages', 'box_mm', 'direction'],
          'kanji_trace': ['max_pages', 'box_mm', 'direction'],
          'arithmetic': ['max_pages', 'format']}.get(kind, ['max_pages']), 'layout')
    doc['layout'] = {'max_pages': integer(layout.get('max_pages', 1), 'max_pages', 1, 20)}
    if spec:
        doc['layout'].update(spec.layout(layout, doc))
        fallback = spec.instructions[locale]
        if callable(fallback):
            fallback = fallback(doc)
    else:
        vertical_trace = kind in TRACE_KINDS and layout.get('direction') != 'horizontal'
        default = {'word_trace': 'うすい もじを なぞって、' + ('となりの' if vertical_trace else 'したの')
                   + ' ますに かきましょう。',
                   'kanji_trace': 'てほんを みて なぞり、あいている ますに かきましょう。',
                   'qa': 'こたえを かきましょう。', 'arithmetic': 'けいさんを しましょう。'}
        fallback = default[kind] if locale == 'ja' else DEFAULT_INSTRUCTIONS[locale][kind]
    doc['instructions'] = text(raw.get('instructions', fallback), 'instructions', 160)
    for field in ('title', 'instructions'):
        neutral(doc[field], field)
    has_model = kind in TRACE_KINDS or (spec and not spec.allows_key(doc))
    answer_key = raw.get('answer_key', spec.wants_key(doc) if spec else not has_model)
    if type(answer_key) is not bool:
        fail('answer_key must be boolean')
    if has_model and answer_key:
        fail(f'{kind} has a model or needs no key on the worksheet; it does not use an answer key')
    doc['answer_key'] = answer_key
    if kind in TRACE_KINDS:
        low, default_box = (12, 16) if kind == 'word_trace' else (16, 20)
        box = layout.get('box_mm', default_box)
        if type(box) not in (int, float) or not math.isfinite(box) or not low <= box <= 22:
            fail(f'box_mm must be a finite number from {low} to 22')
        doc['layout']['box_mm'] = box
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
    if spec:
        spec.document(raw, doc)
    vertical = doc['layout'].get('format') == 'vertical'
    items = raw.get('items', [] if spec and spec.min_items == 0 else None)
    low = spec.min_items if spec else 1
    if not isinstance(items, list) or not low <= len(items) <= 200:
        fail(f'items must contain {low}..200 entries')
    normalized, seen = [], set()
    for i, item in enumerate(items, 1):
        fields = spec.item_fields if spec else {
            'word_trace': ['id', 'text', 'label'],
            'kanji_trace': ['id', 'char', 'reading'],
            'qa': ['id', 'prompt', 'answer', 'answer_lines', 'note'],
            'arithmetic': ['id', 'a', 'b', 'op', 'answer', 'remainder']}[kind]
        keys(item, fields, f'item {i}')
        ident = text(item.get('id'), f'item {i}.id', 40)
        if ident in seen:
            fail(f'Duplicate item id: {ident}')
        seen.add(ident)
        obj = dict(item, id=ident)
        if spec:
            obj = spec.item(item, ident, doc)
        elif kind == 'word_trace':
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
            arithmetic_item(obj, item, ident, vertical)
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


def arithmetic_item(obj, item, ident, vertical):
    for name in ('a', 'b'):
        obj[name] = operand(item.get(name), f'{ident}.{name}')
    a, b, op = obj['a'], obj['b'], item.get('op')
    fa, fb = Fraction(a), Fraction(b)
    decimal = places(a) or places(b)
    if op not in ('add', 'sub', 'mul', 'div'):
        fail(f'{ident}: unsupported arithmetic operation')
    if op == 'div' and fb == 0:
        fail(f'{ident}: division by zero')
    supplied = text(item.get('answer'), f'{ident}.answer', 40)
    if vertical:
        if fa < 0 or fb < 0:
            fail(f'{ident}: vertical layout supports non-negative numbers only')
        if op == 'sub' and fa < fb:
            fail(f'{ident}: vertical subtraction needs a >= b')
        if decimal and op == 'div':
            fail(f'{ident}: column-form division supports integers only; use the horizontal format '
                 'for decimal division')
        if op == 'div':
            if not re.fullmatch(r'\d+', supplied):
                fail(f'{ident}: answer must be a non-negative integer string')
            expected, rest = divmod(a, b)
            given = integer(item.get('remainder', 0), f'{ident}.remainder', 0, 9999)
            if (int(supplied), given) != (expected, rest):
                fail(f'{ident}: incorrect answer; expected {expected} remainder {rest}')
            obj['remainder'] = rest
            obj['answer'] = str(expected)
            return
        if 'remainder' in item:
            fail(f'{ident}: remainder is only for division')
        expected = {'add': fa + fb, 'sub': fa - fb, 'mul': fa * fb}[op]
        if not re.fullmatch(r'\d+(?:\.\d+)?', supplied) or Fraction(supplied) != expected:
            fail(f'{ident}: incorrect answer; expected {decimal_string(expected)}')
        obj['answer'] = decimal_string(expected)
        return
    if 'remainder' in item:
        fail(f'{ident}: remainder is only for vertical division')
    expected = {'add': fa + fb, 'sub': fa - fb, 'mul': fa * fb, 'div': fa / fb if fb else None}[op]
    if decimal:
        shown = decimal_string(expected)
        if shown is None:
            fail(f'{ident}: the quotient does not terminate; choose numbers with an exact decimal answer')
        if not re.fullmatch(r'-?\d+(?:\.\d+)?', supplied):
            fail(f'{ident}: answer must be a decimal string')
        if Fraction(supplied) != expected:
            fail(f'{ident}: incorrect answer; expected {shown}')
        obj['answer'] = shown
        return
    if not re.fullmatch(r'-?\d+(?:/[1-9]\d*)?', supplied):
        fail(f'{ident}: answer must be an integer or fraction string')
    if Fraction(supplied) != expected:
        fail(f'{ident}: incorrect answer; expected {fraction_string(expected)}')
    obj['answer'] = fraction_string(expected)


def prepare(raw):
    doc = validate(raw)
    load_font()
    if measure(doc['title'], 18) > RIGHT - LEFT:
        fail('Title too wide; shorten it without reducing the writing area')
    instructions = wrap(doc['instructions'], 10, RIGHT - LEFT)
    if len(instructions) > 2:
        fail('Instructions must fit within two lines')
    kind = doc['kind']
    if kind in KINDS:
        return doc, KINDS[kind].plan(doc), instructions
    if kind in TRACE_KINDS and doc['layout']['direction'] == 'vertical':
        planner = plan_kanji_columns if kind == 'kanji_trace' else plan_word_columns
        return doc, planner(doc), instructions
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
            def shown(n):
                return f'({n})' if str(n).startswith('-') else str(n)
            symbol = {'add': '＋', 'sub': '－', 'mul': '×', 'div': '÷'}[item['op']]
            prompt = f'{shown(item["a"])} {symbol} {shown(item["b"])} ＝'
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


def columns(item):
    """Digit strings, decimal places, and right shifts (in columns) for a 筆算 cell.

    Addition/subtraction align the decimal points; multiplication aligns the right edge
    and the product takes the sum of both decimal places, as written by hand.
    """
    a, b, answer = str(item['a']), str(item['b']), item['answer']
    pa, pb = places(a), places(b)
    da, db = a.replace('.', ''), b.replace('.', '')
    if item['op'] == 'mul':
        pr, sa, sb = pa + pb, 0, 0
        product = str(int(da) * int(db)).rjust(pr + 1, '0')
        return dict(a=(da, pa, sa), b=(db, pb, sb), answer=(product, pr))
    pr = max(pa, pb)
    value = Fraction(answer) * 10 ** pr
    return dict(a=(da, pa, pr - pa), b=(db, pb, pr - pb), answer=(str(value.numerator), pr))


def vertical_plan(item):
    """Height and width (mm) of one 筆算 cell; columns are counted in PITCH units."""
    a, b, op = str(item['a']), str(item['b']), item['op']
    if op == 'div':
        return 50, len(a) * PITCH + measure(b, 18) + 22
    spec = columns(item)
    (da, _, sa), (db, _, sb), (ans, _) = spec['a'], spec['b'], spec['answer']
    cols = max(len(da) + sa, len(db) + sb, len(ans))
    height = 38
    multiplier = str(int(db))
    if op == 'mul' and len(multiplier) > 1:
        cols = max([cols] + [len(str(int(da) * int(d))) + k for k, d in enumerate(reversed(multiplier))])
        height = 40 + 9.5 * len(multiplier)
    return height, (cols + 1) * PITCH + 12


def grid(c, value, x, y, box, trace):
    for i, char in enumerate(value):
        cell(c, char, x + i * box, y, box, 0.7 if trace else None)


def digits(c, value, right, baseline, size=18, shift=0):
    """Digits centred on the column grid; column 0 (ones) ends at `right`."""
    for i, ch in enumerate(reversed(str(value))):
        centre = right - (i + shift + 0.5) * PITCH
        put(c, centre - measure(ch, size) / 2, baseline, ch, size)


def point(c, right, baseline, decimals, shift=0, size=18):
    """Decimal point on the boundary between column `decimals - 1` and `decimals`."""
    if decimals:
        x = right - (decimals + shift) * PITCH
        put(c, x - measure('.', size) / 2, baseline, '.', size)


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
    spec = columns(item)
    (da, pa, sa), (db, pb, sb), (ans, pr) = spec['a'], spec['b'], spec['answer']
    digits(c, da, right, y + 10, shift=sa)
    point(c, right, y + 10, pa, sa)
    digits(c, db, right, y + 19, shift=sb)
    point(c, right, y + 19, pb, sb)
    width = max(len(da) + sa, len(db) + sb)
    symbol = {'add': '＋', 'sub': '－', 'mul': '×'}[op]
    put(c, right - (width + 0.5) * PITCH - measure(symbol, 16) / 2, y + 19, symbol, 16)
    rule = right - (vertical_plan(item)[1] - 12) - 1
    line(c, rule, y + 22, right + 1, y + 22, 0, 0.35)
    top = y + 24.5
    multiplier = str(int(db))
    if op == 'mul' and len(multiplier) > 1:
        for k, d in enumerate(reversed(multiplier)):
            partial = int(da) * int(d)
            boxes(c, len(str(partial)), right, y + 24 + k * 9.5, k, partial if answers else None)
        second = y + 24 + len(multiplier) * 9.5 + 0.5
        line(c, rule, second, right + 1, second, 0, 0.35)
        top = second + 2
    # The learner places the decimal point; only the answer key prints it.
    boxes(c, len(ans), right, top, value=ans if answers else None)
    if answers:
        point(c, right, top + DIGIT - 1.8, pr, size=16)


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
            if doc['kind'] in KINDS:
                KINDS[doc['kind']].draw(c, doc, b, answers)
                continue
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
        footer(c, ident, page_no, len(pages))
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
              'content_validation': KINDS[doc['kind']].validation if doc['kind'] in KINDS
              else 'exact_arithmetic' if doc['kind'] == 'arithmetic'
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
    parser.add_argument('--find-pictures', metavar='TERMS',
                        help='Search the bundled pictures; comma-separated English or Japanese words')
    parser.add_argument('--picture-categories', action='store_true',
                        help='List bundled picture categories with counts and examples')
    args = parser.parse_args()
    try:
        if args.probe:
            load_font()
            glyphs('Study River とうきょう しんじゅく なまえ 漢字 あまり ＋−×÷ ñáéíóú¿¡')
            print(json.dumps({'ready': True, 'renderer_version': VERSION,
                              'pictures': kinds_language.pictures_ready()}))
            return
        if args.find_pictures is not None:
            print(json.dumps(kinds_language.find_pictures(args.find_pictures), ensure_ascii=False, indent=1))
            return
        if args.picture_categories:
            print(json.dumps(kinds_language.picture_categories(), ensure_ascii=False, indent=1))
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
