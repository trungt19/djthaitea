"""Find a song's sections from its energy curve and draft a story for it."""
import numpy as np

SR = 22050


def features(a):
    """Per-second loudness (dB) and low-end share."""
    n = len(a) // SR
    rms = np.zeros(n); low = np.zeros(n)
    N = 8192; f = np.fft.rfftfreq(N, 1 / SR); win = np.hanning(N)
    for i in range(n):
        s = a[i * SR:(i + 1) * SR]
        rms[i] = 20 * np.log10(np.sqrt((s ** 2).mean()) + 1e-9)
        sp = np.abs(np.fft.rfft(s[:N] * win))
        low[i] = sp[f < 150].sum() / (sp.sum() + 1e-9)
    return rms, low


def estimate_bpm(a):
    """Rough tempo from the autocorrelation of the low-band onset envelope."""
    hop = 512; N = 1024
    seg = a[: SR * 120] if len(a) > SR * 120 else a
    frames = (len(seg) - N) // hop
    f = np.fft.rfftfreq(N, 1 / SR); m = f < 200; win = np.hanning(N)
    env = np.array([np.abs(np.fft.rfft(seg[k * hop:k * hop + N] * win))[m].sum() for k in range(frames)])
    on = np.maximum(0, np.diff(env)); on -= on.mean()
    ac = np.correlate(on, on, 'full')[len(on) - 1:]
    fps = SR / hop
    lags = np.arange(len(ac)); bpm = 60 * fps / np.maximum(lags, 1)
    ok = (bpm >= 100) & (bpm <= 160)
    return float(bpm[ok][np.argmax(ac[ok])])


def sections(a, min_len=18, max_sections=10):
    rms, low = features(a)
    n = len(rms)
    sm = np.convolve(rms, np.ones(4) / 4, 'same')
    # novelty: difference between the next and previous 8 seconds
    w = 8
    nov = np.zeros(n)
    for i in range(w, n - w):
        nov[i] = abs(sm[i:i + w].mean() - sm[i - w:i].mean()) + 6 * abs(low[i:i + w].mean() - low[i - w:i].mean())
    cuts = [0]
    for i in np.argsort(-nov):
        if nov[i] < 1.2 or len(cuts) >= max_sections:
            break
        if all(abs(i - c) >= min_len for c in cuts) and min_len <= i <= n - min_len:
            cuts.append(int(i))
    cuts = sorted(cuts)
    bounds = cuts + [n]
    out = []
    lo, hi = np.percentile(sm, [10, 95])
    for s, e in zip(bounds, bounds[1:]):
        lvl = float(np.clip((sm[s:e].mean() - lo) / (hi - lo + 1e-9), 0, 1))
        out.append(dict(start=float(s), end=float(e), energy=round(lvl, 2)))
    return out


def draft_story(secs, title='', subtitle=''):
    """Map sections to scenes: dark rain -> build -> drops -> psychedelic peak -> ends in light."""
    n = len(secs)
    scenes = []
    for i, s in enumerate(secs):
        e = s['energy']
        if i == 0:
            sc = 'rain_city'
        elif e < 0.45:
            sc = 'bridge_stars'
        elif e < 0.7:
            sc = 'expressway'
        else:
            sc = 'neon_downtown'
        scenes.append(sc)
    # the highest-energy run in the second half becomes the psychedelic tunnel
    if n >= 4:
        cand = [i for i in range(n // 2 - 1, n - 1) if i > 0]
        if cand:
            peak = max(cand, key=lambda i: secs[i]['energy'] * (secs[i]['end'] - secs[i]['start']) ** 0.3)
            scenes[peak] = 'psy_tunnel'
            if peak - 1 > 0 and scenes[peak - 1] != 'rain_city' and secs[peak - 1]['energy'] < secs[peak]['energy']:
                scenes[peak - 1] = 'tunnel'
            for j in range(peak + 1, n):
                scenes[j] = 'dawn_bay'
    scenes[-1] = 'dawn_bay'
    return {
        'title': title, 'subtitle': subtitle, 'blend': 6.0,
        'sections': [dict(start=s['start'], scene=sc, energy=s['energy']) for s, sc in zip(secs, scenes)],
    }
