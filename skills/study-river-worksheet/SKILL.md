---
name: study-river-worksheet
description: "Printable A4 worksheets from any theme: Japanese kana/kanji tracing (vertical, like Japanese notebooks), custom questions with answer keys, and math incl. long division. 好きな言葉でひらがな・漢字のなぞり、問題と解答、筆算をA4プリントに。Hojas A4 imprimibles: trazado de kana/kanji, preguntas con respuestas y matemáticas."
---

# Study River worksheets

Turn the user's chosen content into a downloadable A4 worksheet. You author the
content; the bundled renderer measures the page, checks supported characters,
checks arithmetic answers, and creates the PDF. No Study River API or MCP is used.

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

Read [input-format.md](references/input-format.md) for the actual supported
fields and examples. Choose one format per worksheet:

| Format | Use |
|---|---|
| `word_trace` | Arbitrary kana or kanji words, written top to bottom by default: a light tracing column with an empty column to its left. Read [kana.md](references/kana.md). |
| `kanji_trace` | One character per column (top to bottom, columns right to left): black model, three light tracing boxes, empty practice boxes; optional reading. Read [kanji.md](references/kanji.md). |
| `qa` | Text questions, language practice, supplied short content; separate answer key. Read [text-questions.md](references/text-questions.md). |
| `arithmetic` | Integer addition/subtraction/multiplication/division, horizontal (default) or `layout.format: "vertical"` column form (筆算) with digit boxes, partial products, long division and remainders; exact answer check. |

Tracing is vertical (tategaki) by default, as Japanese handwriting practice is;
use `layout.direction: "horizontal"` only when asked. This prototype does not
render vertical reading passages, pictures, stacked fractions,
decimals in column form, mazes, or spatial logic puzzles. Do not advertise
those as implemented. Offer a relevant supported format or the existing Study
River Web/MCP route without silently replacing the requested exercise.
Describe these as limitations of this plugin prototype, not of Study River as a
whole. The existing Web/MCP generators support additional formats, including mazes.

## Generate and deliver

1. Find this skill's installed directory. Paths below are relative to it; use the
   host's Python/file tools, not a user machine path copied from this document.
2. Run `python scripts/render_a4.py --probe`. It needs Python 3.10+ and ReportLab
   4+ in the host, plus the bundled font. A plugin install does not grant those
   capabilities. Do not ask light users to install Node/MCP. Do not silently
   download dependencies. If execution is unavailable, say PDF generation is
   unavailable in this environment; a text draft is not a completed PDF.
3. Author the complete problem/answer JSON in a writable temporary directory.
   Review facts, readings, level, and linguistic answers. The renderer validates
   structure, not the truth of arbitrary text. Never interpolate content into
   executable code or shell arguments: write JSON using a file tool.
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
   answer page counts separately. For tracing, the model is on the worksheet and
   no separate answer key is needed. Do not hand the user a local host path as
   though it were a downloadable link.

Keep `worksheet.json` and `report.json` for reproduction within the current task;
offer them when requested. Reprint from the saved content/PDF, not a promise that
LLM generation with the same prompt or seed will reproduce it. Do not import this
data into the existing learning record or persist learner profiles automatically.
