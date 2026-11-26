# One continuous music bed under a series of clips (e-learning modules, a long video cut into parts).
#   python SKILL_DIR/scripts/music-bed.py bed.json beds          build the leveled tracks and the long bed(s)
#   python SKILL_DIR/scripts/music-bed.py bed.json mix [ids]     remix clips: stem + their slice of the bed, mux onto the video
#   python SKILL_DIR/scripts/music-bed.py bed.json demo ids...   short listening file across the joins of those clips
# Each clip plays the part of the bed that follows the previous clip, so the music runs on when the clips are joined.
# The bed sits at a CONSTANT level `under` LU below the clip's stem (no ducking: pumping music distracts learners),
# and the final mix gets one linear gain to -16 LUFS. The video stream is copied, never re-encoded.
# bed.json:
# { "dir": "music",                              where the beds are written (relative to the json)
#   "tracks": { "A": {"file": "a.mp3", "from": 0, "to": 99.6}, "B": {...}, "S": {...} },   same key for tracks that alternate
#   "beds": { "main": "AB", "open": "S" },       a bed loops its pattern with crossfades until it is long enough
#   "bed_lufs": -22.5, "crossfade": 4, "under": 17,
#   "clips": [                                   in playing order; offsets add up per bed
#     {"id": "01", "video": "clip-01/render/x.mp4", "stem": "clip-01/stem/vfx.wav", "bed": "open"},
#     {"id": "03", "video": "...", "stem": "...", "bed": "main",
#      "keep": {"from": 12.9, "to": 36.6, "file": "clip-03/stem/oldmus.wav", "lufs": -27}},   optional: a scored passage replaces the bed there (switched, never layered)
#     {"id": "27b", "video": "...", "stem": "...", "same_as": "27"}  ] }                       an alternative take uses the slice of another clip
# The original video is moved to <video dir>/old-music/ the first time; mix again any time from there.
import subprocess, sys, json, os, re
CFG = os.path.abspath(sys.argv[1]); BASE = os.path.dirname(CFG); C = json.load(open(CFG, encoding='utf8'))
P = lambda f: f if os.path.isabs(f) else os.path.join(BASE, f); M = P(C.get('dir', 'music')); os.makedirs(M, exist_ok=True)
BED, XF, UNDER = C.get('bed_lufs', -22.5), C.get('crossfade', 4), C.get('under', 17)
def ff(*a): subprocess.run(['ffmpeg', '-v', 'error', '-y', *a], check=True)
def dur(f): return float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], capture_output=True, text=True).stdout)
def lufs(f, a=None, b=None):
    r = subprocess.run(['ffmpeg', '-hide_banner', *(['-ss', str(a), '-t', str(b - a)] if a is not None else []), '-i', f, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True).stderr
    return float(re.findall(r'I:\s+(-?[\d.]+) LUFS', r)[-1])
def orig(c): v = P(c['video']); k = os.path.join(os.path.dirname(v), 'old-music', os.path.basename(v)); return k if os.path.exists(k) else v
CL = {c['id']: c for c in C['clips']}
def beds():
    for k, t in C['tracks'].items():  # level slow section changes inside a track, then set its loudness
        a, b = t.get('from', 0), t.get('to') or dur(P(t['file']))
        ff('-ss', str(a), '-to', str(b), '-i', P(t['file']), '-af', f'dynaudnorm=f=500:g=21:p=0.5:m=4:r=0.12,afade=t=out:st={b - a - 1.5}:d=1.5,loudnorm=I={BED}:TP=-3:LRA=4,aresample=48000', '-ac', '2', os.path.join(M, k + '.wav'))
    for name, pat in C['beds'].items():
        need = sum(dur(orig(c)) for c in C['clips'] if c.get('bed') == name and 'same_as' not in c) + 30
        seq, tot = [], 0
        while tot < need: k = pat[len(seq) % len(pat)]; seq.append(k); tot += dur(os.path.join(M, k + '.wav')) - (XF if seq[1:] else 0)
        if len(seq) == 1: ff('-i', os.path.join(M, seq[0] + '.wav'), os.path.join(M, name + '.wav'))
        else:
            ins = sum([['-i', os.path.join(M, k + '.wav')] for k in seq], []); fl, last = [], '0:a'
            for i in range(1, len(seq)): fl.append(f'[{last}][{i}:a]acrossfade=d={XF}:c1=tri:c2=tri[x{i}]'); last = f'x{i}'
            ff(*ins, '-filter_complex', ';'.join(fl), '-map', f'[{last}]', os.path.join(M, name + '.wav'))
        print('bed', name, ''.join(seq), '%.0f s' % dur(os.path.join(M, name + '.wav')))
def where(i):
    c = CL[i]; i = c.get('same_as', i); c = CL[i]; off = c.get('offset', 0.0)
    for x in C['clips']:
        if x['id'] == i: return c['bed'], off
        if x.get('bed') == c['bed'] and 'same_as' not in x and 'offset' not in c: off += dur(orig(x))
def mix(i, out=None):
    c = CL[i]; d = dur(orig(c)); bed, off = where(i); src = os.path.join(M, bed + '.wav'); stem = P(c['stem'])
    out = out or os.path.join(os.path.dirname(stem), 'mix.wav'); tmp = out + '.tmp.wav'; g = lufs(stem) - UNDER - BED
    kp = CL[c.get('same_as', i)].get('keep')
    if kp:
        a, b = kp['from'], kp['to']; om = P(kp['file']); go = kp.get('lufs', lufs(stem) - UNDER + 2) - lufs(om, a, b)
        e1 = f"if(lt(t,{a}),1,if(lt(t,{a + .7}),1-(t-{a})/.7,if(lt(t,{b + .9}),0,if(lt(t,{b + 2.1}),(t-{b + .9})/1.2,1))))"
        e2 = f"if(lt(t,{a + .7}),0,if(lt(t,{a + 1.2}),(t-{a + .7})/.5,if(lt(t,{b}),1,if(lt(t,{b + .9}),1-(t-{b})/.9,0))))"
        ff('-i', stem, '-ss', str(off), '-t', str(d), '-i', src, '-i', om, '-filter_complex', f"[1:a]volume={g:.2f}dB,volume='{e1}':eval=frame,afade=t=in:st=0:d=0.8,afade=t=out:st={d - 1}:d=0.9[m];[2:a]volume={go:.2f}dB,volume='{e2}':eval=frame[q];[0:a][m][q]amix=inputs=3:normalize=0[o]", '-map', '[o]', '-ar', '48000', tmp)
    else:
        ff('-i', stem, '-ss', str(off), '-t', str(d), '-i', src, '-filter_complex', f'[1:a]volume={g:.2f}dB,afade=t=in:st=0:d=0.8,afade=t=out:st={d - 1}:d=0.9[m];[0:a][m]amix=inputs=2:normalize=0[o]', '-map', '[o]', '-ar', '48000', tmp)
    ff('-i', tmp, '-af', f'volume={-16 - lufs(tmp):.2f}dB', out); os.remove(tmp); return out
def mux(i):
    v = P(CL[i]['video']); k = os.path.join(os.path.dirname(v), 'old-music', os.path.basename(v)); os.makedirs(os.path.dirname(k), exist_ok=True)
    if not os.path.exists(k): os.replace(v, k)
    ff('-i', k, '-i', mix(i), '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', v); print('mixed', i)
if __name__ == '__main__':
    cmd, ids = sys.argv[2], sys.argv[3:]
    if cmd == 'beds': beds()
    elif cmd == 'mix': [mux(i) for i in (ids or list(CL))]
    elif cmd == 'demo':  # the joins between consecutive clips
        parts = []
        for j, i in enumerate(ids):
            d = dur(orig(CL[i])); n = len(ids)  # first clip: its last 10 s; middle clips: whole; last clip: its first 14 s
            a, b = (0, d) if n == 1 else (max(0, d - 10), d) if j == 0 else (0, min(d, 14)) if j == n - 1 else (0, d)
            w = mix(i, os.path.join(M, f'_d{j}.wav')); o = os.path.join(M, f'_p{j}.mp4'); parts.append(o)
            ff('-ss', str(a), '-to', str(b), '-i', orig(CL[i]), '-ss', str(a), '-to', str(b), '-i', w, '-map', '0:v', '-map', '1:a', '-vf', 'scale=1280:-2', '-c:v', 'libx264', '-crf', '22', '-preset', 'veryfast', '-c:a', 'aac', '-b:a', '192k', o)
        fc = ''.join(f'[{j}:v][{j}:a]' for j in range(len(parts))) + f'concat=n={len(parts)}:v=1:a=1[v][a]'
        ff(*sum([['-i', p] for p in parts], []), '-filter_complex', fc, '-map', '[v]', '-map', '[a]', '-c:v', 'libx264', '-crf', '22', '-preset', 'veryfast', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', os.path.join(M, 'demo.mp4'))
        for x in os.listdir(M):
            if x.startswith('_'): os.remove(os.path.join(M, x))
        print(os.path.join(M, 'demo.mp4'))
