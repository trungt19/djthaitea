"""Footage mode: cut real or AI-generated clips to the music.

Clips live in folders named after scenes (rain_city/, expressway/, ..., plus car/ for hero
car shots). The story decides which scene plays when; cuts land on detected kicks, with
longer shots in calm sections and fast cuts at drops. Each frame is graded per scene and
gets audio-reactive effects (bloom pulse, flash on drops, psychedelic hue/mirror/zoom at peaks).
"""
import json, math, os, random, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SR = 22050
VIDEO_EXT = ('.mp4', '.mov', '.m4v', '.webm', '.mkv')
FALLBACK = {
    'rain_city': ['neon_downtown', 'expressway'], 'expressway': ['rain_city', 'neon_downtown'],
    'bridge_stars': ['expressway', 'neon_downtown'], 'neon_downtown': ['rain_city', 'expressway'],
    'tunnel': ['psy_tunnel', 'expressway'], 'psy_tunnel': ['tunnel', 'neon_downtown'],
    'dawn_bay': ['bridge_stars', 'expressway'],
}
# seconds per shot (min) by scene; drops cut faster
SHOT_LEN = {'rain_city': 5.5, 'expressway': 3.5, 'bridge_stars': 6.0, 'neon_downtown': 1.9,
            'tunnel': 3.0, 'psy_tunnel': 2.2, 'dawn_bay': 5.0}
CAR_SHARE = {'rain_city': .25, 'expressway': .3, 'bridge_stars': .2, 'neon_downtown': .35,
             'tunnel': .3, 'psy_tunnel': .15, 'dawn_bay': .35}
# colour grade: (lift rgb, gain rgb, saturation)
GRADE = {
    'rain_city': ((4, 6, 14), (0.92, 1.0, 1.12), 1.05),
    'expressway': ((8, 2, 14), (1.02, 0.95, 1.1), 1.12),
    'bridge_stars': ((2, 6, 18), (0.9, 0.98, 1.15), 0.95),
    'neon_downtown': ((10, 0, 12), (1.1, 0.92, 1.08), 1.3),
    'tunnel': ((10, 5, 0), (1.12, 0.98, 0.85), 1.1),
    'psy_tunnel': ((6, 0, 10), (1.05, 1.0, 1.05), 1.4),
    'dawn_bay': ((12, 6, 4), (1.12, 1.0, 0.9), 1.08),
}


def probe(path):
    """Return (duration, width, height, mean luma 0-255) for a clip."""
    out = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                          'stream=width,height:format=duration', '-of', 'json', path],
                         capture_output=True, text=True)
    try:
        j = json.loads(out.stdout)
        du = float(j['format']['duration']); w = j['streams'][0]['width']; h = j['streams'][0]['height']
    except (KeyError, ValueError, IndexError):
        return 0.0, 0, 0, 0.0
    lum = []
    for fr in (0.2, 0.5, 0.8):
        raw = subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(du * fr), '-i', path, '-frames:v', '1',
                              '-vf', 'scale=96:54', '-f', 'rawvideo', '-pix_fmt', 'gray', '-'], capture_output=True).stdout
        if raw:
            lum.append(float(np.frombuffer(raw, np.uint8).mean()))
    return du, w, h, (sum(lum) / len(lum) if lum else 0.0)


def scan_clips(root, wide=True, min_luma=10.0):
    """Clips per scene folder, keeping only ones that match the output orientation and aren't too dark.
    Results are cached in <root>/.quality.json."""
    cache_f = os.path.join(root, '.quality.json')
    try:
        cache = json.load(open(cache_f))
    except (OSError, ValueError):
        cache = {}
    lib = {}
    for name in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        d = os.path.join(root, name)
        if not os.path.isdir(d) or name.startswith(('_', '.')):
            continue
        keep = []
        for f in sorted(os.listdir(d)):
            if not f.lower().endswith(VIDEO_EXT):
                continue
            path = os.path.join(d, f); real = os.path.realpath(path)
            if real not in cache:
                cache[real] = probe(real)
            du, w, h, luma = cache[real]
            if du < 1.0 or (wide and w < h) or (not wide and w > h * 1.2) or luma < min_luma:
                continue
            keep.append((path, du))
        lib[name] = keep
    try:
        json.dump(cache, open(cache_f, 'w'))
    except OSError:
        pass
    return lib


def kick_times(a, fps=30):
    """Times of strong low-end onsets (kicks / downbeats)."""
    hop = SR // fps; N = 1024
    f = np.fft.rfftfreq(N, 1 / SR); m = f < 150; win = np.hanning(N)
    n = (len(a) - N) // hop
    env = np.array([np.abs(np.fft.rfft(a[k * hop:k * hop + N] * win))[m].sum() for k in range(n)])
    on = np.maximum(0, np.diff(env, prepend=env[0]))
    thr = np.convolve(on, np.ones(fps) / fps, 'same') * 1.8 + 1e-6
    peaks = [k for k in range(1, n - 1) if on[k] > thr[k] and on[k] >= on[k - 1] and on[k] >= on[k + 1]]
    return np.array(peaks) / fps


def plan(story, lib, audio, duration, seed=7):
    """Return a list of shots: {t0, t1, scene, clip, cin, rate, car}."""
    rng = random.Random(seed)
    kicks = kick_times(audio)
    secs = sorted(story['sections'], key=lambda s: s['start'])
    ends = [s['start'] for s in secs[1:]] + [duration]
    used = {}
    shots = []
    last_car = [-10]

    playhead = {}      # where each clip left off, so a returning clip continues instead of jumping
    last_seen = {}     # shot index where each clip was last used

    def take(f, du, length):
        """Next in-point for clip f: continue from its playhead; restart at a fresh spot if it runs out."""
        rate = 1.0 if du >= length else max(0.5, du / length)
        span = length * rate
        cin = playhead.get(f)
        if cin is None or cin + span > du - 0.1:
            cin = rng.uniform(0, max(0.0, min(du - span - 0.1, du * 0.3)))
        playhead[f] = cin + span + 0.25
        used[f] = used.get(f, 0) + 1
        last_seen[f] = len(shots)
        return f, cin, rate

    def pick(scene, length):
        order = [scene] + FALLBACK.get(scene, []) + [k for k in lib if k != 'car']
        for name in order:
            pool = [c for c in lib.get(name, []) if c[1] >= 1.0]
            if pool:
                break
        else:
            return None
        # avoid the clip we just showed (and anything seen in the last few cuts), then least-used
        recent = lambda f: len(shots) - last_seen.get(f, -99) <= min(4, len(pool) - 1)
        pool.sort(key=lambda c: (recent(c[0]), used.get(c[0], 0), rng.random()))
        f, du = pool[0]
        return take(f, du, length)

    for sec, end in zip(secs, ends):
        scene = sec['scene']; t = float(sec['start'])
        base = SHOT_LEN.get(scene, 3.0) * float(sec.get('cut_scale', 1.0))
        first = True
        while t < end - 0.05:
            target = t + base * rng.uniform(0.85, 1.4)
            later = kicks[(kicks > target) & (kicks < end - 0.5)]
            t1 = float(later[0]) if len(later) and later[0] - target < base else min(target, end)
            if end - t1 < base * 0.6:
                t1 = end
            cars_left = [c for c in lib.get('car', []) if used.get(c[0], 0) < 3]
            gap_ok = len(shots) - last_car[0] >= 4
            use_car = bool(cars_left) and len(shots) > 0 and gap_ok and (
                (first and scene in ('neon_downtown', 'dawn_bay')) or rng.random() < CAR_SHARE.get(scene, .25))
            choice = None
            if use_car:
                cars = sorted(cars_left, key=lambda c: (used.get(c[0], 0), rng.random()))
                last_car[0] = len(shots)
                f, du = cars[0]
                choice = take(f, du, t1 - t)
            if not choice:
                choice = pick(scene, t1 - t)
            if not choice:
                raise SystemExit('No clips found. Put videos into the scene folders first.')
            f, cin, rate = choice
            shots.append(dict(t0=t, t1=t1, scene=scene, clip=f, cin=cin, rate=rate,
                              car=bool(use_car), section_start=first))
            t = t1; first = False
    return shots


class Reader:
    """Streams frames for one shot, scaled and cropped to fill the output."""
    def __init__(self, shot, w, h, fps, skip_frames, nframes):
        start = shot['cin'] + skip_frames / fps * shot['rate']
        dur = nframes / fps * shot['rate'] + 0.5
        vf = (f'setpts=PTS/{shot["rate"]},fps={fps},scale={w}:{h}:force_original_aspect_ratio=increase,'
              f'crop={w}:{h}')
        self.w, self.h, self.left = w, h, nframes
        self.p = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-ss', f'{start:.3f}', '-t', f'{dur:.3f}',
                                   '-i', shot['clip'], '-vf', vf, '-an', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.last = None

    def read(self):
        size = self.w * self.h * 3
        buf = self.p.stdout.read(size)
        if len(buf) == size:
            self.last = np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 3)
        elif self.last is None:
            self.last = np.zeros((self.h, self.w, 3), np.uint8)
        return self.last

    def close(self):
        try:
            self.p.stdout.close(); self.p.kill(); self.p.wait()
        except OSError:
            pass


def _hue_rotate(F, ang):
    """Rotate hue of float RGB image by angle (radians) in YIQ space."""
    c, s = math.cos(ang), math.sin(ang)
    T = np.array([[0.299, 0.587, 0.114], [0.596, -0.274, -0.322], [0.211, -0.523, 0.312]], np.float32)
    Ti = np.linalg.inv(T).astype(np.float32)
    R = np.array([[1, 0, 0], [0, c, -s], [0, s, c]], np.float32)
    M = Ti @ R @ T
    return F @ M.T


class Finisher:
    """Per-frame look: grade, bloom, beat pulses, psychedelic effects, titles, vignette."""
    def __init__(self, w, h, story, dur, bass, energy, fps=30):
        self.w, self.h, self.story, self.dur, self.bass, self.en, self.fps = w, h, story, dur, bass, energy, fps
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
        self.vig = (1 - 0.38 * np.clip(r / 1.3, 0, 1) ** 2.2)[..., None].astype(np.float32)
        rng = np.random.default_rng(3)
        self.grain = [rng.normal(0, 3.5, (h, w, 1)).astype(np.float32) for _ in range(5)]
        ui = '/System/Library/Fonts/Avenir Next.ttc'; jp = '/System/Library/Fonts/ヒラギノ明朝 ProN.ttc'
        self.f_title = ImageFont.truetype(ui, 58 if w >= h else 34, index=5)
        self.f_jp = ImageFont.truetype(jp, 34, index=0)
        self.echo = None
        self.feat = None   # per-instrument features from stems.features(); falls back to the mix's low end

    def fx(self, name, i):
        if self.feat is not None and name in self.feat:
            a = self.feat[name]; return float(a[min(i, len(a) - 1)])
        if name in ('kick', 'bass'):
            return float(self.bass[min(i, len(self.bass) - 1)])
        if name == 'melody_phase':
            return i / self.fps * 0.6
        return 0.0

    def __call__(self, frame, i, shot, prev_scene_blend):
        t = i / self.fps; bass = float(self.bass[min(i, len(self.bass) - 1)])
        scene = shot['scene']
        F = frame.astype(np.float32)
        lift, gain, sat = GRADE.get(scene, ((0, 0, 0), (1, 1, 1), 1.0))
        F = F * np.array(gain, np.float32) + np.array(lift, np.float32)
        lum = F.mean(axis=2, keepdims=True)
        F = lum + (F - lum) * sat
        psy = 1.0 if scene == 'psy_tunnel' else (0.3 if scene == 'neon_downtown' else 0.0)
        # psychedelic: hue drift, mirror on strong kicks, zoom pulse, rgb split, light echo
        if psy > 0:
            if scene == 'psy_tunnel':
                F = _hue_rotate(F, (t * 0.35 + bass * 0.6) % (2 * math.pi))
                if bass > 0.75:
                    half = F[:, : self.w // 2]
                    F = np.concatenate([half, half[:, ::-1]], axis=1)[:, : self.w]
            pz = psy * bass
            if pz > 0.1:
                img = Image.fromarray(np.clip(F, 0, 255).astype(np.uint8))
                sc = 1 + 0.05 * pz
                cw, ch = int(self.w / sc), int(self.h / sc)
                z = img.crop(((self.w - cw) // 2, (self.h - ch) // 2, (self.w - cw) // 2 + cw,
                              (self.h - ch) // 2 + ch)).resize((self.w, self.h), Image.BILINEAR)
                F = F * (1 - 0.5 * pz) + np.asarray(z, np.float32) * 0.5 * pz
                sh = int(8 * pz)
                if sh:
                    F[:, sh:, 0] = F[:, :-sh, 0].copy(); F[:, :-sh, 2] = F[:, sh:, 2].copy()
            if scene == 'psy_tunnel':
                if self.echo is not None:
                    F = np.maximum(F, self.echo * 0.82)
                self.echo = F.copy()
        else:
            self.echo = None
        # bloom pulsing with the bass
        small = Image.fromarray(np.clip(F, 0, 255).astype(np.uint8)).resize((self.w // 4, self.h // 4), Image.BOX)
        s = np.asarray(small, np.float32)
        br = Image.fromarray(np.clip((s - 165) * 1.8, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6))
        bloom = np.asarray(br.resize((self.w, self.h), Image.BILINEAR), np.float32)
        kick, voc, snare, hats = self.fx('kick', i), self.fx('vocals', i), self.fx('snare', i), self.fx('hats', i)
        F += bloom * (0.35 + 0.5 * kick + 0.45 * voc + 0.25 * hats)
        F = (F - 110) * (1 + 0.07 * snare) + 110              # snare: contrast punch
        return self._finish_only(F, i, shot)


def annotate(shots):
    calm = {'rain_city', 'bridge_stars', 'tunnel'}
    for a, b in zip(shots, shots[1:]):
        a['next_calm'] = b['section_start'] and b['scene'] in calm
    if shots:
        shots[-1]['next_calm'] = False
    return shots


# ---------------------------------------------------------------- trip style
TRIP_LEVEL = {'rain_city': .35, 'expressway': .5, 'bridge_stars': .6, 'neon_downtown': .75,
              'tunnel': .6, 'psy_tunnel': 1.0, 'dawn_bay': .3}
KALEIDO = {'neon_downtown': .45, 'psy_tunnel': 1.0, 'bridge_stars': .25}


class TripFinisher(Finisher):
    """Psychedelic flow: breathing warp, colour waves, kaleidoscope, feedback trails."""
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        w, h = self.w, self.h
        self.gx, self.gy = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
        self.sw, self.sh = w // 8, h // 8
        sx, sy = np.meshgrid(np.linspace(0, 1, self.sw, dtype=np.float32), np.linspace(0, 1, self.sh, dtype=np.float32))
        self.sx, self.sy = sx, sy
        cx, cy = w / 2, h / 2
        self.ang = np.arctan2(self.gy - cy, self.gx - cx)
        self.rad = np.hypot(self.gx - cx, self.gy - cy)
        self.fb = None
        self.level = 0.0

    def _upsample(self, a):
        return np.asarray(Image.fromarray(a, mode='F').resize((self.w, self.h), Image.BILINEAR))

    def _gather(self, F, mx, my):
        xi = np.clip(mx, 0, self.w - 1).astype(np.int32); yi = np.clip(my, 0, self.h - 1).astype(np.int32)
        return F[yi, xi]

    def __call__(self, frame, i, shot, prev_scene_blend):
        t = i / self.fps
        kick, bstem, mel = self.fx('kick', i), self.fx('bass', i), self.fx('melody', i)
        voc, snare, hats, mph = self.fx('vocals', i), self.fx('snare', i), self.fx('hats', i), self.fx('melody_phase', i)
        bass = kick
        target = TRIP_LEVEL.get(shot['scene'], .5)
        self.level += (target - self.level) * 0.03          # glide between sections
        L = self.level
        F = frame.astype(np.float32)
        # 1. breathing / melting warp (computed coarse, then upsampled)
        amp = (6 + 22 * L) * (0.45 + 0.7 * bstem + 0.35 * kick)     # the bassline bends the picture
        dx = (np.sin(self.sy * 9 + mph * 1.2) + 0.6 * np.sin((self.sx + self.sy) * 13 - t * 1.4)) * amp
        dy = (np.cos(self.sx * 7 - t * 0.7) + 0.6 * np.sin((self.sx - self.sy) * 11 + t * 1.1)) * amp * 0.8
        breath = 1 - 0.035 * L * (0.5 + bass)               # whole image breathes in on kicks
        mx = (self.gx - self.w / 2) * breath + self.w / 2 + self._upsample(dx)
        my = (self.gy - self.h / 2) * breath + self.h / 2 + self._upsample(dy)
        F = self._gather(F, mx, my)
        # 2. kaleidoscope
        k = KALEIDO.get(shot['scene'], 0) * L
        if k > 0.05:
            seg = 2 * math.pi / 8
            a = np.abs(((self.ang + mph * 0.35) % seg) - seg / 2)   # the melody turns the kaleidoscope
            kx = self.w / 2 + self.rad * np.cos(a); ky = self.h / 2 + self.rad * np.sin(a)
            kal = self._gather(F, kx, ky)
            F = F * (1 - k) + kal * k
        # 3. colour waves: hue drifts in bands across the frame
        hue_amt = min(1.0, max(0.0, (L - 0.32) / 0.6))     # calm sections keep natural colour
        if hue_amt > 0.01:
            F = _hue_rotate(F, math.sin(mph * 0.5) * math.pi * hue_amt + (0.3 * kick + 0.4 * mel) * hue_amt)
        lum = F.mean(axis=2, keepdims=True)
        F = lum + (F - lum) * (1.15 + 0.45 * L)
        # 4. feedback trails: previous output zoomed + rotated, kept where brighter
        if self.fb is not None and L > 0.2:
            prev = Image.fromarray(np.clip(self.fb, 0, 255).astype(np.uint8))
            z = 1.012 + 0.02 * L * bass
            cw, ch = int(self.w / z), int(self.h / z)
            prev = prev.crop(((self.w - cw) // 2, (self.h - ch) // 2, (self.w - cw) // 2 + cw, (self.h - ch) // 2 + ch))
            prev = prev.resize((self.w, self.h), Image.BILINEAR).rotate(0.35 * L, resample=Image.BILINEAR)
            F = np.maximum(F, np.asarray(prev, np.float32) * (0.55 + 0.33 * L))
        self.fb = F
        # 5. glow, transitions, titles, grain (shared look)
        small = Image.fromarray(np.clip(F, 0, 255).astype(np.uint8)).resize((self.w // 4, self.h // 4), Image.BOX)
        s = np.asarray(small, np.float32)
        br = Image.fromarray(np.clip((s - 150) * 1.8, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(7))
        F = F + np.asarray(br.resize((self.w, self.h), Image.BILINEAR), np.float32) * (0.4 + 0.55 * kick + 0.6 * voc)
        F = (F - 110) * (1 + 0.1 * snare * L) + 110               # snare: contrast punch
        sh = int(5 * hats * L)                                       # hats: chromatic sparkle
        if sh:
            F[:, sh:, 0] = F[:, :-sh, 0].copy(); F[:, :-sh, 2] = F[:, sh:, 2].copy()
            F += np.clip(F - 200, 0, None) * 0.6 * hats
        return Finisher._finish_only(self, F, i, shot)


def _finish_only(self, F, i, shot):
    """Transitions, titles, vignette, grain and fades on an already-processed float frame."""
    t = i / self.fps
    if getattr(self, 'logo', None) is not None:
        F = self.logo.apply(np.array(F, np.float32), t, min(1.0, self.fx('kick', i) + 0.5 * self.fx('vocals', i)), shot, self.dur)
    if shot['section_start']:
        k = (t - shot['t0']) * self.fps
        if shot['scene'] in ('neon_downtown', 'psy_tunnel', 'dawn_bay') and k < 10:
            F = F + (1 - k / 10) ** 2 * 160
        elif k < 12:
            F = F * (0.25 + 0.75 * (k / 12))
    img = Image.fromarray(np.clip(F, 0, 255).astype(np.uint8)).convert('RGBA')
    self._chapters_and_warning(img, t)
    title, sub = self.story.get('title', ''), self.story.get('subtitle', '')
    if title:
        for a, b in ((2.5, 11.0), (self.dur - 16.0, self.dur - 3.5)):
            if a <= t <= b:
                kk = min(1, (t - a) / 1.5, (b - t) / 1.5); al = int(255 * max(0, kk) ** 2 * (3 - 2 * max(0, kk)))
                ov = Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
                y = self.h * 0.42
                d.rectangle([0, y - 100, self.w, y + 60], fill=(0, 0, 0, int(al * .3)))
                if sub:
                    d.text((self.w / 2, y - 50), sub, font=self.f_jp, fill=(235, 225, 255, int(al * .85)), anchor='mm')
                d.text((self.w / 2, y + 10), '   '.join(' '.join(wd) for wd in title.upper().split()),
                       font=self.f_title, fill=(255, 255, 255, al), anchor='mm')
                img.alpha_composite(ov)
    F = np.asarray(img.convert('RGB'), np.float32) * self.vig + self.grain[i % len(self.grain)]
    F *= min(1, max(0.35 if self.story.get('warning') else 0.0, t / 2.0), max(0, (self.dur - t) / 3.5))
    return np.clip(F, 0, 255).astype(np.uint8)


Finisher._finish_only = _finish_only


# ---------------------------------------------------------------- audio-reactive logo
class Logo:
    """Artist wordmark that pulses with the kick: small in a corner throughout, large and
    centred for a moment at each drop. Uses an image (PNG with alpha) if given, else text."""
    def __init__(self, w, h, text='TOKYO THAI', sub='東京タイ', image=None, color=(255, 120, 220)):
        self.w, self.h = w, h
        if image and os.path.exists(os.path.expanduser(image)):
            base = Image.open(os.path.expanduser(image)).convert('RGBA')
        else:
            ui = '/System/Library/Fonts/Avenir Next.ttc'; jp = '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc'
            f1 = ImageFont.truetype(ui, 120, index=5); f2 = ImageFont.truetype(jp, 54)
            spaced = '  '.join(text.upper())
            tw = int(f1.getlength(spaced)) + 80
            base = Image.new('RGBA', (tw, 260), (0, 0, 0, 0)); d = ImageDraw.Draw(base)
            d.text((tw // 2, 90), spaced, font=f1, fill=(255, 255, 255, 255), anchor='mm')
            if sub:
                d.text((tw // 2, 205), '   '.join(sub), font=f2, fill=(255, 255, 255, 220), anchor='mm')
        # neon glow version
        glow = base.filter(ImageFilter.GaussianBlur(14))
        g = np.asarray(glow).astype(np.float32)
        g[..., :3] = np.array(color, np.float32); g[..., 3] = np.clip(g[..., 3] * 2.2, 0, 255)
        self.img = Image.alpha_composite(Image.fromarray(g.astype(np.uint8)), base)
        self.cache = {}

    def _sized(self, width):
        width = max(8, int(width))
        if width not in self.cache:
            if len(self.cache) > 64:
                self.cache.clear()
            r = self.img.height / self.img.width
            self.cache[width] = np.asarray(self.img.resize((width, max(1, int(width * r))), Image.BILINEAR)).astype(np.float32) / 255.
        return self.cache[width]

    def _blend(self, F, spr, cx, cy, alpha):
        sh, sw = spr.shape[:2]
        x0, y0 = int(cx - sw / 2), int(cy - sh / 2)
        xa, ya, xb, yb = max(0, x0), max(0, y0), min(self.w, x0 + sw), min(self.h, y0 + sh)
        if xb <= xa or yb <= ya:
            return
        s = spr[ya - y0:yb - y0, xa - x0:xb - x0]
        a = s[..., 3:4] * alpha
        F[ya:yb, xa:xb] = F[ya:yb, xa:xb] * (1 - a) + s[..., :3] * 255 * a   # normal blend
        F[ya:yb, xa:xb] += s[..., :3] * 255 * a * 0.35                       # plus a little light

    def apply(self, F, t, bass, shot, dur):
        if t < 12 or t > dur - 4:          # keep the title cards clean
            return F
        pulse = 0.55 + 0.6 * bass
        cw = self.w * (0.2 if self.w >= self.h else 0.5) * (1 + 0.06 * bass)
        self._blend(F, self._sized(cw), self.w - cw * 0.6, self.h - cw * 0.3, min(1, 0.48 * pulse))
        if shot.get('section_start') and (shot.get('drop') or shot['scene'] in ('neon_downtown', 'psy_tunnel', 'dawn_bay')):
            k = t - shot['t0']
            if 0.15 < k < 2.2:
                env = math.sin(math.pi * (k - 0.15) / 2.05)
                self._blend(F, self._sized(self.w * 0.55 * (1 + 0.08 * bass + 0.05 * k)), self.w / 2, self.h / 2,
                            min(1, 0.55 * env * pulse))
        return F


# ---------------------------------------------------------------- story mode
def plan_storyboard(board, lib, audio, duration, seed=7):
    """Ordered shots from a storyboard timeline. Generated clips (shots_dir/<id>.mp4) play where the
    story says; anything not generated yet falls back to beat-cut stock from the shot's scene folder."""
    kicks = kick_times(audio)
    shots_dir = os.path.expanduser(board.get('shots_dir', ''))
    tl = sorted(board['timeline'], key=lambda e: e['at'])

    def snap(t):
        if t <= 0.5 or not len(kicks):
            return t
        k = kicks[np.argmin(np.abs(kicks - t))]
        return float(k) if abs(k - t) < 0.5 else t

    starts = [snap(e['at']) for e in tl]
    ends = starts[1:] + [duration]
    sections, fixed = [], {}
    for e, t0, t1 in zip(tl, starts, ends):
        scene = e.get('fill') or e.get('fallback', 'neon_downtown')
        sec = dict(start=t0, scene=scene, fx=e.get('fx'), drop=e.get('drop', False))
        if 'shot' in e:
            path = os.path.join(shots_dir, e['shot'] + '.mp4')
            if os.path.exists(path):
                du = probe(path)[0]
                rate = 1.0 if du >= t1 - t0 else max(0.5, du / (t1 - t0))
                fixed[len(sections)] = dict(clip=path, dur=du, rate=rate, shot_id=e['shot'])
            sec['shot_id'] = e['shot']
        sections.append(sec)

    story = {'sections': sections}
    auto = plan(story, lib, audio, duration, seed=seed)
    out = []
    for si, (sec, t1) in enumerate(zip(sections, ends)):
        mine = [s for s in auto if sec['start'] - 1e-6 <= s['t0'] < t1 - 1e-6]
        if si in fixed:
            f = fixed[si]
            hold = min(t1 - sec['start'], f['dur'] / f['rate'])
            out.append(dict(t0=sec['start'], t1=sec['start'] + hold, scene=sec['scene'], clip=f['clip'], cin=0.0,
                            rate=f['rate'], car=False, section_start=True, shot_id=f['shot_id'], fx=sec['fx'], drop=sec['drop']))
            # if the generated clip is shorter than its slot, keep going with stock cuts
            rest = [dict(s, section_start=False, fx=sec['fx']) for s in mine if s['t1'] > sec['start'] + hold + 0.3]
            if rest:
                rest[0]['t0'] = sec['start'] + hold
            out += rest
        else:
            out += [dict(s, fx=sec['fx'], shot_id=sec.get('shot_id'), drop=sec['drop'] and s['section_start']) for s in mine]
    return annotate(out)


def _chapters_and_warning(self, img, t):
    """Lower-left chapter cards (story 'chapters': [{at, time, jp, en}]) and an optional opening
    photosensitivity warning (story 'warning': true)."""
    if not hasattr(self, 'f_ch'):
        ui = '/System/Library/Fonts/Avenir Next.ttc'; jp = '/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc'
        sc = 1.0 if self.w >= self.h else 0.8
        self.f_ch = ImageFont.truetype(ui, int(26 * sc), index=5)
        self.f_ch_jp = ImageFont.truetype(jp, int(40 * sc))
        self.f_warn = ImageFont.truetype(ui, int(22 * sc), index=5)
    ov = None
    for ch in self.story.get('chapters', []):
        k = t - ch['at']
        if 0 <= k <= 5.0:
            a = min(1, k / 0.8, (5.0 - k) / 1.0)
            al = int(255 * a * a * (3 - 2 * a))
            ov = ov or Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
            x = int(self.w * 0.05); y = int(self.h * (0.80 if self.w >= self.h else 0.70))
            slide = int((1 - a) * 18)
            d.line([(x, y - 34), (x + 46, y - 34)], fill=(255, 140, 220, al), width=2)
            d.text((x + slide, y - 26), ch.get('time', ''), font=self.f_ch, fill=(255, 255, 255, int(al * .75)))
            d.text((x + slide, y + 6), ch['jp'], font=self.f_ch_jp, fill=(255, 255, 255, al))
            d.text((x + slide, y + 58), '  '.join(ch['en'].upper()), font=self.f_ch, fill=(255, 255, 255, int(al * .8)))
    if self.story.get('warning') and t < 3.2:
        a = min(1, t / 0.4, (3.2 - t) / 0.6)
        ov = ov or Image.new('RGBA', img.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
        d.text((self.w / 2, self.h * 0.9), 'PHOTOSENSITIVITY WARNING  ·  FLASHING LIGHTS AND PSYCHEDELIC IMAGERY',
               font=self.f_warn, fill=(255, 255, 255, int(200 * a)), anchor='mm')
    if ov is not None:
        img.alpha_composite(ov)


Finisher._chapters_and_warning = _chapters_and_warning
