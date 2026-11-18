# Typography — line breaks and justify

On-screen text must look typeset by a person, not wrapped by a browser. The two failures viewers
notice at once: a lone word dropped onto its own line ("…của khách / hàng"), and justified lines with
huge gaps between words. `assets/template/typeset.js` prevents both; these are its rules.

## 1. Break at meaning boundaries — never let the browser choose

- Write every multi-line block with explicit `<br>` where a reader would pause: between subject and
  predicate, before a conjunction ("mà", "và", "nhưng", "để"), after a comma, around an arrow.
  - Good: `Sự chuyển biến tích cực của khách hàng<br>mới là câu chuyện đáng kể`
  - Bad: letting it wrap as `Sự chuyển biến tích cực của khách / hàng / mới là…`
- Never split a compound word or a fixed phrase across lines. In Vietnamese, many "words" are two
  syllables: khách hàng, sản phẩm, vấn đề, câu chuyện, giải pháp, nguyên nhân, kết quả, cảm xúc…
  Also keep together: number + unit ("45 tuổi"), name + title, a verb and its short object.
- Prefer a balanced shape: a long line over a short one, or lines of similar length. Avoid a last
  line with 1–2 words. Avoid more than 3–4 lines in a heading; rewrite or shrink instead.
- `typeset()` makes every block `nowrap`. If the authored lines don't fit the box, the font shrinks
  a little instead of wrapping. When it would shrink a lot, re-break the lines by hand.

## 2. Smart justify

Justify gives straight left and right edges inside cards and boxes, which looks professional.
But it only works when the gaps it adds are small. `typeset()`:

- sets every line of a block to the width of the block's longest line;
- justifies a line only when it is already at least 80 % of that width (92 % for the last line);
- also requires the added space per word gap to stay at or below 0.22 em;
- leaves every other line left-aligned (short lines, 2–3-word lines, last lines).

So "Đừng bắt đầu bằng sản phẩm. / Hãy bắt đầu bằng khách hàng." becomes a clean justified block,
while "Kết thúc bằng / cảm xúc tích cực" stays left-aligned instead of becoming "Kết   thúc   bằng".

Call it after fonts load and before you register animations, because it rewrites `innerHTML`:

```js
import { typeset, glue, subChunks } from './typeset.js';
const el = document.createElement('div'); el.innerHTML = html; stage.appendChild(el);
typeset(el);                                   // .h1 .h2 .h3 .card .tx .q p by default
// then: el.querySelector('.title') etc. for animations
```

Give a block's box a width with an inline `style="width:…px"` or `data-maxw="…"`. Paddings and
borders are subtracted automatically.

## 3. Subtitles

- Long voiced sentences are split into chunks of at most ~90 characters with `subChunks(line)`. The
  split goes at punctuation near the middle, and each chunk is timed from the word timestamps
  (`scripts/voice-timing.py`). Never show 3-line subtitles.
- `glue(text)` swaps the spaces inside known compound words (`KEEP_VI`, extend per project) for
  non-breaking spaces. Add `text-wrap: balance` on the subtitle element so both lines are similar.
- Subtitles sit in the bottom safe area; keep all other content above them, at least 30 px clear
  of a two-line subtitle.

## 4. Checklist for every still

- [ ] No word alone on a line; no compound word split.
- [ ] No justified line with visibly wide gaps.
- [ ] Nothing overflowing its card or the frame edge, including chips with `nowrap`.
- [ ] Diacritics not clipped (masks ≥ 1.5× font-size tall, line-height ≥ 1.3).
- [ ] Text doesn't collide with subtitles, the progress rail or illustrations.
