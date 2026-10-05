# Picture words and alphabet handwriting

## Bundled pictures

About 2,000 original Study River colour illustrations of everyday nouns (animals,
food, kitchen, home, body and health, clothing, places, transport, tools, school,
occupations, sports, nature, colours, and more). They contain no text, so the same
picture works for any language. They print in gray on a monochrome printer; colour
words (category `colors`) only work when the sheet is printed in colour, so say so
when you use them.

Find picture ids with the renderer; do not guess ids:

```
python scripts/render_a4.py --find-pictures "dog, cat, りんご, ambulance"
python scripts/render_a4.py --picture-categories
```

`--find-pictures` returns up to 12 matches per term with `id`, English headword
`en`, Japanese meaning `ja`, and `cat`egory. A category name returns pictures in
that category. Choose the entry whose meaning matches the word you will print;
`ja` is a meaning note (e.g. 体を洗うスポンジ), not necessarily the word to print.
If nothing fits, say so and drop or replace that word with the user's agreement.
Some pictures are small scenes (a librarian at a desk); prefer object pictures
for beginners.

## picture_words

```json
{
  "schema_version": "1.0",
  "kind": "picture_words",
  "title": "Frutas",
  "locale": "es",
  "layout": {"format": "write"},
  "items": [
    {"id": "f1", "picture": "fruits-0001", "word": "manzana", "note": "la manzana"},
    {"id": "f2", "picture": "fruits-0002", "word": "plátano", "note": "el plátano"}
  ]
}
```

- `picture`: an id from `--find-pictures`. `word`: the word in the target language
  (Latin letters with accents, or Japanese kana/kanji; not a mix in one word).
  You author the word; check spelling, article, and script for the language.
- `note` (optional): a short second line, e.g. article + noun, a translation,
  or a reading. Shown on `cards` and on the answer key.
- `layout.format`:
  - `trace` (default): picture, the word in light gray to trace on a four-line
    guide (Japanese: light boxes), then an empty line/boxes to write it again.
    12 per page in two columns. No answer key.
  - `write`: picture and an empty guide (Japanese: one empty box per character).
    `layout.hint`: `first_letter` (default) or `none`. Answer key shows the word.
    14 per page.
  - `match`: pictures on the left, the same words shuffled on the right; draw lines.
    3–9 per page. The order is deterministic; the key draws the lines.
  - `cards`: picture dictionary page, picture with the word underneath, 12 per
    page (3 × 4). Useful as a vocabulary list or to cut into cards. No key.
- `layout.columns`: 1 or 2 for trace/write. Default: two columns when every word
  fits, otherwise one (long words or short phrases such as "fire truck").
- Japanese words in trace/write are kana or kanji; a word with kanji is traced as
  printed. Use kana for beginners and give a reading in `note` when helpful.

## latin_trace

Letter, word, and sentence handwriting on four lines (ascender, dashed x-height,
baseline, descender), for English, Spanish, or any Latin-alphabet language.

```json
{
  "schema_version": "1.0",
  "kind": "latin_trace",
  "title": "English handwriting",
  "locale": "en",
  "layout": {"size": "large", "repeat": 1},
  "items": [
    {"id": "l1", "text": "Aa Bb Cc Dd Ee"},
    {"id": "l2", "text": "I like dogs.", "label": "sentence"}
  ]
}
```

- `text`: one line, up to 60 characters; it must fit the page width at the chosen
  size (otherwise split it into items). Japanese goes to `word_trace` instead.
- `layout.size`: `large` (about 11 mm between top and bottom line), `medium`
  (default), `small`. `layout.repeat`: empty practice lines after the traced line,
  0–6 (default 1).
- `label` (optional): a small heading above the line.
- No answer key. The typeface is a print-style handwriting font, not cursive, and
  it does not show stroke order or letter formation arrows.
