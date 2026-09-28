# Kana practice

Accept user-specified names and themes, rather than selecting only from the old
single-character bank. Separate a proper name's display label from the reading
that the learner traces. Confirm unusual readings; do not infer them solely by
reading each kanji separately.

Preserve small kana and long-vowel spelling. Normalize composed dakuten to NFC;
the renderer does this too. The prolonged sound mark ー is supported. It is fine
for an official katakana name converted into a hiragana exercise; tell the user
when the exercise spelling differs from the official display name.

Default to five words at 16mm per character when the user requests a one-page
sample. Choose fewer for long words or a request for larger handwriting. Give
the scope briefly, then generate. Never call five selected stations "all stations".
For all members of a set, verify completeness and keep all items, handling the
page-count constraint explicitly.

Use the original bundled Klee One font with its license. It provides handwriting
style shapes, not stroke-order instruction. No correctness score for handwriting
is generated. Tracing is vertical (tategaki, top to bottom) by default: a light tracing
column and one empty column per word. Use horizontal only when asked.
