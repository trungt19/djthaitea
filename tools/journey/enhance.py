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
def enhance(song, stems_dir, key, drops, end_from, out_dir, vocal_gain_db=2.5, ghost=True, voice=None):
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

    # 7. ghost voice: pitched, vocoded chops of her own vocal, stuttering into drops and calling in the peak
    if ghost:
        chops = ghost_voice(vox, key, [(70, 108), (245, 262), (275, 292), (305, 326)])
        ir_g = reverb_ir(3.4, rt60=3.0, bright=9000, seed=7)
        lvl = 10 ** ((ref - 9) / 20)
        def place(sig, at):
            sig = sig + 0.45 * conv(sig, ir_g)[:len(sig)]
            add(out, sig / (np.abs(sig).max() + 1e-9) * lvl * 2.2, at)
        vm, takes = load_voice(voice) if voice else (None, {})
        for di, d in enumerate(exact):
            if di == 0:
                continue
            per = beat_period(drums_m, d - 16, d)
            word = (vm or {}).get('drops', {}).get(str(di + 1))
            if word == 'vowels' and vm.get('extra', {}).get('vowels'):
                vraw = load(os.path.expanduser(vm['extra']['file']))
                src = []
                for k, (v0, v1) in enumerate(vm['extra']['vowels']):          # wordless angelic chops from sung vowels
                    mid = (v0 + v1) / 2
                    g = highpass(vraw[int((mid - 0.25) * SR):int((mid + 0.25) * SR)], 90)
                    g = g / (np.abs(g).max() + 1e-9)
                    f0 = f0_of(g.mean(1)) or 130.0
                    midi = 69 + 12 * np.log2(f0 / 440)
                    tones = [36 + NOTE[key] + 7 + o for o in (0, 3, 7, 12, 15, 19)]          # chord tones near the voice
                    tgt = min(tones, key=lambda m: abs(m - midi))
                    nat = pitch(g, tgt - midi); tuned = np.zeros_like(g); tuned[:len(nat)] = nat
                    fifth = pitch(g, tgt - midi + 7); h5 = np.zeros_like(g); h5[:len(fifth)] = fifth
                    a_ = 0.25 * vocode(g, key, octave=5)
                    c = highpass(0.8 * tuned + 0.35 * h5 + a_, 110); f_ = int(0.006 * SR)
                    c[:f_] *= np.linspace(0, 1, f_)[:, None]; c[-f_ * 4:] *= np.linspace(1, 0, f_ * 4)[:, None]
                    src.append(c / (np.abs(c).max() + 1e-9))
                src = src[di % len(src):] + src[:di % len(src)]
                word = 'your sung vowels (wordless)'
                takes = dict(takes, **{word: None})
            else:
                src = [ghost_word(takes[word], key)] if word in takes else chops
            pat, at = ghost_pattern(src, d, per, bars=2, seed=int(d))
            if word == 'your sung vowels (wordless)':
                pat = pat * 10 ** (4 / 20)
            if word in takes:
                log.append(f'your voice: "{word}" stutters into {int(d // 60)}:{d % 60:04.1f}')
            place(pat, at)
            log.append(f'ghost-voice stutter run into {int(d // 60)}:{d % 60:04.1f}')
        per = beat_period(drums_m, exact[2], exact[2] + 20)
        mixed = list(chops)
        for k, name in enumerate((vm or {}).get('calls', [])):
            if name in takes:
                mixed.insert(1 + 2 * k, ghost_word(takes[name], key))
        place(ghost_calls(mixed, exact[2], exact[3] - 20, per, every_bars=8), exact[2])
        if vm:
            extra = vm.get('extra', {})
            raw = load(os.path.expanduser(extra['file'])) if extra.get('file') else None
            cut = lambda ab: raw[int(ab[0] * SR):int(ab[1] * SR)].copy()
            if raw is not None and extra.get('vowels'):
                vowels = [highpass(cut(ab), 70) for ab in extra['vowels']]
                for a0, a1 in extra.get('choir_at', []):
                    cp = choir_pad(vowels, key, a1 - a0, seed=int(a0))
                    add(out, cp * 10 ** ((ref - extra.get('choir_db_below', 7) - db(cp[int(2.5 * SR):-int(3.5 * SR)])) / 20), a0)
                    log.append(f'your choir under {int(a0 // 60)}:{a0 % 60:04.1f}-{int(a1 // 60)}:{a1 % 60:04.1f}')
            if raw is not None and extra.get('whisper'):
                wv = cut(extra['whisper']); wv = highpass(wv, 150) / (np.abs(wv).max() + 1e-9)
                wverb = conv(wv, reverb_ir(3.0, rt60=2.8, bright=9000, seed=41))
                wsig = 0.5 * wverb; wsig[:len(wv)] += wv
                add(out, wsig * 10 ** ((ref - 8 - db(wv)) / 20), extra['whisper_at'])
                log.append(f'your whisper at {int(extra["whisper_at"] // 60)}:{extra["whisper_at"] % 60:04.1f}')
            if raw is not None and extra.get('line'):
                mv = memory_voice(highpass(cut(extra['line']), 90))
                add(out, mv * 10 ** ((ref - 7 - db(mv[:int(2 * SR)])) / 20), extra['line_at'])
                log.append(f'"Sunrise... together" at {int(extra["line_at"] // 60)}:{extra["line_at"] % 60:04.1f}')
        if vm and vm.get('tag') in takes:
            tag = voice_tag(takes[vm['tag']], key)
            add(out, tag * 10 ** ((ref - 6 - db(tag[:int(0.9 * SR)])) / 20), 3.0)
            log.append('your vocal tag "Tokyo Thai" at 0:03, right after the sonic logo bell')
        log.append(f'ghost-voice calls every 8 bars through the tunnel peak ({len(chops)} chops from her vocal)')
        save(os.path.join(out_dir, 'ghost_chops_preview.wav'), np.vstack([np.vstack([c, np.zeros((SR // 4, 2))]) for c in chops]))

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
    ap.add_argument('--no-ghost', action='store_true'); ap.add_argument('--voice', help='voice_map.json of your recorded words')
    a = ap.parse_args()
    slug = re.sub(r'[^a-z0-9]+', '-', os.path.splitext(os.path.basename(a.song))[0].lower()).strip('-')
    wd = os.path.expanduser(f'~/Movies/Journey/{slug}')
    stems = a.stems or os.path.join(wd, 'stems', 'htdemucs', os.path.splitext(os.path.basename(a.song))[0])
    for line in enhance(a.song, stems, a.key, a.drops, a.end_from, a.out or os.path.join(wd, 'enhanced'), a.vocal_gain, not a.no_ghost, a.voice):
        print(line)



# ---------------------------------------------------------------- ghost voice chops
def _grains(vocals_mono, windows, n=6, length=0.42):
    """Pick sustained, strong vowel grains (steady loudness) from the vocal stem."""
    h = int(0.02 * SR); L = int(length * SR); cands = []
    for a, b in windows:
        seg = vocals_mono[int(a * SR):int(b * SR)]
        e = np.array([np.sqrt(np.mean(seg[i:i + h] ** 2)) for i in range(0, len(seg) - h, h)])
        k = L // h
        for i in range(0, len(e) - k, k // 2):
            w = e[i:i + k]
            if w.min() > 0.02:
                cands.append((w.mean() / (w.std() + 1e-6) * w.mean(), a + i * h / SR))
    cands.sort(reverse=True); picked = []
    for score, t in cands:
        if all(abs(t - p) > 2.0 for p in picked):
            picked.append(t)
        if len(picked) == n:
            break
    return sorted(picked)


def pitch(x, semis):
    """Resample-based pitch shift (chipmunk formants: the classic ghost-voice colour)."""
    r = 2 ** (semis / 12); idx = np.arange(0, len(x) - 1, r)
    return np.stack([np.interp(idx, np.arange(len(x)), x[:, c]) for c in range(2)], 1)


def vocode(mod, key, octave=5):
    """STFT vocoder: the vocal's spectral envelope sung by a minor-chord supersaw."""
    r = NOTE[key]; n = len(mod)
    car = pad([12 * octave + r, 12 * octave + r + 3, 12 * octave + r + 7, 12 * octave + r + 10, 12 * (octave + 1) + r + 2],
              n / SR + 0.1, level=0.5)[:n]
    win, hop = 2048, 512; w = np.hanning(win); out = np.zeros((n + win, 2))
    mm = np.pad(mod.mean(1), (0, win))
    for c in range(2):
        cc = np.pad(car[:, c], (0, win))
        for i in range(0, n, hop):
            M = np.abs(np.fft.rfft(mm[i:i + win] * w)); C = np.fft.rfft(cc[i:i + win] * w)
            env = np.convolve(M, np.ones(24) / 24, 'same')
            out[i:i + win, c] += np.fft.irfft(C / (np.abs(C) + 1e-9) * env, win) * w
    out = out[:n]
    return out / (np.abs(out).max() + 1e-9)


def ghost_voice(vox, key, windows):
    """Grains -> octave-up + fifth-up, blended with a vocoded copy, short fades; returns list of chops."""
    m = vox.mean(1); chops = []
    for t in _grains(m, windows):
        g = vox[int(t * SR):int((t + 0.42) * SR)]
        o, f5 = pitch(g, 12), pitch(g, 19)
        up = o.copy(); up[:len(f5)] += 0.5 * f5
        vc = vocode(up, key)
        c = 0.6 * up / (np.abs(up).max() + 1e-9) + 0.5 * vc
        c = highpass(c, 350)
        f = int(0.006 * SR); c[:f] *= np.linspace(0, 1, f)[:, None]; c[-f * 4:] *= np.linspace(1, 0, f * 4)[:, None]
        chops.append(c / (np.abs(c).max() + 1e-9))
    return chops


def ghost_pattern(chops, drop_t, period, bars=2, seed=0):
    """A stutter run into a drop: 1/8 notes, then 1/16, then 1/32 in the last beat; ends on the downbeat."""
    rng = np.random.default_rng(seed); hits = []
    start = drop_t - bars * 4 * period; t = start
    while t < drop_t - 1e-3:
        left = drop_t - t
        step = period / 2 if left > 4 * period else (period / 4 if left > period else period / 8)
        hits.append((t, step)); t += step
    out = np.zeros((int((drop_t - start + 2.5) * SR), 2))
    base = chops[int(rng.integers(len(chops)))]
    for k, (t, step) in enumerate(hits):
        c = base if (k // 4) % 2 == 0 else chops[(k // 4) % len(chops)]
        g = c[:max(int(step * SR * 0.85), 64)].copy()
        g[-64:] *= np.linspace(1, 0, 64)[:, None]
        pan = np.array([1 - 0.35 * (k % 2), 0.65 + 0.35 * (k % 2)])
        add(out, g * pan * (0.55 + 0.45 * (t - start) / (drop_t - start)), t - start)
    add(out, chops[0] * 1.0, drop_t - start)                       # the full chop lands on the drop
    return out, start


def ghost_calls(chops, t0, t1, period, every_bars=8, seed=1):
    """Call-and-response ghost phrases inside a long section: a 3-hit stutter every N bars."""
    rng = np.random.default_rng(seed); out = np.zeros((int((t1 - t0 + 3) * SR), 2))
    bar = 4 * period; t = t0 + bar * (every_bars - 1) + 2 * period
    k = 0
    while t < t1 - bar:
        c = chops[(k + 1) % len(chops)]
        for j, dt in enumerate((0, period / 2, period * 0.75)):
            g = c[:int(period * 0.45 * SR)].copy() if j < 2 else c
            add(out, g * (0.6 if j < 2 else 0.9), t - t0 + dt)
        t += bar * every_bars; k += 1
    return out



# ---------------------------------------------------------------- the artist's own voice
def load_voice(voice_map):
    import json
    vm = json.load(open(os.path.expanduser(voice_map)))
    a = load(os.path.expanduser(vm['file']))
    takes = {}
    for k, (t0, t1) in vm['takes'].items():
        w = a[int(max(0, t0 - 0.03) * SR):int((t1 + 0.08) * SR)].copy()
        f = int(0.005 * SR); w[:f] *= np.linspace(0, 1, f)[:, None]; w[-f * 6:] *= np.linspace(1, 0, f * 6)[:, None]
        takes[k] = highpass(w, 90) / (np.abs(w).max() + 1e-9)
    return vm, takes


def ghost_word(w, key):
    """A spoken word made to sing in key: vocoded through a minor chord (two octaves), a touch of
    octave-up shimmer and some of the dry voice so it stays intelligible."""
    vc = 0.6 * vocode(w, key, octave=4) + 0.4 * vocode(w, key, octave=5)
    up = pitch(w, 12); sh = np.zeros_like(w); sh[:len(up)] = up
    g = 0.65 * vc + 0.25 * sh + 0.45 * w
    g = highpass(g, 160)
    return g / (np.abs(g).max() + 1e-9)


def voice_tag(w, key):
    """The artist's vocal tag: dry voice up front, vocoded double behind, echo and a long tail."""
    vc = vocode(w, key, octave=4)
    core = 0.8 * w + 0.45 * vc
    echo = pingpong(core, 0.33, repeats=5, feedback=0.5) * 0.5
    verb = conv(core, reverb_ir(3.2, rt60=3.0, bright=8000, seed=11)) * 0.35
    out = np.zeros((max(len(echo), len(verb)), 2)); out[:len(echo)] += echo; out[:len(core)] += core; out[:len(verb)] += verb
    return out / (np.abs(out).max() + 1e-9)



def f0_of(x):
    """Median pitch (Hz) of a voiced mono segment, by frame autocorrelation."""
    h = int(0.05 * SR); lo, hi = int(SR / 400), int(SR / 60); fs = []
    for i in range(0, len(x) - h, h):
        m = x[i:i + h] - x[i:i + h].mean()
        if np.sqrt(np.mean(m ** 2)) < 1e-3:
            continue
        ac = np.correlate(m, m, 'full')[h - 1:]
        k = lo + np.argmax(ac[lo:hi])
        if ac[k] > 0.3 * ac[0]:
            fs.append(SR / k)
    return float(np.median(fs)) if fs else 0.0


def stretch(x, length, seed=0, grain=0.5):
    """Granular stretch of a sustained vowel into a smooth pad of any length."""
    rng = np.random.default_rng(seed); g = int(grain * SR); hop = g // 4
    n = int(length * SR); out = np.zeros((n + g, 2)); w = np.hanning(g)[:, None]
    src = x[int(0.25 * SR):len(x) - int(0.25 * SR)] if len(x) > g + int(0.5 * SR) else x
    for i in range(0, n, hop):
        j = int(rng.integers(0, max(1, len(src) - g)))
        out[i:i + g] += src[j:j + g] * w if len(src) >= g else 0
    out = out[:n]
    return out / (np.abs(out).max() + 1e-9)


def choir_pad(vowels, key, length, seed=0):
    """The artist's sustained vowels tuned onto the minor triad (low voices, small shifts) plus a
    vocoded high layer for the angelic shimmer; slow swell in and out."""
    r = NOTE[key]; targets = [36 + r + 7, 36 + r + 10, 48 + r + 2, 48 + r + 7]     # G2 Bb2 D3 G3 for key G
    voices = np.zeros((int(length * SR), 2))
    for i, v in enumerate(vowels):
        f = f0_of(v.mean(1))
        if not f:
            continue
        midi = 69 + 12 * np.log2(f / 440)
        for tgt in targets:
            shift = tgt - midi
            if abs(shift) <= 7:
                pv = pitch(v, shift)
                voices += stretch(pv, length, seed=seed + i * 7 + int(tgt)) * 0.5
    hi = vocode(stretch(vowels[0], length, seed=seed + 99), key, octave=5)
    pad_ = 0.9 * voices / (np.abs(voices).max() + 1e-9) + 0.2 * hi
    pad_ = highpass(lowpass(pad_, 9000), 80)
    t = np.arange(len(pad_)) / SR
    env = np.minimum(1, t / 2.5) * np.minimum(1, (length - t) / 3.5)
    pad_ = pad_ * env[:, None]
    pad_ = pad_ + 0.6 * conv(pad_, reverb_ir(3.5, rt60=3.6, bright=7000, seed=21))[:len(pad_)]
    return pad_ / (np.abs(pad_).max() + 1e-9)


def memory_voice(w):
    """A spoken line made to sound like a memory: band-limited, slight slow-down, long reverb."""
    m = pitch(w, -0.6)
    m = highpass(lowpass(m, 5200), 250)
    verb = conv(m, reverb_ir(4.0, rt60=3.8, bright=6000, seed=31)) * 0.55
    out = np.zeros((len(verb), 2)); out[:len(m)] += m; out += verb
    return out / (np.abs(out).max() + 1e-9)


if __name__ == '__main__':
    main()
