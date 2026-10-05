# Japanese reading (vertical)

`ja_reading` prints one Japanese passage in vertical columns (tategaki, columns
right to left) with 、。 in the top-right of their position, vertical brackets
「」『』（）, upright ー, a one-character indent for each paragraph (not for
paragraphs that open with a bracket), and 、。」 hanging below a full column.
Half-width letters and digits are printed full-width and upright.

```json
{
  "schema_version": "1.0",
  "kind": "ja_reading",
  "title": "読解 あさの いちば",
  "layout": {"format": "dokkai"},
  "passage": {
    "title": "あさの いちば",
    "credit": "Study River 書き下ろし",
    "paragraphs": ["日曜日の朝、ゆうたは……", "「今日はトマトが安いよ。」と……"]
  },
  "items": [
    {"id": "q1", "prompt": "市場へ出かけたのは何曜日ですか。",
     "choices": ["土曜日", "日曜日", "月曜日"], "answer": "日曜日"},
    {"id": "q2", "prompt": "なぜそう感じたのでしょう。",
     "answer": "自分から重いふくろを持ち、役に立てたから。", "answer_lines": 2,
     "note": "人の役に立てたうれしさが書けていればよい。"}
  ]
}
```

## Passage

- `paragraphs`: a list of paragraph strings (no line breaks inside). Write an
  original passage, or use a public-domain text (e.g. an author whose rights have
  expired, from 青空文庫) and name it in `credit`, e.g. 「宮沢賢治（青空文庫）」.
  Do not reproduce copyrighted textbooks, books, or articles.
- `title` and optional `credit` print small above the passage.
- Choose vocabulary and kanji to suit the reader; add readings in parentheses
  only when needed, e.g. 八百屋（やおや）. Ruby (furigana) is not supported.
- The renderer picks the largest of three text sizes that fits. One page holds
  roughly 600 characters with three short questions, about 1,000 when the passage
  has its own page. A passage that does not fit is an error: shorten it or split
  it into two worksheets.

## Formats

- `dokkai` (default): passage, then questions below it in horizontal text. With
  `layout.max_pages: 2` a long passage gets page 1 and the questions page 2.
  Items: `prompt`; either `choices` (2–4, printed アイウエ; `answer` must be one
  of them exactly) or a written answer with `answer_lines` (1–4). Optional `note`
  (key only): grading guidance or evidence from the passage. Ground every answer
  in the passage. Answer key: chosen option boxed, written model answers.
- `ondoku`: the passage with fields for reading time and up to five times read.
  No items, no key.
- `shisha`: copying practice; the passage as a model column with an empty column
  to its left, `layout.box_mm` 8–14 (default 10, 22 boxes per column, 8 pairs per
  page). Hanging marks take their own box. Long texts need more pages (`max_pages`).
  No items, no key.
