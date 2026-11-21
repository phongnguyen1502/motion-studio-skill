// fx.js — Motion Studio effect library: 20 reusable on-screen effects for talking-head and voiceover videos.
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
};

// ---------- create ----------
// spec: { type, start, end?, cues?, params?, zone? | box? {x,y,w,a}, avoid? [{x,y,w,h}], theme?, format {w,h} }
export function createFx(stage, spec) {
  injectCSS();
  const def = FX[spec.type];
  if (!def) throw new Error(`fx: unknown type "${spec.type}" (use ${Object.keys(FX).join(', ')})`);
  const F = spec.format || { w: stage.offsetWidth, h: stage.offsetHeight };
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
    return def.build(inner, p, { start, end, cues, F, box: b, root });
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
  for (const e of list) (sfx[e.s] || sfx.pop)(ctx, out, e.t, { ...(e.opts || {}), gain: (e.gain ?? 0.25) * gain });
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
