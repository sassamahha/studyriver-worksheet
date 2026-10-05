# Text questions

For A1 English, prefer short, ordinary present-tense sentences and familiar
vocabulary. A level label is an instructional target, not a certification.
Give cloze questions enough context or choices to distinguish the intended
answer. For composition, write a model answer and use `note` for reasonable
alternatives rather than treating one phrasing as the sole correct answer.

For text comprehension, provide the passage in the prompt or make questions
self-contained. Ground the answer in that passage. `qa` prints horizontal
paragraphs; for a Japanese passage in vertical columns use `ja_reading`
([japanese-reading.md](japanese-reading.md)). For vocabulary with pictures use
`picture_words` ([pictures.md](pictures.md)).

For mathematics, use `arithmetic`, `fraction`, `grid`, or `math` so the result is
checked ([math.md](math.md)). Do not pass a wrong numeric answer through `qa` to
bypass a validation failure. Word problems may use `qa`; compute their answers
carefully and, where possible, check the arithmetic with a `math` evaluate item.

Do not imitate a publisher's workbook verbatim. Write original practice material
or work with content the user supplied for this task. Sources belong in the
content JSON; an answer-key `note` can provide a learner-facing explanation.
