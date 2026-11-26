#!/usr/bin/env node
// fx-suggest.mjs — voiceover sentences -> a DRAFT effect plan the agent then finishes by hand.
//
//   node fx-suggest.mjs <timing.json> [--out fx-plan.json] [--theme sach] [--per-min 10] [--voice voice.mp3] [--nguoi]
//
// --nguoi: the video shows the speaker (talking head) — also suggest the effects behind the person / around the face.
// timing.json = scripts/voice-timing.py output. For every line it scores the 20 effects of assets/fx/hieu-ung.json
// (trigger words, numbers, lists, "không phải … mà là", questions, hook/CTA position), keeps the best lines up to
// --per-min effects per minute, never repeats an effect back to back nor puts two heavy ones together, and guesses cues
// from the spoken words. It does NOT write the content: every item gets `_dien` (what to fill) and `_loi` (the line).
// The agent must fill `params` from what is actually said, adjust picks/cues, then delete `_dien`.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const { fold } = await import(new URL('../assets/fx/fx.js', import.meta.url));
const CAT = JSON.parse(fs.readFileSync(path.join(HERE, '../assets/fx/hieu-ung.json'), 'utf8'));
const TYPES = Object.keys(CAT).filter(k => !k.startsWith('_'));

const argv = process.argv.slice(2), arg = (k, d) => { const i = argv.indexOf('--' + k); return i >= 0 ? argv[i + 1] : d; };
const src = argv.find((a, i) => !a.startsWith('--') && !(argv[i - 1] || '').startsWith('--'));
if (!src) { console.error('Dùng: node fx-suggest.mjs <timing.json> [--out fx-plan.json] [--theme sach] [--per-min 10] [--voice voice.mp3]'); process.exit(1); }
const out = arg('out', path.join(path.dirname(src), 'fx-plan.json'));
const perMin = +arg('per-min', 10), theme = arg('theme', 'sach'), voice = arg('voice', null), nguoi = argv.includes('--nguoi');
const lines = JSON.parse(fs.readFileSync(src, 'utf8'));

const NUMW = 'mot hai ba bon tu nam sau bay tam chin muoi muoi lam tram nghin ngan trieu ty linh le phan tram'.split(' ');
const has = (f, k) => (' ' + f + ' ').includes(' ' + fold(k) + ' ');
// Spoken words of a line with their times; tokens of `text` map 1:1 to words that keep letters/digits.
function tokens(line) {
  const ws = line.words || [], toks = line.text.split(/\s+/).filter(Boolean), outT = [];
  let j = 0;
  // same rule as voice-timing.py (a token counts when it has a letter, digit or _), else words shift after e.g. a lone '%'
  for (const t of toks) { if (!/[\p{L}\p{N}_]/u.test(t)) continue; const f = fold(t) || t; outT.push({ raw: t, f, s: ws[j]?.[1] ?? line.start }); j++; }
  return outT;
}
// 'một' (a/one) and 'năm' (year/five) and 'tư' only count when another number word follows ('một trăm', 'năm mươi')
const isNum = (tk, next) => /\d/.test(tk.f) || (NUMW.includes(tk.f) && !['nam', 'tu', 'mot'].includes(tk.f)) || (['nam', 'mot', 'tu'].includes(tk.f) && next && NUMW.includes(next.f) && !['mot', 'nam'].includes(next.f));
// First spoken occurrence of phrase k in the line (returns the phrase as written, for resolvePlan).
const spoken = (toks, k) => { const q = fold(k).split(' '); for (let i = 0; i < toks.length; i++) if (q.every((w, j) => toks[i + j]?.f === w)) return toks.slice(i, i + q.length).map(t => t.raw.replace(/[^\p{L}\p{N}%]/gu, '')).join(' '); return null; };

const N = lines.length, dur = lines.at(-1).end - lines[0].start;
const scored = lines.map((line, i) => {
  const toks = tokens(line), f = toks.map(t => t.f).join(' ');
  const nums = toks.filter((t, k) => isNum(t, toks[k + 1]));
  const sc = Object.fromEntries(TYPES.map(t => [t, 0]));
  for (const t of TYPES) for (const k of CAT[t].tu_khoa || []) if (has(f, k)) sc[t] += 2;
  const years = (f.match(/(1[89]|20)\d\d|hai nghin/g) || []).length;
  const amount = /trieu|ty|dong|nghin|phan tram|%|nguoi|khach|gia dinh/.test(f.replace(/hai nghin/g, ''));
  if (nums.length) { sc['dem-so'] += years && !amount ? 0 : amount ? 4 : 2; sc['bieu-do-cot'] += 1; }
  if (has(f, 'phần trăm') || /%/.test(line.text)) { sc['vong-tron'] += 3; sc['tien-do'] += 2; }
  const listN = ['thứ nhất', 'thứ hai', 'thứ ba', 'thứ tư', 'đầu tiên', 'tiếp theo', 'cuối cùng'].filter(k => has(f, k)).length;
  if (listN >= 2) sc['danh-sach'] += 6;
  if (has(f, 'không phải') && (has(f, 'mà là') || has(f, 'mà'))) sc['gach-thay'] += 6;
  else if (has(f, 'không phải')) sc['chu-dap'] += 2;
  if (/\?\s*$/.test(line.text)) { sc['go-chu'] += 3; sc['binh-chon'] += 1; }
  if (years >= 2) sc['moc-thoi-gian'] += 4; else sc['moc-thoi-gian'] = Math.min(sc['moc-thoi-gian'], 1);
  if (/^luu y|dieu khoan|phu thuoc|ap dung/.test(f)) sc['luu-y'] += 4;
  if (nums.length && ['chi tra', 'duyet', 'nhan duoc'].some(k => f.includes(k))) sc['con-dau'] += 2;
  if (i === 0) { sc['go-chu'] += 2; sc['chu-dap'] += 2; sc['nhan-dan'] += 1; }
  if (i === N - 1) sc['nhan-dan'] += ['theo dõi', 'đăng ký', 'bình luận', 'comment', 'chia sẻ', 'nhắn'].some(k => has(f, k)) ? 6 : 2;
  // need a picture or a speaker: only on clear request
  for (const t of ['mui-ten', 'khoanh-tron', 'mo-tron']) sc[t] = 0;
  if (!has(f, 'tôi là') && !has(f, 'mình là')) sc['the-ten'] = 0;
  // effects around / behind the speaker: only for footage of a person (--nguoi, set by tao-video's dung-video-quay.py)
  if (nguoi) {
    if (i === 0) sc['chu-sau-lung'] += 4;                               // the signature hook of talking-head videos
    if (has(f, 'tôi là') || has(f, 'mình là')) sc['khoa-mat'] += 3;
    if (/[!]\s*$/.test(line.text)) sc['sticker-quanh-dau'] += 1;
  } else for (const t of TYPES) if (CAT[t].can_nguoi || CAT[t].lop === 'sau') sc[t] = 0;
  const rank = TYPES.map(t => [t, sc[t]]).filter(([, s]) => s > 0).sort((a, b) => b[1] - a[1]);
  return { i, line, toks, nums, rank, best: rank[0]?.[1] || 0 };
});

// keep the strongest lines (hook and CTA always), at most perMin per minute
const want = Math.max(3, Math.round((dur / 60) * perMin));
const keep = new Set([0, N - 1]);
for (const s of [...scored].sort((a, b) => b.best - a.best)) { if (keep.size >= want) break; if (s.best >= 2) keep.add(s.i); }

const plan = { theme, voice, words: path.basename(src), music: null, subtitles: true, fx: [] };
let prev = null, prevHeavy = false;
const table = [];
for (const s of scored) {
  const alt = s.rank.slice(0, 3).map(([t, v]) => `${t}(${v})`).join(' ');
  if (!keep.has(s.i) || !s.rank.length) { table.push([s.i, '—', s.line.text, alt]); continue; }
  const pick = s.rank.find(([t]) => t !== prev && !(prevHeavy && CAT[t].nang))?.[0] || s.rank[0][0];
  prev = pick; prevHeavy = !!CAT[pick].nang;
  const next = lines[s.i + 1];
  const end = Math.max(s.line.start + CAT[pick].dur * 0.7, Math.min(next ? next.start - 0.05 : s.line.end + 1.2, s.line.end + 1.2));
  const cues = {}, T = s.toks;
  if (['dem-so', 'vong-tron', 'tien-do'].includes(pick) && s.nums[0]) cues.run = s.nums[0].raw.replace(/[^\p{L}\p{N}%]/gu, '');
  if (pick === 'bieu-do-cot') cues.run = spoken(T, 'tăng') || spoken(T, 'gấp') || s.nums[0]?.raw || '+0.4';
  if (pick === 'danh-sach') ['thứ nhất', 'thứ hai', 'thứ ba', 'thứ tư'].forEach((k, n) => { const w = spoken(T, k); if (w) cues['t' + (n + 1)] = w; });
  if (pick === 'gach-thay') { cues.strike = spoken(T, 'không phải') || '+0.5'; cues.swap = spoken(T, 'mà là') || spoken(T, 'mà') || '+1.2'; }
  if (pick === 'con-dau') { const k = (CAT['con-dau'].tu_khoa || []).map(k => spoken(T, k)).find(Boolean); if (k) cues.hit = k; }
  const item = {
    _loi: s.line.text, _goi_y: alt,
    _dien: Object.entries(CAT[pick].params).map(([k, v]) => `${k}: ${v}`).join(' | '),
    type: pick, start: +(s.line.start - 0.1).toFixed(2), end: +end.toFixed(2), cues, params: {},
  };
  plan.fx.push(item);
  table.push([s.i, pick, s.line.text, alt]);
}

fs.writeFileSync(out, JSON.stringify(plan, null, 2));
const cut = (x, n) => (x.length > n ? x.slice(0, n - 1) + '…' : x.padEnd(n));
console.log(`${N} câu, ${dur.toFixed(1)} s → ${plan.fx.length} hiệu ứng (mục tiêu ${want}, ${perMin}/phút)\n`);
for (const [i, p, t, a] of table) console.log(`${String(i).padStart(3)}  ${cut(p, 13)} ${cut(t, 58)} ${a}`);
console.log(`\n→ ${out}\nViệc của agent: điền params theo ĐÚNG lời nói (xem _dien, giới hạn ký tự trong hieu-ung.json), đổi hiệu ứng nếu chưa hợp ý câu,\nsửa cues, rồi xoá _dien. Số liệu chỉ lấy từ lời nói hoặc tài liệu gốc.`);
