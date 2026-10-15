"""Per-instrument features: split the song with Demucs (drums, bass, other, vocals), then turn each stem
into per-frame envelopes and hit triggers the visuals can follow.

  kick   - low-end hits in the drum stem        -> zoom pulse, flashes, logo pulse
  snare  - mid-band hits in the drum stem       -> contrast punch
  hats   - high-band hits in the drum stem      -> sparkle / chromatic flicker
  bass   - bass stem envelope                   -> breathing / melting warp
  melody - "other" stem (koto, synths, leads)   -> colour and kaleidoscope rotation
  vocals - vocal stem envelope                  -> halo glow, logo lights up
"""
import os, subprocess
import numpy as np

SR = 22050
DEMUCS_PY = os.path.expanduser('~/.venvs/demucs/bin/python')


def separate(song, workdir):
    """Run Demucs once; returns {stem: wav path}."""
    name = os.path.splitext(os.path.basename(song))[0]
    out = os.path.join(workdir, 'stems')
    d = os.path.join(out, 'htdemucs', name)
    paths = {k: os.path.join(d, k + '.wav') for k in ('drums', 'bass', 'other', 'vocals')}
    if not all(os.path.exists(p) for p in paths.values()):
        if not os.path.exists(DEMUCS_PY):
            raise SystemExit('Demucs is not installed (~/.venvs/demucs).')
        dev = 'mps' if subprocess.run([DEMUCS_PY, '-c', 'import torch,sys;sys.exit(0 if torch.backends.mps.is_available() else 1)']).returncode == 0 else 'cpu'
        subprocess.run([DEMUCS_PY, '-m', 'demucs', '-n', 'htdemucs', '-d', dev, '-o', out, song], check=True)
    return paths


def _load(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def _bands(a, n, fps, bands):
    hop = SR // fps; N = 2048; win = np.hanning(N)
    f = np.fft.rfftfreq(N, 1 / SR)
    masks = [(f >= lo) & (f < hi) for lo, hi in bands]
    out = np.zeros((len(bands), n), np.float32)
    for i in range(n):
        c = i * hop; s = a[max(0, c - N // 2): c + N // 2]
        if len(s) < N:
            s = np.pad(s, (0, N - len(s)))
        sp = np.abs(np.fft.rfft(s * win))
        for b, m in enumerate(masks):
            out[b, i] = sp[m].sum()
    return out


def _norm(x):
    lo, hi = np.percentile(x, [5, 98])
    return np.clip((x - lo) / (hi - lo + 1e-9), 0, 1).astype(np.float32)


def _env(x, attack=0.6, release=0.85):
    y = np.zeros_like(x); v = 0.0
    for i, s in enumerate(x):
        v = v + (s - v) * attack if s > v else v * release
        y[i] = v
    return y


def _hits(x, release):
    """Onset triggers (positive flux above a moving threshold), as decaying envelopes."""
    flux = np.maximum(0, np.diff(x, prepend=x[0]))
    thr = np.convolve(flux, np.ones(15) / 15, 'same') * 1.6 + 1e-6
    trig = np.where(flux > thr, np.clip(flux / (thr * 3), 0, 1), 0).astype(np.float32)
    return _env(trig, attack=1.0, release=release)


def features(song, workdir, n, fps=30):
    """Per-frame dict of arrays in 0..1 (cached as stems/features_<fps>.npz)."""
    cache = os.path.join(workdir, 'stems', f'features_{fps}_{n}.npz')
    if os.path.exists(cache):
        return dict(np.load(cache))
    p = separate(song, workdir)
    drums = _load(p['drums'])
    kb, sb, hb = _bands(drums, n, fps, [(20, 150), (150, 2500), (6000, 11000)])
    feat = {
        'kick': _hits(_norm(kb), 0.80),
        'snare': _hits(_norm(sb), 0.78),
        'hats': _hits(_norm(hb), 0.65),
    }
    for stem, key in (('bass', 'bass'), ('other', 'melody'), ('vocals', 'vocals')):
        a = _load(p[stem])
        e = _bands(a, n, fps, [(20, 11000)])[0]
        feat[key] = _env(_norm(e), attack=0.35, release=0.93)
    # slowly accumulating phase driven by the melody (keeps rotation continuous across render chunks)
    feat['melody_phase'] = np.cumsum(0.15 + feat['melody']).astype(np.float32) / fps
    np.savez(cache, **feat)
    return feat
