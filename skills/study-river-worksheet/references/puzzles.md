# Mazes and sudoku

The renderer generates these from a seed and checks them. Pick any integer
seed (vary it for new puzzles); the same seed, size, and renderer version give
the same puzzle again.

## maze

```json
{
  "schema_version": "1.0",
  "kind": "maze",
  "title": "めいろ",
  "items": [{"id": "m1", "cols": 14, "rows": 18, "seed": 20261005}]
}
```

- `cols` 4–36, `rows` 4–46. Every cell is reachable and there is exactly one path
  (a perfect maze); entrance above the top-left cell, exit below the bottom-right,
  both marked ▼. Cells get as large as the page allows (up to 14 mm), so small
  mazes are easy to draw in and several small mazes stack on one page.
- Rough difficulty: 6 × 8 gentle, 12 × 16 medium, 20 × 26 and up demanding.
  Very dense mazes (cells under 4.5 mm) are rejected.
- Answer key: the solution path in gray.

## sudoku

```json
{
  "schema_version": "1.0",
  "kind": "sudoku",
  "title": "数独",
  "items": [
    {"id": "s1", "size": 6, "seed": 2, "level": "easy"},
    {"id": "s2", "size": 9, "puzzle": "53..7....6..195....98....6.8...6...34..8.3..17...2...6.6....28....419..5....8..79"}
  ]
}
```

- `size`: 4 (2 × 2 boxes), 6 (2 × 3 boxes), or 9 (3 × 3 boxes).
- Generated: `seed` and `level` (`easy`, `medium` default, `hard`; for 9 × 9 that
  is 38/32/27 givens). Or supplied: `puzzle` as `size × size` characters row by
  row, digits for givens and `.` or `0` for blanks. Supplied puzzles are rejected
  unless they have exactly one solution.
- Two per row, four 9 × 9 per page. Levels count givens; they do not rate solving
  techniques. Answer key: givens in black, the rest in gray.
