# Kanji practice

Two formats: `word_trace` for words (山手線, 天気) and `kanji_trace` for one
character per row with repeated practice.

Readings are learning content, so check them. Give the conventional kun/on
readings the user asked for (e.g. `やま・サン`); separate them with `・`.
Do not invent readings from components. Omit `reading` rather than guess.

When the user names a school grade or kanji list, use the official list and say
which one you used; the renderer does not know any kanji list. Grade/age may
guide the selection but is not printed on the paper by default.

The bundled Klee One font is a textbook-style handwriting face (とめ・はね・
はらい follow handwriting conventions). It does not show stroke order or check
handwriting. Rare characters outside the font fail with a clear message.

Default to nine characters at 20mm per page (vertical columns); offer 22mm boxes for larger
handwriting (fewer boxes per row) or 16mm for more practice boxes.
