#!/usr/bin/env python3
"""Song enhancement from Demucs stems: sonic logo, vocal lift + echo/reverb throws, risers and impacts
into drops, a rebuilt ending, and a DJ Extended Mix. Everything is synthesized here with numpy (no
samples), tuned to the song's key, and placed on detected downbeats.

  python3 enhance.py SONG.mp3 --key G --drops 61 147 215 334 --end-from 379

Outputs go to ~/Movies/Journey/<slug>/enhanced/ (pre-master WAVs; master them with the song-master chain).
"""
import argparse, math, os, re, subprocess, sys
import numpy as np

SR = 44100
NOTE = {'C': 0, 'C#': 1, 'D': 2, 'D#': 3, 'E': 4, 'F': 5, 'F#': 6, 'G': 7, 'G#': 8, 'A': 9, 'A#': 10, 'B': 11}


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def load(path, mono=False):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-ac', '1' if mono else '2', '-ar', str(SR),
                          '-f', 'f32le', '-'], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.float32).astype(np.float64)
    return a if mono else a.reshape(-1, 2)


def save(path, x):
    x = np.asarray(x, np.float32)
    p = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', '-',
                          '-c:a', 'pcm_s24le', path], stdin=subprocess.PIPE)
    p.stdin.write(x.tobytes()); p.stdin.close(); p.wait()


def db(x):
    return 20 * np.log10(np.sqrt(np.mean(np.square(x))) + 1e-12)


# ---------------------------------------------------------------- building blocks
def conv(x, ir):
    """FFT convolution of (n,2) with (m,2)."""
    n = len(x) + len(ir) - 1; N = 1 << (n - 1).bit_length()
    out = np.zeros((n, 2))
    for c in range(2):
        out[:, c] = np.fft.irfft(np.fft.rfft(x[:, c], N) * np.fft.rfft(ir[:, c], N), N)[:n]
    return out


def reverb_ir(seconds=3.2, rt60=2.8, bright=6000, predelay=0.02, seed=1):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR); t = np.arange(n) / SR
    ir = rng.normal(0, 1, (n, 2)) * np.exp(-6.9 * t / rt60)[:, None]
    f = np.fft.rfftfreq(n, 1 / SR); shape = 1 / (1 + (f / bright) ** 2)
    for c in range(2):
        ir[:, c] = np.fft.irfft(np.fft.rfft(ir[:, c]) * shape, n)
    ir = np.vstack([np.zeros((int(predelay * SR), 2)), ir])
    return ir / np.sqrt(np.sum(ir ** 2) / 2) * 0.6


def lowpass(x, cutoff):
    """Gentle one-pole low-pass via FFT (zero phase), x (n,2)."""
    n = len(x); f = np.fft.rfftfreq(n, 1 / SR); h = 1 / np.sqrt(1 + (f / cutoff) ** 2)
    return np.stack([np.fft.irfft(np.fft.rfft(x[:, c]) * h, n) for c in range(2)], axis=1)


def highpass(x, cutoff):
    n = len(x); f = np.fft.rfftfreq(n, 1 / SR); h = (f / cutoff) / np.sqrt(1 + (f / cutoff) ** 2)
    return np.stack([np.fft.irfft(np.fft.rfft(x[:, c]) * h, n) for c in range(2)], axis=1)


def pingpong(x, delay, repeats=6, feedback=0.55):
    d = int(delay * SR); out = np.zeros((len(x) + d * repeats, 2)); src = x.copy()
    for k in range(1, repeats + 1):
        src = lowpass(src, 9000 / (1 + 0.35 * k))          # each echo a little darker
        g = feedback ** k; side = k % 2
        out[k * d:k * d + len(x), side] += src[:, side] * g + src[:, 1 - side] * g * 0.25
        out[k * d:k * d + len(x), 1 - side] += src[:, 1 - side] * g * 0.15
    return out


def add(dst, src, at):
    i = int(at * SR)
    if i < 0:
        src = src[-i:]; i = 0
    j = min(len(dst), i + len(src))
    if j > i:
        dst[i:j] += src[:j - i]


# ---------------------------------------------------------------- analysis
def frames_db(x, hop=0.05):
    h = int(hop * SR); n = len(x) // h
    return np.array([db(x[i * h:(i + 1) * h]) for i in range(n)]), hop


def drop_downbeat(drums_mono, t, window=1.5):
    """Exact drop time: the biggest jump in low-end energy near t."""
    h = 441; lo = max(0, int((t - window) * SR)); hi = int((t + window) * SR)
    seg = drums_mono[lo:hi]
    f = np.fft.rfftfreq(len(seg), 1 / SR); b = np.fft.irfft(np.fft.rfft(seg) * (f < 160), len(seg))
    e = np.array([np.abs(b[i:i + h]).mean() for i in range(0, len(b) - h, h)])
    best, bt = 0, t
    for i in range(20, len(e) - 20):
        jump = e[i:i + 20].mean() / (e[i - 20:i].mean() + 1e-9)
        if jump > best:
            best, bt = jump, (lo + i * h) / SR
    return bt


def beat_period(drums_mono, t0, t1):
    seg = drums_mono[int(t0 * SR):int(t1 * SR)]
    h = 441; f = np.fft.rfftfreq(len(seg), 1 / SR); b = np.fft.irfft(np.fft.rfft(seg) * (f < 160), len(seg))
    e = np.array([np.abs(b[i:i + h]).mean() for i in range(0, len(b) - h, h)])
    on = np.maximum(0, np.diff(e)); on -= on.mean()
    ac = np.correlate(on, on, 'full')[len(on) - 1:]
    fps = SR / h; lags = np.arange(len(ac)); ok = (lags > fps * 60 / 160) & (lags < fps * 60 / 110)
    lag = lags[ok][np.argmax(ac[ok])]
    return lag / fps


def phrase_ends(vocals_mono, min_len=1.5, on_db=-40, off_db=-48):
    d, hop = frames_db(vocals_mono); ends = []; start = None
    for i, v in enumerate(d):
        if v > on_db and start is None:
            start = i
        elif v < off_db and start is not None:
            if (i - start) * hop >= min_len:
                ends.append(i * hop)
            start = None
    return ends


# ---------------------------------------------------------------- the sounds
def bell(f0, dur=6.0, level=0.5, seed=0):
    """Temple bell: inharmonic partials with long, staggered decays."""
    t = np.arange(int(dur * SR)) / SR; rng = np.random.default_rng(seed)
    parts = [(0.5, 0.6, 4.5), (1.0, 1.0, 3.6), (1.19, 0.45, 2.4), (1.56, 0.4, 2.0), (2.0, 0.5, 1.8),
             (2.74, 0.3, 1.2), (3.76, 0.2, 0.8), (5.4, 0.12, 0.5)]
    y = np.zeros((len(t), 2))
    for ratio, amp, dec in parts:
        for c in range(2):
            beat = 1 + rng.uniform(-0.0015, 0.0015)
            y[:, c] += amp * np.sin(2 * np.pi * f0 * ratio * beat * t + rng.uniform(0, 6.28)) * np.exp(-t / dec)
    y *= np.minimum(1, t / 0.004)[:, None]
    return y / np.abs(y).max() * level


def pad(chord_midis, dur, level=0.3, seed=2):
    """Soft detuned-saw pad, low-passed."""
    t = np.arange(int(dur * SR)) / SR; rng = np.random.default_rng(seed); y = np.zeros((len(t), 2))
    for m in chord_midis:
        for det in (-0.08, 0.0, 0.08):
            for c in range(2):
                f = hz(m + det + rng.uniform(-0.03, 0.03))
                ph = rng.uniform(0, 1)
                y[:, c] += 2 * ((f * t + ph) % 1) - 1
    y = lowpass(y, 2200)
    return y / np.abs(y).max() * level


def sonic_logo(key):
    """~3.5 s: a reversed shimmer chord swells into a temple-bell strike in the song's key."""
    r = NOTE[key]
    chord = [48 + r + 7, 48 + r + 10, 60 + r + 2, 60 + r + 7, 60 + r + 9 + 3]   # minor add9 voicing around the root
    sh = pad(chord, 2.2, level=0.5)
    sh = conv(sh, reverb_ir(2.5, rt60=2.2, bright=9000))[: int(3.5 * SR)]
    swell = sh[::-1][-int(1.7 * SR):] * np.linspace(0, 1, int(1.7 * SR))[:, None] ** 2
    b = bell(hz(60 + r + 7 - 12), dur=5.0, level=0.6)
    b = b + 0.35 * conv(b, reverb_ir(3.0, rt60=3.2))[:len(b)]
    out = np.zeros((int(5.2 * SR), 2)); add(out, swell, 0.0); add(out, b, 1.7)
    return out / np.abs(out).max() * 0.7


def riser(seconds, seed=3):
    """Filtered noise sweep + rising tone; loudest at the end, cut exactly at the drop."""
    n = int(seconds * SR); rng = np.random.default_rng(seed); noise = rng.normal(0, 1, (n, 2))
    hop, win = 1024, 4096; out = np.zeros((n + win, 2)); w = np.hanning(win)
    f = np.fft.rfftfreq(win, 1 / SR)
    for i in range(0, n - win, hop):
        p = i / n
        fc = 250 * (14000 / 250) ** (p ** 1.5)
        mask = np.exp(-0.5 * ((np.log2(f + 1) - np.log2(fc)) / 1.1) ** 2)
        for c in range(2):
            out[i:i + win, c] += np.fft.irfft(np.fft.rfft(noise[i:i + win, c] * w) * mask, win) * w
    out = out[:n]
    t = np.arange(n) / SR; tone = np.sin(2 * np.pi * np.cumsum(110 * 2 ** (3 * t / seconds)) / SR) * 0.25
    out += np.stack([tone, tone], 1) * (t / seconds)[:, None]
    env = (t / seconds) ** 2.2
    out *= env[:, None]
    return out / (np.abs(out).max() + 1e-9)


def impact(seed=4):
    t = np.arange(int(2.5 * SR)) / SR; rng = np.random.default_rng(seed)
    f = 72 * np.exp(-t / 0.35) + 38
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.9)
    crash = highpass(rng.normal(0, 1, (len(t), 2)), 3000) * np.exp(-t / 0.6)[:, None] * 0.35
    y = np.stack([boom, boom], 1) + crash
    y = y + 0.4 * conv(y, reverb_ir(2.5, rt60=2.0))[:len(y)]
    return y / np.abs(y).max()


# ---------------------------------------------------------------- the edit
def enhance(song, stems_dir, key, drops, end_from, out_dir, vocal_gain_db=2.5):
    os.makedirs(out_dir, exist_ok=True)
    mix = load(song)
    st = {k: load(os.path.join(stems_dir, k + '.wav')) for k in ('drums', 'bass', 'other', 'vocals')}
    n = min(len(mix), *(len(v) for v in st.values()))
    mix = mix[:n]; st = {k: v[:n] for k, v in st.items()}
    drums_m = st['drums'].mean(1); vox = st['vocals']
    ref = db(mix)
    out = mix.copy()
    log = []

    # 3. her voice: a little louder, and echo/reverb throws on phrase endings
    out += vox * (10 ** (vocal_gain_db / 20) - 1)
    ends = phrase_ends(vox.mean(1))
    ir = reverb_ir(3.6, rt60=3.4)
    for te in ends:
        if te > end_from - 2 or te < 10:      # leave the intro to the sonic logo
            continue
        a, b = max(0, te - 1.4), te
        tail = vox[int(a * SR):int(b * SR)]
        tail = tail * np.linspace(0.2, 1, len(tail))[:, None]
        period = beat_period(drums_m, max(0, te - 12), te + 2)
        echo = pingpong(tail, period * 0.75, repeats=6) * 0.55
        verb = conv(tail, ir) * 0.5
        wet = np.zeros((max(len(echo), len(verb)), 2)); wet[:len(echo)] += echo; wet[:len(verb)] += verb
        add(out, wet * 10 ** (-4 / 20), a)
        log.append(f'vocal throw at {int(te // 60)}:{te % 60:04.1f} (echo {period * 0.75:.2f}s)')

    # 4. risers into each drop and an impact on the downbeat
    exact = []
    for d in drops:
        t = drop_downbeat(drums_m, d); exact.append(t)
        r = riser(8.0) * 10 ** ((ref - 3 - db(riser(8.0)[-SR:])) / 20)
        add(out, r, t - 8.0)
        im = impact() * 10 ** ((ref - 3 - db(impact()[:SR // 2])) / 20)
        add(out, im, t)
        log.append(f'riser + impact into drop at {int(t // 60)}:{t % 60:04.1f}')

    # 5. rebuild the ending: no stutter, drums and bass breathe out, pads and bells carry it home
    e0 = drop_downbeat(drums_m, end_from, window=2.0) if end_from else None
    if end_from:
        e0 = end_from
        i0 = int(e0 * SR); L = n - i0; t = np.arange(L) / SR
        xf = np.clip(t / 2.5, 0, 1)[:, None]                                   # 2.5 s crossfade
        rhythm_tail = (st['drums'][i0:i0 + int(2.5 * SR)] + st['bass'][i0:i0 + int(2.5 * SR)])
        rhythm_tail = conv(rhythm_tail * np.linspace(1, 0, len(rhythm_tail))[:, None], reverb_ir(3.0, rt60=2.6))
        bed = st['other'][i0:] + vox[i0:]
        bed_fade = np.clip((L / SR - t) / 14.0, 0, 1)[:, None] ** 1.5            # long final fade
        new_end = bed * bed_fade
        add(new_end, rhythm_tail * 0.6, 0.0)
        r = NOTE[key]
        for at, note in ((0.0, 60 + r + 7 - 12), (4.0, 60 + r + 2), (9.0, 60 + r + 7 - 24 + 12), (15.0, 60 + r + 7 - 12)):
            if at < L / SR - 2:
                add(new_end, bell(hz(note), dur=7.0, level=10 ** ((ref - 8 + 3) / 20)), at)
        new_end = new_end + 0.3 * conv(new_end, reverb_ir(3.0, rt60=3.0))[:len(new_end)]
        out[i0:] = out[i0:] * (1 - xf) + new_end[:L] * xf
        out[-int(0.5 * SR):] *= np.linspace(1, 0, int(0.5 * SR))[:, None]
        log.append(f'ending rebuilt from {int(e0 // 60)}:{e0 % 60:04.1f}: drums/bass breathe out, pads, 4 temple bells, long fade')

    # 2. sonic logo over the first seconds (keeps the original timing, so videos stay in sync)
    logo = sonic_logo(key)
    save(os.path.join(out_dir, 'sonic_logo.wav'), logo)
    logo_lvl = logo * 10 ** ((ref - 7 - db(logo[int(1.7 * SR):int(2.7 * SR)])) / 20)
    out[: int(2.2 * SR)] *= np.linspace(0.35, 1, int(2.2 * SR))[:, None]       # make room for the tag
    add(out, logo_lvl, 0.0)
    log.append('sonic logo: reversed shimmer chord into a temple bell, 0:00-0:05')

    save(os.path.join(out_dir, 'album_enhanced_premaster.wav'), out)

    # 6. DJ Extended Mix: 32-bar drum/bass intro and outro looped from the song's own grooves
    first = exact[0]
    p = beat_period(drums_m, first, first + 20)
    bar8 = int(round(32 * p * SR))
    loop_d = st['drums'][int(first * SR):int(first * SR) + bar8]
    loop_db = loop_d + st['bass'][int(first * SR):int(first * SR) + bar8]
    fade = int(0.004 * SR)
    def seam(x):
        x = x.copy(); x[:fade] *= np.linspace(0, 1, fade)[:, None]; x[-fade:] *= np.linspace(1, 0, fade)[:, None]; return x
    intro = np.vstack([seam(loop_d), seam(loop_d), seam(loop_db), seam(loop_db)])
    intro[: int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))[:, None]
    body = out[int(first * SR):int(end_from * SR)] if end_from else out[int(first * SR):]
    last_drop = exact[-1]
    q = beat_period(drums_m, last_drop, last_drop + 20)
    bar8b = int(round(32 * q * SR))
    o0 = int(end_from * SR) - bar8b
    loop_o_db = st['drums'][o0:o0 + bar8b] + st['bass'][o0:o0 + bar8b]
    loop_o_d = st['drums'][o0:o0 + bar8b]
    outro = np.vstack([seam(loop_o_db), seam(loop_o_db), seam(loop_o_d), seam(loop_o_d)])
    tail_bell = bell(hz(60 + NOTE[key] + 7 - 12), dur=6.0, level=10 ** ((ref - 6) / 20))
    tail_bell = tail_bell + 0.4 * conv(tail_bell, reverb_ir(3.0))[:len(tail_bell)]
    ext = np.vstack([intro, body, outro, tail_bell])
    save(os.path.join(out_dir, 'extended_mix_premaster.wav'), ext)
    log.append(f'extended mix: 32-bar intro (beat {p:.3f}s = {60 / p:.1f} BPM) + song from {int(first // 60)}:{first % 60:04.1f} + 32-bar outro, {len(ext) / SR / 60:.1f} min')
    return log


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('song'); ap.add_argument('--stems'); ap.add_argument('--out')
    ap.add_argument('--key', default='G'); ap.add_argument('--drops', type=float, nargs='+', required=True)
    ap.add_argument('--end-from', type=float); ap.add_argument('--vocal-gain', type=float, default=2.5)
    a = ap.parse_args()
    slug = re.sub(r'[^a-z0-9]+', '-', os.path.splitext(os.path.basename(a.song))[0].lower()).strip('-')
    wd = os.path.expanduser(f'~/Movies/Journey/{slug}')
    stems = a.stems or os.path.join(wd, 'stems', 'htdemucs', os.path.splitext(os.path.basename(a.song))[0])
    for line in enhance(a.song, stems, a.key, a.drops, a.end_from, a.out or os.path.join(wd, 'enhanced'), a.vocal_gain):
        print(line)


if __name__ == '__main__':
    main()
