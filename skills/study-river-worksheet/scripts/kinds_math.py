"""Mathematics beyond integer arithmetic: stacked fractions, 100-square grids, and
algebraic expressions. Every answer is checked exactly (Fraction arithmetic)."""
from __future__ import annotations

import math
import re
from fractions import Fraction

from core import (BODY_W, LEFT, RIGHT, Kind, choice, fail, integer, keys, line, measure, paginate,
                  put, put_center, rect, text)

SYMBOL = {'add': '＋', 'sub': '－', 'mul': '×', 'div': '÷'}


# ---- fractions ----------------------------------------------------------------

FRACTION = re.compile(r'(-)?(?:(\d{1,4}) )?(\d{1,4})(?:/(\d{1,4}))?')


def parse_fraction(value, where):
    """'3/4', '1 2/3' (mixed), '-5/6', or '2' → (Fraction, (sign, whole, num, den))."""
    if type(value) is int:
        value = str(value)
    if not isinstance(value, str):
        fail(f'{where}: expected a fraction string such as "3/4" or "1 2/3"')
    match = FRACTION.fullmatch(value.strip())
    if not match:
        fail(f'{where}: expected a fraction string such as "3/4", "1 2/3", or "2"')
    sign, whole, num, den = match.groups()
    if whole and not den:
        fail(f'{where}: a mixed number needs a fraction part, e.g. "1 2/3"')
    num, den = int(num), int(den or 1)
    if den == 0:
        fail(f'{where}: zero denominator')
    if whole and num >= den:
        fail(f'{where}: the fraction part of a mixed number must be proper')
    value = (int(whole or 0) + Fraction(num, den)) * (-1 if sign else 1)
    return value, ('-' if sign else '', int(whole) if whole else None, num, den if match.group(4) else None)


class FractionKind(Kind):
    name = 'fraction'
    item_fields = ('id', 'a', 'op', 'b', 'answer')
    validation = 'exact_fraction_arithmetic'
    instructions = {'ja': 'けいさんを しましょう。こたえは できるだけ かんたんな 分数に しましょう。',
                    'en': 'Solve each problem. Write answers in simplest form.',
                    'es': 'Resuelve cada operación. Escribe el resultado simplificado.'}

    def item(self, raw, ident, doc):
        op = choice(raw.get('op'), f'{ident}.op', ('add', 'sub', 'mul', 'div', 'simplify'))
        a, a_parts = parse_fraction(raw.get('a'), f'{ident}.a')
        obj = dict(id=ident, op=op, a=raw['a'], a_parts=a_parts)
        if op == 'simplify':
            if 'b' in raw:
                fail(f'{ident}: simplify takes only a')
            if a_parts[3] is None or math.gcd(a_parts[2], a_parts[3]) == 1:
                fail(f'{ident}: choose a fraction that can be simplified')
            expected = a
        else:
            b, b_parts = parse_fraction(raw.get('b'), f'{ident}.b')
            if op == 'div' and b == 0:
                fail(f'{ident}: division by zero')
            obj.update(b=raw['b'], b_parts=b_parts)
            expected = {'add': a + b, 'sub': a - b, 'mul': a * b, 'div': a / b if b else 0}[op]
        answer, parts = parse_fraction(text(str(raw.get('answer', '')), f'{ident}.answer', 20),
                                       f'{ident}.answer')
        if answer != expected:
            fail(f'{ident}: incorrect answer; expected {mixed_text(expected)} (or {expected})')
        if parts[3] and math.gcd(parts[2], parts[3]) != 1:
            fail(f'{ident}: answer is not in lowest terms; expected {mixed_text(expected)} or {expected}')
        if parts[3] == 1:
            fail(f'{ident}: write a whole-number answer without a denominator')
        obj.update(answer=raw['answer'], answer_parts=parts)
        return obj

    def plan(self, doc):
        items = doc['items']
        whole_box = any(i['answer_parts'][1] is not None or i['answer_parts'][3] is None for i in items)
        entries = []
        for n in range(0, len(items), 2):
            row = items[n:n + 2]
            for k, item in enumerate(row):
                width = frac_width(item['a_parts']) + (frac_width(item['b_parts']) + 9 if 'b_parts' in item else 0)
                if width + 48 > BODY_W / 2:
                    fail(f'{item["id"]}: fractions too wide for the two-column layout')
            entries.append((22, dict(id=row[0]['id'], row=[dict(item, number=n + k + 1)
                                                           for k, item in enumerate(row)], whole_box=whole_box)))
        return paginate(doc, entries)

    def draw(self, c, doc, block, answers):
        for k, item in enumerate(block['row']):
            x, mid = LEFT + k * BODY_W / 2, block['y'] + 12
            put(c, x, mid - 3, f'{item["number"]}.', 10)
            x += 9
            x += draw_fraction(c, x, mid, item['a_parts']) + 2.5
            if 'b_parts' in item:
                put_center(c, x + 2.5, mid + 2, SYMBOL[item['op']], 14)
                x += 7
                x += draw_fraction(c, x, mid, item['b_parts']) + 2.5
            put_center(c, x + 2.5, mid + 2, '＝', 14)
            x += 7.5
            sign, whole, num, den = item['answer_parts']
            if answers and sign:  # the learner writes a sign in front; the key shows it there
                put(c, x - 5.5, mid + 1.8, '－', 14)
            if block['whole_box']:
                rect(c, x, mid - 4.5, 9, 9)
                if answers and (whole is not None or den is None):
                    put_center(c, x + 4.5, mid + 2.2, str(whole if den else num), 14)
                x += 11
            rect(c, x, mid - 9, 10, 7.5)
            line(c, x - 1, mid, x + 11, mid, 0, 0.35)
            rect(c, x, mid + 1.5, 10, 7.5)
            if answers and den:
                put_center(c, x + 5, mid - 3, str(num), 13)
                put_center(c, x + 5, mid + 7, str(den), 13)


def frac_width(parts):
    sign, whole, num, den = parts
    w = measure(sign and '－', 14) if sign else 0
    if whole is not None:
        w += measure(str(whole), 15) + 1
    return w + (max(measure(str(num), 13), measure(str(den), 13)) + 2 if den else measure(str(num), 15))


def draw_fraction(c, x, mid, parts):
    """Stacked fraction (with optional sign and whole part); returns the width used."""
    sign, whole, num, den = parts
    start = x
    if sign:
        put(c, x, mid + 2, '－', 14)
        x += measure('－', 14)
    if whole is not None:
        put(c, x, mid + 2.3, str(whole), 15)
        x += measure(str(whole), 15) + 1
    if den is None:
        put(c, x, mid + 2.3, str(num), 15)
        return x + measure(str(num), 15) - start
    w = max(measure(str(num), 13), measure(str(den), 13)) + 2
    put_center(c, x + w / 2, mid - 1.6, str(num), 13)
    line(c, x, mid, x + w, mid, 0, 0.35)
    put_center(c, x + w / 2, mid + 5.4, str(den), 13)
    return x + w - start


def mixed_text(value):
    if value.denominator == 1:
        return str(value.numerator)
    whole, rest = divmod(abs(value.numerator), value.denominator)
    sign = '-' if value < 0 else ''
    return f'{sign}{whole} {rest}/{value.denominator}' if whole else f'{sign}{rest}/{value.denominator}'


# ---- 100-square grid ------------------------------------------------------------

GRID_CELL = 15.4  # 11 columns × 15.4 = 169.4mm, wide enough to write in


class GridKind(Kind):
    name = 'grid'
    item_fields = ('id', 'op', 'top', 'left')
    validation = 'exact_arithmetic; answers computed by the renderer'
    instructions = {'ja': 'うえの かずと ひだりの かずで けいさんして、ますに かきましょう。',
                    'en': 'Combine the top number and the left number; write each result in its square.',
                    'es': 'Combina el número de arriba con el de la izquierda y escribe el resultado.'}

    def item(self, raw, ident, doc):
        op = choice(raw.get('op'), f'{ident}.op', ('add', 'sub', 'mul'))
        lists = {}
        for name in ('top', 'left'):
            values = raw.get(name)
            if not isinstance(values, list) or not 2 <= len(values) <= 10:
                fail(f'{ident}.{name}: expected 2..10 integers')
            lists[name] = [integer(v, f'{ident}.{name}', 0, 99) for v in values]
        if op == 'sub' and min(lists['top']) < max(lists['left']):
            fail(f'{ident}: subtraction needs every top number >= every left number (no negatives)')
        return dict(id=ident, op=op, **lists)

    def plan(self, doc):
        return paginate(doc, [((len(i['left']) + 1) * GRID_CELL + 6, dict(id=i['id'], item=i))
                              for i in doc['items']])

    def draw(self, c, doc, block, answers):
        g = block['item']
        cols, rows = len(g['top']), len(g['left'])
        x0 = LEFT + (BODY_W - (cols + 1) * GRID_CELL) / 2
        y0 = block['y'] + 2
        for r in range(rows + 1):
            for col in range(cols + 1):
                x, y = x0 + col * GRID_CELL, y0 + r * GRID_CELL
                header = r == 0 or col == 0
                rect(c, x, y, GRID_CELL, GRID_CELL, 0 if header else 0.55, 0.45 if header else 0.25)
                base = y + GRID_CELL / 2 + 2.4
                if r == 0 and col == 0:
                    put_center(c, x + GRID_CELL / 2, base, SYMBOL[g['op']], 15)
                elif r == 0:
                    put_center(c, x + GRID_CELL / 2, base, str(g['top'][col - 1]), 14)
                elif col == 0:
                    put_center(c, x + GRID_CELL / 2, base, str(g['left'][r - 1]), 14)
                elif answers:
                    t, left = g['top'][col - 1], g['left'][r - 1]
                    value = {'add': t + left, 'sub': t - left, 'mul': t * left}[g['op']]
                    put_center(c, x + GRID_CELL / 2, base - 0.4, str(value), 12)


# ---- algebraic expressions --------------------------------------------------------

NORMALIZE = str.maketrans({'×': '*', '·': '*', '÷': '/', '−': '-', '－': '-', '–': '-', '＋': '+',
                           '＝': '=', '（': '(', '）': ')', '［': '(', '］': ')', '[': '(', ']': ')',
                           '　': ' ', **{chr(0xFF10 + i): str(i) for i in range(10)}})
SUPERSCRIPT = '⁰¹²³⁴⁵⁶⁷⁸⁹'
TOKEN = re.compile(r'\s*(?:(\d+(?:\.\d+)?)|([a-z])|(\^)|([-+*/()=]))')


class Poly(dict):
    """Polynomial: {((var, power), ...): Fraction coefficient} with zero terms dropped."""

    @staticmethod
    def const(value):
        return Poly({(): Fraction(value)}) if value else Poly()

    def __add__(self, other):
        out = Poly(self)
        for mono, coef in other.items():
            out[mono] = out.get(mono, 0) + coef
            if out[mono] == 0:
                del out[mono]
        return out

    def __neg__(self):
        return Poly({m: -c for m, c in self.items()})

    def __sub__(self, other):
        return self + (-other)

    def __mul__(self, other):
        out = Poly()
        for m1, c1 in self.items():
            for m2, c2 in other.items():
                powers = dict(m1)
                for var, p in m2:
                    powers[var] = powers.get(var, 0) + p
                out = out + Poly({tuple(sorted(powers.items())): c1 * c2})
        return out

    def variables(self):
        return sorted({v for mono in self for v, _ in mono})

    def degree(self):
        return max((sum(p for _, p in mono) for mono in self), default=0)

    def constant(self):
        if any(self.keys() - {()}):
            return None
        return self.get((), Fraction(0))


class Parser:
    def __init__(self, source, where):
        self.where = where
        self.src = source.translate(NORMALIZE)
        for i, sup in enumerate(SUPERSCRIPT):
            self.src = self.src.replace(sup, f'^{i}')
        self.tokens, pos = [], 0
        while pos < len(self.src.rstrip()):
            m = TOKEN.match(self.src, pos)
            if not m:
                fail(f'{where}: cannot read "{self.src[pos:pos + 8]}". Use numbers, single-letter '
                     'variables, + − × ÷ ^ ( ) and =')
            self.tokens.append(next(g for g in m.groups() if g))
            pos = m.end()
        self.i = 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def take(self, expected=None):
        tok = self.peek()
        if tok is None or (expected and tok != expected):
            fail(f'{self.where}: incomplete expression')
        self.i += 1
        return tok

    def done(self):
        if self.peek() is not None:
            fail(f'{self.where}: unexpected "{self.peek()}"')

    def expr(self):
        value = self.term()
        while self.peek() in ('+', '-'):
            value = value + self.term() if self.take() == '+' else value - self.term()
        return value

    def term(self):
        value = self.unary()
        while True:
            tok = self.peek()
            if tok in ('*', '/'):
                self.take()
                rhs = self.unary()
                if tok == '/':
                    divisor = rhs.constant()
                    if not divisor:
                        fail(f'{self.where}: division is supported only by a nonzero number')
                    rhs = Poly.const(1 / divisor)
                value = value * rhs
            elif tok is not None and (tok == '(' or tok[0].isalpha()):
                value = value * self.power()  # implicit: 2x, 3(x+1)
            else:
                return value

    def is_product(self):
        """True when the top level is one term built from brackets or powers: (x+1)(x-2), 3(x+2), (x+1)^2."""
        depth, prev = 0, None
        for tok in self.tokens:
            if tok == '(':
                depth += 1
            elif tok == ')':
                depth -= 1
            elif tok in '+-' and depth == 0 and prev not in (None, '(', '*', '/', '^'):
                return False
            prev = tok
        return '(' in self.tokens or '^' in self.tokens

    def unary(self):
        if self.peek() in ('+', '-'):
            return -self.unary() if self.take() == '-' else self.unary()
        return self.power()

    def power(self):
        base = self.atom()
        if self.peek() == '^':
            self.take()
            exponent = self.unary().constant()
            if exponent is None or exponent.denominator != 1 or not 0 <= exponent <= 9:
                fail(f'{self.where}: exponents must be whole numbers 0..9')
            result = Poly.const(1)
            for _ in range(int(exponent)):
                result = result * base
            return result
        return base

    def atom(self):
        tok = self.take()
        if tok == '(':
            value = self.expr()
            self.take(')')
            return value
        if tok[0].isdigit():
            return Poly.const(Fraction(tok))
        if tok[0].isalpha():
            return Poly({((tok, 1),): Fraction(1)})
        fail(f'{self.where}: unexpected "{tok}"')


def parse_expr(source, where):
    parser = Parser(source, where)
    if '=' in parser.tokens:
        fail(f'{where}: "=" is only for equations (task "solve")')
    value = parser.expr()
    parser.done()
    return value, parser


def parse_number(source, where):
    value = parse_expr(source, where)[0].constant()
    if value is None:
        fail(f'{where}: expected a number')
    return value


def rational_sqrt(value):
    if value < 0:
        return None
    n, d = math.isqrt(value.numerator), math.isqrt(value.denominator)
    return Fraction(n, d) if n * n == value.numerator and d * d == value.denominator else None


def solve(source, where):
    parser = Parser(source, where)
    if parser.tokens.count('=') != 1:
        fail(f'{where}: an equation needs exactly one "="')
    left = parser.expr()
    parser.take('=')
    right = parser.expr()
    parser.done()
    poly = left - right
    names = poly.variables()
    if len(names) != 1:
        fail(f'{where}: an equation must use exactly one variable')
    var = names[0]
    coef = {sum(p for _, p in mono): c for mono, c in poly.items()}
    degree = poly.degree()
    if degree == 1:
        return var, [-coef.get(0, 0) / coef[1]]
    if degree == 2:
        a, b, k = coef[2], coef.get(1, 0), coef.get(0, 0)
        root = rational_sqrt(b * b - 4 * a * k)
        if root is None:
            fail(f'{where}: the solutions are not rational numbers; choose another equation')
        return var, sorted({(-b - root) / (2 * a), (-b + root) / (2 * a)})
    fail(f'{where}: only linear and quadratic equations are supported')


def number_text(value):
    if value.denominator == 1:
        return str(value.numerator).replace('-', '－')
    return f'{value.numerator}/{value.denominator}'.replace('-', '－')


def display(source, divide='÷'):
    """Paper form of the author's expression: full-width ＋ － ＝, × and ÷ (or / in
    algebra, where x/3 reads as a fraction), and superscript powers."""
    shown = source.translate(str.maketrans({'*': '×', '/': divide, '-': '－', '−': '－', '+': '＋', '=': '＝'}))
    return re.sub(r'\^(\d)', lambda m: SUPERSCRIPT[int(m.group(1))], shown)


class MathKind(Kind):
    name = 'math'
    item_fields = ('id', 'task', 'expr', 'answer', 'note')
    layout_fields = ('max_pages', 'work_mm', 'columns')
    validation = 'exact_algebra (equivalence of polynomials / exact solutions)'
    instructions = {'ja': 'つぎの もんだいを ときましょう。', 'en': 'Solve each problem.',
                    'es': 'Resuelve cada problema.'}

    def layout(self, raw, doc):
        work = raw.get('work_mm', 0)
        if type(work) not in (int, float) or not 0 <= work <= 60:
            fail('layout.work_mm must be a number 0..60 (writing space under each problem)')
        return dict(work_mm=work, columns=choice(raw.get('columns', 2), 'layout.columns', (1, 2)))

    def item(self, raw, ident, doc):
        task = choice(raw.get('task'), f'{ident}.task', ('evaluate', 'simplify', 'factor', 'solve'))
        expr = text(raw.get('expr'), f'{ident}.expr', 80)
        answer = text(raw.get('answer'), f'{ident}.answer', 80)
        obj = dict(id=ident, task=task, expr=expr, answer=answer)
        if 'note' in raw:
            obj['note'] = text(raw['note'], f'{ident}.note', 200)
        if task == 'solve':
            var, roots = solve(expr, f'{ident}.expr')
            given = answer.translate(NORMALIZE).replace(' ', '')
            given = re.sub(rf'(?:^|(?<=,)|(?<=or)){var}=', '', given).replace('or', ',')
            values = sorted({parse_number(part, f'{ident}.answer') for part in given.split(',') if part})
            if values != roots:
                fail(f'{ident}: incorrect answer; expected {var} = '
                     + ', '.join(number_text(r) for r in roots))
            obj['var'] = var
            obj['answer_shown'] = ', '.join(f'{var} = {number_text(r)}' for r in roots)
            return obj
        value, _ = parse_expr(expr, f'{ident}.expr')
        if task == 'evaluate':
            if value.constant() is None:
                fail(f'{ident}: evaluate needs an expression without variables')
            if parse_number(answer, f'{ident}.answer') != value.constant():
                fail(f'{ident}: incorrect answer; expected {number_text(value.constant())}')
        else:
            given, parser = parse_expr(answer, f'{ident}.answer')
            if given != value:
                fail(f'{ident}: the answer is not equivalent to the expression')
            if task == 'factor' and not parser.is_product():
                fail(f'{ident}: a factored answer must be a product, e.g. (x + 2)(x − 3)')
        obj['answer_shown'] = display(answer, '÷' if task == 'evaluate' else '/')
        return obj

    def plan(self, doc):
        layout = doc['layout']
        cols = layout['columns']
        width = BODY_W / cols
        items = doc['items']
        for item in items:
            prompt = self.prompt(item)
            item['prompt'] = prompt
            need = measure(prompt, 13) + max(measure(item['answer_shown'], 13), 22) + 14
            if need > width:
                if cols == 2:
                    layout['columns'] = 1
                    return self.plan(doc)
                fail(f'{item["id"]}: expression too wide for the page')
        height = 13 + layout['work_mm'] + (5 if any('note' in i for i in items) else 0)
        entries = []
        for n in range(0, len(items), layout['columns']):
            row = [dict(item, number=n + k + 1) for k, item in enumerate(items[n:n + layout['columns']])]
            entries.append((height, dict(id=row[0]['id'], row=row)))
        return paginate(doc, entries)

    @staticmethod
    def prompt(item):
        shown = display(item['expr'], '÷' if item['task'] == 'evaluate' else '/')
        if item['task'] == 'solve':
            return shown
        return shown + ' ＝'

    def draw(self, c, doc, block, answers):
        width = BODY_W / doc['layout']['columns']
        for k, item in enumerate(block['row']):
            x, y = LEFT + k * width, block['y'] + 8
            put(c, x, y, f'{item["number"]}.', 10)
            put(c, x + 9, y, item['prompt'], 13)
            ax = x + 9 + measure(item['prompt'], 13) + 3
            if item['task'] == 'solve':
                ax += 5
                put(c, ax, y, f'{item["var"]} ＝' if not answers else '', 13)
                if not answers:
                    ax += measure(f'{item["var"]} ＝', 13) + 2
            if answers:
                put(c, ax, y, item['answer_shown'], 13)
                if item.get('note'):
                    put(c, x + 9, y + 5.5, item['note'], 8.5, 0.3)
            else:
                line(c, ax, y + 1.5, min(ax + 30, x + width - 3), y + 1.5, 0, 0.3)


KINDS = (FractionKind(), GridKind(), MathKind())
