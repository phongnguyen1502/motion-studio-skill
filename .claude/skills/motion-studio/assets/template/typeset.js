// typeset.js — professional line breaking + smart justify for on-screen text (pure DOM, no deps).
//
// Rules (see references/typography.md):
//  1. Author line breaks with <br> at MEANING boundaries ("Sự chuyển biến tích cực của khách hàng<br>
//     mới là câu chuyện đáng kể"). The browser must never choose a break: every block becomes nowrap.
//  2. A block that is still too wide for its box is scaled down (font-size), never wrapped.
//  3. All lines of a block get the width of the longest line. A line is justified only when it already
//     fills ≥ 80 % of that width (last line ≥ 92 %) AND the extra space per word gap stays ≤ 0.22 em —
//     so you get straight edges without rivers of white space. Short lines stay left-aligned.
//
// Usage (call AFTER fonts are loaded, BEFORE registering animations — it rewrites innerHTML):
//   import { typeset, glue, subChunks } from './typeset.js';
//   typeset(sceneEl);                                  // all .h1 .h2 .h3 .card .tx .q p inside
//   typeset(sceneEl, { selector: '.title, .body' });   // or your own classes
//   subtitleEl.textContent = glue(text);               // keeps compound words together

export const DEFAULT_SELECTOR = '.h1, .h2, .h3, .card, .q p, .tx';

// Width available to `el`: the nearest ancestor with an inline px width, minus the paddings/borders in between.
function availWidth(el, fallback) {
  let pad = 0;
  for (let n = el; n && n !== document.body; n = n.parentElement) {
    const cs = getComputedStyle(n);
    if (n.dataset && n.dataset.maxw) return parseFloat(n.dataset.maxw) - pad;
    if (n.style && n.style.width && n.style.width.endsWith('px'))
      return parseFloat(n.style.width) - (n === el ? parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight) : pad);
    pad += parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight) + parseFloat(cs.borderLeftWidth) + parseFloat(cs.borderRightWidth);
  }
  return fallback;
}

export function typeset(root, { selector = DEFAULT_SELECTOR, fallbackWidth = 1640, fill = 0.8, lastFill = 0.92, maxGapEm = 0.22 } = {}) {
  const blocks = [...root.querySelectorAll(selector)];
  for (const el of blocks) {
    if (blocks.some(o => o !== el && el.contains(o))) continue;   // inner blocks are set on their own
    el.style.whiteSpace = 'nowrap';
    const avail = availWidth(el, fallbackWidth);
    const shrink = (w) => { if (w > avail) el.style.fontSize = (parseFloat(getComputedStyle(el).fontSize) * avail / w).toFixed(1) + 'px'; };
    if (!/<br\s*\/?>/i.test(el.innerHTML)) { shrink(el.scrollWidth); continue; }
    el.innerHTML = el.innerHTML.split(/<br\s*\/?>/i).map(p => `<span class="tl" style="white-space:nowrap">${p.trim()}</span>`).join('');
    const spans = [...el.querySelectorAll(':scope > .tl')];
    spans.forEach(sp => { sp.style.display = 'inline-block'; });
    let w = spans.map(sp => sp.scrollWidth);
    if (Math.max(...w) > avail) { shrink(Math.max(...w)); w = spans.map(sp => sp.scrollWidth); }
    const W = Math.ceil(Math.max(...w)) + 2;
    spans.forEach((sp, i) => {
      const last = i === spans.length - 1, r = w[i] / W;
      sp.style.display = 'block'; sp.style.width = W + 'px';
      const gaps = (sp.textContent.trim().match(/\s+/g) || []).length, fs = parseFloat(getComputedStyle(sp).fontSize);
      const extra = gaps ? (W - w[i]) / gaps : Infinity;
      if (((!last && r >= fill) || (last && r >= lastFill)) && extra <= maxGapEm * fs) { sp.style.textAlign = 'justify'; sp.style.textAlignLast = 'justify'; }
    });
  }
}

// Vietnamese compound words that must never be split across lines (subtitles, auto-wrapped text).
// Extend per project with domain terms.
export const KEEP_VI = ['khách hàng', 'sản phẩm', 'câu chuyện', 'cảm xúc', 'tích cực', 'giải pháp', 'nguyên nhân', 'kết quả', 'giá trị', 'tính năng', 'bảo hiểm', 'nhân thọ', 'thời gian', 'gia đình', 'vấn đề', 'thu nhập', 'tài chính', 'dự phòng', 'người dùng', 'bán hàng', 'chúng ta', 'đặc tính', 'an tâm', 'tự tin', 'thoải mái', 'tự hào', 'chủ động', 'cuộc sống', 'điều khoản', 'hợp đồng', 'quyền lợi', 'mức phí', 'thực tại', 'hiệu quả', 'công việc', 'biến cố', 'rủi ro', 'chi trả', 'cha mẹ', 'học hành', 'người thân', 'nhẹ nhàng', 'mệt mỏi', 'tư duy', 'kiến tạo', 'trình bày', 'giới thiệu', 'phương pháp', 'thuận lợi', 'dễ dàng', 'tiết kiệm', 'hoàn thành', 'nhận diện', 'nhu cầu', 'thay đổi', 'mong muốn', 'tiếp tục', 'phù hợp', 'kế hoạch', 'quan trọng', 'chuẩn bị', 'bảo vệ', 'phạm vi', 'điều kiện', 'khác biệt', 'nổi bật', 'đáng nhớ', 'công thức', 'hoàn toàn', 'xây dựng', 'chuyển biến', 'ý nghĩa', 'hoạt động', 'câu hỏi', 'tưởng tượng', 'xảy ra', 'cần thiết', 'hữu ích', 'đào tạo', 'tư vấn', 'doanh nghiệp', 'thị trường', 'chiến lược', 'mục tiêu', 'năng lực', 'kỹ năng', 'hiệu suất', 'lợi ích', 'ưu đãi', 'bí quyết', 'bình an', 'đầu tư', 'dự phòng', 'tài sản', 'mục tiêu', 'chi phí', 'theo dõi'];
export function glue(text, keep = KEEP_VI) {
  const re = new RegExp('(' + [...keep].sort((a, b) => b.length - a.length).map(k => k.replace(/ /g, '\\s')).join('|') + ')', 'giu');
  return text.replace(re, m => m.replace(/\s/g, ' '));
}

// Split a long voiced line into subtitle chunks (≤ maxChars) at punctuation near the middle,
// timed from word timestamps. `line` = { text, start, end, words: [[word, t], ...] } (see scripts/voice-timing.py).
export function subChunks(line, maxChars = 92) {
  const toks = line.text.split(/\s+/), ws = line.words || [];
  const timeOf = k => (toks.length === ws.length ? ws[k][1] : line.start + (line.end - line.start) * k / toks.length);
  const out = [];
  const rec = (i0, i1) => {
    const text = toks.slice(i0, i1).join(' ');
    if (text.length <= maxChars || i1 - i0 < 8) { out.push({ k: i0, text }); return; }
    const mid = (i0 + i1) / 2; let best = -1, bs = 1e9;
    for (let k = i0 + 3; k < i1 - 3; k++) {
      const punct = /[,.:;]$/.test(toks[k - 1]);
      const sc = Math.abs(k - mid) * (punct ? 1 : 3) + (punct ? 0 : 4);
      if (sc < bs) { bs = sc; best = k; }
    }
    rec(i0, best); rec(best, i1);
  };
  rec(0, toks.length);
  return out.map(c => ({ t: c.k === 0 ? line.start : timeOf(c.k) - 0.05, text: c.text }));
}
