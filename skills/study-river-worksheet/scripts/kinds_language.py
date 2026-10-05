"""Language practice: picture words (bundled monochrome pictures), Latin-alphabet
handwriting on four-line guides, and vertical (tategaki) Japanese reading."""
from __future__ import annotations

import hashlib
import io
import json
import re
import unicodedata
import zipfile
from functools import lru_cache

from reportlab.lib.units import mm

from core import (ASSETS, BODY_BOTTOM, BODY_TOP, BODY_W, HEIGHT, LABELS, LEFT, LIGHT, RIGHT, Kind,
                  cell, check_pages, choice, dashed, fail, glyph_in_box, glyphs, integer, is_kana,
                  is_kanji, keys, line, measure, paginate, put, put_center, rect, text, wrap)

PICTURE_ZIP = ASSETS / 'pictures/pictures.zip'
PICTURE_CATALOG = ASSETS / 'pictures/catalog.json'


# ---- bundled pictures ---------------------------------------------------------

@lru_cache(maxsize=1)
def catalog():
    if not PICTURE_CATALOG.exists():
        fail('Bundled pictures are missing from this installation')
    return {p['id']: p for p in json.loads(PICTURE_CATALOG.read_text(encoding='utf-8'))['pictures']}


def pictures_ready():
    try:
        import PIL  # noqa: F401  (ReportLab embeds PNG pictures through Pillow)
    except ImportError:
        return False
    return PICTURE_ZIP.exists() and PICTURE_CATALOG.exists()


@lru_cache(maxsize=None)
def picture_bytes(ident):
    with zipfile.ZipFile(PICTURE_ZIP) as archive:
        return archive.read(ident + '.png')


def draw_picture(c, ident, x, y, size):
    try:
        from reportlab.lib.utils import ImageReader
        reader = ImageReader(io.BytesIO(picture_bytes(ident)))
    except ImportError:
        fail('Pictures need Pillow in the host Python; no PDF was generated.')
    c.drawImage(reader, x * mm, (HEIGHT - y - size) * mm, size * mm, size * mm,
                preserveAspectRatio=True, anchor='c')


def find_pictures(terms):
    """Best matches per comma-separated term, searching English words, Japanese senses,
    categories, and ids. The agent picks ids; the printed word is authored separately."""
    entries = list(catalog().values())
    out = {}
    for term in [t.strip() for t in re.split(r'[,、，\n]', terms) if t.strip()]:
        low = unicodedata.normalize('NFKC', term).lower()
        ranked = []
        for p in entries:
            en, ja = p['en'].lower(), p['ja']
            if low in (en, ja, p['id']):
                rank = 0
            elif low == p['cat']:
                rank = 1
            elif en.startswith(low) or ja.startswith(low) or re.search(rf'\b{re.escape(low)}\b', en):
                rank = 2
            elif low in en or low in ja:
                rank = 3
            else:
                continue
            ranked.append((rank, len(en), p['id']))
        ranked.sort()
        out[term] = [dict(id=i, en=catalog()[i]['en'], ja=catalog()[i]['ja'], cat=catalog()[i]['cat'])
                     for _, _, i in ranked[:12]]
    return out


def picture_categories():
    cats = {}
    for p in catalog().values():
        entry = cats.setdefault(p['cat'], {'count': 0, 'examples': []})
        entry['count'] += 1
        if len(entry['examples']) < 6:
            entry['examples'].append(p['en'])
    return {'pictures': len(catalog()), 'categories': cats}


# ---- four-line handwriting guide (Latin letters) ------------------------------

# Klee One: x-height 0.48 em, ascender/cap 0.71 em, descender 0.18 em (from the font's glyphs).
X_HEIGHT, ASCENT, DESCENT = 0.48, 0.72, 0.21
SIZES = {'large': 34, 'medium': 26, 'small': 20}


def guide_height(size):
    return (ASCENT + DESCENT) * size * 0.3528  # points → mm


def guide(c, x1, x2, top, size):
    """Four lines: ascender (light), x-height (dashed), baseline (dark), descender (light)."""
    em = size * 0.3528
    base = top + ASCENT * em
    line(c, x1, top, x2, top, 0.6, 0.2)
    dashed(c, x1, base - X_HEIGHT * em, x2, base - X_HEIGHT * em, 0.6, 0.2)
    line(c, x1, base, x2, base, 0.25, 0.3)
    line(c, x1, base + DESCENT * em, x2, base + DESCENT * em, 0.6, 0.2)
    return base


def script_of(word, where):
    if all(is_kana(ch) or is_kanji(ch) for ch in word):
        return 'ja'
    if any(is_kana(ch) or is_kanji(ch) for ch in word):
        fail(f'{where}: mix of Japanese and Latin letters in one word is unsupported')
    return 'latin'


# ---- picture words ------------------------------------------------------------

PIC_INSTRUCTIONS = {
    'trace': {'ja': 'えを みて、うすい じを なぞってから かきましょう。',
              'en': 'Look at the picture, trace the word, then write it.',
              'es': 'Mira el dibujo, repasa la palabra y luego escríbela.'},
    'write': {'ja': 'えを みて、ことばを かきましょう。', 'en': 'Look at the picture and write the word.',
              'es': 'Mira el dibujo y escribe la palabra.'},
    'match': {'ja': 'えと ことばを せんで むすびましょう。', 'en': 'Draw a line from each picture to its word.',
              'es': 'Une cada dibujo con su palabra.'},
    'cards': {'ja': 'えと ことばを みて おぼえましょう。', 'en': 'Look at each picture and say the word.',
              'es': 'Mira cada dibujo y di la palabra.'},
}


class PictureWords(Kind):
    name = 'picture_words'
    item_fields = ('id', 'picture', 'word', 'note')
    layout_fields = ('max_pages', 'format', 'hint', 'columns')
    instructions = {loc: (lambda doc, loc=loc: PIC_INSTRUCTIONS[doc['layout']['format']][loc])
                    for loc in ('ja', 'en', 'es')}

    def layout(self, raw, doc):
        form = choice(raw.get('format', 'trace'), 'layout.format', ('trace', 'write', 'match', 'cards'))
        hint = choice(raw.get('hint', 'first_letter' if form == 'write' else 'none'), 'layout.hint',
                      ('none', 'first_letter'))
        if hint != 'none' and form != 'write':
            fail('layout.hint applies only to format "write"')
        columns = raw.get('columns')
        if columns is not None:
            choice(columns, 'layout.columns', (1, 2))
        return dict(format=form, hint=hint, columns=columns)

    def wants_key(self, doc):
        return doc['layout']['format'] in ('write', 'match')

    def allows_key(self, doc):
        return self.wants_key(doc)

    def item(self, raw, ident, doc):
        picture = text(raw.get('picture'), f'{ident}.picture', 40)
        if picture not in catalog():
            fail(f'{ident}: unknown picture "{picture}". Search with --find-pictures and use an id it returns.')
        word = text(raw.get('word'), f'{ident}.word', 40)
        obj = dict(id=ident, picture=picture, word=word, script=script_of(word, f'{ident}.word'))
        if 'note' in raw:
            obj['note'] = text(raw['note'], f'{ident}.note', 40)
        return obj

    def plan(self, doc):
        layout, items = doc['layout'], doc['items']
        form = layout['format']
        for item in items:
            glyphs(item['word'] + item.get('note', ''))
        if form == 'cards':
            for item in items:
                if measure(item['word'], 15) > 58 or (item.get('note') and measure(item['note'], 9) > 58):
                    fail(f'{item["id"]}: word too wide for a picture card')
            rows = [items[i:i + 3] for i in range(0, len(items), 3)]
            return paginate(doc, [(58, dict(id=r[0]['id'], row=r, start=3 * n)) for n, r in enumerate(rows)])
        if form == 'match':
            if len(items) < 3:
                fail('match needs at least 3 pictures')
            per_page = 9
            pages = []
            for start in range(0, len(items), per_page):
                group = items[start:start + per_page]
                if len(group) < 3:
                    fail('the last match page would have fewer than 3 pictures; change the count')
                for item in group:
                    if measure(item['word'], 15) > 70:
                        fail(f'{item["id"]}: word too wide for the matching column')
                pages.append([dict(id=group[0]['id'], items=group, order=match_order(group), y=BODY_TOP)])
            return check_pages(doc, pages)
        columns = layout['columns'] or (2 if all(self.fits(i, BODY_W / 2) for i in items) else 1)
        layout['columns'] = columns
        width = BODY_W / columns
        for item in items:
            if not self.fits(item, width):
                fail(f'{item["id"]}: "{item["word"]}" is too long for the writing area; '
                     'shorten it or split it into separate items')
        height = 34 if form == 'trace' else 30
        rows = [items[i:i + columns] for i in range(0, len(items), columns)]
        return paginate(doc, [(height, dict(id=r[0]['id'], row=r, start=columns * n))
                              for n, r in enumerate(rows)])

    @staticmethod
    def fits(item, width):
        room = width - 26 - 9
        if item['script'] == 'ja':
            return len(item['word']) * 11 <= room
        return measure(item['word'], SIZES['medium']) + 4 <= room

    def draw(self, c, doc, block, answers):
        form = doc['layout']['format']
        if form == 'match':
            return draw_match(c, block, answers)
        if form == 'cards':
            for k, item in enumerate(block['row']):
                x, y = LEFT + k * BODY_W / 3, block['y']
                rect(c, x + 2, y + 1, BODY_W / 3 - 4, 55, 0.7, 0.2)
                draw_picture(c, item['picture'], x + (BODY_W / 3 - 38) / 2, y + 3, 38)
                put_center(c, x + BODY_W / 6, y + 48, item['word'], 15)
                if item.get('note'):
                    put_center(c, x + BODY_W / 6, y + 53.5, item['note'], 9, 0.3)
            return
        width = BODY_W / doc['layout']['columns']
        for k, item in enumerate(block['row']):
            x, y = LEFT + k * width, block['y']
            put(c, x, y + 5, f'{block["start"] + k + 1}.', 9, 0.3)
            rect(c, x + 6, y + 2, 26, 26, 0.75, 0.2)
            draw_picture(c, item['picture'], x + 7, y + 3, 24)
            wx, right = x + 36, x + width - 3
            word = item['word']
            if item['script'] == 'ja':
                box = 11
                for i, ch in enumerate(word):
                    if form == 'trace':
                        cell(c, ch, wx + i * box, y + 3, box, LIGHT)
                        cell(c, ch, wx + i * box, y + 3 + box + 2, box)
                    else:
                        show = answers or (doc['layout']['hint'] == 'first_letter' and i == 0)
                        cell(c, ch, wx + i * box, y + 8, box, 0 if show else None)
                if item.get('note') and answers:
                    put(c, wx, y + 27, item['note'], 8.5, 0.3)
                continue
            size = SIZES['medium']
            if form == 'trace':
                base = guide(c, wx, right, y + 3, size)
                put(c, wx + 1, base, word, size, LIGHT)
                guide(c, wx, right, y + 3 + guide_height(size) + 4.5, size)
            else:
                base = guide(c, wx, right, y + 8, size)
                if answers:
                    put(c, wx + 1, base, word, size, 0)
                elif doc['layout']['hint'] == 'first_letter':
                    put(c, wx + 1, base, word[0], size, 0)
            if item.get('note') and answers:
                put(c, wx, y + 28.5, item['note'], 8.5, 0.3)


def match_order(group):
    """Deterministic shuffle of the word column (never the same order as the pictures)."""
    keyed = sorted(range(len(group)),
                   key=lambda i: hashlib.sha256((group[i]['id'] + group[i]['word']).encode()).hexdigest())
    if keyed == list(range(len(group))):
        keyed = keyed[1:] + keyed[:1]
    return keyed


def draw_match(c, block, answers):
    items, order = block['items'], block['order']
    row_h = (BODY_BOTTOM - BODY_TOP) / 9
    pic = min(22, row_h - 3)
    left_dot, right_dot = LEFT + 42, RIGHT - 78
    for i, item in enumerate(items):
        y = BODY_TOP + i * row_h
        put(c, LEFT, y + pic / 2 + 1.5, f'{i + 1}.', 9, 0.3)
        draw_picture(c, item['picture'], LEFT + 10, y + 1, pic)
        c.setFillGray(0)
        c.circle(left_dot * mm, (HEIGHT - y - 1 - pic / 2) * mm, 1.1 * mm, stroke=0, fill=1)
    for slot, index in enumerate(order):
        y = BODY_TOP + slot * row_h + 1 + pic / 2
        c.setFillGray(0)
        c.circle(right_dot * mm, (HEIGHT - y) * mm, 1.1 * mm, stroke=0, fill=1)
        put(c, right_dot + 5, y + 2, items[index]['word'], 15)
        if answers:
            line(c, left_dot, BODY_TOP + index * row_h + 1 + pic / 2, right_dot, y, 0.45, 0.35)


# ---- Latin-alphabet handwriting ------------------------------------------------

class LatinTrace(Kind):
    name = 'latin_trace'
    item_fields = ('id', 'text', 'label')
    layout_fields = ('max_pages', 'size', 'repeat')
    answer_key_default = False
    instructions = {'ja': 'うすい もじを なぞってから、したの せんに かきましょう。',
                    'en': 'Trace the light letters, then write them on the lines below.',
                    'es': 'Repasa las letras claras y luego escríbelas en las líneas de abajo.'}

    def allows_key(self, doc):
        return False

    def layout(self, raw, doc):
        return dict(size=choice(raw.get('size', 'medium'), 'layout.size', tuple(SIZES)),
                    repeat=integer(raw.get('repeat', 1), 'layout.repeat', 0, 6))

    def item(self, raw, ident, doc):
        value = text(raw.get('text'), f'{ident}.text', 60)
        if script_of(value, f'{ident}.text') != 'latin':
            fail(f'{ident}: latin_trace is for alphabet letters; use word_trace for Japanese')
        obj = dict(id=ident, text=value)
        if 'label' in raw:
            obj['label'] = text(raw['label'], f'{ident}.label', 60)
        return obj

    def plan(self, doc):
        size, repeat = SIZES[doc['layout']['size']], doc['layout']['repeat']
        row = guide_height(size) + 3.5
        entries = []
        for n, item in enumerate(doc['items'], 1):
            if measure(item['text'], size) > BODY_W - 10:
                fail(f'{item["id"]}: text too wide for one line at size {doc["layout"]["size"]}; '
                     'split it or choose a smaller size')
            label = 5 if item.get('label') else 0
            entries.append((label + row * (1 + repeat) + 3, dict(id=item['id'], item=item, number=n)))
        return paginate(doc, entries)

    def draw(self, c, doc, block, answers):
        size, repeat = SIZES[doc['layout']['size']], doc['layout']['repeat']
        item, y = block['item'], block['y']
        put(c, LEFT, y + 4, f'{block["number"]}.', 9, 0.3)
        if item.get('label'):
            put(c, LEFT + 8, y + 4, item['label'], 9, 0.3)
            y += 5
        row = guide_height(size) + 3.5
        base = guide(c, LEFT + 6, RIGHT, y + 2, size)
        put(c, LEFT + 8, base, item['text'], size, LIGHT)
        for r in range(1, repeat + 1):
            guide(c, LEFT + 6, RIGHT, y + 2 + r * row, size)


# ---- vertical Japanese reading -------------------------------------------------

# Character advance and column advance (mm), largest first; a passage uses the largest that fits.
PITCHES = ((7.0, 10.4), (6.0, 8.9), (5.0, 7.6))
HANG = set('、。」』）')         # never at the top of a column: hang at the previous column's end
NO_INDENT = set('「『（')
FULLWIDTH = {chr(c): chr(c + 0xFEE0) for c in range(0x21, 0x7F)}
FULLWIDTH[' '] = '　'


def vertical_text(value):
    return ''.join(FULLWIDTH.get(ch, ch) for ch in value)


def to_columns(paragraphs, per_col, indent=True):
    cols = []
    for para in paragraphs:
        cur = '　' if indent and para[0] not in NO_INDENT else ''
        for ch in para:
            if len(cur) >= per_col:
                if ch in HANG and len(cur) < per_col + 2:
                    cur += ch
                    continue
                cols.append(cur)
                cur = ''
            cur += ch
        if cur:
            cols.append(cur)
    return cols


def fit_passage(paragraphs, height):
    """Largest text size whose columns fit `height` mm and the page width."""
    for pitch, column in PITCHES:
        per_col = int(height // pitch) - 2  # spare positions for hanging marks such as 。」
        cols = to_columns(paragraphs, per_col)
        if per_col >= 14 and len(cols) * column <= BODY_W + 0.5:
            return dict(cols=cols, pitch=pitch, column=column, height=(per_col + 2) * pitch)
    return None


def too_long(paragraphs, height):
    pitch, column = PITCHES[-1]
    per_col = int(height // pitch) - 2
    need = len(to_columns(paragraphs, per_col))
    return (f'Passage needs {need} columns of {per_col} characters; a page holds '
            f'{int((BODY_W + 0.5) // column)}. Shorten the passage or split it into two worksheets.')


def draw_column(c, column, cx, top, pitch, gray=0, scale=0.84):
    for j, ch in enumerate(column):
        if ch != '　':
            glyph_in_box(c, ch, cx - pitch / 2, top + j * pitch, pitch, gray, vertical=True, scale=scale)


READ_INSTRUCTIONS = {
    'dokkai': {'ja': 'ぶんしょうを よんで、もんだいに こたえましょう。',
               'en': 'Read the passage and answer the questions.',
               'es': 'Lee el texto y responde las preguntas.'},
    'ondoku': {'ja': 'こえに だして よみましょう。', 'en': 'Read the passage aloud.',
               'es': 'Lee el texto en voz alta.'},
    'shisha': {'ja': 'てほんを みて、となりの ますに かきうつしましょう。',
               'en': 'Copy the model into the empty boxes beside it.',
               'es': 'Copia el modelo en las casillas vacías de al lado.'},
}
MARKS = 'アイウエ'


class JaReading(Kind):
    name = 'ja_reading'
    item_fields = ('id', 'prompt', 'choices', 'answer', 'answer_lines', 'note')
    layout_fields = ('max_pages', 'format', 'box_mm')
    extra_fields = ('passage',)
    min_items = 0
    instructions = {loc: (lambda doc, loc=loc: READ_INSTRUCTIONS[doc['layout']['format']][loc])
                    for loc in ('ja', 'en', 'es')}

    def layout(self, raw, doc):
        form = choice(raw.get('format', 'dokkai'), 'layout.format', ('dokkai', 'ondoku', 'shisha'))
        box = raw.get('box_mm', 10)
        if type(box) not in (int, float) or not 8 <= box <= 14:
            fail('layout.box_mm must be 8..14 (copying boxes)')
        return dict(format=form, box_mm=box)

    def wants_key(self, doc):
        return doc['layout']['format'] == 'dokkai'

    def allows_key(self, doc):
        return self.wants_key(doc)

    def document(self, raw, doc):
        passage = raw.get('passage')
        keys(passage, ('title', 'credit', 'paragraphs'), 'passage')
        paragraphs = passage.get('paragraphs')
        if not isinstance(paragraphs, list) or not 1 <= len(paragraphs) <= 40:
            fail('passage.paragraphs must be a list of 1..40 paragraph strings')
        doc['passage'] = dict(
            title=text(passage.get('title'), 'passage.title', 40),
            paragraphs=[vertical_text(text(p, f'passage.paragraphs[{i}]', 1200)) for i, p in enumerate(paragraphs)])
        if 'credit' in passage:
            doc['passage']['credit'] = text(passage['credit'], 'passage.credit', 80)
        glyphs(''.join(doc['passage']['paragraphs']))
        if doc['layout']['format'] != 'dokkai' and raw.get('items'):
            fail(f'{doc["layout"]["format"]} has no questions; remove items')
        if doc['layout']['format'] == 'dokkai' and not raw.get('items'):
            fail('dokkai needs question items')

    def item(self, raw, ident, doc):
        obj = dict(id=ident, prompt=text(raw.get('prompt'), f'{ident}.prompt', 200),
                   answer=text(raw.get('answer'), f'{ident}.answer', 200))
        if 'choices' in raw:
            choices = raw['choices']
            if not isinstance(choices, list) or not 2 <= len(choices) <= 4:
                fail(f'{ident}.choices: expected 2..4 choices')
            obj['choices'] = [text(ch, f'{ident}.choices', 40) for ch in choices]
            if obj['answer'] not in obj['choices']:
                fail(f'{ident}: answer must be exactly one of the choices')
            if 'answer_lines' in raw:
                fail(f'{ident}: answer_lines is for written answers, not choices')
        else:
            obj['answer_lines'] = integer(raw.get('answer_lines', 1), f'{ident}.answer_lines', 1, 4)
        if 'note' in raw:
            obj['note'] = text(raw['note'], f'{ident}.note', 200)
        return obj

    def plan(self, doc):
        form, passage = doc['layout']['format'], doc['passage']
        head = 8
        if form == 'shisha':
            return self.plan_shisha(doc)
        if form == 'ondoku':
            fit = fit_passage(passage['paragraphs'], BODY_BOTTOM - BODY_TOP - head - 14)
            if not fit:
                fail(too_long(passage['paragraphs'], BODY_BOTTOM - BODY_TOP - head - 14))
            return check_pages(doc, [[dict(id='passage', part='passage', y=BODY_TOP, record=True, **fit)]])
        questions, q_height = self.questions(doc)
        room = BODY_BOTTOM - BODY_TOP - head - q_height - 4
        fit = fit_passage(passage['paragraphs'], room) if room >= 14 * PITCHES[-1][0] else None
        if fit:
            return check_pages(doc, [[dict(id='passage', part='passage', y=BODY_TOP, **fit),
                                      dict(id='questions', part='questions', questions=questions,
                                           y=BODY_TOP + head + fit['height'] + 4)]])
        fit = fit_passage(passage['paragraphs'], BODY_BOTTOM - BODY_TOP - head)
        if not fit:
            fail(too_long(passage['paragraphs'], BODY_BOTTOM - BODY_TOP - head))
        if q_height > BODY_BOTTOM - BODY_TOP:
            fail('Questions do not fit on one page; reduce questions or answer lines')
        return check_pages(doc, [[dict(id='passage', part='passage', y=BODY_TOP, **fit)],
                                 [dict(id='questions', part='questions', questions=questions, y=BODY_TOP)]])

    def questions(self, doc):
        out, total = [], 0
        for n, item in enumerate(doc['items'], 1):
            prompt = wrap(item['prompt'], 11, BODY_W - 10)
            answer = wrap(item['answer'], 10.5, BODY_W - 12) if 'choices' not in item else []
            notes = wrap(item['note'], 8.5, BODY_W - 12) if item.get('note') else []
            if 'choices' in item:
                options = [f'{MARKS[i]} {ch}' for i, ch in enumerate(item['choices'])]
                choice_rows = pack(options, 10.5, BODY_W - 12)
                height = len(prompt) * 5.5 + len(choice_rows) * 6 + len(notes) * 4.5 + 4
            else:
                choice_rows = []
                height = len(prompt) * 5.5 + max(item['answer_lines'] * 9, len(answer) * 5.5 + len(notes) * 4.5) + 4
            out.append(dict(number=n, item=item, prompt=prompt, answer=answer, notes=notes,
                            rows=choice_rows, height=height))
            total += height
        return out, total

    def plan_shisha(self, doc):
        box = doc['layout']['box_mm']
        per_col = int((BODY_BOTTOM - BODY_TOP - 8) // box)
        pair = 2 * box + 3
        per_page = int((BODY_W + 3) // pair)
        cols = to_columns(doc['passage']['paragraphs'], per_col, indent=True)
        if any(len(col) > per_col for col in cols):  # a hung mark needs its own box when copying
            cols = to_columns(doc['passage']['paragraphs'], per_col - 2, indent=True)
        pages = [[dict(id='copy', part='copy', cols=cols[i:i + per_page], y=BODY_TOP, box=box, per_col=per_col)]
                 for i in range(0, len(cols), per_page)]
        return check_pages(doc, pages)

    def draw(self, c, doc, block, answers):
        passage, y = doc['passage'], block['y']
        if block['part'] in ('passage', 'copy'):
            credit = passage['title'] + (f'　{passage["credit"]}' if passage.get('credit') else '')
            put(c, RIGHT - measure(credit, 9), y + 4, credit, 9, 0.3)
        if block['part'] == 'copy':
            box, per_col = block['box'], block['per_col']
            pair = 2 * box + 3
            right = LEFT + (BODY_W + len(block['cols']) * pair - 3) / 2
            for i, col in enumerate(block['cols']):
                model_x = right - i * pair - box
                for j in range(per_col):
                    rect(c, model_x, y + 8 + j * box, box, box, 0.6, 0.2)
                    rect(c, model_x - box, y + 8 + j * box, box, box, 0.6, 0.2)
                for j, ch in enumerate(col):
                    if ch != '　':
                        glyph_in_box(c, ch, model_x, y + 8 + j * box, box, 0, vertical=True, scale=0.72)
            return
        if block['part'] == 'passage':
            for i, col in enumerate(block['cols']):
                draw_column(c, col, RIGHT - i * block['column'] - block['column'] / 2, y + 8, block['pitch'])
            if block.get('record'):
                labels = LABELS[doc['locale']]
                ry = BODY_BOTTOM - 4
                put(c, LEFT, ry, labels['time'], 10, 0.3)
                x = LEFT + measure(labels['time'], 10) + 3
                for unit in ('minutes', 'seconds'):
                    line(c, x, ry + 1, x + 12, ry + 1, 0, 0.3)
                    put(c, x + 13, ry, labels[unit], 10)
                    x += 14 + measure(labels[unit], 10) + 3
                x += 8
                put(c, x, ry, labels['times'], 10, 0.3)
                x += measure(labels['times'], 10) + 3
                for k in range(5):
                    rect(c, x + k * 7, ry - 4, 5, 5, 0.5)
            return
        qy = y
        for q in block['questions']:
            item = q['item']
            put(c, LEFT, qy + 4.5, f'{q["number"]})', 9, 0.3)
            for n, s in enumerate(q['prompt']):
                put(c, LEFT + 8, qy + 4.5 + n * 5.5, s, 11)
            after = qy + len(q['prompt']) * 5.5
            if 'choices' in item:
                for r, row in enumerate(q['rows']):
                    x = LEFT + 10
                    for option, index in row:
                        put(c, x, after + 4.5 + r * 6, option, 10.5)
                        width = measure(option, 10.5)
                        if answers and item['choices'][index] == item['answer']:
                            rect(c, x - 1.2, after + 0.4 + r * 6, width + 2.4, 5.6, 0.2, 0.4)
                        x += width + 7
                after += len(q['rows']) * 6
            elif answers:
                for n, s in enumerate(q['answer']):
                    put(c, LEFT + 10, after + 4.5 + n * 5.5, s, 10.5)
                after += len(q['answer']) * 5.5
            else:
                for n in range(item['answer_lines']):
                    line(c, LEFT + 10, after + 7 + n * 9, RIGHT, after + 7 + n * 9)
            if answers:
                for n, s in enumerate(q['notes']):
                    put(c, LEFT + 10, after + 4 + n * 4.5, s, 8.5, 0.3)
            qy += q['height']


def pack(options, size, width):
    """Lay out choice labels on as few rows as possible: [[(text, index), ...], ...]."""
    rows, row, used = [], [], 0
    for index, option in enumerate(options):
        w = measure(option, size) + 7
        if w > width:
            fail(f'Choice too wide: {option}')
        if row and used + w > width:
            rows.append(row)
            row, used = [], 0
        row.append((option, index))
        used += w
    rows.append(row)
    return rows


KINDS = (PictureWords(), LatinTrace(), JaReading())
