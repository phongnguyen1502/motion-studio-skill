"""voice-timing.py — word timestamps for a voiceover, aligned to the script, 100 % local (faster-whisper).

  python voice-timing.py <voice.mp3|wav> <script.txt> <out/timing.json> [--model medium] [--lang vi]

script.txt: one sentence/line per line (blank lines ignored) — exactly what the voice reads.
Output timing.json: [{ "i", "start", "end", "text", "miss", "words": [[normalized_word, t_start], ...] }, ...]
`miss` = words of that line whisper did not match (their times are interpolated). Lines with many
misses deserve a look (TTS may skip a line, e.g. an English phrase).

Needs a Python with faster-whisper (pip install faster-whisper) and ffmpeg on PATH. Lessons baked in:
- audio is decoded with ffmpeg to 16 kHz float32 and passed as an array (passing an mp3 path can crash
  in PyAV with "unexpected keyword argument 'metadata_errors'");
- no initial_prompt and condition_on_previous_text=False (a long prompt made the first ~20 s garbage);
- matching uses difflib on normalized words, so ASR spelling slips ("Score" vs "SCORE") don't matter.
"""
import argparse, json, re, subprocess, sys, unicodedata, difflib
import numpy as np
for _s in (sys.stdout, sys.stderr):  # Windows pipes default to cp1252 -> Vietnamese print crashes
    if hasattr(_s, 'reconfigure'): _s.reconfigure(encoding='utf-8', errors='replace')


def norm(s):
    return re.sub(r'[^\w]', '', unicodedata.normalize('NFC', s.lower()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('voice'); ap.add_argument('script'); ap.add_argument('out')
    ap.add_argument('--model', default='medium'); ap.add_argument('--lang', default='vi')
    ap.add_argument('--threads', type=int, default=8)
    a = ap.parse_args()

    from faster_whisper import WhisperModel
    pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', a.voice, '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    audio = np.frombuffer(pcm, dtype=np.float32)
    model = WhisperModel(a.model, device='cpu', compute_type='int8', cpu_threads=a.threads)
    segs, _ = model.transcribe(audio, language=a.lang, word_timestamps=True, beam_size=5,
                               condition_on_previous_text=False, vad_filter=False)
    W = []
    for s in segs:
        for w in s.words:
            W.append({'w': w.word.strip(), 's': round(w.start, 2), 'e': round(w.end, 2)})
        print(f'{s.start:7.1f}  {s.text.strip()[:80]}', file=sys.stderr, flush=True)

    lines = [l.strip() for l in open(a.script, encoding='utf-8') if l.strip()]
    st, own = [], []
    for i, l in enumerate(lines):
        for t in l.split():
            n = norm(t)
            if n: st.append(n); own.append(i)
    wt = [norm(w['w']) for w in W]
    tm = [None] * len(st)
    for x, y, n in difflib.SequenceMatcher(None, st, wt, autojunk=False).get_matching_blocks():
        for k in range(n): tm[x + k] = [W[y + k]['s'], W[y + k]['e']]
    known = [k for k in range(len(st)) if tm[k]]
    kset = set(known)
    for k in range(len(st)):                       # interpolate words whisper missed
        if tm[k] is None:
            p = max([j for j in known if j < k], default=None); q = min([j for j in known if j > k], default=None)
            if p is None: tm[k] = [0, 0.2]
            elif q is None: tm[k] = [tm[p][1], tm[p][1] + 0.25]
            else:
                f = (k - p) / (q - p); s0 = tm[p][1] + (tm[q][0] - tm[p][1]) * f; tm[k] = [s0, s0 + 0.2]
    res = []
    for i, l in enumerate(lines):
        idx = [k for k in range(len(st)) if own[k] == i]
        res.append({'i': i, 'start': round(tm[idx[0]][0], 2), 'end': round(tm[idx[-1]][1], 2), 'text': l,
                    'miss': sum(1 for k in idx if k not in kset), 'words': [[st[k], round(tm[k][0], 2)] for k in idx]})
    json.dump(res, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False)
    for r in res:
        flag = '  <-- check' if r['miss'] > len(r['words']) / 3 else ''
        print(f"{r['i']:3d} {r['start']:7.2f}-{r['end']:7.2f} miss {r['miss']}/{len(r['words'])}  {r['text'][:50]}{flag}")


if __name__ == '__main__':
    main()
