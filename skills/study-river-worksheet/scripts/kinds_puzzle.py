"""Generated puzzles: mazes and sudoku. The agent picks size and seed; the renderer
builds the puzzle deterministically and checks it (solution path, unique solution)."""
from __future__ import annotations

from reportlab.lib.units import mm

from core import BODY_BOTTOM, BODY_TOP, BODY_W, HEIGHT, LEFT, Kind, choice, fail, integer, line, paginate, put_center, rect, text


class Rng:
    """mulberry32: small, portable, deterministic."""

    def __init__(self, seed):
        self.state = seed & 0xFFFFFFFF

    def random(self):
        self.state = (self.state + 0x6D2B79F5) & 0xFFFFFFFF
        t = self.state
        t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
        t ^= (t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

    def randint(self, low, high):
        return low + int(self.random() * (high - low + 1))

    def shuffle(self, values):
        values = list(values)
        for i in range(len(values) - 1, 0, -1):
            j = self.randint(0, i)
            values[i], values[j] = values[j], values[i]
        return values


# ---- maze ----------------------------------------------------------------------

STEPS = {'E': (1, 0), 'N': (0, -1), 'S': (0, 1), 'W': (-1, 0)}
OPPOSITE = {'E': 'W', 'W': 'E', 'N': 'S', 'S': 'N'}


def make_maze(cols, rows, seed):
    """Recursive backtracker; entrance above the top-left cell, exit below the bottom-right."""
    rng = Rng(seed)
    open_ = [[set() for _ in range(cols)] for _ in range(rows)]
    seen = [[False] * cols for _ in range(rows)]
    stack, seen[0][0] = [(0, 0)], True
    while stack:
        c, r = stack[-1]
        options = [(d, c + dx, r + dy) for d, (dx, dy) in STEPS.items()
                   if 0 <= c + dx < cols and 0 <= r + dy < rows and not seen[r + dy][c + dx]]
        if not options:
            stack.pop()
            continue
        d, nc, nr = options[rng.randint(0, len(options) - 1)]
        open_[r][c].add(d)
        open_[nr][nc].add(OPPOSITE[d])
        seen[nr][nc] = True
        stack.append((nc, nr))
    prev, queue = {(0, 0): None}, [(0, 0)]
    while queue:
        c, r = queue.pop(0)
        for d in sorted(open_[r][c]):
            nxt = (c + STEPS[d][0], r + STEPS[d][1])
            if nxt not in prev:
                prev[nxt] = (c, r)
                queue.append(nxt)
    path, cur = [], (cols - 1, rows - 1)
    while cur is not None:
        path.append(cur)
        cur = prev[cur]
    return open_, path[::-1]


class MazeKind(Kind):
    name = 'maze'
    item_fields = ('id', 'cols', 'rows', 'seed')
    validation = 'generated; solution path computed by the renderer'
    instructions = {'ja': 'うえの ▼から したの ▼まで、みちを たどりましょう。',
                    'en': 'Find the path from the top ▼ to the bottom ▼.',
                    'es': 'Encuentra el camino desde ▼ arriba hasta ▼ abajo.'}

    def item(self, raw, ident, doc):
        return dict(id=ident, cols=integer(raw.get('cols'), f'{ident}.cols', 4, 36),
                    rows=integer(raw.get('rows'), f'{ident}.rows', 4, 46),
                    seed=integer(raw.get('seed'), f'{ident}.seed', 0, 2 ** 31 - 1))

    def plan(self, doc):
        entries = []
        for item in doc['items']:
            size = min(BODY_W / item['cols'], (BODY_BOTTOM - BODY_TOP - 14) / item['rows'], 14)
            if size < 4.5:
                fail(f'{item["id"]}: maze too dense to draw clearly; use fewer columns/rows')
            entries.append((item['rows'] * size + 14, dict(id=item['id'], item=item, size=size)))
        return paginate(doc, entries)

    def draw(self, c, doc, block, answers):
        item, size = block['item'], block['size']
        cols, rows = item['cols'], item['rows']
        open_, path = make_maze(cols, rows, item['seed'])
        x0 = LEFT + (BODY_W - cols * size) / 2
        y0 = block['y'] + 7
        put_center(c, x0 + size / 2, y0 - 1.5, '▼', 11)
        put_center(c, x0 + (cols - 0.5) * size, y0 + rows * size + 5.5, '▼', 11)
        weight = 0.5 if size >= 7 else 0.4
        for r in range(rows):
            for col in range(cols):
                x, y = x0 + col * size, y0 + r * size
                if 'N' not in open_[r][col] and not (r == 0 and col == 0):
                    line(c, x, y, x + size, y, 0, weight)
                if 'W' not in open_[r][col]:
                    line(c, x, y, x, y + size, 0, weight)
                if r == rows - 1 and not col == cols - 1:
                    line(c, x, y + size, x + size, y + size, 0, weight)
                if col == cols - 1:
                    line(c, x + size, y, x + size, y + size, 0, weight)
        if answers:
            c.setStrokeGray(0.55)
            c.setLineWidth(size * 0.28 * mm)
            c.setLineCap(1)
            c.setLineJoin(1)
            points = [(x0 + size / 2, y0 - 2)] + [(x0 + (pc + 0.5) * size, y0 + (pr + 0.5) * size)
                                                  for pc, pr in path] + [(x0 + (cols - 0.5) * size, y0 + rows * size + 1)]
            p = c.beginPath()
            p.moveTo(points[0][0] * mm, (HEIGHT - points[0][1]) * mm)
            for px, py in points[1:]:
                p.lineTo(px * mm, (HEIGHT - py) * mm)
            c.drawPath(p, stroke=1, fill=0)
            c.setLineCap(0)
            c.setLineJoin(0)


# ---- sudoku ----------------------------------------------------------------------

BOX = {4: (2, 2), 6: (2, 3), 9: (3, 3)}          # box rows × box columns
CLUES = {4: {'easy': 8, 'medium': 6, 'hard': 5}, 6: {'easy': 18, 'medium': 14, 'hard': 12},
         9: {'easy': 38, 'medium': 32, 'hard': 27}}
SUDOKU_CELL = {4: 15, 6: 12.5, 9: 9.5}


def peers(size):
    br, bc = BOX[size]
    out = []
    for i in range(size * size):
        r, c = divmod(i, size)
        group = {r * size + k for k in range(size)} | {k * size + c for k in range(size)}
        r0, c0 = r // br * br, c // bc * bc
        group |= {(r0 + a) * size + c0 + b for a in range(br) for b in range(bc)}
        group.discard(i)
        out.append(sorted(group))
    return out


def count_solutions(grid, size, limit=2, rng=None, found=None):
    """Backtracking with the most-constrained cell first. Fills `found` with the first solution."""
    grid = list(grid)
    near = peers(size)
    count = 0

    def search():
        nonlocal count
        best, options = None, None
        for i, v in enumerate(grid):
            if v == 0:
                used = {grid[j] for j in near[i]}
                cand = [d for d in range(1, size + 1) if d not in used]
                if not cand:
                    return
                if options is None or len(cand) < len(options):
                    best, options = i, cand
                    if len(cand) == 1:
                        break
        if best is None:
            count += 1
            if found is not None and not found:
                found.extend(grid)
            return
        for d in (rng.shuffle(options) if rng else options):
            grid[best] = d
            search()
            if count >= limit:
                return
        grid[best] = 0

    search()
    return count


def make_sudoku(size, seed, clues):
    rng = Rng(seed)
    solution = []
    count_solutions([0] * size * size, size, 1, rng, solution)
    puzzle = list(solution)
    for i in rng.shuffle(range(size * size)):
        if sum(1 for v in puzzle if v) <= clues:
            break
        keep, puzzle[i] = puzzle[i], 0
        if count_solutions(puzzle, size) != 1:
            puzzle[i] = keep
    return puzzle, solution


class SudokuKind(Kind):
    name = 'sudoku'
    item_fields = ('id', 'size', 'seed', 'level', 'puzzle')
    validation = 'unique solution verified by the renderer'
    instructions = {'ja': 'たて・よこ・ふとい わくの なかに、おなじ すうじが はいらないように うめましょう。',
                    'en': 'Fill the grid so no number repeats in any row, column, or bold box.',
                    'es': 'Completa la cuadrícula sin repetir números en filas, columnas ni recuadros.'}

    def item(self, raw, ident, doc):
        size = choice(raw.get('size'), f'{ident}.size', (4, 6, 9))
        obj = dict(id=ident, size=size)
        if 'puzzle' in raw:
            if 'seed' in raw or 'level' in raw:
                fail(f'{ident}: give either puzzle or seed/level, not both')
            source = text(raw['puzzle'], f'{ident}.puzzle', 100).replace(' ', '')
            if len(source) != size * size or any(ch not in '.0123456789'[:size + 2] for ch in source):
                fail(f'{ident}.puzzle: expected {size * size} characters of 1-{size}, with . or 0 for blanks')
            puzzle = [0 if ch in '.0' else int(ch) for ch in source]
            near = peers(size)
            if any(v and v in (puzzle[j] for j in near[i]) for i, v in enumerate(puzzle)):
                fail(f'{ident}: the givens repeat a number in a row, column, or box')
            solution = []
            count = count_solutions(puzzle, size, 2, None, solution)
            if count != 1:
                fail(f'{ident}: the puzzle has {"no" if count == 0 else "more than one"} solution')
            obj.update(puzzle=puzzle, solution=solution)
        else:
            seed = integer(raw.get('seed'), f'{ident}.seed', 0, 2 ** 31 - 1)
            level = choice(raw.get('level', 'medium'), f'{ident}.level', ('easy', 'medium', 'hard'))
            puzzle, solution = make_sudoku(size, seed, CLUES[size][level])
            obj.update(seed=seed, level=level, puzzle=puzzle, solution=solution)
        return obj

    def plan(self, doc):
        items, entries = doc['items'], []
        for n in range(0, len(items), 2):
            row = [dict(item, number=n + k + 1) for k, item in enumerate(items[n:n + 2])]
            height = max(SUDOKU_CELL[i['size']] * i['size'] for i in row) + 12
            entries.append((height, dict(id=row[0]['id'], row=row)))
        return paginate(doc, entries)

    def draw(self, c, doc, block, answers):
        for k, item in enumerate(block['row']):
            size, cell_mm = item['size'], SUDOKU_CELL[item['size']]
            br, bc = BOX[size]
            width = size * cell_mm
            x0 = LEFT + k * BODY_W / 2 + (BODY_W / 2 - width) / 2
            y0 = block['y'] + 7
            put_center(c, x0 - 5, y0 + 3, f'{item["number"]}.', 9, 0.3)
            for i in range(size * size):
                r, col = divmod(i, size)
                x, y = x0 + col * cell_mm, y0 + r * cell_mm
                rect(c, x, y, cell_mm, cell_mm, 0.6, 0.2)
                value, gray = item['puzzle'][i], 0
                if not value and answers:
                    value, gray = item['solution'][i], 0.45
                if value:
                    put_center(c, x + cell_mm / 2, y + cell_mm * 0.68, str(value), cell_mm * 1.75, gray)
            for r in range(0, size + 1, br):
                line(c, x0, y0 + r * cell_mm, x0 + width, y0 + r * cell_mm, 0, 0.55)
            for col in range(0, size + 1, bc):
                line(c, x0 + col * cell_mm, y0, x0 + col * cell_mm, y0 + width, 0, 0.55)


KINDS = (MazeKind(), SudokuKind())
