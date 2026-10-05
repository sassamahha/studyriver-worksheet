# Fractions, grids, and algebra

Every answer is checked exactly with rational arithmetic. A wrong answer is an
error with the expected value; fix the data rather than the check. Choose
numbers that match the user's level; the renderer does not pick problems.

## fraction

```json
{
  "schema_version": "1.0",
  "kind": "fraction",
  "title": "分数の けいさん",
  "items": [
    {"id": "f1", "a": "3/4", "op": "add", "b": "5/6", "answer": "1 7/12"},
    {"id": "f2", "a": "12/18", "op": "simplify", "answer": "2/3"}
  ]
}
```

- `a`, `b`: `"3/4"`, mixed `"2 1/3"` (space between whole and fraction part),
  whole `"2"`, or negative `"-1/3"`. `op`: add/sub/mul/div, or `simplify` (no `b`;
  `a` must be reducible).
- `answer` must equal the result and be in lowest terms. Write it as the user's
  curriculum expects: mixed (`"1 7/12"`) or improper (`"19/12"`); a whole number
  as `"1"`. The key prints it in that form.
- Printed stacked, two columns, 20 per page. Answer boxes: numerator and
  denominator, plus a whole-number box on every item when any answer on the
  sheet is mixed or whole, so the box itself does not give answers away.

## Decimals (in `arithmetic`)

Give `a`/`b` as decimal strings (`"3.25"`, up to 4 places); see
[input-format.md](input-format.md). Horizontal: all four operations, the answer
must be exact (choose divisions that terminate). Column form (`layout.format:
"vertical"`): addition and subtraction align the decimal points; multiplication
aligns the right edge with partial products. The learner places the point in the
answer; the key shows it, keeping zeros a hand calculation produces (0.25 × 0.4
→ 0.100). Column-form decimal division is not supported.

## grid (100-square calculation)

```json
{
  "schema_version": "1.0",
  "kind": "grid",
  "title": "100マス計算 たしざん",
  "items": [
    {"id": "g1", "op": "add", "top": [3, 7, 1, 9, 4, 0, 6, 2, 8, 5],
     "left": [6, 2, 9, 4, 0, 7, 3, 8, 1, 5]}
  ]
}
```

- `op`: add/sub/mul. `top`, `left`: 2–10 integers 0–99 each (shuffle them; 10 × 10
  is the classic 100-square, 5 × 5 a short warm-up). The renderer computes all
  answers. Subtraction needs every top number ≥ every left number (e.g. top 10–19,
  left 0–9).
- A 10 × 10 grid fills one page; smaller grids stack.

## math (expressions and equations)

```json
{
  "schema_version": "1.0",
  "kind": "math",
  "title": "式と方程式",
  "layout": {"work_mm": 10},
  "items": [
    {"id": "m1", "task": "evaluate", "expr": "(-3) × 4 + 15 ÷ (-5)", "answer": "-15"},
    {"id": "m2", "task": "simplify", "expr": "2(3a - 4) - (a + 1)", "answer": "5a - 9"},
    {"id": "m3", "task": "solve", "expr": "4(x - 2) = 2x + 6", "answer": "x = 7"},
    {"id": "m4", "task": "solve", "expr": "x^2 - x - 6 = 0", "answer": "x = 3, x = -2"},
    {"id": "m5", "task": "factor", "expr": "x^2 + 5x + 6", "answer": "(x + 2)(x + 3)"}
  ]
}
```

- Write `expr` and `answer` as they should read: numbers (integers or decimals),
  single-letter variables, `+ - × ÷ * /`, `^` for powers (0–9) or ², parentheses,
  implicit multiplication (`2x`, `3(x + 1)`, `(x + 1)(x - 2)`). Division is only by
  a number (`x/3`, `6x ÷ 2`); `1/x` is rejected.
- `task`:
  - `evaluate`: no variables; `answer` is a number (`"-15"`, `"3/4"`, `"0.5"`).
  - `simplify`: also for expanding; `answer` must be equivalent.
  - `factor`: `answer` must be equivalent and written as a product.
  - `solve`: one `=`, one variable; linear or quadratic with rational solutions.
    `answer`: `"x = 7"`, `"7"`, or every solution separated by commas.
- `note` (optional): a short hint or method shown on the answer key only.
- Paper shows ＋ － ＝ × ÷ and superscript powers; `/` stays `/` in algebra
  (x/3) and becomes ÷ in `evaluate`. Two columns when everything fits, else one;
  `layout.columns: 1` forces one. `layout.work_mm` (0–60) adds writing space under
  each problem for working.
- Not supported: inequalities, simultaneous equations, roots/radicals, functions,
  graphs, geometry. Use `qa` with a verified answer only if the user accepts an
  unchecked answer key, and say it is unchecked.
