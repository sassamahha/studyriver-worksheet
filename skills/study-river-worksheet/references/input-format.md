# Worksheet JSON v1

The renderer accepts one format per document. UTF-8 JSON; no Markdown or HTML
markup. All text fields are single-line strings (the renderer wraps paragraphs).
Unknown fields are rejected to avoid silently ignoring user constraints.

Common fields:

- `schema_version`: `"1.0"`
- `kind`: `word_trace`, `kanji_trace`, `qa`, `arithmetic` (this file), or
  `picture_words`, `latin_trace` ([pictures.md](pictures.md)), `ja_reading`
  ([japanese-reading.md](japanese-reading.md)), `fraction`, `grid`, `math`
  ([math.md](math.md)), `maze`, `sudoku` ([puzzles.md](puzzles.md))
- `title`, optional `instructions`: paper text
- `locale`: `ja` (default), `en`, or `es`; controls fixed labels and default
  instructions, not subject matter
- `answer_key`: boolean; default true when something is hidden (questions,
  arithmetic, write/match, puzzles), false when the model is on the worksheet
  (tracing, cards, reading aloud, copying), where a key is rejected
- `layout.max_pages`: maximum problem pages, default 1; the answer key uses the
  same number of pages separately. Never raise it against the user's page limit.
- `items`: 1–200 entries, each with a unique string `id` (`ja_reading` ondoku and
  shisha have no items)
- `sources`: optional list of `{title, url, checked_on}`; https URLs, retained in
  the content JSON, not fetched by the renderer or printed automatically

## Kana words

```json
{
  "schema_version": "1.0",
  "kind": "word_trace",
  "title": "どうぶつの なまえ",
  "instructions": "なぞってから、したの ますに かきましょう。",
  "locale": "ja",
  "layout": {"max_pages": 1, "box_mm": 16},
  "items": [
    {"id": "animal-1", "label": "きりん", "text": "きりん"},
    {"id": "animal-2", "label": "しまうま", "text": "しまうま"}
  ]
}
```

`text` is the word to trace: hiragana, katakana, ー, and kanji (e.g. `山手線`);
`label` is an optional display name or reading shown above the column.

`layout.direction`: `"vertical"` (default, 縦書き) or `"horizontal"`. Vertical:
each word is a light tracing column with an empty column to its left, words run
right to left. ー is drawn upright and small kana sit top-right, as in tategaki.
At 16mm: 5 words per page, up to 14 characters per word; the heading must fit
two box widths. Horizontal: the default 16mm boxes fit up to 11 characters per word and 5 words
per page. Box size is configurable from 12 to 22mm; larger boxes reduce capacity.
No automatic shrink or truncation. Use a larger-page allowance only when wanted.

## Single-character practice (kanji_trace)

```json
{
  "schema_version": "1.0",
  "kind": "kanji_trace",
  "title": "かんじの れんしゅう",
  "layout": {"max_pages": 1, "box_mm": 20},
  "items": [
    {"id": "k1", "char": "山", "reading": "やま・サン"},
    {"id": "k2", "char": "川", "reading": "かわ・セン"}
  ]
}
```

`char`: exactly one kanji (or kana) character. `reading`: optional text above
the column; it must fit the box width at small size (about 7 characters at 20mm).
Default `direction: "vertical"`: one column per character, columns right to
left; black model, three light tracing boxes, then empty boxes to the bottom
(20mm: 9 characters per page, 11 boxes per column). `direction: "horizontal"`
gives one row per character (8 per page). `box_mm` 16–22, default 20. No answer
key. Stroke order is not printed.

## Questions and answers

```json
{
  "schema_version": "1.0",
  "kind": "qa",
  "title": "English A1 - everyday sentences",
  "instructions": "Fill in the missing word.",
  "locale": "en",
  "items": [
    {"id": "q1", "prompt": "I ___ a student. (am / is / are)",
     "answer": "am", "answer_lines": 1}
  ]
}
```

`answer` is required even when `answer_key` is false. `answer_lines` is 1–4
(default 1). Optional `note` appears only on the answer page: use it for a
permitted alternative answer or a concise evidence/explanation. The renderer
does not check the semantic correctness of text. Different-length questions and
answers share measured row heights so answer numbering stays aligned.

## Arithmetic

```json
{
  "schema_version": "1.0",
  "kind": "arithmetic",
  "title": "たしざん",
  "items": [
    {"id": "m1", "a": 7, "b": 8, "op": "add", "answer": "15"}
  ]
}
```

`a`/`b`: integers -9999..9999, or decimal strings such as `"3.25"` (up to 4
places). `op`: add/sub/mul/div. `answer`: an integer or fraction string (e.g.
`"3/2"`); with decimals, an exact decimal string (`"0.06"`), and a division must
terminate. Zero divisor and wrong answers fail. The renderer
checks the result exactly and derives the printed expression from operands; do
not add a competing prompt. This is not the existing generator's full set of
carry/borrow/remainder/grade constraints. Choose numbers matching the user.

### Column form (筆算)

Set `"layout": {"format": "vertical"}`. Two problems per row, digits aligned on
a column grid with an empty box per answer digit.

```json
{"id": "d1", "a": 745, "b": 6, "op": "div", "answer": "124", "remainder": 1}
```

- Non-negative numbers only; subtraction needs `a >= b`. Decimals work for
  add/sub/mul (points aligned for add/sub; see [math.md](math.md)); division is
  integers only.
- `answer` is an integer string. For `div` it is the quotient, and `remainder`
  (integer, default 0) must be the exact remainder; both are checked.
  `remainder` is rejected outside vertical division.
- Multiplication with a 2+ digit `b` prints one partial-product row per digit
  of `b` (filled on the answer key), then the total.
- If any division on the sheet has a remainder, every division shows an
  あまり/R field, so its presence does not reveal individual answers.
- Capacity: 12 add/sub/one-digit-multiply or 8 division problems per page;
  2-digit multipliers take more height. Too-wide numbers fail with a message.

## Output

`worksheet.pdf`, optional `answer-key.pdf`, normalized `worksheet.json`, and
`report.json` with actual page counts, item count, content ID, PDF hashes,
renderer version, font hash, and what was validated (`content_validation`). Output is refused if the directory is nonempty.
For a saved JSON, this renderer/font version uses deterministic PDF metadata;
it does not claim byte compatibility with Study River MCP.
