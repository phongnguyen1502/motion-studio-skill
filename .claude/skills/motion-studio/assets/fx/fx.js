// fx.js — Motion Studio effect library: 28 reusable on-screen effects for talking-head and voiceover videos
// (8 of them need a speaker on screen: text behind the person, and effects that follow the face — see the end of FX).
// Self-contained (no import from kit.js). Every effect is a pure function of time t, like the rest of the studio.
//
//   import { createFx, resolvePlan, fxSounds } from './fx/fx.js';
//   const fx = createFx(stage, { type: 'dem-so', start: 2.1, end: 5.4, cues: { run: 2.6 },
//                                params: { label: 'Khách hàng mới', value: 1200, unit: 'người' },
//                                zone: 'giua', theme: 'sach', format: { w: 1080, h: 1920 } });
//   window.seek = t => fx.seek(t);
//   // sound: fxSounds([fx]) -> [{ t, s: 'pop', gain }], play them with kit.js `sfx[s](ctx, out, t, opts)`
//
// The catalogue (what fits which sentence, cues, params, limits) is in fx/hieu-ung.json.
// The page must load Be Vietnam Pro (template/fonts-vi/gf.css) and wait for fonts BEFORE createFx,
// because effects measure their text to fit it.

// ---------- time ----------
export const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
export const lerp = (a, b, p) => a + (b - a) * p;
export const E = {
  linear: p => p,
  outCubic: p => 1 - (1 - p) ** 3,
  inCubic: p => p ** 3,
  inOutCubic: p => (p < 0.5 ? 4 * p ** 3 : 1 - (-2 * p + 2) ** 3 / 2),
  outQuint: p => 1 - (1 - p) ** 5,
  outExpo: p => (p >= 1 ? 1 : 1 - 2 ** (-10 * p)),
  inExpo: p => (p <= 0 ? 0 : 2 ** (10 * p - 10)),
  outBack: (p, s = 1.70158) => 1 + (s + 1) * (p - 1) ** 3 + s * (p - 1) ** 2,
};
export const prog = (t, start, dur, e = E.outCubic) => e(clamp((t - start) / dur));
export function spring(t, { stiffness = 170, damping = 14, mass = 1 } = {}) {
  if (t <= 0) return 0;
  const w0 = Math.sqrt(stiffness / mass), z = damping / (2 * Math.sqrt(stiffness * mass));
  if (z < 1) {
    const wd = w0 * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * w0 * t) * (Math.cos(wd * t) + ((z * w0) / wd) * Math.sin(wd * t));
  }
  return 1 - Math.exp(-w0 * t) * (1 + w0 * t);
}
export function rng(seed = 1) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
// Decaying shake offset (px) after time `at`.
function shake(t, at, amp, dur = 0.3, seed = 3) {
  const a = t - at;
  if (a < 0 || a > dur) return [0, 0];
  const k = (1 - a / dur) ** 2, f = Math.floor(a * 60), r = rng(seed + f);
  return [(r() * 2 - 1) * amp * k, (r() * 2 - 1) * amp * k];
}

// ---------- text ----------
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
// *từ khoá* -> highlighted, \n -> line break.
export const rich = s => esc(s).replace(/\*([^*]+)\*/g, '<em>$1</em>').replace(/\n/g, '<br>');
// Words with their highlight flag; *...* may span several words.
function richWords(s) {
  const out = []; let hl = false;
  for (const line of String(s ?? '').split('\n')) {
    for (let w of line.split(/\s+/).filter(Boolean)) {
      const open = w.startsWith('*'), close = w.endsWith('*') && (w.length > 1 || !open);
      w = w.replace(/\*/g, '');
      if (open) hl = true;
      out.push({ w, hl, br: false });
      if (close) hl = false;
    }
    out.push({ br: true });
  }
  out.pop();
  return out;
}
// 1234567.5 -> "1.234.567,5" (Vietnamese grouping).
export function fmtNum(v, dec = 0) {
  const s = Math.abs(v).toFixed(dec); let [i, d] = s.split('.');
  i = i.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return (v < 0 ? '-' : '') + i + (d ? ',' + d : '');
}
function h(tag, cls, parent, html) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html != null) n.innerHTML = html;
  if (parent) parent.appendChild(n);
  return n;
}
function svg(tag, attrs, parent) {
  const n = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const k in attrs) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}
// Shrinks one line of text until it fits `maxW` px (never wraps it).
function fit(el, maxW, min = 0.35) {
  el.style.whiteSpace = 'nowrap';
  const base = parseFloat(getComputedStyle(el).fontSize);
  let s = 1;
  while (el.scrollWidth > maxW + 0.5 && s > min) { s -= 0.03; el.style.fontSize = base * s + 'px'; }
  return s;
}
const innerW = el => { const cs = getComputedStyle(el); return el.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight); };

// ---------- themes ----------
// Pick one per video (the studio wants a distinct look per topic), or pass { base: 'sach', accent: '#c8102e' }.
export const THEMES = {
  kinh: { // dark glass over footage
    font: "'Be Vietnam Pro', system-ui, sans-serif", ink: '#ffffff', muted: 'rgba(255,255,255,.72)',
    card: 'rgba(16,20,36,.62)', border: '1.5px solid rgba(255,255,255,.28)', radius: '.8em',
    shadow: '0 .6em 2em rgba(0,0,0,.35)', blur: 'blur(18px) saturate(1.3)',
    accent: '#ffd23f', accent2: '#ff5470', good: '#3ddc97', bad: '#ff6b81', hl: '#ffd23f', track: 'rgba(255,255,255,.18)',
    free: '#ffffff', freeStroke: '#0b1020',
  },
  giay: { // paper + ink, hand-made feel
    font: "'Be Vietnam Pro', system-ui, sans-serif", ink: '#1d2a44', muted: '#5b6478',
    card: '#fffaf0', border: '.11em solid #1d2a44', radius: '.45em', shadow: '.28em .28em 0 #1d2a44', blur: 'none',
    accent: '#e4572e', accent2: '#2a9d8f', good: '#2a9d8f', bad: '#e4572e', hl: '#e4572e', track: '#ece3cf',
    free: '#fffaf0', freeStroke: '#1d2a44',
  },
  dam: { // loud black/yellow for hooks and social
    font: "'Be Vietnam Pro', system-ui, sans-serif", ink: '#ffffff', muted: '#c4c4c4',
    card: '#101012', border: 'none', radius: '.22em', shadow: '0 .45em 0 rgba(0,0,0,.3)', blur: 'none',
    accent: '#ffe600', accent2: '#ff3b5c', good: '#38e07b', bad: '#ff3b5c', hl: '#ffe600', track: '#34343a',
    free: '#ffffff', freeStroke: '#000000',
  },
  sach: { // clean corporate (insurance, banking, training)
    font: "'Be Vietnam Pro', system-ui, sans-serif", ink: '#10243f', muted: '#5a6b85',
    card: '#ffffff', border: '1px solid #dfe6f0', radius: '.7em', shadow: '0 .8em 2.2em rgba(16,36,63,.20)', blur: 'none',
    accent: '#0a6cff', accent2: '#ff7a00', good: '#12b76a', bad: '#f04438', hl: '#0a6cff', track: '#e8eef7',
    free: '#ffffff', freeStroke: '#10243f',
  },
};
function themeVars(theme) {
  const t = typeof theme === 'string' ? THEMES[theme] : { ...THEMES[theme?.base || 'kinh'], ...(theme || {}) };
  if (!t) throw new Error(`fx: unknown theme "${theme}" (use ${Object.keys(THEMES).join(', ')})`);
  return t;
}

// ---------- CSS (injected once) ----------
const CSS = `
.fx{position:absolute;box-sizing:border-box;font-family:var(--fx-font);color:var(--fx-ink);line-height:1.22;-webkit-font-smoothing:antialiased;pointer-events:none}
.fx *{box-sizing:border-box}
.fx em{font-style:normal;color:var(--fx-hl)}
.fx-in{position:relative;transform-origin:50% 50%}
.fx-card{background:var(--fx-card);border:var(--fx-border);border-radius:var(--fx-radius);box-shadow:var(--fx-shadow);backdrop-filter:var(--fx-blur);-webkit-backdrop-filter:var(--fx-blur);padding:.85em 1.05em .95em}
.fx-label{font-weight:800;font-size:.6em;letter-spacing:.12em;text-transform:uppercase;color:var(--fx-muted)}
.fx-title{font-weight:800;font-size:.95em;line-height:1.15;margin-bottom:.55em}
.fx-big{display:inline-block;font-weight:900;font-size:3.3em;line-height:1.05;letter-spacing:-.03em;color:var(--fx-accent);font-variant-numeric:tabular-nums}
.fx-unit{font-weight:800;font-size:1.1em;margin-left:.3em;color:var(--fx-ink)}
.fx-row{display:flex;align-items:baseline}
.fx-chip{display:inline-block;margin-top:.35em;padding:.18em .55em;border-radius:99em;background:var(--fx-good);color:#fff;font-weight:800;font-size:.7em;transform-origin:0 50%}
.fx-free{font-weight:900;color:var(--fx-free);-webkit-text-stroke:.09em var(--fx-free-stroke);paint-order:stroke fill;text-shadow:0 .06em .25em rgba(0,0,0,.35);text-transform:uppercase;letter-spacing:-.01em;line-height:1.02}
.fx-free em{color:var(--fx-accent)}
/* bars */
.fx-bars{display:flex;align-items:flex-end;gap:.55em;height:6.2em;margin-top:.3em}
.fx-col{flex:1;display:flex;flex-direction:column;align-items:center;height:100%;justify-content:flex-end}
.fx-col b{font-weight:900;font-size:.8em;margin-bottom:.2em;font-variant-numeric:tabular-nums}
.fx-col i{display:block;width:100%;border-radius:.25em .25em 0 0;background:var(--fx-track);transform-origin:50% 100%}
.fx-col.hl i{background:var(--fx-accent)} .fx-col.hl b{color:var(--fx-accent)}
.fx-col span{font-size:.62em;font-weight:700;color:var(--fx-muted);margin-top:.35em;white-space:nowrap}
/* compare */
.fx-cmp{display:grid;grid-template-columns:1fr 1fr;gap:.7em}
.fx-cmp h4{margin:0 0 .45em;font-weight:900;font-size:.74em;letter-spacing:.06em;padding:.25em .6em;border-radius:.3em;display:inline-block;color:#fff;white-space:nowrap}
.fx-cmp .l h4{background:var(--fx-bad)} .fx-cmp .r h4{background:var(--fx-good)}
.fx-cmp p{margin:.35em 0;font-weight:700;font-size:.95em;display:flex;gap:.4em;line-height:1.2}
.fx-cmp p span{text-wrap:pretty} .fx-cmp .l p{color:var(--fx-muted)} .fx-cmp p s{text-decoration:none;font-weight:900;flex:none}
.fx-cmp .l p s{color:var(--fx-bad)} .fx-cmp .r p s{color:var(--fx-good)}
/* checklist */
.fx-item{display:flex;align-items:center;gap:.55em;margin:.42em 0;font-weight:700;font-size:.85em}
.fx-box{flex:none;width:1.25em;height:1.25em;border-radius:.3em;border:.12em solid var(--fx-muted);position:relative}
.fx-box svg{position:absolute;inset:-.1em;width:1.45em;height:1.45em;overflow:visible}
/* progress */
.fx-track{height:1.1em;border-radius:99em;background:var(--fx-track);overflow:hidden;margin-top:.45em}
.fx-fill{height:100%;border-radius:99em;background:linear-gradient(90deg,var(--fx-accent2),var(--fx-accent));transform-origin:0 50%}
/* timeline */
.fx-tl{position:relative;padding-left:1.6em}
.fx-tl .ln{position:absolute;left:.42em;top:.4em;bottom:.4em;width:.16em;background:var(--fx-accent);transform-origin:50% 0;border-radius:1em}
.fx-tl .it{position:relative;margin:.15em 0 .7em}
.fx-tl .it:last-child{margin-bottom:.1em}
.fx-tl .dot{position:absolute;left:-1.52em;top:.22em;width:.9em;height:.9em;border-radius:50%;background:var(--fx-card);border:.2em solid var(--fx-accent)}
.fx-tl .tm{font-weight:900;font-size:.75em;color:var(--fx-accent);letter-spacing:.04em}
.fx-tl .tx{font-weight:700;font-size:.85em}
/* quote */
.fx-q{position:relative;padding-top:.55em}
.fx-q .mk{position:absolute;left:-.05em;top:-.5em;font-size:3.2em;font-weight:900;color:var(--fx-accent);line-height:1}
.fx-q .tx{font-weight:800;font-size:1.05em;line-height:1.3;text-wrap:pretty}
.fx-q .tx span{display:inline-block;margin-right:.26em}
.fx-q .au{margin-top:.6em;font-weight:700;font-size:.62em;color:var(--fx-muted);letter-spacing:.06em}
/* stamp */
.fx-stamp{display:inline-block;padding:.25em .55em .3em;border:.16em solid currentColor;outline:.06em solid currentColor;outline-offset:.12em;border-radius:.25em;font-weight:900;text-transform:uppercase;letter-spacing:.06em;line-height:1.05;text-align:center;filter:url(#fx-grunge)}
.fx-stamp small{display:block;font-size:.32em;letter-spacing:.2em;margin-top:.25em}
/* typewriter */
.fx-tw{font-weight:800;font-size:1.2em;line-height:1.3}
.fx-tw .c{visibility:hidden}
.fx-tw .cur{display:inline-block;width:.09em;height:1.05em;margin-left:.04em;vertical-align:-.15em;background:var(--fx-accent)}
/* lower third */
.fx-lt{display:flex;align-items:stretch}
.fx-lt .bar{width:.35em;background:var(--fx-accent);transform-origin:50% 100%}
.fx-lt .bd{display:flex;flex-direction:column;align-items:flex-start}
.fx-lt .nm{background:var(--fx-card);padding:.25em .65em .28em;font-weight:900;font-size:1.5em;white-space:nowrap}
.fx-lt .rl{background:var(--fx-accent);color:var(--fx-card);padding:.3em .95em;font-weight:800;font-size:.82em;letter-spacing:.06em;white-space:nowrap;align-self:flex-start}
/* notifications */
.fx-nt{display:flex;gap:.6em;align-items:center;margin-bottom:.45em;padding:.6em .75em}
.fx-nt:last-child{margin-bottom:0}
.fx-nt .ic{flex:none;width:1.9em;height:1.9em;border-radius:.5em;display:grid;place-items:center;font-weight:900;color:#fff;font-size:.8em}
.fx-nt .hd{display:flex;justify-content:space-between;font-size:.55em;font-weight:700;color:var(--fx-muted);letter-spacing:.04em;text-transform:uppercase}
.fx-nt .tt{font-weight:800;font-size:.78em;margin-top:.1em}
.fx-nt .ms{font-weight:500;font-size:.72em;color:var(--fx-ink);opacity:.85}
.fx-nt .bd{flex:1;min-width:0}
/* poll */
.fx-op{position:relative;margin:.4em 0;border-radius:.45em;overflow:hidden;background:var(--fx-track);padding:.45em .7em;display:flex;justify-content:space-between;font-weight:800;font-size:.8em}
.fx-op i{position:absolute;inset:0;background:var(--fx-muted);opacity:.35;transform-origin:0 50%}
.fx-op.win i{background:var(--fx-accent);opacity:1}
.fx-op span,.fx-op b{position:relative;font-variant-numeric:tabular-nums}
/* callout */
.fx-co{display:flex;gap:.7em;align-items:flex-start;border-left:.35em solid var(--fx-accent2)}
.fx-co .ic{flex:none;width:1.5em;height:1.5em;border-radius:50%;background:var(--fx-accent2);color:#fff;display:grid;place-items:center;font-weight:900;font-size:.9em}
.fx-co .tt{font-weight:900;font-size:.75em;letter-spacing:.1em;color:var(--fx-accent2)}
.fx-co .tx{font-weight:600;font-size:.78em;line-height:1.35;margin-top:.2em;text-wrap:pretty}
/* donut */
.fx-dn{display:flex;align-items:center;gap:.9em}
.fx-dn svg{flex:none;width:6.2em;height:6.2em;transform:rotate(-90deg)}
.fx-dn .lg{flex:1}
.fx-dn .lg p{margin:.35em 0;display:flex;align-items:center;gap:.45em;font-weight:700;font-size:.75em}
.fx-dn .lg i{flex:none;width:.8em;height:.8em;border-radius:.2em}
.fx-dn .lg b{margin-left:auto;font-weight:900;font-variant-numeric:tabular-nums}
.fx-dn .ctr{position:absolute;width:6.2em;height:6.2em;display:grid;place-items:center;font-weight:900;font-size:1em;text-align:center;line-height:1.05}
/* sticker */
.fx-stk{display:flex;flex-direction:column;align-items:center;gap:.12em}
.fx-stk span{display:block;background:var(--fx-card);color:var(--fx-ink);padding:.08em .35em .12em;font-weight:900;text-transform:uppercase;line-height:1.08;border-radius:.12em;box-shadow:var(--fx-shadow);white-space:nowrap}
/* slam / strike */
.fx-sl{display:flex;flex-direction:column;align-items:center;text-align:center}
.fx-sl div{display:block;white-space:nowrap;transform-origin:50% 60%;line-height:1.12;margin:.03em 0}
.fx-st{position:relative;display:flex;flex-direction:column;align-items:center}
.fx-st .old{position:relative;color:var(--fx-free);opacity:1}
.fx-st .line{position:absolute;left:-4%;right:-4%;top:52%;height:.13em;background:var(--fx-accent2);transform-origin:0 50%;border-radius:1em}
.fx-st .new{color:var(--fx-accent);transform-origin:50% 0}
/* behind the speaker (layer "sau") */
.fx-bk{position:absolute;left:0;width:100%;text-align:center;transform-origin:50% 50%}
.fx-bk .ln{display:block;width:max-content;margin:0 auto;white-space:nowrap;font-weight:900;line-height:1.02;letter-spacing:-.02em;text-transform:uppercase;text-shadow:0 .02em .09em rgba(0,0,0,.22)}
.fx-bk .ln span{display:inline-block}
.fx-bk.vien .ln{color:transparent!important;-webkit-text-stroke:.022em var(--fx-bk-c);text-shadow:none}
.fx-bk.vien .ln em{-webkit-text-stroke-color:var(--fx-accent)}
.fx-dim{position:absolute;inset:0;background:#000}
.fx-neon .ln{display:block;width:max-content;margin:0 auto;white-space:nowrap;font-weight:700;line-height:1.1;color:#fff;-webkit-text-stroke:.012em var(--nc);
  text-shadow:0 0 .02em #fff,0 0 .07em var(--nc),0 0 .18em var(--nc),0 0 .42em var(--nc),0 0 .9em var(--nc)}
.fx-neon .ln em{color:#fff}
.fx-mq{position:absolute;left:0;white-space:nowrap;font-weight:900;line-height:1.2;text-transform:uppercase;letter-spacing:-.01em;color:var(--fx-bk-c)}
.fx-mq.vien{color:transparent;-webkit-text-stroke:.02em var(--fx-bk-c)}
/* around the face */
.fx-sk{position:absolute;left:0;top:0;transform-origin:50% 50%}
.fx-sk.emo{font-size:3.4em;line-height:1;font-family:'Segoe UI Emoji','Apple Color Emoji','Noto Color Emoji',sans-serif;filter:drop-shadow(0 .06em .12em rgba(0,0,0,.35))}
.fx-sk.txt{font-size:1.45em;font-weight:900;white-space:nowrap;background:var(--fx-card);color:var(--fx-ink);padding:.16em .55em .2em;border-radius:.45em;border:.13em solid #fff;box-shadow:0 .25em .7em rgba(0,0,0,.3)}
.fx-sk.txt em{color:var(--fx-accent)}
.fx-lock{position:absolute;left:0;top:0;text-align:center;white-space:nowrap}
.fx-lock .nm{display:inline-block;font-weight:900;font-size:1.35em;background:var(--fx-accent);color:#fff;padding:.14em .55em .18em;border-radius:.2em}
.fx-lock .sb{display:block;margin-top:.25em;font-weight:700;font-size:.8em;color:#fff;text-shadow:0 .05em .25em rgba(0,0,0,.6);letter-spacing:.04em}
/* wave 2: app-like UI (generic, no real app names or logos) */
.fx-av{flex:none;width:2.1em;height:2.1em;border-radius:50%;display:grid;place-items:center;font-weight:900;color:#fff;font-size:.9em}
.fx-dts{display:flex;gap:.28em}.fx-dts i{width:.55em;height:.55em;border-radius:50%;background:#ff5f57}.fx-dts i+i{background:#febc2e}.fx-dts i+i+i{background:#28c840}
.fx-cur{display:inline-block;width:.08em;height:1.1em;background:var(--fx-accent);vertical-align:-.2em;margin-left:.05em}
.fx-chat .hd{display:flex;align-items:center;gap:.55em;padding-bottom:.55em;margin-bottom:.45em;border-bottom:1px solid var(--fx-track)}
.fx-chat .nm{font-weight:800;font-size:.85em}.fx-chat .st{font-size:.58em;color:var(--fx-good);font-weight:700}
.fx-chat .row{display:flex;margin:.32em 0;position:relative}.fx-chat .row.minh{justify-content:flex-end}
.fx-chat .bb{max-width:78%;padding:.42em .75em .48em;border-radius:1.1em;font-weight:600;font-size:.8em;line-height:1.3;transform-origin:0 100%}
.fx-chat .ho .bb{background:var(--fx-track);color:var(--fx-ink);border-bottom-left-radius:.3em}
.fx-chat .minh .bb{background:var(--fx-accent);border-bottom-right-radius:.3em;transform-origin:100% 100%}
.fx-chat .dots{position:absolute;left:0;top:0;padding:.6em .75em;border-radius:1.1em;background:var(--fx-track);display:flex;gap:.25em;font-size:.8em}
.fx-chat .dots i{width:.45em;height:.45em;border-radius:50%;background:var(--fx-muted)}
.fx-cm .top{display:flex;gap:.6em}.fx-cm .nm{font-weight:800;font-size:.75em}.fx-cm .nm span{font-weight:600;color:var(--fx-muted);font-size:.85em;margin-left:.3em}
.fx-cm .tx{font-weight:600;font-size:.85em;margin-top:.15em;line-height:1.3}
.fx-cm .ft{display:flex;align-items:center;gap:.45em;margin:.5em 0 0 2.6em;font-size:.72em;color:var(--fx-muted);font-weight:700}
.fx-cm .ht{color:#ff3b5c;font-size:1.3em;display:inline-block}.fx-cm .ft b{color:var(--fx-ink);min-width:2.6em;font-variant-numeric:tabular-nums}
.fx-fly{position:absolute;left:0;top:0;color:#ff3b5c;pointer-events:none;text-shadow:0 .05em .2em rgba(0,0,0,.25)}
.fx-call{background:#16181d;color:#fff;border-radius:1.4em;padding:1em 1.1em 1.1em;box-shadow:0 .8em 2em rgba(0,0,0,.4)}
.fx-call .tp{display:flex;align-items:center;gap:.9em}.fx-call .aw{position:relative;flex:none}
.fx-call .aw i{position:absolute;inset:0;border-radius:50%;border:.1em solid #30d158}
.fx-call .lb{font-size:.6em;letter-spacing:.12em;text-transform:uppercase;color:#9aa0aa;font-weight:700}
.fx-call .nm{font-weight:900;font-size:1.35em;line-height:1.15}.fx-call .sb{font-size:.7em;color:#c9ced6;font-weight:600;font-variant-numeric:tabular-nums}
.fx-call .bt{display:flex;justify-content:space-between;margin-top:.9em;padding:0 .8em}
.fx-call .bt span{width:2.6em;height:2.6em;border-radius:50%;display:grid;place-items:center}
.fx-call .no{background:#ff3b5c}.fx-call .no svg{transform:rotate(135deg)}.fx-call .yes{background:#30d158}.fx-call svg{width:1.3em;height:1.3em;fill:#fff}
.fx-br{overflow:hidden}.fx-br .bar{display:flex;align-items:center;gap:.6em;padding:.55em .7em;background:var(--fx-track)}
.fx-br .ad{flex:1;background:var(--fx-card);border-radius:99em;padding:.3em .8em;font-size:.68em;font-weight:600;white-space:nowrap;overflow:hidden;color:var(--fx-ink)}
.fx-br .ad b{font-weight:600;color:var(--fx-muted)}.fx-br .ld{height:.18em;background:var(--fx-accent);transform-origin:0 50%}
.fx-br .pg{padding:.8em 1em 1em}.fx-br .ti{font-weight:900;font-size:1.1em;line-height:1.2}
.fx-br .tx{font-weight:500;font-size:.75em;color:var(--fx-muted);margin-top:.4em;line-height:1.4}
.fx-br .sk{height:.55em;border-radius:.3em;background:var(--fx-track);margin-top:.5em}.fx-br .sk+.sk{width:70%}
.fx-tm{background:#0d1117;border-radius:.7em;overflow:hidden;box-shadow:0 .8em 2em rgba(0,0,0,.4);color:#e6edf3}
.fx-tm .bar{display:flex;align-items:center;gap:.6em;padding:.45em .7em;background:#161b22}
.fx-tm .bar span{font-size:.58em;color:#8b949e;font-weight:600;flex:1;text-align:center;margin-right:3em}
.fx-tm .bd{padding:.7em .9em .9em;font-family:'Cascadia Mono',Consolas,'Courier New',monospace;font-size:.72em;line-height:1.55}
.fx-tm .ln{white-space:pre-wrap;word-break:break-word}.fx-tm .pr{color:#3fb950;font-weight:700}.fx-tm .o{color:#9da7b3}.fx-tm em{color:#ffd23f}
.fx-rc{display:flex;flex-direction:column;align-items:center}
.fx-rc .sl{width:100%;height:.75em;border-radius:.38em;background:#26272b;box-shadow:inset 0 -.15em .2em rgba(255,255,255,.12);position:relative;z-index:2}
.fx-rc .wr{width:84%;overflow:hidden;margin-top:-.38em;padding-bottom:.8em;filter:drop-shadow(0 .35em .5em rgba(0,0,0,.28))}
.fx-rc .pp{background:#fffdf7;color:#1d1d1f;padding:1.2em 1em 1.5em;font-family:'Cascadia Mono',Consolas,'Courier New',monospace;font-size:.72em}
.fx-rc .t{text-align:center;font-weight:800;font-size:1.25em;letter-spacing:.08em}.fx-rc .hr{border-top:.12em dashed #9a9a9a;margin:.6em 0}
.fx-rc .r{display:flex;gap:.4em;margin:.28em 0;align-items:baseline}.fx-rc .r i{flex:1;border-bottom:.12em dotted #b0b0b0}
.fx-rc .r b{font-weight:700;white-space:nowrap}.fx-rc .tot{font-size:1.25em;font-weight:900}.fx-rc .tot b{font-weight:900}
.fx-rc .nt{text-align:center;color:#666;margin-top:.55em}.fx-rc em{color:#d62d20}
.fx-pf{position:relative}.fx-pf .rw{display:flex;align-items:center;gap:.7em}.fx-pf .nm{font-weight:900;font-size:1.05em;line-height:1.15}
.fx-pf .hd{font-size:.7em;color:var(--fx-muted);font-weight:600}.fx-pf .stt{display:flex;justify-content:space-around;margin:.75em 0 .8em;text-align:center}
.fx-pf .stt b{display:block;font-weight:900;font-size:1em;font-variant-numeric:tabular-nums}.fx-pf .stt span{font-size:.58em;color:var(--fx-muted);font-weight:700}
.fx-pf .btn{text-align:center;font-weight:800;font-size:.8em;padding:.55em;border-radius:.6em;background:var(--fx-accent)}
.fx-pf .cur{position:absolute;left:0;top:0;width:1.7em;height:1.7em;filter:drop-shadow(0 .1em .2em rgba(0,0,0,.45))}
.fx-sr .bar{display:flex;align-items:center;gap:.55em;padding:.6em 1em;border-radius:99em}
.fx-sr svg{width:1.1em;height:1.1em;flex:none;stroke:var(--fx-muted);fill:none;stroke-width:2.6;stroke-linecap:round}
.fx-sr .q{font-weight:700;font-size:.9em;white-space:nowrap;overflow:hidden}
.fx-sr .dd{margin-top:.4em;padding:.35em 0;border-radius:.9em}.fx-sr .it{display:flex;align-items:center;gap:.6em;padding:.45em 1em;font-size:.78em;font-weight:500}
.fx-sr .it b{font-weight:800}.fx-sr .it.on{background:var(--fx-track)}
.fx-rv .sts{display:flex;gap:.12em;font-size:1.6em;line-height:1}.fx-rv .st{position:relative;color:var(--fx-track);display:inline-block}
.fx-rv .st i{position:absolute;left:0;top:0;overflow:hidden;color:#ffc531;font-style:normal;white-space:nowrap}
.fx-rv .tx{font-weight:700;font-size:.92em;line-height:1.35;margin:.5em 0 .6em;text-wrap:pretty}
.fx-rv .au{display:flex;align-items:center;gap:.5em;font-size:.7em}.fx-rv .au b{font-weight:800;display:block}.fx-rv .au span{color:var(--fx-muted);font-weight:600}
.fx-cta{text-align:left}.fx-cta .lb{display:inline-block;font-weight:900;font-size:.85em;padding:.3em .7em;border-radius:.4em;background:var(--fx-accent);margin-bottom:.45em;box-shadow:var(--fx-shadow)}
.fx-cta .bar{display:flex;align-items:center;gap:.55em;padding:.5em .6em;border-radius:99em}
.fx-cta .f{flex:1;font-weight:800;font-size:.95em;padding:.32em .8em;border-radius:99em;background:var(--fx-track);white-space:nowrap;overflow:hidden;min-height:1.7em}
.fx-cta .ph{color:var(--fx-muted);font-weight:600}.fx-cta .snd{flex:none;width:2.1em;height:2.1em;border-radius:50%;background:var(--fx-accent);display:grid;place-items:center}
.fx-cta .snd svg{width:1.05em;height:1.05em}.fx-cta .ok{display:inline-block;margin-top:.45em;font-weight:800;font-size:.7em;padding:.25em .7em;border-radius:99em;background:var(--fx-good);color:#fff}
/* wave 2: paper and magazine */
.fx-mag{position:absolute;left:0;width:100%;text-align:center;font-family:Cambria,'Times New Roman',serif;font-weight:700;line-height:.9;letter-spacing:-.02em;white-space:nowrap;text-shadow:0 .03em .12em rgba(0,0,0,.3)}
.fx-mag-i{position:absolute;left:0;width:100%;display:flex;align-items:center;gap:.8em;justify-content:center;font-weight:800;letter-spacing:.25em;text-shadow:0 .05em .2em rgba(0,0,0,.5)}
.fx-mag-i i{flex:none;width:3em;height:.1em;background:currentColor}
.fx-mag-l{position:absolute;font-weight:900;text-transform:uppercase;line-height:1.05;text-shadow:0 .05em .25em rgba(0,0,0,.55)}
.fx-mag-l em{display:block;font-family:Cambria,'Times New Roman',serif;font-size:2.1em;line-height:.95;color:var(--fx-accent)}
.fx-pl{width:54%;margin:0 auto;background:#fdfdf8;padding:.55em .55em 0;box-shadow:0 .6em 1.6em rgba(0,0,0,.35);position:relative;transform-origin:50% 0}
.fx-pl .im{width:100%;overflow:hidden;background:#ddd}.fx-pl img{width:100%;height:100%;object-fit:cover;object-position:50% 28%;display:block}
.fx-pl .cp{color:#2b2b2b;text-align:center;font-weight:700;font-style:italic;font-size:.95em;padding:.5em .2em .7em;line-height:1.2}
.fx-tape{position:absolute;left:50%;top:-.6em;width:4.2em;height:1.2em;margin-left:-2.1em;background:rgba(255,246,214,.75);box-shadow:0 .05em .15em rgba(0,0,0,.15);transform:rotate(-4deg)}
.fx-cal{width:8.5em;margin:0 auto;position:relative}
.fx-cal .hd{background:var(--fx-accent);border-radius:.5em .5em 0 0;padding:.5em 0 .45em;text-align:center;font-weight:900;font-size:.8em;letter-spacing:.12em;position:relative}
.fx-cal .hd::before,.fx-cal .hd::after{content:'';position:absolute;top:-.35em;width:.45em;height:1em;border-radius:.3em;background:#333;left:25%}.fx-cal .hd::after{left:auto;right:25%}
.fx-cal .pg{background:#fff;color:#1d1d1f;height:6.2em;display:grid;place-items:center;box-shadow:0 .6em 1.4em rgba(0,0,0,.3)}
.fx-cal .pg b{font-size:4.6em;font-weight:900;line-height:1;font-variant-numeric:tabular-nums;letter-spacing:-.04em}
.fx-cal .bot{border-radius:0 0 .5em .5em}.fx-cal .fl{position:absolute;left:0;right:0;transform-origin:50% 0;box-shadow:0 .2em .6em rgba(0,0,0,.25)}
.fx-cal-l{text-align:center;margin-top:.45em;font-size:1.25em}
.fx-sb .g{display:grid;gap:.55em}.fx-sb .pn{display:flex;flex-direction:column;gap:.3em}
.fx-sb .fr{aspect-ratio:3/4;border:.12em solid var(--fx-ink);border-radius:.35em;display:grid;place-items:center;overflow:hidden;background:var(--fx-track);position:relative}
.fx-sb .fr b{font-weight:900;font-size:1.6em;color:var(--fx-muted)}.fx-sb .fr img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:50% 28%}
.fx-sb .cp{font-weight:800;font-size:.7em;text-align:center;line-height:1.2}.fx-sb .pn.on .fr{border-color:var(--fx-accent);box-shadow:0 0 0 .12em var(--fx-accent)}
.fx-tp{filter:drop-shadow(0 .3em .5em rgba(0,0,0,.3))}.fx-tp .s{padding:.75em 1.3em;color:#1d2a44;text-align:center}
.fx-tp .tx{font-weight:900;font-size:1.5em;line-height:1.15;white-space:nowrap}.fx-tp .tx em{color:#e4572e}
.fx-tp .sb{font-weight:700;font-size:.72em;margin-top:.25em;color:#4a5568}
.fx-nt2{width:74%;margin:0 auto;padding:1.4em 1.1em 1.2em;color:#2b2b2b;position:relative;box-shadow:0 .9em 1.2em -.6em rgba(0,0,0,.45),0 .1em .3em rgba(0,0,0,.15)}
.fx-nt2 .t{font-weight:900;font-size:1.15em;display:inline-block;position:relative}
.fx-nt2 .t svg{position:absolute;left:-.1em;bottom:-.35em;width:110%;height:.5em;overflow:visible}
.fx-nt2 .it{font-weight:700;font-size:.85em;margin-top:.5em;display:flex;gap:.45em;line-height:1.25}.fx-nt2 .it::before{content:'–';flex:none}
.fx-nt2 em{color:#d62d20}
/* wave 3: film overlays */
.fx-bar{position:absolute;left:0;width:100%;background:#000;display:flex;align-items:center;justify-content:center}
.fx-bar span{color:#fff;font-weight:600;letter-spacing:.35em;font-size:.62em;text-transform:uppercase;opacity:.9}
.fx-hud{position:absolute;color:#fff;font-family:'Cascadia Mono',Consolas,'Courier New',monospace;font-weight:700;text-shadow:0 0 .2em rgba(0,0,0,.6),0 .05em .1em rgba(0,0,0,.6);white-space:nowrap}
.fx-hud .dot{display:inline-block;width:.7em;height:.7em;border-radius:50%;background:#ff2d2d;margin-right:.4em;vertical-align:-.02em;box-shadow:0 0 .4em #ff2d2d}
.fx-bat{display:inline-block;width:1.9em;height:.9em;border:.12em solid #fff;border-radius:.15em;position:relative;vertical-align:-.1em;margin-left:.4em}
.fx-bat::after{content:'';position:absolute;right:-.32em;top:.2em;width:.18em;height:.35em;background:#fff;border-radius:0 .1em .1em 0}
.fx-bat i{position:absolute;left:.1em;top:.1em;bottom:.1em;background:#fff}
.fx-leak{position:absolute;left:0;top:0;border-radius:50%;pointer-events:none}
.fx-osd{position:absolute;color:#f4f4f4;font-family:'Cascadia Mono',Consolas,'Courier New',monospace;font-weight:700;letter-spacing:.06em;white-space:nowrap;text-shadow:.06em 0 0 rgba(255,40,80,.7),-.06em 0 0 rgba(40,200,255,.7),0 0 .25em rgba(255,255,255,.35)}
`;
function injectCSS() {
  if (document.getElementById('fx-css')) return;
  const st = h('style', null, document.head); st.id = 'fx-css'; st.textContent = CSS;
  // Ink texture for the stamp: deterministic turbulence (fixed seed).
  const s = svg('svg', { width: 0, height: 0, style: 'position:absolute', 'aria-hidden': 'true' }, document.body);
  s.innerHTML = `<filter id="fx-grunge"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="4" result="n"/>
    <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 -2.2 1.6" result="m"/>
    <feComposite in="SourceGraphic" in2="m" operator="in" result="c"/>
    <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="1" seed="9" result="w"/>
    <feDisplacementMap in="c" in2="w" scale="4"/></filter>`;
}

// ---------- layout ----------
// Zones keep cards off the subtitle band (9:16: y 1440–1560, 16:9: bottom 15 %).
export function zones(F) {
  const { w: W, h: H } = F;
  if (H > W) return {
    tren: { x: W * 0.08, y: H * 0.11, w: W * 0.84, a: 'top' },
    giua: { x: W * 0.08, y: H * 0.42, w: W * 0.84, a: 'center' },
    duoi: { x: W * 0.08, y: H * 0.735, w: W * 0.84, a: 'bottom' },
    'duoi-trai': { x: W * 0.06, y: H * 0.735, w: W * 0.7, a: 'bottom' },
  };
  return {
    trai: { x: W * 0.04, y: H * 0.46, w: W * 0.33, a: 'center' },
    phai: { x: W * 0.63, y: H * 0.46, w: W * 0.33, a: 'center' },
    giua: { x: W * 0.25, y: H * 0.46, w: W * 0.5, a: 'center' },
    tren: { x: W * 0.25, y: H * 0.08, w: W * 0.5, a: 'top' },
    duoi: { x: W * 0.25, y: H * 0.83, w: W * 0.5, a: 'bottom' },
    'duoi-trai': { x: W * 0.05, y: H * 0.83, w: W * 0.4, a: 'bottom' },
  };
}
const overlap = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

// ---------- enter / exit ----------
function enterExit(node, kind, t, start, end) {
  const a = t - start;
  let o = 1, tf = '';
  if (kind === 'pop') { const s = spring(a, { stiffness: 260, damping: 17 }); tf = `scale(${0.55 + 0.45 * s})`; o = clamp(a / 0.12); }
  else if (kind === 'rise') { const p = prog(t, start, 0.5, E.outExpo); tf = `translateY(${(1 - p) * 1.4}em)`; o = p; }
  else if (kind === 'drop') { const s = spring(a, { stiffness: 210, damping: 16 }); tf = `translateY(${(1 - s) * -2.4}em)`; o = clamp(a / 0.1); }
  const q = prog(t, end - 0.28, 0.28, E.inCubic);
  if (q > 0) { o *= 1 - q; tf += ` translateY(${-q * 0.6}em) scale(${1 - q * 0.05})`; }
  node.style.opacity = o; node.style.transform = tf;
}

// ---------- the speaker (talking-head mode) ----------
// c.face(t) -> { x, y, w, h, top, cx, cy } in stage px: the face box from spec.track (mat.json, loaded by overlay.html),
// else derived from the plan's avoid box, else a centred guess. top = top of the head (hair), from the person matte.
function faceFn(spec, F) {
  const a = spec.avoid?.[0];
  let fb;
  if (a) { const w = a.w / 1.5, h = a.h / 1.75; fb = { x: a.x + w * 0.25, y: a.y + h * 0.45, w, h }; }
  else fb = { x: F.w * 0.36, y: F.h * 0.24, w: F.w * 0.28, h: F.w * 0.34 };
  fb.top = fb.y - fb.h * 0.35;
  const done = b => ({ ...b, cx: b.x + b.w / 2, cy: b.y + b.h / 2 });
  const FB = done(fb);
  return t => { const b = spec.track?.(t); return b ? done(b) : FB; };
}
function faceAvg(face, a, b) {
  const n = 9, s = { x: 0, y: 0, w: 0, h: 0, top: 0 };
  for (let i = 0; i < n; i++) { const f = face(a + ((b - a) * i) / (n - 1)); for (const k in s) s[k] += f[k] / n; }
  return { ...s, cx: s.x + s.w / 2, cy: s.y + s.h / 2 };
}
// Lines of big text made of letter spans (for per-letter motion); *từ* = accent colour, \n = new line.
function letterLines(parent, s, cls, maxW) {
  const lines = [];
  for (const raw of String(s ?? '').split('\n')) {
    const ln = h('div', cls, parent), letters = [];
    for (const w of richWords(raw)) {
      if (w.br) continue;
      if (ln.childNodes.length) ln.appendChild(document.createTextNode(' '));
      const host = w.hl ? h('em', null, ln) : ln;
      for (const ch of Array.from(w.w.normalize('NFC'))) letters.push(h('span', null, host, esc(ch)));
    }
    if (maxW) fit(ln, maxW, 0.2);
    lines.push({ ln, letters });
  }
  return lines;
}
const fadeOut = (t, end, d = 0.3) => 1 - prog(t, end - d, d, E.inCubic);
// ---------- stacked lines of Vietnamese capitals ----------
// Marks reach 1.17 em above the baseline (Ỗ, Ẫ, Ế) and 0.26 em below it (Ọ, Ậ), so a fixed tight line-height lets the
// dot of one line land on the hat of the next ("GIỌNG / VIỆT"), and a fixed loose one leaves lines without such marks
// far apart. stackLines measures the real ink and adds space only where a mark below meets a mark above.
let _ink;
function inkOf(el, s) {
  const cs = getComputedStyle(el);
  _ink ??= document.createElement('canvas').getContext('2d');
  _ink.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
  if (cs.textTransform === 'uppercase') s = s.toUpperCase();
  const m = _ink.measureText(s);
  return { up: m.actualBoundingBoxAscent, down: m.actualBoundingBoxDescent, fa: m.fontBoundingBoxAscent, fd: m.fontBoundingBoxDescent, fs: parseFloat(cs.fontSize) };
}
// Ink of a line: per letter (x range + up/down) when it is made of one-letter spans (letterLines), else the whole text.
function lineInk(el) {
  const sp = [...el.querySelectorAll('span')].filter(s => Array.from(s.textContent).length === 1 && s.textContent.trim());
  const all = inkOf(el, el.textContent);
  if (!sp.length) return { ...all, parts: [{ x0: -1e9, x1: 1e9, up: all.up, down: all.down }] };
  return { ...all, parts: sp.map(s => { const r = s.getBoundingClientRect(), k = inkOf(s, s.textContent); return { x0: r.left, x1: r.right, up: k.up, down: k.down }; }) };
}
// Adds margin-top to each line after the first so that marks never touch (gap in em of the smaller line).
export function stackLines(els, gap = 0.1) {
  els = els.filter(Boolean);
  for (const e of els.slice(1)) e.style.marginTop = '';
  for (let i = 1; i < els.length; i++) {
    const A = lineInk(els[i - 1]), B = lineInk(els[i]);
    let need = 0;
    for (const a of A.parts) for (const c of B.parts) if (a.x1 > c.x0 && c.x1 > a.x0) need = Math.max(need, a.down + c.up);
    need += gap * Math.min(A.fs, B.fs);
    // baseline-to-baseline distance the CSS boxes give now
    const lh = e => { const v = parseFloat(getComputedStyle(e).lineHeight); return isNaN(v) ? parseFloat(getComputedStyle(e).fontSize) * 1.2 : v; };
    const pitch = lh(els[i - 1]) / 2 - (A.fa - A.fd) / 2 + lh(els[i]) / 2 + (B.fa - B.fd) / 2;
    if (need > pitch) els[i].style.marginTop = need - pitch + 'px';
  }
}
// Wrapped text of one element: a line-height that keeps the marks of consecutive lines apart (whole-text ink).
function safeLineHeight(el, min = 1.05, gap = 0.1) {
  const k = inkOf(el, el.textContent);
  el.style.lineHeight = Math.max(min, (k.up + k.down) / k.fs + gap);
}
// Big text behind the head: the head may cover only the lower ~35 % of the block, so the word stays readable.
// When the head is high in the frame the text shrinks (down to 60 %) to fit the room above it; y (0–1) overrides.
function placeBehindHead(blocks, f, H, y) {
  const top0 = H * 0.04, stack = () => blocks.forEach(b => stackLines([...b.querySelectorAll('.ln')]));
  stack();
  if (y == null) {
    const bh = Math.max(...blocks.map(b => b.offsetHeight)), room = (f.top - top0) / 0.65;
    const s = clamp(room / bh, 0.6, 1);
    if (s < 1) { for (const b of blocks) for (const ln of b.querySelectorAll('.ln')) ln.style.fontSize = parseFloat(getComputedStyle(ln).fontSize) * s + 'px'; stack(); }
  }
  const bh = Math.max(...blocks.map(b => b.offsetHeight));
  const yc = y != null ? y * H : clamp(f.top + bh * 0.35 - bh / 2, top0 + bh / 2, H * 0.6);
  for (const b of blocks) b.style.top = yc - b.offsetHeight / 2 + 'px';
}
const STAR = (r, n = 5) => Array.from({ length: n * 2 }, (_, i) => { const a = (i * Math.PI) / n - Math.PI / 2, q = i % 2 ? r * 0.45 : r; return `${(Math.cos(a) * q).toFixed(1)} ${(Math.sin(a) * q).toFixed(1)}`; }).join(' L');
// Doodles in face-width units (100 = face width), drawn from their anchor.
const DOODLES = {
  tia: [{ at: f => [f.cx - f.w * 0.66, f.cy - f.h * 0.22], d: 'M0 -20 L-24 -34 M2 0 L-28 0 M0 20 L-24 34' },
        { at: f => [f.cx + f.w * 0.66, f.cy - f.h * 0.22], d: 'M0 -20 L24 -34 M-2 0 L28 0 M0 20 L24 34' }],
  sao: [{ at: f => [f.cx - f.w * 0.74, f.top + f.h * 0.02], d: 'M' + STAR(15) + 'Z' },
        { at: f => [f.cx + f.w * 0.8, f.top + f.h * 0.14], d: 'M' + STAR(10) + 'Z' }],
  xoan: [{ at: f => [f.cx + f.w * 0.06, f.top - f.h * 0.2], d: 'M' + Array.from({ length: 60 }, (_, i) => { const a = i * 0.24, r = 2 + i * 0.3; return `${(Math.cos(a) * r).toFixed(1)} ${(Math.sin(a) * r * 0.55).toFixed(1)}`; }).join(' L') }],
  'vuong-mien': [{ at: f => [f.cx, f.top + f.h * 0.03], d: 'M-38 0 L-44 -36 L-21 -15 L0 -44 L21 -15 L44 -36 L38 0 Z' }],
  tim: [{ at: f => [f.cx + f.w * 0.78, f.cy - f.h * 0.62], d: 'M0 14 C-26 -4 -16 -24 0 -12 C16 -24 26 -4 0 14 Z' }],
  'dau-hoi': [{ at: f => [f.cx + f.w * 0.72, f.top - f.h * 0.02], d: 'M-10 -14 C-10 -30 14 -30 14 -14 C14 -4 2 -2 2 8 M2 20 L2 21' }],
};

// ---------- wave 2 helpers ----------
const AV_COLORS = ['#ff7a59', '#7c5cff', '#00b894', '#0984e3', '#e84393', '#e17055'];
// Round avatar with the first letter of a name (no photos of real people).
function avatar(parent, name, size) {
  const s = String(name ?? '?').replace(/\*/g, '').trim(), a = h('div', 'fx-av', parent, esc((Array.from(s)[0] || '?').toUpperCase()));
  let n = 0; for (const ch of s) n = (n * 31 + ch.charCodeAt(0)) | 0;
  a.style.background = AV_COLORS[Math.abs(n) % AV_COLORS.length];
  if (size) a.style.fontSize = 0.9 * size + 'em';
  return a;
}
// Readable text colour on top of the theme accent (yellow accent → dark text).
function onAccent(node, v = '--fx-accent') {
  const c = getComputedStyle(node).getPropertyValue(v).trim(), m = c.match(/^#([0-9a-f]{6})$/i);
  if (!m) return '#fff';
  const n = parseInt(m[1], 16), L = (0.299 * (n >> 16) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255;
  return L > 0.62 ? '#111' : '#fff';
}
// Image paths in params are relative to the PROJECT (the page lives in PROJ/fx/). "khung:12.5" = a still of the footage
// at 12.5 s, which dung-video-quay.py extracts to PROJ/work/khung_12.50.jpg before rendering.
export function imgSrc(s) {
  const m = String(s ?? '').match(/^khung:(\d+(?:\.\d+)?)$/);
  if (m) return `../work/khung_${(+m[1]).toFixed(2)}.jpg`;
  return /^(https?:|data:|\/|\.\.\/)/.test(s) ? s : '../' + s;
}
// 12500 → "12,5K" (the short form social apps use).
const fmtShort = v => (v >= 1e4 ? (v >= 1e6 ? (v / 1e6).toFixed(1) + 'M' : (v / 1e3).toFixed(1) + 'K').replace(/\.0(?=[KM])/, '').replace('.', ',') : fmtNum(Math.round(v)));
// Characters typed from `at` at `cps` per second into node (plain text), with an optional cursor element after it.
const typed = (node, text, t, at, cps) => { const ch = Array.from(String(text)), n = clamp(Math.floor((t - at) * cps), 0, ch.length); node.textContent = ch.slice(0, n).join(''); return n >= ch.length; };
const typeTicks = (text, at, cps, gain = 0.05) => Array.from(String(text)).filter((_, i) => i % 2 === 0).map((_, i) => ({ t: at + (i * 2) / cps, s: 'tick', gain, opts: { f: 3000 } }));
const PHONE_SVG = '<svg viewBox="0 0 24 24"><path d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25 11.4 11.4 0 0 0 3.6.57 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.57 3.57a1 1 0 0 1-.25 1z"/></svg>';
const SEARCH_SVG = '<svg viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21"/></svg>';
const SEND_SVG = '<svg viewBox="0 0 24 24"><path d="M3 11.5 20.5 4l-7.5 17.5-2.2-7.8z" fill="currentColor"/></svg>';
const CURSOR_SVG = '<svg viewBox="0 0 24 24"><path d="M4 2.5v17l4.6-4.3 3 6.6 2.9-1.3-3-6.5 6.3-.3z" fill="#fff" stroke="#111" stroke-width="1.4" stroke-linejoin="round"/></svg>';
// Jagged polygon (torn paper) for clip-path, in px of a w×h box.
function tornPath(w, h, amp, seed, sides = 'tb') {
  const r = rng(seed), n = Math.max(8, Math.round(w / (amp * 2.2))), pts = [];
  for (let i = 0; i <= n; i++) pts.push(`${(w * i) / n}px ${sides.includes('t') ? r() * amp : 0}px`);
  for (let i = n; i >= 0; i--) pts.push(`${(w * i) / n}px ${sides.includes('b') ? h - r() * amp : h}px`);
  return `polygon(${pts.join(',')})`;
}

// ---------- the effects ----------
// Each: dur (default length), enter, zones (preference), cues {name: default offset from start}, defaults, build().
// build(el, p, c) returns { seek(t), sounds: [{ t, s, gain?, opts? }] }. c = { start, end, cues, F, box, root }.
const ticks = (from, dur, n, gain = 0.05) => Array.from({ length: n }, (_, i) => ({ t: from + (dur * 0.8 * i) / n, s: 'tick', gain }));

export const FX = {
  'dem-so': {
    dur: 3.6, enter: 'pop', zones: ['giua', 'tren', 'duoi', 'phai', 'trai'], cues: { run: 0.35 },
    defaults: { label: 'Doanh thu năm nay', value: 650, from: 0, decimals: 0, prefix: '', unit: 'triệu', delta: '' },
    build(el, p, c) {
      el.classList.add('fx-card');
      h('div', 'fx-label', el, rich(p.label));
      const row = h('div', 'fx-row', el), num = h('span', 'fx-big', row);
      if (p.unit) h('span', 'fx-unit', row, rich(p.unit));
      num.textContent = p.prefix + fmtNum(p.value, p.decimals);
      fit(row, innerW(el));
      // No reserved width: the number grows from the left and the unit follows it (tabular digits, so it only
      // moves when a digit is added). Before the cue the number waits dimmed instead of showing a bare "0".
      const chip = p.delta ? h('div', 'fx-chip', el, esc(p.delta)) : null;
      const T = c.cues.run, D = 1.3;
      return {
        seek(t) {
          num.textContent = p.prefix + fmtNum(lerp(+p.from, +p.value, prog(t, T, D, E.outQuint)), p.decimals);
          const w = prog(t, T - 0.15, 0.15);
          num.style.opacity = 0.25 + 0.75 * w; num.style.transform = `scale(${0.85 + 0.15 * w})`; num.style.transformOrigin = '0 70%';
          if (chip) { const s = spring(t - (T + D - 0.25), { stiffness: 300, damping: 14 }); chip.style.transform = `scale(${s})`; chip.style.opacity = clamp(s * 3); }
        },
        sounds: [{ t: c.start, s: 'pop' }, ...ticks(T, D, 10), ...(chip ? [{ t: T + D - 0.25, s: 'pop', gain: 0.3 }] : [])],
      };
    },
  },

  'bieu-do-cot': {
    dur: 4, enter: 'rise', zones: ['giua', 'tren', 'phai', 'trai'], cues: { run: 0.4 },
    defaults: { title: 'Tăng trưởng qua các năm', unit: '', hl: -1, bars: [{ label: '2023', value: 40 }, { label: '2024', value: 65 }, { label: '2025', value: 120 }] },
    build(el, p, c) {
      el.classList.add('fx-card');
      if (p.title) h('div', 'fx-title', el, rich(p.title));
      const wrap = h('div', 'fx-bars', el), max = Math.max(...p.bars.map(b => +b.value)) || 1;
      const hl = p.hl < 0 ? p.bars.length + p.hl : p.hl;
      const cols = p.bars.map((b, i) => {
        const col = h('div', 'fx-col' + (i === hl ? ' hl' : ''), wrap);
        const v = h('b', null, col), bar = h('i', null, col); h('span', null, col, esc(b.label));
        bar.style.height = Math.max(4, (b.value / max) * 82) + '%';
        return { v, bar, val: +b.value };
      });
      const T = c.cues.run;
      return {
        seek(t) {
          cols.forEach((k, i) => {
            const q = prog(t, T + i * 0.2, 0.75, E.outCubic);
            k.bar.style.transform = `scaleY(${q})`;
            k.v.textContent = fmtNum(k.val * q) + (p.unit ? ' ' + p.unit : '');
            k.v.style.opacity = clamp(q * 4);
          });
        },
        sounds: cols.map((_, i) => ({ t: T + i * 0.2, s: 'pop', gain: 0.18 })),
      };
    },
  },

  'so-sanh': {
    dur: 4.2, enter: 'rise', zones: ['giua', 'tren', 'duoi'], cues: { left: 0.25, right: 1.2 },
    defaults: { left: { title: 'TRƯỚC', items: ['Làm thủ công', 'Mất 3 ngày'] }, right: { title: 'SAU', items: ['Tự động hoá', 'Chỉ 10 phút'] } },
    build(el, p, c) {
      el.classList.add('fx-card');
      const g = h('div', 'fx-cmp', el);
      const side = (cls, d, mark) => {
        const col = h('div', cls, g); fit(h('h4', null, col, esc(d.title)), (innerW(g) - 0.7 * parseFloat(getComputedStyle(g).fontSize)) / 2);
        return [...col.querySelectorAll('h4')].concat(d.items.map(s => h('p', null, col, `<s>${mark}</s><span>${rich(s)}</span>`)));
      };
      const L = side('l', p.left, '✕'), R = side('r', p.right, '✓');
      const show = (nodes, at, t) => nodes.forEach((n, i) => {
        const q = prog(t, at + i * 0.16, 0.4, E.outCubic);
        n.style.opacity = q; n.style.transform = `translateY(${(1 - q) * 0.6}em)`;
      });
      return {
        seek(t) { show(L, c.cues.left, t); show(R, c.cues.right, t); },
        sounds: [{ t: c.cues.left, s: 'tick', gain: 0.12 }, { t: c.cues.right, s: 'pop', gain: 0.25 }],
      };
    },
  },

  'danh-sach': {
    dur: 4.5, enter: 'rise', zones: ['giua', 'tren', 'duoi', 'phai', 'trai'], cues: { tick: 0.8 },
    defaults: { title: 'Việc cần làm', items: ['Xác định mục tiêu', 'Lập kế hoạch tài chính', 'Chọn gói bảo vệ phù hợp'] },
    build(el, p, c) {
      el.classList.add('fx-card');
      if (p.title) h('div', 'fx-title', el, rich(p.title));
      const rows = p.items.map((s, i) => {
        const r = h('div', 'fx-item', el), box = h('div', 'fx-box', r);
        const sv = svg('svg', { viewBox: '0 0 24 24' }, box);
        const path = svg('path', { d: 'M5 12.5l4.5 4.5L19.5 6.5', fill: 'none', stroke: 'var(--fx-accent)', 'stroke-width': 4, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', pathLength: 1, 'stroke-dasharray': 1 }, sv);
        const tx = h('span', null, r, rich(s));
        const at = c.cues['t' + (i + 1)] ?? c.cues.tick + i * 0.55;
        return { r, box, path, tx, at, show: c.start + 0.1 + i * 0.12 };
      });
      return {
        seek(t) {
          for (const k of rows) {
            const a = prog(t, k.show, 0.35); k.r.style.opacity = a; k.r.style.transform = `translateX(${(1 - a) * 1}em)`;
            const d = prog(t, k.at, 0.28, E.outCubic);
            k.path.setAttribute('stroke-dashoffset', 1 - d);
            k.box.style.borderColor = d > 0 ? 'var(--fx-accent)' : '';
            k.box.style.transform = `scale(${1 + 0.25 * Math.sin(Math.PI * clamp((t - k.at) / 0.25))})`;
          }
        },
        sounds: rows.map(k => ({ t: k.at, s: 'pop', gain: 0.22 })),
      };
    },
  },

  'tien-do': {
    dur: 3.6, enter: 'rise', zones: ['giua', 'duoi', 'tren'], cues: { run: 0.35 },
    defaults: { label: 'Mức độ hoàn thành', value: 75, note: '' },
    build(el, p, c) {
      el.classList.add('fx-card');
      const top = h('div', 'fx-row', el); top.style.justifyContent = 'space-between';
      h('div', 'fx-label', top, rich(p.label));
      const pct = h('b', null, top); pct.style.cssText = 'font-weight:900;font-size:1.4em;color:var(--fx-accent);font-variant-numeric:tabular-nums';
      const fill = h('div', 'fx-fill', h('div', 'fx-track', el));
      if (p.note) { const n = h('div', null, el, rich(p.note)); n.style.cssText = 'margin-top:.45em;font-weight:600;font-size:.7em;color:var(--fx-muted)'; }
      const T = c.cues.run;
      return {
        seek(t) { const q = prog(t, T, 1.4, E.inOutCubic) * p.value / 100; fill.style.transform = `scaleX(${q})`; pct.textContent = Math.round(q * 100) + '%'; },
        sounds: ticks(T, 1.4, 12, 0.04),
      };
    },
  },

  'vong-tron': {
    dur: 3.6, enter: 'pop', zones: ['giua', 'tren', 'phai', 'trai'], cues: { run: 0.35 },
    defaults: { value: 80, unit: '%', label: 'Khách hàng hài lòng' },
    build(el, p, c) {
      el.classList.add('fx-card'); el.style.textAlign = 'center';
      const wrap = h('div', null, el); wrap.style.cssText = 'position:relative;width:7em;height:7em;margin:.2em auto .4em';
      const sv = svg('svg', { viewBox: '0 0 200 200', style: 'width:100%;height:100%;transform:rotate(-90deg)' }, wrap);
      svg('circle', { cx: 100, cy: 100, r: 82, fill: 'none', stroke: 'var(--fx-track)', 'stroke-width': 20 }, sv);
      const arc = svg('circle', { cx: 100, cy: 100, r: 82, fill: 'none', stroke: 'var(--fx-accent)', 'stroke-width': 20, 'stroke-linecap': 'round', pathLength: 100, 'stroke-dasharray': '0 100' }, sv);
      const num = h('div', null, wrap); num.style.cssText = 'position:absolute;inset:0;display:grid;place-items:center;font-weight:900;font-size:1.9em;font-variant-numeric:tabular-nums';
      h('div', 'fx-label', el, rich(p.label));
      const T = c.cues.run;
      return {
        seek(t) { const q = prog(t, T, 1.4, E.outCubic); const v = p.value * q; arc.setAttribute('stroke-dasharray', `${Math.max(0.01, v)} 100`); num.textContent = Math.round(v) + p.unit; },
        sounds: [{ t: c.start, s: 'pop' }, ...ticks(T, 1.4, 10, 0.04)],
      };
    },
  },

  'moc-thoi-gian': {
    dur: 4.6, enter: 'rise', zones: ['giua', 'phai', 'trai', 'tren'], cues: { run: 0.3 },
    defaults: { title: '', items: [{ time: '2019', text: 'Thành lập' }, { time: '2022', text: '1.000 khách hàng' }, { time: '2025', text: 'Mở 20 chi nhánh' }] },
    build(el, p, c) {
      el.classList.add('fx-card');
      if (p.title) h('div', 'fx-title', el, rich(p.title));
      const tl = h('div', 'fx-tl', el), ln = h('div', 'ln', tl);
      const its = p.items.map(d => { const it = h('div', 'it', tl); const dot = h('div', 'dot', it); h('div', 'tm', it, esc(d.time)); h('div', 'tx', it, rich(d.text)); return { it, dot }; });
      const T = c.cues.run, step = 0.5;
      return {
        seek(t) {
          ln.style.transform = `scaleY(${prog(t, T, step * its.length, E.inOutCubic)})`;
          its.forEach((k, i) => {
            const at = T + i * step, q = prog(t, at, 0.4, E.outCubic), s = spring(t - at, { stiffness: 320, damping: 15 });
            k.it.style.opacity = q; k.it.style.transform = `translateX(${(1 - q) * 0.8}em)`; k.dot.style.transform = `scale(${s})`;
          });
        },
        sounds: its.map((_, i) => ({ t: T + i * step, s: 'tick', gain: 0.14 })),
      };
    },
  },

  'trich-dan': {
    dur: 5, enter: 'rise', zones: ['giua', 'tren', 'duoi'], cues: { on: 0.3 },
    defaults: { text: 'Chuẩn bị hôm nay là *bình an* ngày mai.', author: '' },
    build(el, p, c) {
      el.classList.add('fx-card', 'fx-q');
      h('div', 'mk', el, '“');
      const tx = h('div', 'tx', el);
      const spans = richWords(p.text).map(w => w.br ? (h('br', null, tx), null) : h('span', null, tx, w.hl ? `<em>${esc(w.w)}</em>` : esc(w.w))).filter(Boolean);
      const au = p.author ? h('div', 'au', el, '— ' + esc(p.author)) : null;
      const T = c.cues.on, per = Math.min(0.16, Math.max(0.05, (c.end - 1 - T) / spans.length));
      return {
        seek(t) {
          spans.forEach((s, i) => { const q = prog(t, T + i * per, 0.35, E.outCubic); s.style.opacity = q; s.style.transform = `translateY(${(1 - q) * 0.4}em)`; s.style.filter = q < 1 ? `blur(${(1 - q) * 6}px)` : 'none'; });
          if (au) au.style.opacity = prog(t, T + spans.length * per, 0.4);
        },
        sounds: [{ t: c.start, s: 'whoosh', gain: 0.15, opts: { dur: 0.3 } }],
      };
    },
  },

  'con-dau': {
    dur: 3, enter: 'none', zones: ['giua', 'tren', 'duoi'], cues: { hit: 0.35 },
    defaults: { text: 'Đã duyệt', sub: '', color: '', rotate: -9 },
    build(el, p, c) {
      el.style.textAlign = 'center';
      const st = h('div', 'fx-stamp', el, rich(p.text) + (p.sub ? `<small>${esc(p.sub)}</small>` : ''));
      st.style.color = p.color || 'var(--fx-accent2)'; st.style.fontSize = '2.6em';
      fit(st, c.box.w * 0.92);
      const H = c.cues.hit;
      return {
        seek(t) {
          const q = prog(t, H - 0.2, 0.2, E.inCubic), [sx, sy] = shake(t, H, 14, 0.35);
          st.style.opacity = t < H - 0.2 ? 0 : 0.92 * clamp(q * 1.5);
          st.style.transform = `translate(${sx}px,${sy}px) rotate(${p.rotate}deg) scale(${lerp(2.6, 1, q)})`;
        },
        sounds: [{ t: H, s: 'impact', gain: 0.55 }, { t: H, s: 'snare', gain: 0.3 }],
      };
    },
  },

  'go-chu': {
    dur: 4, enter: 'rise', zones: ['giua', 'tren', 'duoi'], cues: { on: 0.25 },
    defaults: { text: 'Bạn đã có *kế hoạch* cho gia đình chưa?', cps: 18, card: true },
    build(el, p, c) {
      if (p.card) el.classList.add('fx-card');
      const tw = h('div', 'fx-tw', el), chars = [];
      for (const w of richWords(p.text)) {
        if (w.br) { h('br', null, tw); continue; }
        const word = h('span', null, tw); word.style.whiteSpace = 'nowrap';
        for (const ch of Array.from(w.w.normalize('NFC'))) { const s = h('span', 'c', word, esc(ch)); if (w.hl) s.style.color = 'var(--fx-hl)'; chars.push(s); }
        chars.push(tw.appendChild(document.createTextNode(' ')) && null);
      }
      const cs = chars.filter(Boolean), cur = h('span', 'cur', tw), T = c.cues.on;
      let shown = -1;
      return {
        seek(t) {
          const n = clamp(Math.floor((t - T) * p.cps), 0, cs.length);
          if (n !== shown) { cs.forEach((s, i) => { s.style.visibility = i < n ? 'visible' : 'hidden'; }); (n ? cs[n - 1].parentNode : tw).insertBefore(cur, n ? cs[n - 1].nextSibling : tw.firstChild); shown = n; }
          cur.style.opacity = (n < cs.length && t >= T) || Math.floor(t * 2.2) % 2 === 0 ? 1 : 0;
        },
        sounds: cs.filter((_, i) => i % 2 === 0).map((_, i) => ({ t: T + (i * 2) / p.cps, s: 'tick', gain: 0.05, opts: { f: 3200 } })),
      };
    },
  },

  'chu-dap': {
    dur: 3, enter: 'none', zones: ['giua', 'tren', 'duoi'], cues: {},
    defaults: { lines: ['Không phải', '*may mắn*'], size: 2.6, gap: 0.38 },
    build(el, p, c) {
      const wrap = h('div', 'fx-free fx-sl', el);
      const ls = p.lines.map((s, i) => {
        const d = h('div', null, wrap, rich(s)); d.style.fontSize = p.size * (i === p.lines.length - 1 ? 1.15 : 1) + 'em';
        fit(d, c.box.w * 0.96);
        return { d, at: c.cues['l' + (i + 1)] ?? c.start + 0.12 + i * p.gap };
      });
      return {
        seek(t) {
          let sx = 0, sy = 0;
          for (const k of ls) {
            const q = prog(t, k.at - 0.16, 0.16, E.inCubic), s = spring(t - k.at, { stiffness: 420, damping: 18 });
            k.d.style.opacity = t < k.at - 0.16 ? 0 : clamp(q * 2);
            k.d.style.transform = `scale(${t < k.at ? lerp(2.4, 1, q) : 1 + 0.06 * (1 - s) * -1})`;
            k.d.style.filter = q < 1 && t < k.at ? `blur(${(1 - q) * 8}px)` : 'none';
            const [a, b] = shake(t, k.at, 9, 0.25, 11); sx += a; sy += b;
          }
          wrap.style.transform = `translate(${sx}px,${sy}px)`;
        },
        sounds: ls.map(k => ({ t: k.at, s: 'kick', gain: 0.7 })),
      };
    },
  },

  'the-ten': {
    dur: 4, enter: 'none', zones: ['duoi-trai'], cues: {},
    defaults: { name: 'Nguyễn Văn An', role: 'Chuyên gia hoạch định tài chính' },
    build(el, p, c) {
      const lt = h('div', 'fx-lt', el), bar = h('div', 'bar', lt), bd = h('div', 'bd', lt);
      const nm = h('div', 'nm', bd, rich(p.name)), rl = h('div', 'rl', bd, rich(p.role));
      fit(rl, c.box.w * 0.9); fit(nm, c.box.w * 0.9);
      const S = c.start, X = c.end - 0.45;
      return {
        seek(t) {
          const out = prog(t, X, 0.4, E.inCubic);
          bar.style.transform = `scaleY(${prog(t, S, 0.3, E.outExpo) * (1 - prog(t, X + 0.2, 0.25))})`;
          nm.style.clipPath = `inset(0 ${(1 - prog(t, S + 0.12, 0.45, E.outExpo) + out) * 100}% 0 0)`;
          rl.style.clipPath = `inset(0 ${(1 - prog(t, S + 0.3, 0.45, E.outExpo) + out) * 100}% 0 0)`;
        },
        sounds: [{ t: S + 0.3, s: 'whoosh', gain: 0.18, opts: { dur: 0.35 } }],
      };
    },
    noExit: true,
  },

  'mui-ten': {
    dur: 3, enter: 'none', full: true, cues: { draw: 0.2 },
    defaults: { from: null, to: null, label: '', bend: 0.28, width: 0 },
    build(el, p, c) {
      const { w: W, h: H } = c.F, sw = p.width || Math.min(W, H) * 0.014;
      const A = p.from || { x: W * 0.22, y: H * 0.68 }, B = p.to || { x: W * 0.55, y: H * 0.42 };
      const dx = B.x - A.x, dy = B.y - A.y, L = Math.hypot(dx, dy);
      const C = { x: (A.x + B.x) / 2 - dy * p.bend, y: (A.y + B.y) / 2 + dx * p.bend };
      const sv = svg('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}`, style: 'position:absolute;inset:0;overflow:visible' }, el);
      const st = { fill: 'none', stroke: 'var(--fx-accent)', 'stroke-width': sw, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', pathLength: 1, 'stroke-dasharray': 1, style: 'filter:drop-shadow(0 3px 6px rgba(0,0,0,.35))' };
      const body = svg('path', { ...st, d: `M${A.x} ${A.y} Q${C.x} ${C.y} ${B.x} ${B.y}` }, sv);
      const ang = Math.atan2(B.y - C.y, B.x - C.x), hl = Math.min(L * 0.18, sw * 5);
      const pt = da => `${B.x - hl * Math.cos(ang + da)} ${B.y - hl * Math.sin(ang + da)}`;
      const head = svg('path', { ...st, d: `M${pt(0.55)} L${B.x} ${B.y} L${pt(-0.55)}` }, sv);
      let lab = null;
      if (p.label) {
        lab = h('div', 'fx-card', el, rich(p.label));
        lab.style.cssText += `position:absolute;font-weight:800;font-size:${Math.min(W, H) * 0.042}px;padding:.3em .7em;white-space:nowrap;top:${A.y}px;transform-origin:50% 0`;
        const lw = lab.offsetWidth, m = Math.min(W, H) * 0.04;
        lab.style.left = clamp(A.x, lw / 2 + m, W - lw / 2 - m) + 'px';
      }
      const D = c.cues.draw;
      return {
        seek(t) {
          body.setAttribute('stroke-dashoffset', 1 - prog(t, D, 0.5, E.inOutCubic));
          head.setAttribute('stroke-dashoffset', 1 - prog(t, D + 0.45, 0.18, E.outCubic));
          const o = 1 - prog(t, c.end - 0.3, 0.3); sv.style.opacity = o;
          if (lab) { const s = spring(t - c.start, { stiffness: 260, damping: 16 }); lab.style.opacity = o * clamp(s * 3); lab.style.transform = `translate(-50%, ${sw * 1.2}px) scale(${0.6 + 0.4 * s})`; }
        },
        sounds: [{ t: D + 0.5, s: 'whoosh', gain: 0.2, opts: { dur: 0.4 } }],
      };
    },
    noExit: true,
  },

  'khoanh-tron': {
    dur: 3, enter: 'none', full: true, cues: { draw: 0.2 },
    defaults: { target: null, label: '', width: 0, seed: 5 },
    build(el, p, c) {
      const { w: W, h: H } = c.F, sw = p.width || Math.min(W, H) * 0.011;
      const T = p.target || { x: W * 0.3, y: H * 0.35, w: W * 0.4, h: H * 0.12 };
      const cx = T.x + T.w / 2, cy = T.y + T.h / 2, rx = T.w / 2 + sw * 3, ry = T.h / 2 + sw * 3, r = rng(p.seed);
      const pts = [], N = 90, a0 = -2.6;
      for (let i = 0; i <= N; i++) {
        const a = a0 + (i / N) * Math.PI * 2 * 1.12, k = 1 + (r() - 0.5) * 0.03 + 0.06 * (i / N);
        pts.push(`${(cx + Math.cos(a) * rx * k).toFixed(1)} ${(cy + Math.sin(a) * ry * k).toFixed(1)}`);
      }
      const sv = svg('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}`, style: 'position:absolute;inset:0;overflow:visible' }, el);
      const path = svg('path', { d: 'M' + pts.join(' L'), fill: 'none', stroke: 'var(--fx-accent2)', 'stroke-width': sw, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', pathLength: 1, 'stroke-dasharray': 1, style: 'filter:drop-shadow(0 3px 6px rgba(0,0,0,.3))' }, sv);
      let lab = null;
      if (p.label) {
        lab = h('div', 'fx-free', el, rich(p.label));
        const below = cy + ry + sw * 4 + Math.min(W, H) * 0.06 < H * 0.74;
        lab.style.cssText += `position:absolute;font-size:${Math.min(W, H) * 0.05}px;left:${cx}px;top:${below ? cy + ry + sw * 3 : cy - ry - sw * 3}px;white-space:nowrap;transform:translate(-50%,${below ? 0 : -100}%)`;
      }
      const D = c.cues.draw;
      return {
        seek(t) {
          path.setAttribute('stroke-dashoffset', 1 - prog(t, D, 0.55, E.inOutCubic));
          const o = 1 - prog(t, c.end - 0.3, 0.3); sv.style.opacity = o;
          if (lab) lab.style.opacity = o * prog(t, D + 0.45, 0.3);
        },
        sounds: [{ t: D + 0.3, s: 'whoosh', gain: 0.14, opts: { dur: 0.5, from: 800, to: 3000 } }],
      };
    },
    noExit: true,
  },

  'gach-thay': {
    dur: 3.4, enter: 'none', zones: ['giua', 'tren', 'duoi'], cues: { strike: 0.6, swap: 1.15 },
    defaults: { old: 'Chi phí', new: 'Đầu tư', size: 2.4 },
    build(el, p, c) {
      const st = h('div', 'fx-free fx-st', el); st.style.fontSize = p.size + 'em';
      const old = h('div', 'old', st, rich(p.old)), line = h('div', 'line', old), nw = h('div', 'new', st, rich(p.new));
      fit(old, c.box.w * 0.9); fit(nw, c.box.w * 0.9);
      stackLines([old, nw], 0.12);
      return {
        seek(t) {
          const a = prog(t, c.start, 0.3);
          old.style.opacity = a * lerp(1, 0.55, prog(t, c.cues.swap, 0.3));
          line.style.transform = `rotate(-4deg) scaleX(${prog(t, c.cues.strike, 0.25, E.outCubic)})`;
          const s = spring(t - c.cues.swap, { stiffness: 260, damping: 13 });
          nw.style.opacity = clamp(s * 3); nw.style.transform = `translateY(${(1 - s) * -0.5}em) scale(${0.6 + 0.4 * s})`;
        },
        sounds: [{ t: c.cues.strike, s: 'whoosh', gain: 0.18, opts: { dur: 0.2, from: 1500, to: 6000 } }, { t: c.cues.swap, s: 'pop', gain: 0.3 }],
      };
    },
  },

  'thong-bao': {
    dur: 4, enter: 'none', zones: ['tren', 'giua'], cues: {},
    defaults: { notes: [{ app: 'Lịch hẹn', icon: 'L', color: '#0a84ff', title: 'Nhắc lịch', msg: 'Gặp khách hàng lúc 9:00', time: 'bây giờ' }] },
    build(el, p, c) {
      const ns = p.notes.slice(0, 3).map((d, i) => {
        const n = h('div', 'fx-card fx-nt', el), ic = h('div', 'ic', n, esc(d.icon || (d.app || '?')[0]));
        ic.style.background = d.color || 'var(--fx-accent)';
        const bd = h('div', 'bd', n);
        h('div', 'hd', bd, `<span>${esc(d.app)}</span><span>${esc(d.time || 'bây giờ')}</span>`);
        if (d.title) h('div', 'tt', bd, rich(d.title));
        h('div', 'ms', bd, rich(d.msg));
        return { n, at: c.cues['n' + (i + 1)] ?? c.start + 0.15 + i * 0.7 };
      });
      return {
        seek(t) {
          for (const k of ns) {
            const s = spring(t - k.at, { stiffness: 240, damping: 19 });
            k.n.style.opacity = clamp((t - k.at) / 0.12); k.n.style.transform = `translateY(${(1 - s) * -1.6}em) scale(${0.94 + 0.06 * s})`;
          }
          el.style.opacity = 1 - prog(t, c.end - 0.3, 0.3);
        },
        sounds: ns.flatMap(k => [{ t: k.at, s: 'pop', gain: 0.22 }, { t: k.at + 0.06, s: 'tick', gain: 0.08, opts: { f: 1800 } }]),
      };
    },
    noExit: true,
  },

  'binh-chon': {
    dur: 4.4, enter: 'rise', zones: ['giua', 'tren', 'phai', 'trai'], cues: { run: 0.6 },
    defaults: { question: 'Bạn đã có quỹ dự phòng chưa?', options: [{ text: 'Đã có', pct: 38 }, { text: 'Chưa có', pct: 62 }] },
    build(el, p, c) {
      el.classList.add('fx-card');
      h('div', 'fx-title', el, rich(p.question));
      const win = p.options.reduce((b, o, i) => (o.pct > p.options[b].pct ? i : b), 0);
      const ops = p.options.map((o, i) => {
        const r = h('div', 'fx-op' + (i === win ? ' win' : ''), el), bar = h('i', null, r);
        h('span', null, r, rich(o.text) + (i === win ? ' ✓' : '')); const b = h('b', null, r);
        return { bar, b, pct: +o.pct, r };
      });
      const T = c.cues.run;
      return {
        seek(t) {
          ops.forEach((k, i) => {
            const a = prog(t, c.start + 0.1 + i * 0.1, 0.35); k.r.style.opacity = a;
            const q = prog(t, T, 1.1, E.outCubic); k.bar.style.transform = `scaleX(${(k.pct / 100) * q})`; k.b.textContent = Math.round(k.pct * q) + '%';
          });
        },
        sounds: [{ t: T, s: 'whoosh', gain: 0.15, opts: { dur: 0.3 } }, { t: T + 1.1, s: 'pop', gain: 0.25 }],
      };
    },
  },

  'luu-y': {
    dur: 5, enter: 'rise', zones: ['duoi', 'giua', 'tren'], cues: {},
    defaults: { title: 'Lưu ý', text: 'Quyền lợi cụ thể phụ thuộc điều khoản hợp đồng. Vui lòng đọc kỹ trước khi tham gia.' },
    build(el, p, c) {
      el.classList.add('fx-card', 'fx-co');
      h('div', 'ic', el, '!');
      const bd = h('div', null, el); h('div', 'tt', bd, rich(p.title).toUpperCase()); h('div', 'tx', bd, rich(p.text));
      return { seek() {}, sounds: [{ t: c.start, s: 'tick', gain: 0.12, opts: { f: 1200 } }] };
    },
  },

  'bieu-do-tron': {
    dur: 4.4, enter: 'rise', zones: ['giua', 'tren', 'phai', 'trai'], cues: { run: 0.4 },
    defaults: { title: 'Phân bổ thu nhập', center: '', parts: [{ label: 'Chi tiêu', value: 50 }, { label: 'Tiết kiệm', value: 30 }, { label: 'Bảo vệ', value: 20 }] },
    build(el, p, c) {
      el.classList.add('fx-card');
      if (p.title) h('div', 'fx-title', el, rich(p.title));
      const row = h('div', 'fx-dn', el), sv = svg('svg', { viewBox: '0 0 200 200' }, row);
      if (p.center) { const ct = h('div', 'ctr', row, rich(p.center)); row.style.position = 'relative'; row.insertBefore(ct, sv); }
      const lg = h('div', 'lg', row), cols = ['var(--fx-accent)', 'var(--fx-accent2)', 'var(--fx-good)', 'var(--fx-muted)'];
      const tot = p.parts.reduce((s, x) => s + +x.value, 0) || 1;
      let acc = 0;
      const segs = p.parts.slice(0, 4).map((x, i) => {
        const pc = (x.value / tot) * 100, off = acc; acc += pc;
        const arc = svg('circle', { cx: 100, cy: 100, r: 72, fill: 'none', stroke: cols[i], 'stroke-width': 34, pathLength: 100, 'stroke-dasharray': '0 100', 'stroke-dashoffset': -off }, sv);
        const pr = h('p', null, lg); h('i', null, pr).style.background = cols[i]; h('span', null, pr, rich(x.label)); const b = h('b', null, pr);
        return { arc, pc, b, pr };
      });
      const T = c.cues.run;
      return {
        seek(t) {
          segs.forEach((k, i) => {
            const q = prog(t, T + i * 0.35, 0.55, E.outCubic);
            k.arc.setAttribute('stroke-dasharray', `${Math.max(0.01, k.pc * q - 0.6)} 100`);
            k.b.textContent = Math.round(k.pc * q) + '%'; k.pr.style.opacity = clamp(0.25 + q);
          });
        },
        sounds: segs.map((_, i) => ({ t: T + i * 0.35, s: 'pop', gain: 0.18 })),
      };
    },
  },

  'nhan-dan': {
    dur: 3, enter: 'pop', zones: ['tren', 'giua', 'duoi'], cues: {},
    defaults: { text: 'Gõ *1 lệnh*\nxong video', size: 1.9, rotate: -3, wiggle: false },
    build(el, p, c) {
      const wrap = h('div', 'fx-stk', el); wrap.style.fontSize = p.size + 'em';
      const lines = String(p.text).split('\n').map(s => { const sp = h('span', null, wrap, rich(s)); fit(sp, c.box.w * 0.95); return sp; });
      return {
        seek(t) { wrap.style.transform = `rotate(${p.rotate + (p.wiggle ? Math.sin(t * 9) * 1.2 : 0)}deg)`; lines.forEach((s, i) => { s.style.opacity = prog(t, c.start + i * 0.08, 0.15); }); },
        sounds: [{ t: c.start, s: 'pop', gain: 0.3 }],
      };
    },
  },

  // ===== talking-head effects: need a speaker on screen. layer 'sau' = drawn BEHIND the person (needs the person
  // matte, dung-video-quay.py makes it); the others follow the face track. =====
  'chu-sau-lung': {
    dur: 3.6, enter: 'none', full: true, layer: 'sau', loud: true, noExit: true, cues: {},
    defaults: { text: 'Bí quyết', texts: null, style: 'dac', color: '', size: 0.24, y: null },
    build(el, p, c) {
      const { w: W, h: H } = c.F, f = c.faceAvg(c.start, c.end);
      const texts = (p.texts?.length ? p.texts : [p.text]).slice(0, 4);
      const box = h('div', 'fx-bk' + (p.style === 'vien' ? ' vien' : ''), el);
      box.style.setProperty('--fx-bk-c', p.color || 'var(--fx-free)');
      const step = (c.end - c.start - 0.3) / texts.length;
      const groups = texts.map((s, i) => {
        const g = h('div', null, box); g.style.cssText = 'position:absolute;left:0;width:100%';
        g.style.fontSize = W * p.size + 'px';
        const lines = letterLines(g, s, 'ln', W * 0.94);
        lines.forEach(l => { l.ln.style.color = p.color || 'var(--fx-free)'; });
        const at = c.cues['d' + (i + 1)] ?? c.start + i * step;
        return { g, letters: lines.flatMap(l => l.letters), at };
      });
      groups.forEach((g, i) => { g.until = groups[i + 1]?.at ?? Infinity; });
      placeBehindHead(groups.map(g => g.g), f, H, p.y);
      return {
        seek(t) {
          box.style.transform = `scale(${1.05 - 0.05 * prog(t, c.start, c.end - c.start, E.linear)})`;
          box.style.opacity = fadeOut(t, c.end);
          for (const g of groups) {
            const on = t >= g.at - 0.001 && t < g.until + 0.2;
            g.g.style.display = on ? '' : 'none';
            if (!on) continue;
            const out = prog(t, g.until, 0.2, E.inCubic);
            g.g.style.opacity = 1 - out; g.g.style.transform = `scale(${1 - 0.12 * out})`;
            const n = g.letters.length, mid = (n - 1) / 2;
            g.letters.forEach((s, k) => {
              const q = spring(t - g.at - Math.abs(k - mid) * 0.035, { stiffness: 230, damping: 17 });
              s.style.opacity = clamp(q * 2); s.style.transform = `translateY(${(1 - q) * 0.45}em) scale(${0.7 + 0.3 * Math.min(q, 1.1)})`;
            });
          }
        },
        sounds: groups.flatMap((g, i) => [{ t: g.at, s: 'whoosh', gain: 0.2, opts: { dur: 0.35 } }, ...(i ? [] : [{ t: g.at + 0.12, s: 'kick', gain: 0.45 }])]),
      };
    },
  },

  'neon-sau-lung': {
    dur: 3.8, enter: 'none', full: true, layer: 'sau', loud: true, noExit: true, cues: { on: 0.15 },
    defaults: { text: 'Đột phá', color: '#ff2bd6', size: 0.17, toi: 0.45, y: null },
    build(el, p, c) {
      const { w: W, h: H } = c.F, f = c.faceAvg(c.start, c.end);
      const dim = p.toi > 0 ? h('div', 'fx-dim', el) : null;
      if (dim) Object.assign(dim.style, { width: W + 'px', height: H + 'px' });
      const box = h('div', 'fx-bk fx-neon', el);
      box.style.setProperty('--nc', p.color); box.style.fontSize = W * p.size + 'px';
      letterLines(box, p.text, 'ln', W * 0.92);
      placeBehindHead([box], f, H, p.y);
      const T = c.cues.on, N = 18;
      // flicker on: a fixed random on/off pattern for N frames, then a steady hum
      const pat = Array.from({ length: N }, (_, i) => (i > N - 4 ? 1 : rng(i * 7 + 3)() > 0.45 ? 1 : 0.12));
      const sounds = [{ t: c.start, s: 'whoosh', gain: 0.1, opts: { dur: 0.3, from: 200, to: 900 } }];
      pat.forEach((v, i) => { if (v === 1 && pat[i - 1] !== 1) sounds.push({ t: T + i / 30, s: 'tick', gain: 0.16, opts: { f: 160 } }); });
      return {
        seek(t) {
          const k = Math.floor((t - T) * 30), o = fadeOut(t, c.end);
          const lit = t < T ? 0 : k < N ? pat[k] : 0.94 + 0.06 * Math.sin(t * 37) * Math.sin(t * 11);
          box.style.opacity = lit * o;
          if (dim) dim.style.opacity = p.toi * prog(t, c.start, 0.35) * o;
        },
        sounds,
      };
    },
  },

  'chu-truot-sau': {
    dur: 4, enter: 'none', full: true, layer: 'sau', loud: true, noExit: true, cues: {},
    defaults: { text: 'Sáng tạo', rows: 3, speed: 0.22, size: 0.15, y: null, color: '' },
    build(el, p, c) {
      const { w: W, h: H } = c.F, f = c.faceAvg(c.start, c.end), fs = W * p.size, n = clamp(p.rows | 0, 1, 5);
      const yc = p.y != null ? p.y * H : clamp(f.top + f.h * 0.45, H * 0.08 + (n * fs * 1.45) / 2, H * 0.62);
      const text = String(p.text).replace(/\n/g, ' ') + ' • ';
      const k0 = (() => { const t = h('div', 'fx-mq', el); t.style.fontSize = fs + 'px'; const k = inkOf(t, text); t.remove(); return k; })();
      const pitch = Math.max(fs * 1.05, k0.down + k0.up + fs * 0.1);   // every row has the same text: Ọ of one row vs Ế of the next
      const rows = Array.from({ length: n }, (_, i) => {
        const r = h('div', 'fx-mq' + (i % 2 ? ' vien' : ''), el);
        r.style.setProperty('--fx-bk-c', p.color || 'var(--fx-free)');
        r.style.fontSize = fs + 'px'; r.style.top = yc - (n * pitch) / 2 + i * pitch + 'px';
        const unit = h('span', null, r, rich(String(p.text).replace(/\n/g, ' ')) + '&nbsp;•&nbsp;');
        const uw = unit.offsetWidth;
        for (let k = 0; k < Math.ceil((W * 2) / uw) + 1; k++) r.appendChild(unit.cloneNode(true));
        return { r, uw, dir: i % 2 ? 1 : -1, off: i * 0.37 };
      });
      return {
        seek(t) {
          const o = prog(t, c.start, 0.3) * fadeOut(t, c.end);
          for (const k of rows) {
            const x = (t - c.start) * p.speed * W * k.dir + k.off * k.uw, m = ((x % k.uw) + k.uw) % k.uw;
            k.r.style.transform = `translateX(${m - k.uw}px)`; k.r.style.opacity = o;
          }
        },
        sounds: [{ t: c.start, s: 'whoosh', gain: 0.18, opts: { dur: 0.6, from: 200, to: 2500 } }],
      };
    },
  },

  'hao-quang': {
    dur: 3.4, enter: 'none', full: true, noExit: true, cues: {},
    defaults: { color: '#ffd84a', sparkle: true },
    build(el, p, c) {
      const { w: W, h: H } = c.F, fa = c.faceAvg(c.start, c.end);
      const sv = svg('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}`, style: 'position:absolute;inset:0;overflow:visible' }, el);
      const glow = `drop-shadow(0 0 ${fa.w * 0.04}px ${p.color}) drop-shadow(0 0 ${fa.w * 0.1}px ${p.color})`;
      const ring = svg('ellipse', { fill: 'none', stroke: p.color, 'stroke-width': fa.w * 0.055, style: `filter:${glow}` }, sv);
      const core = svg('ellipse', { fill: 'none', stroke: '#fffbe6', 'stroke-width': fa.w * 0.016 }, sv);
      const stars = p.sparkle ? Array.from({ length: 5 }, (_, i) => svg('path', { d: 'M0 -1 L.22 -.22 L1 0 L.22 .22 L0 1 L-.22 .22 L-1 0 L-.22 -.22Z', fill: '#fff', style: `filter:drop-shadow(0 0 4px ${p.color})` }, sv)) : [];
      return {
        seek(t) {
          const f = c.face(t), s = spring(t - c.start, { stiffness: 150, damping: 13 }), o = clamp((t - c.start) / 0.15) * fadeOut(t, c.end);
          const rx = f.w * 0.43, ry = rx * 0.22, cx = f.cx, cy = f.top - ry * 1.5 - (1 - s) * f.h * 0.5 + Math.sin(t * 2.6) * f.h * 0.015;
          for (const e of [ring, core]) { e.setAttribute('cx', cx); e.setAttribute('cy', cy); e.setAttribute('rx', rx); e.setAttribute('ry', ry); }
          sv.style.opacity = o;
          stars.forEach((st, i) => {
            const a = -2.6 + i * 1.3, k = Math.max(0, Math.sin(t * 4.5 + i * 1.9)) * f.w * 0.07 * clamp(s);
            st.setAttribute('transform', `translate(${cx + Math.cos(a) * rx * 1.25} ${cy + Math.sin(a) * ry * 2.4}) scale(${k})`);
          });
        },
        sounds: [{ t: c.start, s: 'whoosh', gain: 0.14, opts: { dur: 0.5, from: 1500, to: 7000 } }, ...[0.35, 0.5, 0.62].map((d, i) => ({ t: c.start + d, s: 'tick', gain: 0.07, opts: { f: 3200 + i * 900 } }))],
      };
    },
  },

  'sticker-quanh-dau': {
    dur: 3.4, enter: 'none', full: true, noExit: true, cues: {},
    defaults: { items: ['🔥', 'Đỉnh!', '💯'], size: 1 },
    build(el, p, c) {
      const { w: W, h: H } = c.F;
      const SLOTS = [[-1.0, -0.55], [1.02, -0.62], [-1.12, 0.38], [1.12, 0.42], [0, -1.4]];
      const emoji = s => /^[\p{Extended_Pictographic}‍️\s]+$/u.test(s);
      const ks = p.items.slice(0, 5).map((s, i) => {
        const n = h('div', 'fx-sk ' + (emoji(s) ? 'emo' : 'txt'), el, emoji(s) ? esc(s) : rich(s));
        n.style.fontSize = (emoji(s) ? 3.4 : 1.45) * p.size + 'em';
        return { n, sl: SLOTS[i], rot: (i % 2 ? 9 : -8), at: c.cues['s' + (i + 1)] ?? c.start + 0.1 + i * 0.32, w: n.offsetWidth, h: n.offsetHeight };
      });
      return {
        seek(t) {
          const f = c.face(t), o = fadeOut(t, c.end);
          for (const k of ks) {
            const s = spring(t - k.at, { stiffness: 320, damping: 12 });
            const x = clamp(f.cx + k.sl[0] * f.w, k.w / 2 + 20, W - k.w / 2 - 20), y = clamp(f.cy + k.sl[1] * f.h + Math.sin(t * 2.2 + k.rot) * 6, k.h / 2 + 20, H * 0.72);
            k.n.style.opacity = t < k.at ? 0 : clamp(s * 3) * o;
            k.n.style.transform = `translate(${x - k.w / 2}px,${y - k.h / 2}px) rotate(${k.rot}deg) scale(${Math.max(0, s)})`;
          }
        },
        sounds: ks.map(k => ({ t: k.at, s: 'pop', gain: 0.26 })),
      };
    },
  },

  've-tay-quanh-dau': {
    dur: 3.4, enter: 'none', full: true, noExit: true, cues: {},
    defaults: { items: ['tia', 'sao'], color: '#ffffff', width: 0 },
    build(el, p, c) {
      const { w: W, h: H } = c.F, fa = c.faceAvg(c.start, c.end);
      const sv = svg('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}`, style: 'position:absolute;inset:0;overflow:visible;filter:drop-shadow(0 3px 5px rgba(0,0,0,.45))' }, el);
      const fid = 'fx-boil-' + Math.round(c.start * 100);
      sv.innerHTML = `<filter id="${fid}"><feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="1" seed="1"/><feDisplacementMap in="SourceGraphic" scale="${(fa.w * 0.025).toFixed(1)}"/></filter>`;
      const turb = sv.querySelector('feTurbulence');
      const g0 = svg('g', { filter: `url(#${fid})` }, sv);
      const sw = p.width || fa.w * 0.03;
      const parts = p.items.flatMap(k => DOODLES[k] || []).map((d, i) => {
        const g = svg('g', {}, g0);
        const path = svg('path', { d: d.d, fill: 'none', stroke: p.color, 'stroke-width': sw, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'vector-effect': 'non-scaling-stroke', pathLength: 1, 'stroke-dasharray': 1 }, g);
        return { g, path, at: d.at, t0: c.cues['v' + (i + 1)] ?? c.start + 0.08 + i * 0.16 };
      });
      return {
        seek(t) {
          const f = c.face(t), k = f.w / 100;
          turb.setAttribute('seed', 1 + (Math.floor(t * 8) % 4));
          sv.style.opacity = fadeOut(t, c.end);
          for (const q of parts) {
            const [x, y] = q.at(f);
            q.g.setAttribute('transform', `translate(${x} ${y}) scale(${k})`);
            q.path.setAttribute('stroke-dashoffset', 1 - prog(t, q.t0, 0.38, E.outCubic));
          }
        },
        sounds: parts.map(q => ({ t: q.t0, s: 'whoosh', gain: 0.09, opts: { dur: 0.22, from: 2000, to: 6000 } })),
      };
    },
  },

  'khoa-mat': {
    dur: 3.6, enter: 'none', full: true, noExit: true, cues: { lock: 0.5 },
    defaults: { label: '', sub: '', color: '' },
    build(el, p, c) {
      const { w: W, h: H } = c.F;
      const col = p.color || 'var(--fx-accent)';
      const sv = svg('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}`, style: 'position:absolute;inset:0;overflow:visible;filter:drop-shadow(0 2px 4px rgba(0,0,0,.4))' }, el);
      const br = svg('path', { fill: 'none', 'stroke-width': c.faceAvg(c.start, c.end).w * 0.028, 'stroke-linecap': 'square' }, sv);
      let lab = null;
      if (p.label) { lab = h('div', 'fx-lock', el, `<span class="nm">${rich(p.label)}</span>` + (p.sub ? `<span class="sb">${rich(p.sub)}</span>` : '')); lab.querySelector('.nm').style.background = col; }
      const L = c.cues.lock, lw = lab?.offsetWidth || 0, lh = lab?.offsetHeight || 0;
      return {
        seek(t) {
          const f = c.face(t), q = prog(t, c.start, L - c.start, E.outExpo), o = clamp((t - c.start) / 0.1) * fadeOut(t, c.end);
          const pulse = 1 + 0.08 * Math.sin(Math.PI * clamp((t - L) / 0.25)), k = lerp(2.3, 1, q) * pulse;
          const bw = f.w * 1.45 * k, bh = f.h * 1.55 * k, x0 = f.cx - bw / 2, y0 = f.cy - bh / 2 - f.h * 0.05, x1 = x0 + bw, y1 = y0 + bh, a = Math.min(bw, bh) * 0.2;
          br.setAttribute('d', `M${x0} ${y0 + a}V${y0}H${x0 + a}M${x1 - a} ${y0}H${x1}V${y0 + a}M${x1} ${y1 - a}V${y1}H${x1 - a}M${x0 + a} ${y1}H${x0}V${y1 - a}`);
          br.setAttribute('stroke', t >= L ? col : '#ffffff');
          br.setAttribute('transform', `rotate(${(1 - q) * 18} ${f.cx} ${f.cy})`);
          sv.style.opacity = o;
          if (lab) {
            const r = prog(t, L + 0.05, 0.35, E.outExpo), below = y1 + 16 + lh < H * 0.72;
            const ly = below ? y1 + 16 : y0 - 16 - lh;
            lab.style.transform = `translate(${clamp(f.cx - lw / 2, 20, W - lw - 20)}px,${ly}px)`;
            lab.style.clipPath = `inset(0 ${(1 - r) * 100}% 0 0)`; lab.style.opacity = o;
          }
        },
        sounds: [...[0, 0.12, 0.24, 0.36].map(d => ({ t: c.start + d * (L - c.start) / 0.5, s: 'tick', gain: 0.1, opts: { f: 2600 } })), { t: L, s: 'pop', gain: 0.3 }],
      };
    },
  },

  'mo-tron': {
    dur: 1.2, enter: 'none', full: true, noExit: true, cues: {},
    defaults: { mode: 'mo', color: '#000000', time: 0.75, ring: true },
    build(el, p, c) {
      const { w: W, h: H } = c.F;
      const sv = svg('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}`, style: 'position:absolute;inset:0' }, el);
      const mask = svg('path', { fill: p.color, 'fill-rule': 'evenodd' }, sv);
      const ring = p.ring ? svg('circle', { fill: 'none', stroke: 'var(--fx-accent)', 'stroke-width': W * 0.012 }, sv) : null;
      const D = p.time, open = p.mode !== 'dong', close = p.mode !== 'mo';
      return {
        seek(t) {
          const f = c.face(t), cx = f.cx, cy = f.cy;
          const R = Math.max(...[[0, 0], [W, 0], [0, H], [W, H]].map(([x, y]) => Math.hypot(x - cx, y - cy))) * 1.02;
          let k = 1;
          if (open) k = Math.min(k, prog(t, c.start, D, E.inOutCubic));
          if (close) k = Math.min(k, 1 - prog(t, c.end - D, D, E.inOutCubic));
          const r = Math.max(0, R * k);
          mask.setAttribute('d', `M0 0H${W}V${H}H0Z` + (r > 0.5 ? `M${cx - r} ${cy}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0Z` : ''));
          sv.style.display = k >= 0.999 ? 'none' : '';
          if (ring) { ring.setAttribute('cx', cx); ring.setAttribute('cy', cy); ring.setAttribute('r', r); ring.style.opacity = r > 2 && k < 0.98 ? 1 : 0; }
        },
        // kit.js whoosh peaks AT t (it starts dur earlier): peak when the circle is fully open / fully closed
        sounds: [...(open ? [{ t: c.start + D, s: 'whoosh', gain: 0.22, opts: { dur: D, from: 300, to: 3000 } }] : []),
                 ...(close ? [{ t: c.end, s: 'whoosh', gain: 0.22, opts: { dur: D, from: 3000, to: 300 } }] : [])],
      };
    },
  },

  // ===== wave 2: app-like UI. Generic look: never a real app's name, logo or layout as "proof". =====
  'khung-chat': {
    dur: 4.5, enter: 'rise', zones: ['giua', 'tren', 'duoi'], cues: {},
    defaults: { title: 'Lan', status: 'Đang hoạt động', messages: [{ from: 'ho', text: 'Mai anh rảnh không?' }, { from: 'minh', text: 'Rảnh nè, có gì vậy em?' }] },
    build(el, p, c) {
      el.classList.add('fx-card', 'fx-chat');
      const hd = h('div', 'hd', el); avatar(hd, p.title);
      const tt = h('div', null, hd); h('div', 'nm', tt, rich(p.title)); if (p.status) h('div', 'st', tt, '● ' + esc(p.status));
      const on = onAccent(el);
      let at = c.start + 0.3;
      const ms = p.messages.slice(0, 5).map((m, i) => {
        const mine = m.from === 'minh', row = h('div', 'row ' + (mine ? 'minh' : 'ho'), el), bb = h('div', 'bb', row, rich(m.text));
        if (mine) bb.style.color = on;
        const dots = mine ? null : h('div', 'dots', row, '<i></i><i></i><i></i>');
        const show = c.cues['m' + (i + 1)] ?? at + (mine ? 0.1 : 0.55);
        at = show + 0.75;
        return { bb, dots, show, mine };
      });
      return {
        seek(t) {
          for (const k of ms) {
            const s = spring(t - k.show, { stiffness: 320, damping: 20 });
            k.bb.style.opacity = t < k.show ? 0 : clamp(s * 3); k.bb.style.transform = `scale(${t < k.show ? 0.6 : 0.6 + 0.4 * s})`;
            if (k.dots) {
              k.dots.style.opacity = t >= k.show - 0.55 && t < k.show ? 1 : 0;
              [...k.dots.children].forEach((d, j) => { d.style.transform = `translateY(${-Math.max(0, Math.sin(t * 9 - j * 0.9)) * 0.28}em)`; });
            }
          }
        },
        sounds: ms.map(k => (k.mine ? { t: k.show, s: 'whoosh', gain: 0.1, opts: { dur: 0.15, from: 2000, to: 7000 } } : { t: k.show, s: 'pop', gain: 0.22 })),
      };
    },
  },

  'binh-luan': {
    dur: 4, enter: 'rise', zones: ['duoi', 'giua', 'tren'], cues: { like: 1.1 },
    defaults: { name: 'Minh Anh', text: 'Video hữu ích quá, cảm ơn chị!', likes: 128, time: '2 giờ' },
    build(el, p, c) {
      el.classList.add('fx-card', 'fx-cm');
      const top = h('div', 'top', el); avatar(top, p.name);
      const bd = h('div', null, top);
      h('div', 'nm', bd, rich(p.name) + (p.time ? `<span>${esc(p.time)}</span>` : '')); h('div', 'tx', bd, rich(p.text));
      const ft = h('div', 'ft', el), ht = h('span', 'ht', ft, '♥'), cnt = h('b', null, ft); h('span', null, ft, 'Trả lời');
      const L = c.cues.like, from = Math.max(0, p.likes - Math.min(24, p.likes));
      const x0 = ht.offsetLeft, y0 = ht.offsetTop, fs = parseFloat(getComputedStyle(ht).fontSize);   // offsetParent = el
      const fly = Array.from({ length: 7 }, (_, i) => ({ n: h('span', 'fx-fly', el, '♥'), at: L + i * 0.13, dx: (rng(i + 3)() - 0.5) * 2.4, s: 0.8 + rng(i + 9)() * 0.9 }));
      return {
        seek(t) {
          cnt.textContent = fmtShort(lerp(from, p.likes, prog(t, L, 1.1, E.outCubic)));
          ht.style.transform = `scale(${1 + 0.45 * Math.sin(Math.PI * clamp((t - L) / 0.3))})`;
          for (const k of fly) {
            const a = (t - k.at) / 1.3;
            k.n.style.opacity = a < 0 || a > 1 ? 0 : 1 - a * a;
            k.n.style.fontSize = fs * k.s + 'px';
            k.n.style.transform = `translate(${x0 + (Math.sin(a * 7 + k.dx) * 0.5 + k.dx * a) * fs}px,${y0 - a * 5 * fs}px) scale(${0.6 + 0.6 * Math.min(1, a * 4)})`;
          }
        },
        sounds: [{ t: c.start, s: 'pop', gain: 0.2 }, { t: L, s: 'pop', gain: 0.3 }, ...[0.15, 0.4, 0.65].map(d => ({ t: L + d, s: 'tick', gain: 0.06, opts: { f: 2600 } }))],
      };
    },
  },

  'cuoc-goi': {
    dur: 4, enter: 'drop', zones: ['tren', 'giua'], cues: {},
    defaults: { name: 'Mẹ', sub: 'Di động', label: 'Cuộc gọi đến' },
    build(el, p, c) {
      el.classList.add('fx-call');
      const tp = h('div', 'tp', el), aw = h('div', 'aw', tp), rings = [0, 1].map(() => h('i', null, aw)); avatar(aw, p.name, 1.7);
      const tx = h('div', null, tp); h('div', 'lb', tx, esc(p.label)); h('div', 'nm', tx, rich(p.name)); const sb = h('div', 'sb', tx, esc(p.sub));
      const bt = h('div', 'bt', el), no = h('span', 'no', bt, PHONE_SVG), yes = h('span', 'yes', bt, PHONE_SVG);
      const N = c.cues.nhan, stop = N ?? c.end;
      const sounds = [];
      for (let r = c.start + 0.2; r < stop - 0.2; r += 1.2) for (const d of [0, 0.09, 0.18, 0.4, 0.49, 0.58]) sounds.push({ t: r + d, s: 'tick', gain: 0.07, opts: { f: 1450 } });
      if (N != null) sounds.push({ t: N, s: 'pop', gain: 0.3 });
      return {
        seek(t) {
          const ringing = N == null || t < N, ph = (t - c.start - 0.2) % 1.2;
          c.root.style.transform = ringing && ph >= 0 && ph < 0.65 ? `rotate(${Math.sin(t * 95) * 1.3}deg)` : '';
          rings.forEach((r, i) => { const f = (t * 0.9 + i * 0.5) % 1; r.style.transform = `scale(${1 + f * 0.7})`; r.style.opacity = ringing ? 1 - f : 0; });
          if (!ringing) { sb.textContent = '00:' + String(Math.floor(t - N)).padStart(2, '0'); yes.style.transform = `scale(${1 + 0.18 * Math.sin(Math.PI * clamp((t - N) / 0.3))})`; no.style.opacity = 0.3; }
          else { sb.textContent = p.sub; no.style.opacity = 1; yes.style.transform = `scale(${1 + 0.06 * Math.sin(t * 8)})`; }
        },
        sounds,
      };
    },
  },

  'trinh-duyet': {
    dur: 4.6, enter: 'rise', zones: ['giua', 'tren', 'duoi'], cues: { go: 0.3 },
    defaults: { url: 'tenmien.vn/bai-viet', title: 'Tiêu đề trang', text: 'Đoạn mô tả ngắn hiện ra khi trang tải xong.', cps: 22 },
    build(el, p, c) {
      el.classList.add('fx-card', 'fx-br'); el.style.padding = '0';
      const bar = h('div', 'bar', el); h('div', 'fx-dts', bar, '<i></i><i></i><i></i>');
      const ad = h('div', 'ad', bar); h('b', null, ad, 'https://'); const u = h('span', null, ad), cur = h('span', 'fx-cur', ad);
      const ld = h('div', 'ld', el), pg = h('div', 'pg', el);
      const parts = [h('div', 'ti', pg, rich(p.title)), h('div', 'tx', pg, rich(p.text)), h('div', 'sk', pg), h('div', 'sk', pg)];
      const T = c.cues.go, L = T + Array.from(p.url).length / p.cps + 0.15, D = 0.6;
      return {
        seek(t) {
          const done = typed(u, p.url, t, T, p.cps);
          cur.style.opacity = !done || Math.floor(t * 2.2) % 2 === 0 ? (t < L ? 1 : 0) : 0;
          ld.style.transform = `scaleX(${prog(t, L, D, E.inOutCubic)})`; ld.style.opacity = 1 - prog(t, L + D, 0.2);
          parts.forEach((n, i) => { const q = prog(t, L + D * 0.6 + i * 0.12, 0.35); n.style.opacity = q; n.style.transform = `translateY(${(1 - q) * 0.5}em)`; });
        },
        sounds: [...typeTicks(p.url, T, p.cps), { t: L + D, s: 'pop', gain: 0.2 }],
      };
    },
  },

  'terminal': {
    dur: 4.6, enter: 'rise', zones: ['giua', 'tren', 'duoi'], cues: { go: 0.3 },
    defaults: { title: 'terminal', lines: [{ cmd: 'dựng video clip-1.mp4' }, { out: '✔ Đã cắt 12 chỗ vấp' }, { out: '✔ Xuất *video.mp4*' }], cps: 20 },
    build(el, p, c) {
      el.classList.add('fx-tm');
      const bar = h('div', 'bar', el); h('div', 'fx-dts', bar, '<i></i><i></i><i></i>'); h('span', null, bar, esc(p.title));
      const bd = h('div', 'bd', el);
      let at = c.cues.go;
      const ls = p.lines.slice(0, 6).map((l, i) => {
        const n = h('div', 'ln', bd), cue = c.cues['l' + (i + 1)];
        if (cue != null) at = cue;
        if (l.cmd != null) {
          n.innerHTML = '<span class="pr">❯</span> '; const tx = h('span', null, n), cur = h('span', 'fx-cur', n);
          const k = { n, tx, cur, cmd: l.cmd, at, end: at + Array.from(l.cmd).length / p.cps }; at = k.end + 0.3; return k;
        }
        n.className = 'ln o'; n.innerHTML = rich(l.out); const k = { n, at }; at += 0.3; return k;
      });
      return {
        seek(t) {
          const last = ls.filter(k => k.cmd != null && k.at <= t).at(-1);   // the cursor sits on the latest command
          for (const k of ls) {
            k.n.style.visibility = t >= k.at ? 'visible' : 'hidden';
            if (k.cmd == null) continue;
            typed(k.tx, k.cmd, t, k.at, p.cps);
            k.cur.style.display = k === last ? '' : 'none';
            k.cur.style.opacity = t < k.end || Math.floor(t * 2.2) % 2 === 0 ? 1 : 0;
          }
        },
        sounds: ls.flatMap(k => (k.cmd != null ? typeTicks(k.cmd, k.at, p.cps, 0.05) : [{ t: k.at, s: 'tick', gain: 0.08, opts: { f: 1200 } }])),
      };
    },
  },

  'hoa-don': {
    dur: 4.6, enter: 'none', zones: ['giua', 'tren'], cues: { print: 0.3 },
    defaults: { title: 'HOÁ ĐƠN', items: [{ name: 'Gói cơ bản', price: '199.000đ' }, { name: 'Phí giao hàng', price: '0đ' }], total: '199.000đ', note: 'Cảm ơn quý khách!' },
    build(el, p, c) {
      el.classList.add('fx-rc');
      h('div', 'sl', el); const wr = h('div', 'wr', el), pp = h('div', 'pp', wr);
      h('div', 't', pp, rich(p.title)); h('div', 'hr', pp);
      for (const it of p.items.slice(0, 6)) { const r = h('div', 'r', pp); h('span', null, r, rich(it.name)); h('i', null, r); h('b', null, r, esc(it.price)); }
      h('div', 'hr', pp);
      const tr = h('div', 'r tot', pp); h('span', null, tr, 'TỔNG'); h('i', null, tr); h('b', null, tr, esc(p.total));
      if (p.note) h('div', 'nt', pp, rich(p.note));
      const W0 = pp.offsetWidth, H0 = pp.offsetHeight, n = 22, tw = W0 / n, pts = ['0 0', `${W0}px 0`];
      for (let i = n; i >= 0; i--) pts.push(`${i * tw}px ${H0 - (i % 2 ? tw * 0.5 : 0)}px`);
      pp.style.clipPath = `polygon(${pts.join(',')})`;
      const T = c.cues.print, D = 0.4 + 0.18 * (p.items.length + 4);
      return {
        seek(t) {
          const q = prog(t, T, D, E.linear), qs = Math.floor(q * 24) / 24;   // stepped, like a printer
          pp.style.transform = `translateY(${-(1 - qs) * 100}%)`;
          el.style.opacity = 1 - prog(t, c.end - 0.3, 0.3);
        },
        sounds: Array.from({ length: Math.floor(D / 0.06) }, (_, i) => ({ t: T + i * 0.06, s: 'tick', gain: 0.045, opts: { f: 900 + (i % 3) * 120 } })),
      };
    },
    noExit: true,
  },

  'theo-doi': {
    dur: 4, enter: 'rise', zones: ['giua', 'tren', 'duoi'], cues: { bam: 1.7 },
    defaults: { name: 'Gabee Studio', handle: '@gabee', followers: 12500, posts: 86, following: 120, button: 'Theo dõi', done: 'Đang theo dõi' },
    build(el, p, c) {
      el.classList.add('fx-card', 'fx-pf');
      const rw = h('div', 'rw', el); avatar(rw, p.name, 1.5);
      const nm = h('div', null, rw); h('div', 'nm', nm, rich(p.name)); h('div', 'hd', nm, esc(p.handle));
      const st = h('div', 'stt', el), stat = (v, l) => { const d = h('div', null, st), b = h('b', null, d, fmtShort(v)); h('span', null, d, esc(l)); return b; };
      stat(p.posts, 'bài viết'); const fb = stat(p.followers, 'người theo dõi'); stat(p.following, 'đang theo dõi');
      const btn = h('div', 'btn', el, esc(p.button)), on = onAccent(el); btn.style.color = on;
      const cur = h('div', 'cur', el, CURSOR_SVG);
      const B = c.cues.bam, bx = btn.offsetLeft + btn.offsetWidth * 0.62, by = btn.offsetTop + btn.offsetHeight * 0.45, em1 = parseFloat(getComputedStyle(el).fontSize);
      return {
        seek(t) {
          fb.textContent = fmtShort(lerp(p.followers * 0.9, p.followers, prog(t, c.start + 0.2, 1, E.outCubic)) + (t >= B ? 1 : 0));
          const m = prog(t, B - 0.65, 0.55, E.inOutCubic), click = Math.sin(Math.PI * clamp((t - B) / 0.18));
          cur.style.opacity = clamp((t - (B - 0.7)) / 0.15) * (1 - prog(t, B + 0.6, 0.3));
          cur.style.transform = `translate(${bx + (1 - m) * 4 * em1}px,${by + (1 - m) * 2.5 * em1}px) scale(${1 - 0.18 * click})`;
          const done = t >= B;
          btn.textContent = done ? '✓ ' + p.done : p.button;
          btn.style.background = done ? 'var(--fx-track)' : ''; btn.style.color = done ? 'var(--fx-ink)' : on;
          btn.style.transform = `scale(${1 - 0.05 * click})`;
        },
        sounds: [{ t: B, s: 'tick', gain: 0.2, opts: { f: 1800 } }, { t: B + 0.05, s: 'pop', gain: 0.28 }],
      };
    },
  },

  'tim-kiem': {
    dur: 4, enter: 'drop', zones: ['tren', 'giua'], cues: { go: 0.3 },
    defaults: { query: 'cách tiết kiệm mỗi tháng', suggestions: ['cách tiết kiệm mỗi tháng 5 triệu', 'cách tiết kiệm cho người mới đi làm'], cps: 18 },
    build(el, p, c) {
      el.classList.add('fx-sr');
      const bar = h('div', 'fx-card bar', el); bar.insertAdjacentHTML('beforeend', SEARCH_SVG);
      const q = h('div', 'q', bar), qt = h('span', null, q), cur = h('span', 'fx-cur', q);
      const dd = h('div', 'fx-card dd', el);
      const its = p.suggestions.slice(0, 4).map((s, i) => {
        const it = h('div', 'it' + (i ? '' : ' on'), dd); it.insertAdjacentHTML('beforeend', SEARCH_SVG);
        const k = fold(p.query), str = String(s);
        it.insertAdjacentHTML('beforeend', fold(str).startsWith(k) ? `<span>${esc(str.slice(0, p.query.length))}<b>${esc(str.slice(p.query.length))}</b></span>` : `<span>${rich(str)}</span>`);
        return it;
      });
      const T = c.cues.go, L = T + Array.from(p.query).length / p.cps;
      return {
        seek(t) {
          const done = typed(qt, p.query, t, T, p.cps);
          cur.style.opacity = !done || Math.floor(t * 2.2) % 2 === 0 ? 1 : 0;
          const o = prog(t, L - 0.2, 0.25); dd.style.opacity = o; dd.style.transform = `translateY(${(1 - o) * -0.4}em)`;
          its.forEach((it, i) => { it.style.opacity = prog(t, L - 0.1 + i * 0.1, 0.25); });
        },
        sounds: typeTicks(p.query, T, p.cps),
      };
    },
  },

  'danh-gia': {
    dur: 4, enter: 'rise', zones: ['giua', 'tren', 'duoi'], cues: { run: 0.35 },
    defaults: { stars: 5, text: 'Dùng 3 tháng rồi, rất đáng tiền!', name: 'Thu Hà', sub: 'Khách hàng' },
    build(el, p, c) {
      el.classList.add('fx-card', 'fx-rv');
      const row = h('div', 'sts', el), v = clamp(Math.round(p.stars * 2) / 2, 0, 5);
      const st = Array.from({ length: 5 }, (_, i) => { const s = h('span', 'st', row, '★'), f = h('i', null, s, '★'); f.style.width = clamp(v - i) * 100 + '%'; return { s, on: v - i > 0 }; });
      h('div', 'tx', el, '“' + rich(p.text) + '”');
      const au = h('div', 'au', el); avatar(au, p.name, 0.9); const nm = h('div', null, au); h('b', null, nm, rich(p.name)); if (p.sub) h('span', null, nm, esc(p.sub));
      const T = c.cues.run;
      return {
        seek(t) { st.forEach((k, i) => { const s = spring(t - T - i * 0.13, { stiffness: 380, damping: 13 }); k.s.style.transform = `scale(${t < T + i * 0.13 ? 0.5 : 0.5 + 0.5 * s})`; k.s.style.opacity = t < T + i * 0.13 ? 0.35 : 1; }); },
        sounds: st.filter(k => k.on).map((_, i) => ({ t: T + i * 0.13, s: 'tick', gain: 0.12, opts: { f: 2200 + i * 260 } })),
      };
    },
  },

  'cta-binh-luan': {
    dur: 4, enter: 'rise', zones: ['duoi', 'giua'], cues: { go: 0.5 },
    defaults: { label: 'Bình luận để nhận tài liệu', text: 'MUỐN', placeholder: 'Viết bình luận…', you: 'Bạn', cps: 8 },
    build(el, p, c) {
      el.classList.add('fx-cta');
      const on = onAccent(el);
      const lb = h('div', 'lb', el, rich(p.label)); lb.style.color = on;
      const bar = h('div', 'fx-card bar', el); avatar(bar, p.you);
      const f = h('div', 'f', bar), ph = h('span', 'ph', f, esc(p.placeholder)), tx = h('span', null, f), cur = h('span', 'fx-cur', f);
      const snd = h('div', 'snd', bar, SEND_SVG); snd.style.color = on;
      const ok = h('div', 'ok', el, '✓ Đã gửi');
      const T = c.cues.go, S = T + Array.from(p.text).length / p.cps + 0.3;
      return {
        seek(t) {
          typed(tx, p.text, t, T, p.cps);
          ph.style.display = t < T ? '' : 'none'; cur.style.display = t >= T && t < S ? '' : 'none';
          snd.style.transform = `scale(${1 + 0.3 * Math.sin(Math.PI * clamp((t - S) / 0.25))})`;
          if (t >= S + 0.1) { tx.textContent = ''; ph.style.display = ''; }
          const s = spring(t - S - 0.15, { stiffness: 300, damping: 15 }); ok.style.opacity = t < S + 0.15 ? 0 : clamp(s * 3); ok.style.transform = `scale(${t < S + 0.15 ? 0.6 : 0.6 + 0.4 * s})`;
        },
        sounds: [...typeTicks(p.text, T, p.cps, 0.07), { t: S, s: 'whoosh', gain: 0.15, opts: { dur: 0.2, from: 1500, to: 6000 } }, { t: S + 0.15, s: 'pop', gain: 0.25 }],
      };
    },
  },

  // ===== wave 2: paper and magazine =====
  'bia-tap-chi': {
    dur: 4, enter: 'none', full: true, noExit: true, cues: {},
    defaults: { title: 'TÂM AN', issue: 'SỐ 12 · THÁNG 11/2026', lines: ['*5* thói quen giữ tiền', 'Sống chậm giữa phố đông'], color: '#ffffff' },
    build(el, p, c) {
      const { w: W, h: H } = c.F;
      const ms = h('div', 'fx-mag', el, rich(p.title)); ms.style.color = p.color; ms.style.fontSize = W * 0.3 + 'px';
      ms.style.width = 'max-content'; fit(ms, W * 0.92, 0.3); ms.style.width = '100%'; ms.style.top = H * 0.035 + 'px';
      const is = h('div', 'fx-mag-i', el, `<i></i><span>${esc(p.issue)}</span><i></i>`); is.style.color = p.color; is.style.fontSize = W * 0.022 + 'px';
      is.style.top = H * 0.035 + ms.offsetHeight + W * 0.01 + 'px';
      const ls = p.lines.slice(0, 3).map((s, i) => {
        const l = h('div', 'fx-mag-l', el), parts = String(s).match(/^\*([^*]+)\*\s*(.*)$/);
        l.innerHTML = parts ? `<em>${esc(parts[1])}</em>${esc(parts[2])}` : rich(s);
        Object.assign(l.style, { left: W * 0.06 + 'px', width: W * 0.4 + 'px', fontSize: W * 0.042 + 'px', color: p.color });
        safeLineHeight(l);
        return l;
      });
      let y = H * 0.5;
      for (const l of ls) { l.style.top = y + 'px'; y += l.offsetHeight + W * 0.035; }
      const bc = svg('svg', { width: W * 0.13, height: W * 0.07, viewBox: '0 0 60 32', style: `position:absolute;right:${W * 0.06}px;top:${H * 0.85}px;background:#fff;padding:3px` }, el);
      const r = rng(7); for (let x = 2; x < 58; x += 1 + Math.floor(r() * 2)) if (r() > 0.35) svg('rect', { x, y: 2, width: r() > 0.6 ? 1.6 : 0.8, height: 28, fill: '#111' }, bc);
      return {
        seek(t) {
          const o = fadeOut(t, c.end), a = prog(t, c.start, 0.6, E.outExpo);
          ms.style.opacity = a * o; ms.style.transform = `translateY(${(1 - a) * -0.25}em)`; ms.style.clipPath = `inset(0 0 ${(1 - a) * 100}% 0)`;
          is.style.opacity = prog(t, c.start + 0.35, 0.3) * o;
          ls.forEach((l, i) => { const q = prog(t, c.start + 0.5 + i * 0.2, 0.45, E.outExpo); l.style.opacity = q * o; l.style.transform = `translateX(${(1 - q) * -1.5}em)`; });
          bc.style.opacity = prog(t, c.start + 0.9, 0.3) * o;
        },
        sounds: [{ t: c.start + 0.1, s: 'impact', gain: 0.35 }, ...ls.map((_, i) => ({ t: c.start + 0.5 + i * 0.2, s: 'whoosh', gain: 0.1, opts: { dur: 0.2 } }))],
      };
    },
  },

  'polaroid': {
    dur: 3.6, enter: 'none', zones: ['duoi', 'giua', 'tren'], cues: {},
    defaults: { img: 'khung:1', caption: 'Ngày đầu tiên', rotate: -5, ratio: 1 },
    build(el, p, c) {
      const pl = h('div', 'fx-pl', el); h('div', 'fx-tape', pl);
      const im = h('div', 'im', pl); im.style.aspectRatio = String(p.ratio || 1);
      const img = h('img', null, im); img.src = imgSrc(p.img);
      if (p.caption) h('div', 'cp', pl, rich(p.caption));
      return {
        seek(t) {
          const s = spring(t - c.start, { stiffness: 140, damping: 11 }), o = fadeOut(t, c.end);
          pl.style.opacity = clamp((t - c.start) / 0.12) * o;
          pl.style.transform = `translateY(${(1 - s) * -6}em) rotate(${p.rotate + (1 - s) * 14 + Math.sin(t * 1.7) * 0.6}deg)`;
        },
        sounds: [{ t: c.start + 0.05, s: 'whoosh', gain: 0.15, opts: { dur: 0.25 } }, { t: c.start + 0.3, s: 'snare', gain: 0.12 }],
      };
    },
    noExit: true,
  },

  'lich-xe': {
    dur: 3.8, enter: 'pop', zones: ['duoi', 'giua', 'tren'], cues: { run: 0.5 },
    defaults: { month: 'THÁNG 12', from: 1, to: 25, label: '', run: 1.6 },
    build(el, p, c) {
      const cal = h('div', 'fx-cal', el), hd = h('div', 'hd', cal, esc(p.month)); hd.style.color = onAccent(el);
      const pg = h('div', 'pg bot', cal), num = h('b', null, pg);
      const fl = h('div', 'pg fl', cal), fnum = h('b', null, fl); fl.style.top = hd.offsetHeight + 'px';
      const lab = p.label ? h('div', 'fx-free fx-cal-l', el, rich(p.label)) : null;
      const N = Math.abs(p.to - p.from), dir = Math.sign(p.to - p.from) || 1, T = c.cues.run, D = p.run;
      const tk = Array.from({ length: N }, (_, k) => T + D * (1 - Math.cbrt(1 - (k + 1) / N)));   // outCubic: fast, then slow
      return {
        seek(t) {
          let k = 0; while (k < N && tk[k] <= t) k++;
          num.textContent = p.from + dir * k;
          const a = k ? (t - tk[k - 1]) / 0.4 : 1;
          fl.style.display = a < 1 ? '' : 'none';
          if (a < 1) { fnum.textContent = p.from + dir * (k - 1); fl.style.transform = `translateY(${a * a * 6}em) rotate(${a * 25}deg)`; fl.style.opacity = 1 - a; }
          if (lab) { const s = spring(t - (T + D), { stiffness: 260, damping: 14 }); lab.style.opacity = t < T + D ? 0 : clamp(s * 3); lab.style.transform = `scale(${0.6 + 0.4 * Math.max(0, s)})`; }
        },
        sounds: [...tk.filter((_, i) => i % Math.ceil(N / 14) === 0).map(t => ({ t, s: 'tick', gain: 0.07, opts: { f: 1600 } })), ...(lab ? [{ t: T + D, s: 'pop', gain: 0.28 }] : [])],
      };
    },
  },

  'storyboard': {
    dur: 4.6, enter: 'rise', zones: ['giua', 'tren', 'duoi'], cues: {},
    defaults: { title: '', panels: [{ text: 'Quay' }, { text: 'Cắt' }, { text: 'Đăng' }] },
    build(el, p, c) {
      el.classList.add('fx-card', 'fx-sb');
      if (p.title) h('div', 'fx-title', el, rich(p.title));
      const ps = p.panels.slice(0, 4), g = h('div', 'g', el);
      g.style.gridTemplateColumns = `repeat(${ps.length === 4 ? 2 : ps.length},1fr)`;
      const pn = ps.map((d, i) => {
        const n = h('div', 'pn', g), fr = h('div', 'fr', n);
        if (d.img) { const im = h('img', null, fr); im.src = imgSrc(d.img); } else h('b', null, fr, String(i + 1).padStart(2, '0'));
        h('div', 'cp', n, rich(d.text));
        return { n, at: c.cues['p' + (i + 1)] ?? c.start + 0.3 + i * 0.6 };
      });
      return {
        seek(t) {
          pn.forEach((k, i) => {
            const q = prog(t, k.at, 0.35, E.outCubic); k.n.style.opacity = 0.15 + 0.85 * q; k.n.style.transform = `translateY(${(1 - q) * 0.6}em)`;
            k.n.classList.toggle('on', t >= k.at && t < (pn[i + 1]?.at ?? c.end));
          });
        },
        sounds: pn.map(k => ({ t: k.at, s: 'tick', gain: 0.14, opts: { f: 1500 } })),
      };
    },
  },

  'giay-xe': {
    dur: 3.6, enter: 'none', zones: ['duoi', 'tren', 'giua'], cues: {},
    defaults: { text: 'Bắt đầu từ *hôm nay*', sub: '', color: '#fff7e6', rotate: -2 },
    build(el, p, c) {
      el.style.textAlign = 'center';
      const wr = h('div', 'fx-tp', el); wr.style.display = 'inline-block';
      const s = h('div', 's', wr); s.style.background = p.color;
      const tx = h('div', 'tx', s, rich(p.text)); if (p.sub) h('div', 'sb', s, rich(p.sub));
      fit(tx, c.box.w * 0.84);
      s.style.clipPath = tornPath(s.offsetWidth, s.offsetHeight, s.offsetHeight * 0.09, 11);
      return {
        seek(t) {
          const q = prog(t, c.start, 0.55, E.outExpo), o = fadeOut(t, c.end);
          wr.style.opacity = clamp(q * 3) * o; wr.style.transform = `translateX(${(1 - q) * -110}%) rotate(${p.rotate}deg)`;
        },
        sounds: [{ t: c.start + 0.05, s: 'whoosh', gain: 0.2, opts: { dur: 0.3, from: 400, to: 2500 } }],
      };
    },
    noExit: true,
  },

  'ghi-chu-dan': {
    dur: 4.2, enter: 'none', zones: ['giua', 'tren', 'duoi'], cues: {},
    defaults: { title: 'Ghi nhớ', items: ['Chi tiêu ít hơn thu nhập', 'Trích *10%* mỗi tháng'], color: '#ffe066', rotate: 3 },
    build(el, p, c) {
      const n = h('div', 'fx-nt2', el); n.style.background = p.color; h('div', 'fx-tape', n);
      const tt = h('div', 't', n, rich(p.title)), sv = svg('svg', { viewBox: '0 0 100 10', preserveAspectRatio: 'none' }, tt);
      const ul = svg('path', { d: 'M1 6 C 25 2, 50 9, 99 4', fill: 'none', stroke: '#d62d20', 'stroke-width': 3, 'stroke-linecap': 'round', pathLength: 1, 'stroke-dasharray': 1, 'vector-effect': 'non-scaling-stroke' }, sv);
      const its = p.items.slice(0, 5).map((s, i) => ({ n: h('div', 'it', n, rich(s)), at: c.cues['i' + (i + 1)] ?? c.start + 0.7 + i * 0.4 }));
      return {
        seek(t) {
          const s = spring(t - c.start, { stiffness: 220, damping: 14 }), o = fadeOut(t, c.end);
          n.style.opacity = clamp((t - c.start) / 0.1) * o; n.style.transform = `rotate(${p.rotate + (1 - s) * -8}deg) scale(${0.7 + 0.3 * s})`;
          ul.setAttribute('stroke-dashoffset', 1 - prog(t, c.start + 0.35, 0.35, E.outCubic));
          for (const k of its) { const q = prog(t, k.at, 0.3); k.n.style.opacity = q; k.n.style.transform = `translateX(${(1 - q) * 0.6}em)`; }
        },
        sounds: [{ t: c.start, s: 'pop', gain: 0.25 }, ...its.map(k => ({ t: k.at, s: 'tick', gain: 0.08, opts: { f: 2000 } }))],
      };
    },
    noExit: true,
  },

  // ===== wave 3: film overlays (the camera moves and colour looks themselves are footage passes: tao-video canh_may.py) =====
  'khung-dien-anh': {
    dur: 4, enter: 'none', full: true, noExit: true, cues: {},
    defaults: { visible: 0.62, text: '', color: '#000000', time: 0.5 },
    build(el, p, c) {
      const { w: W, h: H } = c.F, bh = (H * (1 - p.visible)) / 2;
      const top = h('div', 'fx-bar', el), bot = h('div', 'fx-bar', el);
      for (const b of [top, bot]) Object.assign(b.style, { height: bh + 'px', background: p.color, fontSize: W * 0.045 + 'px' });
      top.style.top = '0px'; bot.style.top = H - bh + 'px';
      const tx = p.text ? h('span', null, bot, rich(p.text)) : null;
      return {
        seek(t) {
          const q = prog(t, c.start, p.time, E.outCubic) * (1 - prog(t, c.end - p.time, p.time, E.inCubic));
          top.style.transform = `translateY(${-(1 - q) * 100}%)`; bot.style.transform = `translateY(${(1 - q) * 100}%)`;
          if (tx) tx.style.opacity = prog(t, c.start + p.time, 0.4) * (1 - prog(t, c.end - p.time - 0.2, 0.2));
        },
        sounds: [{ t: c.start + p.time, s: 'whoosh', gain: 0.14, opts: { dur: p.time, from: 200, to: 900 } }],
      };
    },
  },

  'may-quay-rec': {
    dur: 4, enter: 'none', full: true, noExit: true, cues: {},
    defaults: { label: 'REC', info: '4K · 30FPS', pin: 72 },
    build(el, p, c) {
      const { w: W, h: H } = c.F, m = W * 0.06, fs = W * 0.042;
      const sv = svg('svg', { width: W, height: H, viewBox: `0 0 ${W} ${H}`, style: 'position:absolute;inset:0;filter:drop-shadow(0 0 3px rgba(0,0,0,.5))' }, el);
      const L = W * 0.08, y0 = H * 0.08, y1 = H * 0.9;
      svg('path', { d: `M${m} ${y0 + L}V${y0}H${m + L}M${W - m - L} ${y0}H${W - m}V${y0 + L}M${W - m} ${y1 - L}V${y1}H${W - m - L}M${m + L} ${y1}H${m}V${y1 - L}`, fill: 'none', stroke: '#fff', 'stroke-width': W * 0.006 }, sv);
      svg('path', { d: `M${W / 2 - L * 0.3} ${H / 2}H${W / 2 + L * 0.3}M${W / 2} ${H / 2 - L * 0.3}V${H / 2 + L * 0.3}`, stroke: 'rgba(255,255,255,.6)', 'stroke-width': W * 0.003 }, sv);
      const hud = (x, y, html, right) => { const n = h('div', 'fx-hud', el, html); n.style.fontSize = fs + 'px'; n.style.top = y + 'px'; n.style[right ? 'right' : 'left'] = x + 'px'; return n; };
      const rec = hud(m + W * 0.03, y0 + W * 0.03, `<span class="dot"></span>${esc(p.label)}`);
      hud(m + W * 0.03, y0 + W * 0.03, `${clamp(p.pin, 0, 100) | 0}%<span class="fx-bat"><i style="width:${clamp(p.pin, 5, 100) * 0.0145}em"></i></span>`, true);
      const tc = hud(m + W * 0.03, y1 - W * 0.03 - fs * 1.3, '00:00:00:00');
      hud(m + W * 0.03, y1 - W * 0.03 - fs * 1.3, esc(p.info), true);
      const dot = rec.querySelector('.dot');
      return {
        seek(t) {
          const a = Math.max(0, t - c.start), fr = Math.floor(a * 30), ss = Math.floor(a);
          tc.textContent = `00:${String(Math.floor(ss / 60)).padStart(2, '0')}:${String(ss % 60).padStart(2, '0')}:${String(fr % 30).padStart(2, '0')}`;
          dot.style.opacity = Math.floor(a * 1.6) % 2 === 0 ? 1 : 0.15;
          el.style.opacity = clamp((t - c.start) / 0.15) * fadeOut(t, c.end, 0.2);
        },
        sounds: [{ t: c.start, s: 'tick', gain: 0.2, opts: { f: 1000 } }, { t: c.start + 0.08, s: 'tick', gain: 0.15, opts: { f: 1500 } }],
      };
    },
  },

  'light-leak': {
    dur: 2.2, enter: 'none', full: true, noExit: true, cues: {},
    defaults: { color: '#ff7a2f', color2: '#ffd36b', manh: 0.6 },
    build(el, p, c) {
      const { w: W, h: H } = c.F, D = c.end - c.start;
      const blobs = [[p.color, 1.2, 0], [p.color2, 0.8, 0.15], [p.color, 0.7, 0.35]].map(([col, sz, off]) => {
        const b = h('div', 'fx-leak', el), r = W * sz;
        Object.assign(b.style, { width: r + 'px', height: r * 1.3 + 'px', background: `radial-gradient(closest-side, ${col}, transparent)` });
        return { b, r, off };
      });
      return {
        seek(t) {
          const q = clamp((t - c.start) / D), env = Math.sin(Math.PI * q);
          blobs.forEach((k, i) => {
            const u = clamp(q * 1.2 - k.off * 0.5);
            k.b.style.opacity = p.manh * env * (i ? 0.8 : 1);
            k.b.style.transform = `translate(${-k.r * 0.6 + (W + k.r * 0.2) * u}px,${H * (0.05 + 0.25 * i) - k.r * 0.4 + H * 0.12 * u}px)`;
          });
        },
        sounds: [{ t: c.start + D * 0.45, s: 'whoosh', gain: 0.1, opts: { dur: D * 0.4, from: 300, to: 1500 } }],
      };
    },
  },

  'osd-vhs': {
    dur: 4, enter: 'none', full: true, noExit: true, cues: {},
    defaults: { text: 'PLAY ►', date: '26.11.2026', clock: '20:15:00' },
    build(el, p, c) {
      const { w: W, h: H } = c.F, fs = W * 0.055;
      const at = (x, y, s) => { const n = h('div', 'fx-osd', el, s); Object.assign(n.style, { left: x + 'px', top: y + 'px', fontSize: fs + 'px' }); return n; };
      const play = at(W * 0.07, H * 0.06, esc(p.text));
      at(W * 0.07, H * 0.855, esc(p.date));
      const clk = at(W * 0.07, H * 0.855 + fs * 1.25, ''), [hh, mm, s0] = String(p.clock).split(':').map(Number);
      return {
        seek(t) {
          const s = (hh * 3600 + mm * 60 + (s0 || 0) + Math.floor(Math.max(0, t - c.start))) % 86400;
          clk.textContent = [Math.floor(s / 3600), Math.floor(s / 60) % 60, s % 60].map(v => String(v).padStart(2, '0')).join(':');
          play.style.opacity = t - c.start < 2 ? (Math.floor((t - c.start) * 2.5) % 2 ? 0.25 : 1) : 1;
          el.style.opacity = clamp((t - c.start) / 0.1) * fadeOut(t, c.end, 0.15) * (0.9 + 0.1 * Math.sin(t * 50));
        },
        sounds: [{ t: c.start, s: 'tick', gain: 0.18, opts: { f: 700 } }],
      };
    },
  },
};

// ---------- create ----------
// spec: { type, start, end?, cues?, params?, zone? | box? {x,y,w,a}, avoid? [{x,y,w,h}], theme?, format {w,h} }
export function createFx(stage, spec) {
  injectCSS();
  const def = FX[spec.type];
  if (!def) throw new Error(`fx: unknown type "${spec.type}" (use ${Object.keys(FX).join(', ')})`);
  const F = spec.format || { w: stage.offsetWidth, h: stage.offsetHeight };
  const face = faceFn(spec, F);
  const p = { ...def.defaults, ...(spec.params || {}) };
  const start = +spec.start, end = spec.end != null ? +spec.end : start + def.dur;
  const cues = {};
  for (const k in def.cues) cues[k] = start + def.cues[k];
  for (const k in spec.cues || {}) if (typeof spec.cues[k] === 'number') cues[k] = spec.cues[k];

  const root = h('div', 'fx fx-' + spec.type, stage);
  const th = themeVars(spec.theme || 'kinh');
  for (const [k, v] of Object.entries(th)) root.style.setProperty('--fx-' + k.replace(/[A-Z]/g, m => '-' + m.toLowerCase()), v);
  const inner = h('div', 'fx-in', root);

  let box, api;
  const em = b => b.size || b.w / (F.h > F.w ? 17 : 20); // 1 em = 1/17 (9:16) or 1/20 of the box width
  const build = b => {
    inner.innerHTML = ''; inner.className = 'fx-in'; inner.removeAttribute('style');
    Object.assign(root.style, { left: b.x + 'px', top: b.y + 'px', width: b.w + 'px', fontSize: em(b) + 'px' });
    return def.build(inner, p, { start, end, cues, F, box: b, root, face, faceAvg: (a, z) => faceAvg(face, a, z) });
  };
  if (def.full) {
    box = { x: 0, y: 0, w: F.w, a: 'top', size: Math.min(F.w, F.h) / 24 };
    root.style.height = F.h + 'px';
    api = build(box);
  } else {
    const Z = zones(F);
    const prefs = [...new Set([spec.zone, ...(def.zones || ['giua']), ...Object.keys(Z).filter(z => z !== 'duoi-trai')])].filter(z => z && Z[z]);
    box = spec.box || Z[prefs[0] || 'giua'];
    api = build(box);
    const hEm = root.offsetHeight / em(box);           // height in em: the same in any zone
    const top = b => { const ht = hEm * em(b); return b.a === 'center' ? b.y - ht / 2 : b.a === 'bottom' ? b.y - ht : b.y; };
    if (!spec.box && spec.avoid?.length) {
      // try every zone at full size, then smaller (close-ups leave little room); else the least overlap, smallest size
      const scaled = (b, s) => (s === 1 ? b : { ...b, x: b.x + (b.w * (1 - s)) / 2, w: b.w * s });
      const rect = b => ({ x: b.x, y: top(b), w: b.w, h: hEm * em(b) });
      const area = b => spec.avoid.reduce((sum, r) => { const q = rect(b), w = Math.min(q.x + q.w, r.x + r.w) - Math.max(q.x, r.x), h = Math.min(q.y + q.h, r.y + r.h) - Math.max(q.y, r.y); return sum + (w > 0 && h > 0 ? w * h : 0); }, 0);
      const cands = [1, 0.85, 0.72].flatMap(s => prefs.map(z => scaled(Z[z], s)));
      const pick = cands.find(b => area(b) === 0) || cands.slice(-prefs.length).sort((p, q) => area(p) - area(q))[0];
      if (pick && pick !== box) { box = pick; api = build(box); }
    }
    root.style.top = top(box) + 'px';
  }

  const fx = {
    type: spec.type, root, start, end, cues, box,
    layer: spec.layer || def.layer || 'truoc',   // 'sau' = behind the speaker (composited under the person matte)
    loud: !!def.loud,                            // big free text: the subtitle steps aside while it is up
    rect: () => ({ x: root.offsetLeft, y: root.offsetTop, w: root.offsetWidth, h: root.offsetHeight }),
    sounds: (api.sounds || []).filter(s => s.t >= start - 0.6 && s.t <= end),
    seek(t) {
      const on = t >= start - 0.001 && t <= end;
      root.style.display = on ? '' : 'none';
      if (!on) return;
      if (!def.noExit || def.enter !== 'none') enterExit(inner, def.enter, t, start, def.noExit ? Infinity : end);
      api.seek(t);
    },
  };
  fx.seek(start - 1);
  return fx;
}

// ---------- sound ----------
export const fxSounds = list => list.flatMap(f => f.sounds);
// Plays fx sounds with kit.js `sfx` (import { sfx } from './kit.js'). Missing names fall back to 'pop'.
export function playFxSounds(ctx, out, sfx, list, { gain = 1 } = {}) {
  for (const e of list) {
    if (e.t < 0.02) continue;
    const o = { ...(e.opts || {}), gain: (e.gain ?? 0.25) * gain };
    // sounds that build up before t (whoosh, riser) must not start before 0: Web Audio throws on a negative start
    if ((e.s === 'whoosh' || e.s === 'riser') && e.t - (o.dur ?? (e.s === 'riser' ? 2 : 0.5)) < 0) o.dur = Math.max(0.05, e.t - 0.01);
    (sfx[e.s] || sfx.pop)(ctx, out, e.t, o);
  }
}

// ---------- cues from spoken words ----------
// Words: voice-timing.py lines [{ words: [[w, t], ...] }] or flat [{ w|word|text, s|start, e|end }].
export function flattenWords(data) {
  if (!Array.isArray(data)) data = data?.words || [];
  if (data.length && Array.isArray(data[0]?.words)) return data.flatMap(l => l.words.map(([w, s]) => ({ w, s })));
  return data.map(x => ({ w: x.w ?? x.word ?? x.text, s: +(x.s ?? x.start), e: +(x.e ?? x.end) }));
}
export const fold = s => String(s ?? '').toLowerCase().replace(/đ/g, 'd').normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^\p{L}\p{N}%]+/gu, ' ').trim();
// Time of the first occurrence of `phrase` (one or more words) in [from, to).
export function findWord(words, phrase, from = 0, to = Infinity) {
  const toks = fold(phrase).split(' ').filter(Boolean);
  if (!toks.length) return null;
  const fw = words.map(x => fold(x.w));
  for (let i = 0; i < words.length; i++) {
    if (words[i].s < from - 0.05 || words[i].s >= to) continue;
    if (toks.every((tk, j) => fw[i + j] === tk)) return words[i].s;
  }
  return null;
}
// Value forms: 12.4 (absolute s) | "12.4" | "+0.8" (after base) | "word or phrase" (spoken word).
export function resolveTime(v, words, from, to, base) {
  if (v == null) return null;
  if (typeof v === 'number') return v;
  const s = String(v).trim();
  if (/^[+-]\d/.test(s)) return base + parseFloat(s);
  if (/^\d+(\.\d+)?$/.test(s)) return parseFloat(s);
  return findWord(words, s, from, to);
}
// plan.fx items -> numbers. start/end may be words; cues are searched between start and end.
export function resolvePlan(items, words = []) {
  const W = flattenWords(words), warnings = [];
  const out = items.map((it, n) => {
    const r = { ...it, cues: {} };
    const lo = resolveTime(it.from ?? 0, W, 0, Infinity, 0) ?? 0;
    r.start = resolveTime(it.start, W, lo, Infinity, lo);
    if (r.start == null) { warnings.push(`#${n + 1} ${it.type}: không thấy từ bắt đầu "${it.start}"`); r.start = lo; }
    const def = FX[it.type];
    r.end = it.end != null ? resolveTime(it.end, W, r.start, Infinity, r.start) : null;
    if (it.end != null && r.end == null) warnings.push(`#${n + 1} ${it.type}: không thấy từ kết thúc "${it.end}"`);
    if (r.end == null) r.end = r.start + (def?.dur || 3.5);
    for (const [k, v] of Object.entries(it.cues || {})) {
      const t = resolveTime(v, W, r.start, r.end + 0.01, r.start);
      if (t == null) warnings.push(`#${n + 1} ${it.type}: cue "${k}" không thấy từ "${v}" trong đoạn ${r.start.toFixed(2)}–${r.end.toFixed(2)}s`);
      else r.cues[k] = t;
    }
    return r;
  });
  return { items: out, warnings };
}

// ---------- spoken text: tokens, chunks, subtitles ----------
// Tokens of a voice-timing.py line with their spoken time. A token counts when it has a letter, digit or _
// (the rule voice-timing.py uses), so times stay aligned after a lone "%" or "–".
export function spokenTokens(line) {
  const ws = line.words || [], out = [];
  let j = 0, last = line.start;
  for (const raw of String(line.text).split(/\s+/).filter(Boolean)) {
    const counted = /[\p{L}\p{N}_]/u.test(raw), s = counted ? (ws[j++]?.[1] ?? last) : last;
    last = s; out.push({ raw, f: fold(raw), s });
  }
  return out;
}
// Greedy chunks ≤ max chars, preferring breaks after punctuation, never between the two words of a pair in
// `glue` (folded "a b" strings: compound words, highlighted phrases), and no orphan tail.
export function chunkTokens(toks, max, glue = []) {
  const out = []; let cur = [];
  const len = a => a.map(t => t.raw).join(' ').length;
  const glued = (a, b) => a && b && glue.some(g => g === a.f + ' ' + b.f || g.includes(a.f + ' ' + b.f));
  toks.forEach((t, k) => {
    if (cur.length && len([...cur, t]) > max && !glued(cur.at(-1), t)) { out.push(cur); cur = []; }
    cur.push(t);
    if (/[,.?!:;…]$/.test(t.raw) && len(cur) >= max * 0.45 && k < toks.length - 1) { out.push(cur); cur = []; }
  });
  if (cur.length) out.push(cur);
  if (out.length > 1 && len(out.at(-1)) < max * 0.35 && len([...out.at(-2), ...out.at(-1)]) <= max * 1.3) out.splice(-2, 2, [...out.at(-2), ...out.at(-1)]);
  return out;
}
const SUB_CSS = `
.fx-sub{position:absolute;left:0;right:0;display:flex;justify-content:center;pointer-events:none;z-index:20}
.fx-sub>div{font-family:var(--fx-font);white-space:nowrap;text-align:center}
.fx-sub.tiktok>div{font-weight:900;color:var(--fx-free);-webkit-text-stroke:.14em var(--fx-free-stroke);paint-order:stroke fill;text-shadow:0 .08em .3em rgba(0,0,0,.35);letter-spacing:-.01em}
.fx-sub.pill>div{font-weight:800;color:var(--fx-ink);background:var(--fx-card);padding:.22em .6em .28em;border-radius:.5em;box-shadow:0 .3em 1em rgba(0,0,0,.18)}
.fx-sub span{display:inline-block;transform-origin:50% 70%}
.fx-sub.tiktok span{margin:0 .1em}
`;
// lines = voice-timing.py output. style 'tiktok' (white + outline, current word in accent; for footage) or 'pill'.
// Returns { seek(t, visible = true) }.
export function createSubtitles(stage, lines, { F, theme = 'kinh', style = 'tiktok', max, y, size, highlight = [], glue = [] } = {}) {
  injectCSS();
  if (!document.getElementById('fx-sub-css')) { const s = h('style', null, document.head); s.id = 'fx-sub-css'; s.textContent = SUB_CSS; }
  F ??= { w: stage.offsetWidth, h: stage.offsetHeight };
  const V = F.h > F.w, th = themeVars(theme);
  const box = h('div', 'fx-sub ' + style, stage), inner = h('div', null, box);
  for (const [k, v] of Object.entries(th)) box.style.setProperty('--fx-' + k.replace(/[A-Z]/g, m => '-' + m.toLowerCase()), v);
  const fs = size || (style === 'tiktok' ? (V ? 66 : 54) : (V ? 50 : 40));
  inner.style.fontSize = fs + 'px';
  box.style.top = (y ?? (V ? F.h * 0.775 : F.h * 0.86)) - fs * 0.75 + 'px';   // centre of the subtitle band
  max ??= style === 'tiktok' ? (V ? 24 : 40) : (V ? 30 : 48);
  const HL = highlight.map(x => fold(x).split(' '));
  const G = [...glue, ...highlight.map(fold).filter(x => x.includes(' '))];
  const chunks = [];
  lines.forEach((line, li) => {
    const toks = spokenTokens(line), next = lines[li + 1];
    toks.forEach((t, k) => { t.hl = /\d/.test(t.f) || HL.some(p => { const i = p.indexOf(t.f); return i >= 0 && p.every((w, j) => toks[k - i + j]?.f === w); }); });
    const end = next ? Math.min(next.start - 0.05, line.end + 0.6) : line.end + 0.8;
    const cs = chunkTokens(toks.filter(t => t.f), max, G);
    cs.forEach((c, ci) => chunks.push({ toks: c, a: c[0].s - 0.08, b: cs[ci + 1] ? cs[ci + 1][0].s - 0.08 : end }));
  });
  let shown = null, spans = [];
  return {
    chunks,
    seek(t, visible = true) {
      const c = visible ? chunks.find(c => t >= c.a && t < c.b) : null;
      box.style.display = c ? '' : 'none';
      if (!c) return;
      if (shown !== c) {
        inner.innerHTML = ''; spans = c.toks.map((tk, i) => { if (i) inner.appendChild(document.createTextNode(' ')); const s = h('span', null, inner, esc(tk.raw)); return { s, tk }; });
        const maxW = F.w * 0.9; inner.style.transform = ''; const wdt = inner.scrollWidth;
        inner.dataset.k = wdt > maxW ? maxW / wdt : 1; shown = c;
      }
      const pop = spring(t - c.a, { stiffness: 420, damping: 22 });
      inner.style.transform = `scale(${inner.dataset.k * (0.88 + 0.12 * pop)})`;
      spans.forEach(({ s, tk }, i) => {
        const nextS = spans[i + 1]?.tk.s ?? c.b, now = t >= tk.s - 0.04 && t < nextS - 0.04, said = t >= tk.s - 0.04;
        if (style === 'tiktok') {
          s.style.color = now || tk.hl ? 'var(--fx-accent)' : '';
          s.style.opacity = said ? 1 : 0.78;
          s.style.transform = now ? `scale(${1 + 0.1 * spring(t - tk.s, { stiffness: 500, damping: 18 })})` : 'none';
        } else {
          s.style.color = said ? (tk.hl ? 'var(--fx-accent)' : 'var(--fx-ink)') : 'var(--fx-muted)';
        }
      });
    },
  };
}
