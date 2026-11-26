# Sound effects on the frame where the motion starts.
#   python SKILL_DIR/scripts/fx-retime.py PROJ --video PROJ/render/x-16x9.mp4 [--check] [-v] [--snap 0.35]
# Needs (render them first):
#   PROJ/stem/vo.wav   render.mjs PROJ --audio-only --query "nomus=1&nofx=1" --out stem --name vo
#   PROJ/stem/fx.wav   render.mjs PROJ --audio-only --query "nomus=1&novoice=1" --out stem --name fx
#   PROJ/stem/fx.json  node scripts/fx-log.mjs PROJ
# --check only prints how far each effect is from the nearest visible motion onset.
# Otherwise writes PROJ/stem/vfx.wav = voice + effects, each effect moved onto its motion onset
# (if within --snap s), dropped if no motion is visible near it, and only one effect per onset.
# Mix vfx.wav with the music (scripts/music-bed.py) and mux it onto the video; no frame re-render.
# Python: any with numpy (the ASR venv works).
import subprocess, sys, json, os, argparse, numpy as np
ap = argparse.ArgumentParser(); ap.add_argument('proj'); ap.add_argument('--video', required=True); ap.add_argument('--snap', type=float, default=.35)
ap.add_argument('--check', action='store_true'); ap.add_argument('-v', action='store_true'); A = ap.parse_args()
FPS, SR = 30, 48000
def rd(f): return np.frombuffer(subprocess.run(['ffmpeg', '-v', 'error', '-i', f, '-ac', '2', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout, dtype=np.float32).reshape(-1, 2).copy()
def wr(f, a): subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', '-', '-c:a', 'pcm_s16le', f], input=np.clip(a, -1, 1).astype(np.float32).tobytes(), check=True)
def onsets(v):
    # 16 x 9 tiles; an onset is a tile that changes clearly over 3 frames after being still (catches pops, slides and fades, ignores slow background drift)
    fps = eval(subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=r_frame_rate', '-of', 'csv=p=0', v], capture_output=True, text=True).stdout.strip())
    W, H, T = 192, 108, 12
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', v, '-vf', f'scale={W}:{H},format=gray', '-f', 'rawvideo', '-'], capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32)
    g = np.abs(fr[3:] - fr[:-3]).reshape(-1, H // T, T, W // T, T).mean((2, 4)); d = np.concatenate([np.zeros((3,) + g.shape[1:]), g])
    on = []
    for k in range(4, len(d)):
        if ((d[k] > 2.0) & (d[k - 2] < .8) & (d[k - 3] < .8)).any() and (not on or k / fps - on[-1] > .1): on.append((k - 2) / fps)
    return np.array(on)
D = os.path.join(A.proj, 'stem'); vo, fx = rd(os.path.join(D, 'vo.wav')), rd(os.path.join(D, 'fx.wav')); L = min(len(vo), len(fx)); vo, fx = vo[:L], fx[:L]
starts = sorted(set(round(x[0] if isinstance(x, list) else x, 3) for x in json.load(open(os.path.join(D, 'fx.json')))))
on = onsets(A.video); env = np.convolve(np.abs(fx).max(1), np.ones(240) / 240, 'same')
b = [max(0, int((s - .01) * SR)) for s in starts] + [L]
out = np.zeros_like(fx); kept = moved = dropped = 0; rep = []; used = set()
for i in range(len(starts)):
    a, c = b[i], b[i + 1]
    if c - a < 50 or env[a:c].max() < 1e-3: continue
    seg, e = fx[a:c], env[a:c]; hit = (a + int(np.argmax(e > e.max() * .5))) / SR  # where it becomes audible; a whoosh counts at its peak
    k = int(np.argmin(np.abs(on - hit))) if len(on) else -1; dt = on[k] - hit if k >= 0 else 99
    if A.check: rep.append(f'{hit:7.2f} {dt:+.2f}' + (' dup' if abs(dt) <= A.snap and k in used else '')); used.add(k) if abs(dt) <= A.snap else None; continue
    if abs(dt) <= A.snap and k in used: dropped += 1; rep.append(f'{hit:.2f} duplicate'); continue
    if abs(dt) > A.snap: dropped += 1; rep.append(f'{hit:.2f} no motion'); continue
    used.add(k); s = int(round(dt * SR)) if abs(dt) > .04 else 0; a2 = a + s; lo = max(0, -a2); c2 = min(L, a2 + len(seg))
    out[max(0, a2):c2] += seg[lo:c2 - a2]
    if s: moved += 1; rep.append(f'{hit:.2f}->{hit + dt:.2f}')
    else: kept += 1
if A.check:
    off = np.array([float(r.split()[1]) for r in rep]); print(f'{len(rep)} effects, |offset| > 0.1 s: {(abs(off) > .1).sum()}, no motion within {A.snap} s: {(abs(off) > A.snap).sum()}, several on one motion: {sum(r.endswith("dup") for r in rep)}')
    if A.v: print('  ' + ' | '.join(rep))
else:
    wr(os.path.join(D, 'vfx.wav'), vo + out); print(f'{len(starts)} effects: on time {kept}, moved {moved}, dropped {dropped}')
    if A.v: print('  ' + ' | '.join(rep))
