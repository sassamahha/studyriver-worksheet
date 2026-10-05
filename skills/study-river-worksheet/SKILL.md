---
name: study-river-worksheet
description: "Printable A4 worksheets from any theme, with answer keys: picture vocabulary (2,000+ bundled pictures, any language), kana/kanji tracing (vertical), alphabet handwriting, Japanese vertical reading comprehension, questions, arithmetic incl. long division and decimals, fractions, 100-square grids, algebra/equations, mazes, sudoku. 絵カード・単語、なぞり、縦書き読解、計算・分数・方程式、迷路、数独をA4プリントに。Hojas A4: vocabulario con dibujos, caligrafía, fracciones, ecuaciones, laberintos, sudoku."
---

# Study River worksheets

Turn the user's chosen content into a downloadable A4 worksheet. You author the
content; the bundled renderer measures the page, checks characters, checks every
mathematical answer exactly, and creates the PDF. No Study River API or MCP is used.

## Select content and format

- Set `locale` to the user's language: `ja`, `en`, or `es` (fixed paper labels
  and default instructions). It does not limit the subject: an English speaker
  practising kana gets `en` labels with Japanese tracing content.
- Preserve the user's topic, language, number of items, and page constraints.
  Infer routine defaults and proceed. Ask only when a missing choice changes the
  task or explicit constraints cannot coexist.
- Content is open-ended; do not restrict requests to an existing drill bank.
  For example, choose appropriate Yamanote station names and readings, then pass
  those strings to the renderer. The renderer does not know station names.
- For proper names or changing facts, verify uncertain details with available
  authoritative sources and retain those sources in the data. Do not invent
  readings or claim a lookup happened when it did not. If essential verification
  is unavailable, ask for the source list or describe the uncertainty.
- When neither a count nor complete coverage is requested, a one-page selection
  is acceptable: announce it briefly, e.g. "山手線の駅名から5駅で作ります。"
  A request for all stations must keep all stations, even if that needs a page
  tradeoff. A selection must never be labelled as the complete list.
- Age/grade may guide initial difficulty and amount; they do not restrict who can
  learn. Never print a grade, school year, age, or target learner on the paper,
  even when the user states one: not in `title`, `instructions`, or items
  (write 「英語 基礎問題」, not 「中学1年 英語」). Mention the level only in chat.
  The renderer rejects such titles/instructions.
- Paper is black and light gray only (home printers). Pictures are bundled in
  monochrome; colour names cannot be taught with pictures.

Read [input-format.md](references/input-format.md) for the common fields, then the
reference for the chosen kind. One kind per worksheet:

| Kind | Use | Reference |
|---|---|---|
| `word_trace` | Kana/kanji words, top to bottom: light tracing column + empty column | [kana.md](references/kana.md) |
| `kanji_trace` | One character per column: model, three traces, practice boxes | [kanji.md](references/kanji.md) |
| `picture_words` | Bundled pictures with words in any language: `trace`, `write`, `match`, `cards` | [pictures.md](references/pictures.md) |
| `latin_trace` | Alphabet letters, words, sentences on four-line handwriting guides | [pictures.md](references/pictures.md) |
| `ja_reading` | Japanese passage in vertical columns: `dokkai` (questions), `ondoku` (reading aloud), `shisha` (copying) | [japanese-reading.md](references/japanese-reading.md) |
| `qa` | Any text questions with a separate answer key | [text-questions.md](references/text-questions.md) |
| `arithmetic` | Integers and decimals, horizontal or column form (筆算) incl. long division | [input-format.md](references/input-format.md) |
| `fraction` | Stacked fractions and mixed numbers: + − × ÷, simplifying | [math.md](references/math.md) |
| `grid` | 100-square (or smaller) calculation grids; renderer computes answers | [math.md](references/math.md) |
| `math` | Signed numbers, expressions, simplify/expand, factor, linear/quadratic equations | [math.md](references/math.md) |
| `maze` | Generated maze from a seed; key shows the path | [puzzles.md](references/puzzles.md) |
| `sudoku` | 4×4, 6×6, 9×9: generated from a seed or supplied; unique solution checked | [puzzles.md](references/puzzles.md) |

Not supported: colour, geometry diagrams (areas/angles), graphs, stroke-order
diagrams, spatial logic puzzles other than mazes and sudoku. Say so and offer a
supported kind; never silently replace the requested exercise. Describe these as
limits of this skill, not of Study River as a whole.

## Generate and deliver

1. Find this skill's installed directory. Paths below are relative to it; use the
   host's Python/file tools, not a user machine path copied from this document.
2. Run `python scripts/render_a4.py --probe`. It needs Python 3.10+ and ReportLab
   4+ (Pillow too for pictures; the probe reports `"pictures": true`), plus the
   bundled assets. Do not ask light users to install Node/MCP. Do not silently
   download dependencies. If execution is unavailable, say PDF generation is
   unavailable in this environment; a text draft is not a completed PDF.
3. Author the complete problem/answer JSON in a writable temporary directory.
   Review facts, readings, level, and linguistic answers. The renderer validates
   mathematics exactly and structure otherwise, not the truth of arbitrary text.
   Never interpolate content into executable code or shell arguments: write JSON
   using a file tool.
4. Run `python scripts/render_a4.py INPUT.json --check`. Correct data/layout
   problems, preserving explicit user choices. If the requested count cannot fit,
   ask whether count or page count may change. Set `layout.max_pages` only to the
   agreed limit; it is not permission to silently add pages. Stop after two failed
   correction attempts and explain the unresolved issue.
5. Run `python scripts/render_a4.py INPUT.json --output-dir NEW_DIRECTORY`.
   Use a new writable directory per attempt; previous results are preserved.
6. Inspect `report.json` and the actual PDF. If a PDF preview tool is available,
   check the first page and any layout boundary page. State any inspection limit
   honestly. Check question count, page count, legibility, and matching answers.
7. Attach/link the generated `worksheet.pdf` using the host's real downloadable
   artifact mechanism, plus `answer-key.pdf` when generated. Mention problem and
   answer page counts separately. Tracing, cards, reading aloud, and copying have
   the model on the worksheet and no separate key. Do not hand the user a local
   host path as though it were a downloadable link.

Keep `worksheet.json` and `report.json` for reproduction within the current task;
offer them when requested. Reprint from the saved content/PDF, not a promise that
LLM generation with the same prompt will reproduce it (mazes and sudoku do repeat
for the same seed in this renderer version). Do not import this data into the
existing learning record or persist learner profiles automatically.
