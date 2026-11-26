// node SKILL_DIR/scripts/fx-log.mjs PROJ [PROJ2 ...] [--entry index.html]
// Writes PROJ/stem/fx.json: the start time of every sound effect the page schedules
// (sources that reach the effects bus: a gain node with role 'fx' from kit.js buses(),
// or, for older pages, a gain node set to 0.55). Used by fx-retime.py.
import { chromium } from 'playwright'; import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path';
const args = process.argv.slice(2), ei = args.indexOf('--entry'), ENTRY = ei >= 0 ? args.splice(ei, 2)[1] : 'index.html';
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.wav': 'audio/wav', '.mp3': 'audio/mpeg', '.m4a': 'audio/mp4', '.ttf': 'font/ttf', '.otf': 'font/otf', '.woff2': 'font/woff2', '.svg': 'image/svg+xml' };
const browser = await chromium.launch();
for (const dir of args) {
  const root = path.resolve(dir);
  const server = http.createServer((q, r) => { const f = path.join(root, decodeURIComponent(q.url.split('?')[0])); if (!fs.existsSync(f) || fs.statSync(f).isDirectory()) { r.writeHead(404); return r.end(); } r.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); fs.createReadStream(f).pipe(r); });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const page = await browser.newPage();
  await page.addInitScript(() => {
    const E = new Map(), S = []; window.__E = E; window.__S = S;
    const c0 = AudioNode.prototype.connect; AudioNode.prototype.connect = function (d, ...a) { if (d instanceof AudioNode) { if (!E.has(this)) E.set(this, []); E.get(this).push(d); } return c0.call(this, d, ...a); };
    for (const P of [AudioBufferSourceNode.prototype, OscillatorNode.prototype]) { const s0 = P.start; P.start = function (t = 0, ...a) { S.push([this, t]); return s0.call(this, t, ...a); }; }
  });
  await page.goto(`http://127.0.0.1:${server.address().port}/${ENTRY}?render=1&nomus=1`, { waitUntil: 'networkidle' });
  await page.evaluate(() => window.MOTION && window.MOTION.ready);
  const ev = await page.evaluate(async () => {
    await window.renderAudio(8000); const E = window.__E;
    const isFx = n => n instanceof GainNode && (n.role === 'fx' || (n.role === undefined && Math.abs(n.gain.value - .55) < 1e-6));
    const reach = (n, seen = new Set()) => { if (isFx(n)) return true; if (seen.has(n)) return false; seen.add(n); return (E.get(n) || []).some(d => reach(d, seen)); };
    const t = window.__S.filter(s => reach(s[0])).map(s => s[1]).sort((a, b) => a - b);
    const out = []; for (const x of t) { if (out.length && x - out[out.length - 1] < .035) continue; out.push(+x.toFixed(3)); } return out;
  });
  fs.mkdirSync(path.join(root, 'stem'), { recursive: true }); fs.writeFileSync(path.join(root, 'stem', 'fx.json'), JSON.stringify(ev));
  console.log(dir, ev.length, 'effects'); await page.close(); server.close();
}
await browser.close();
