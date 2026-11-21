# Effect library (`assets/fx/`)

Twenty ready-made on-screen effects for talking-head and voiceover videos: counters, charts,
checklists, comparisons, timelines, quotes, stamps, typewriter, word slams, name bars, hand-drawn
arrows and circles, phone notifications, polls, disclaimers, donut charts and stickers.
Written for this studio (not copied from any other package). Everything is a pure function of `t`.

| File | What |
|---|---|
| `fx.js` | the library: `createFx`, `resolvePlan`, `fxSounds`, `playFxSounds`, `THEMES`, `zones` |
| `hieu-ung.json` | the catalogue — per effect: what sentence it fits, trigger words, cues, params + character limits, `nang` (heavy), when NOT to use it, sound |
| `index.html` | gallery of all 20 effects (preview / stills / theme check) |
| `overlay.html` | renders an `fx-plan.json` as a layer — transparent WebM for laying over footage |

## Choosing effects

Read `hieu-ung.json`, then for each sentence of the voiceover:
- pick the effect whose `hop_voi` matches the **meaning** of the sentence (the `tu_khoa` list is only a hint);
- 6–10 effects per minute; never the same effect twice in a row; never two `nang: true` effects back to back;
- fill `params` with **what is actually said** (or in the source document). Never invent figures.
  Respect the character limits. `*word*` highlights a word;
- anchor `cues` to the spoken word that motivates the motion (the number, "tăng", "mà là", "chi trả"…);
- `thong-bao`: never fake bank transfers, view counts or real apps/logos as "proof";
- insurance / finance figures with conditions → add a `luu-y` with the condition.

## Themes — one per video

`kinh` (dark glass, over footage) · `giay` (paper + ink, hand-made) · `dam` (black/yellow, loud social) ·
`sach` (clean corporate: insurance, banking, training). Brand colours: `theme: { base: 'sach', accent: '#c8102e', hl: '#c8102e' }`
(keys: font, ink, muted, card, border, radius, shadow, blur, accent, accent2, good, bad, hl, track, free, freeStroke).
The pitch of 2–3 style directions still applies: the theme is part of that direction, not a default.

## Layout and faces

Cards go into **zones** (`zones(F)`), which keep the subtitle band free (9:16: y 1440–1560; 16:9: bottom 15 %).
9:16: `tren`, `giua`, `duoi`, `duoi-trai`. 16:9: `trai`, `phai`, `giua`, `tren`, `duoi`, `duoi-trai`.
Pass `avoid: [{x,y,w,h}]` (face boxes) and `createFx` picks the first zone, in the effect's preference order
then the other zones, where the card does not touch a face. `box: {x,y,w,a}` places it exactly (`a` = top|center|bottom).
`mui-ten` and `khoanh-tron` draw over the whole frame with pixel coordinates (`from`/`to`, `target`).

## Use inside an engine-code page

```js
import { createFx, fxSounds, playFxSounds } from './fx/fx.js';   // cp -R SKILL_DIR/assets/fx PROJ/fx
// after fonts are loaded (effects measure their text):
const fx = [
  createFx(stage, { type: 'dem-so', start: K(3, 'mười'), end: K(4, 'năm') , cues: { run: K(3, 'mười') },
                    params: { label: 'Gia đình được bảo vệ', value: 12000, unit: 'gia đình' }, theme: 'sach', format: F }),
];
// in seek(t):            fx.forEach(f => f.seek(t));
// in renderAudio build:  playFxSounds(ctx, sfxBus, sfx, fxSounds(fx));   // sfx from kit.js
```

## Use as a layer over video (talking head, tao-video)

1. `cp -R SKILL_DIR/assets/fx PROJ/fx` and `cp SKILL_DIR/assets/template/kit.js PROJ/` (+ `fonts-vi/` if PROJ has none).
2. Write `PROJ/fx-plan.json`:
   ```json
   { "theme": "sach", "words": "timing.json", "avoid": [{ "x": 360, "y": 330, "w": 360, "h": 420 }],
     "fx": [
       { "type": "dem-so", "start": "năm nay", "end": "+3", "cues": { "run": "mười hai" },
         "params": { "label": "Gia đình được bảo vệ", "value": 12000, "unit": "gia đình" } },
       { "type": "con-dau", "start": "hồ sơ", "end": "+3", "cues": { "hit": "chi trả" }, "params": { "text": "Đã chi trả" } }
     ] }
   ```
   `words` = `voice-timing.py` output (or a flat `[{w,s,e}]` list). Times accept seconds, `"+0.8"` (after start) or a
   spoken word/phrase (matched without diacritics; cues are searched between start and end).
   Unmatched words are printed as `[fx] …` warnings by the renderer — fix them before the final render.
3. Check stills: `node SKILL_DIR/scripts/render.mjs PROJ --entry fx/overlay.html --query plan=../fx-plan.json --format 9x16 --stills 2.5,6`
4. Render the layer: same command with `--alpha --name fx` instead of `--stills` → `PROJ/render/fx-9x16.webm`
   (VP9 with alpha + the effects' sounds, Opus).
5. Lay it over the footage — the alpha decoder must be named before the WebM input:
   ```bash
   ffmpeg -i base.mp4 -c:v libvpx-vp9 -i render/fx-9x16.webm \
     -filter_complex "[0:v][1:v]overlay=format=auto[v];[0:a][1:a]amix=inputs=2:normalize=0[a]" \
     -map "[v]" -map "[a]" -c:v libx264 -crf 18 -c:a aac out.mp4
   ```

## Gallery and checks

```bash
node SKILL_DIR/scripts/render.mjs SKILL_DIR/assets --entry fx/index.html --serve --format 9x16
node SKILL_DIR/scripts/render.mjs SKILL_DIR/assets --entry fx/index.html --query "theme=giay&only=dem-so,con-dau" --format 16x9 --every 1
```
`index.html` options: `theme=`, `only=a,b`, `face=0` (no stand-in speaker), `alpha=1`.

## Adding an effect

Add an entry to `FX` in `fx.js`: `{ dur, enter: 'pop'|'rise'|'drop'|'none', zones, cues: {name: offset}, defaults, build(el, p, c) }`.
`build` creates DOM inside `el` (sizes in `em`: 1 em = 1/17 of the box width in 9:16, 1/20 in 16:9), and returns
`{ seek(t), sounds: [{ t, s: 'pop'|'tick'|'whoosh'|'impact'|'kick'|'snare', gain, opts }] }`. Use `fit()` for one-line text,
`prog`/`spring`/`shake` for motion, `rich()` for `*highlight*`. Then add its catalogue entry to `hieu-ung.json` and a demo
params block in `index.html`, and check stills in all four themes and both formats.
