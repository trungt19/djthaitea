#!/usr/bin/env python3
"""Journey engine: procedural audio-reactive night-drive renderer.

Driven by a compiled story (see story.py). Use journey.py as the CLI.
"""
import sys, os, math, colorsys, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SR = 22050

W, H, FPS = 1920, 1080, 30
HZ = int(H * 0.47)          # horizon line
CX = W / 2


def configure(w, h, fps=30):
    """Set output size before creating a Renderer (16:9 or 9:16)."""
    global W, H, FPS, HZ, CX
    W, H, FPS = w, h, fps
    HZ = int(H * (0.47 if w >= h else 0.6))
    CX = W / 2
FOC = 1050.0
CAMX = -1.75                # left-hand traffic: we drive in the right lane of the left carriageway
NEAR = 1.2

FONT_JP = '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'
FONT_JP_LIGHT = '/System/Library/Fonts/ヒラギノ明朝 ProN.ttc'
FONT_UI = '/System/Library/Fonts/Avenir Next.ttc'


# ---------------------------------------------------------------- helpers
def h01(*a):
    """Deterministic hash of ints -> [0,1)."""
    x = 2166136261
    for v in a:
        x = ((x ^ (int(v) & 0xffffffff)) * 16777619) & 0xffffffff
    x ^= x >> 15; x = (x * 0x2c1b3c6d) & 0xffffffff
    x ^= x >> 12; x = (x * 0x297a2d39) & 0xffffffff
    x ^= x >> 15
    return (x & 0xffffff) / float(0x1000000)


def lerp(a, b, k):
    if isinstance(a, tuple):
        return tuple(x + (y - x) * k for x, y in zip(a, b))
    return a + (b - a) * k


def smooth(k):
    return k * k * (3 - 2 * k)


def mixc(c, fog, f):
    return tuple(int(x + (y - x) * f) for x, y in zip(c, fog))


def scalec(c, k):
    return tuple(int(min(255, v * k)) for v in c)


def decode_audio(src, cache_dir):
    os.makedirs(cache_dir, exist_ok=True)
    out = os.path.join(cache_dir, 'audio.f32')
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(src):
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', src,
                        '-ac', '1', '-ar', str(SR), '-f', 'f32le', out], check=True)
    return np.fromfile(out, dtype=np.float32)


def audio_features(a, n):
    N = 2048; win = np.hanning(N)
    f = np.fft.rfftfreq(N, 1 / SR); lowm = f < 150
    rms = np.zeros(n); low = np.zeros(n)
    for i in range(n):
        c = int(i / FPS * SR); s = a[max(0, c - N // 2): c + N // 2]
        if len(s) < N: s = np.pad(s, (0, N - len(s)))
        sp = np.abs(np.fft.rfft(s * win))
        rms[i] = np.sqrt((s ** 2).mean()); low[i] = sp[lowm].sum()
    def norm(x):
        lo, hi = np.percentile(x, [5, 97]); return np.clip((x - lo) / (hi - lo + 1e-9), 0, 1)
    rms, low = norm(rms), norm(low)
    bass = np.zeros(n); en = np.zeros(n); b = e = 0.
    for i in range(n):
        b = low[i] if low[i] > b else b * 0.82
        e += (rms[i] - e) * 0.02
        bass[i] = b; en[i] = e
    return bass, en


# ---------------------------------------------------------------- assets
def make_skyline():
    rng = np.random.default_rng(7)
    PW, SH = W * 3, 430
    sil = Image.new('L', (PW, SH), 0); emi = Image.new('RGB', (PW, SH), (0, 0, 0))
    ds, de = ImageDraw.Draw(sil), ImageDraw.Draw(emi)
    blinks = []
    x = 0
    while x < PW:
        bw = int(rng.uniform(18, 80))
        cl = 0.5 + 0.5 * math.sin(x / PW * 2 * math.pi * 5 + 1.3)
        bh = int(rng.uniform(25, 110) + cl ** 2 * rng.uniform(0, 250))
        ds.rectangle([x, SH - bh, x + bw, SH], fill=255)
        for wy in range(SH - bh + 6, SH - 4, 7):
            for wx in range(x + 3, x + bw - 3, 6):
                if rng.random() < 0.22:
                    c = (255, 205, 150) if rng.random() < 0.6 else (170, 210, 255)
                    kk = rng.uniform(0.25, 0.8)
                    de.rectangle([wx, wy, wx + 2, wy + 2], fill=scalec(c, kk))
        if bh > 190 and rng.random() < 0.7:
            blinks.append((x + bw // 2, SH - bh - 2, rng.random()))
        x += bw + int(rng.uniform(-6, 4))
    # lattice tower (orange)
    tx, th = int(W * 1.25), 360
    ds.polygon([(tx - 46, SH), (tx + 46, SH), (tx + 3, SH - th), (tx - 3, SH - th)], fill=255)
    orange = (255, 120, 40)
    for s in (-1, 1):
        de.line([(tx + s * 46, SH), (tx + s * 3, SH - th)], fill=orange, width=3)
    for yy in range(SH - 10, SH - th, -14):
        frac = (SH - yy) / th; hw = 46 - 43 * frac
        de.line([(tx - hw, yy), (tx + hw, yy - 14)], fill=scalec(orange, .7), width=1)
        de.line([(tx + hw, yy), (tx - hw, yy - 14)], fill=scalec(orange, .7), width=1)
    for frac in (.36, .62):
        yy = SH - th * frac; hw = 46 - 43 * frac + 6
        de.rectangle([tx - hw, yy - 6, tx + hw, yy], fill=(255, 190, 130))
    blinks.append((tx, SH - th - 2, 0.3))
    # tall needle tower (blue-white)
    sx_, sh_ = int(W * 2.1), 425
    ds.polygon([(sx_ - 16, SH), (sx_ + 16, SH), (sx_ + 2, SH - sh_), (sx_ - 2, SH - sh_)], fill=255)
    for frac in (.55, .74):
        yy = SH - sh_ * frac
        ds.rectangle([sx_ - 12, yy - 8, sx_ + 12, yy], fill=255)
        de.rectangle([sx_ - 12, yy - 8, sx_ + 12, yy], fill=(170, 200, 255))
    for yy in range(SH - 6, int(SH - sh_ * .9), -9):
        de.point([(sx_ - 3, yy), (sx_ + 3, yy)], fill=(120, 160, 255))
    blinks.append((sx_, SH - sh_ - 2, 0.7))
    sil_a = np.asarray(sil, dtype=np.float32) / 255.
    emi_a = np.asarray(emi, dtype=np.float32)
    return sil_a, emi_a, blinks, PW, SH


SIGN_WORDS = ['東京', 'ラーメン', 'カラオケ', '居酒屋', 'ホテル', '天空', '星', '夢', '旅',
              '喫茶', '夜光', '酒場', '薬局', '書店', '銀河', '宇宙']
SIGN_COLS = [(255, 60, 180), (60, 230, 255), (255, 50, 70), (255, 210, 60), (80, 255, 150),
             (170, 100, 255), (255, 140, 40)]


def make_signs():
    font = ImageFont.truetype(FONT_JP, 92)
    sprites = []
    for idx, word in enumerate(SIGN_WORDS):
        col = SIGN_COLS[idx % len(SIGN_COLS)]
        n = len(word); sw, sh = 140, 60 + n * 104
        txt = Image.new('RGBA', (sw, sh), (0, 0, 0, 0)); dt = ImageDraw.Draw(txt)
        core = tuple(int(c * .45 + 255 * .55) for c in col)
        for j, ch in enumerate(word):
            dt.text((sw // 2, 40 + j * 104 + 46), ch, font=font, fill=core + (255,), anchor='mm')
        dt.rounded_rectangle([6, 6, sw - 7, sh - 7], radius=10, outline=col + (255,), width=6)
        glow = txt.filter(ImageFilter.GaussianBlur(9))
        panel = Image.new('RGBA', (sw, sh), (0, 0, 0, 0))
        ImageDraw.Draw(panel).rounded_rectangle([4, 4, sw - 5, sh - 5], radius=12, fill=(14, 8, 20, 235))
        # tint the glow with the neon colour
        g = np.asarray(glow).astype(np.float32)
        g[..., :3] = np.array(col, np.float32)
        g[..., 3] = np.clip(g[..., 3] * 1.6, 0, 255)
        out = Image.alpha_composite(panel, Image.fromarray(g.astype(np.uint8)))
        out = Image.alpha_composite(out, txt)
        sprites.append(out)
    return sprites


# ---------------------------------------------------------------- camera
class Cam:
    def __init__(self, curv, camh, sway):
        self.curv, self.camh, self.sway = curv, camh, sway

    def P(self, x, y, z):
        z = max(z, NEAR)
        xr = x - CAMX + self.curv * z * z
        return (CX + FOC * xr / z + self.sway, HZ + FOC * (self.camh - y) / z)

    def quad(self, x0, x1, y0, y1, z0, z1):
        """Quad on plane: if x0==x1 a vertical wall along z; if z0==z1 a facing rect; else ground."""
        if z0 == z1:
            return [self.P(x0, y0, z0), self.P(x1, y0, z0), self.P(x1, y1, z0), self.P(x0, y1, z0)]
        if x0 == x1:
            return [self.P(x0, y0, z0), self.P(x0, y1, z0), self.P(x0, y1, z1), self.P(x0, y0, z1)]
        return [self.P(x0, y0, z0), self.P(x1, y0, z0), self.P(x1, y0, z1), self.P(x0, y0, z1)]


def fogf(z, fogd):
    return 1 - math.exp(-max(z, 0) / fogd)


def add_glow(G, x, y, rx, ry, col, inten):
    if inten <= 0.003 or rx < 0.3: return
    rx = min(rx, 260); ry = min(ry, 420)
    x0, x1 = int(x - 3 * rx), int(x + 3 * rx) + 1
    y0, y1 = int(y - 3 * ry), int(y + 3 * ry) + 1
    if x1 < 0 or y1 < 0 or x0 >= W or y0 >= H: return
    cx0, cx1, cy0, cy1 = max(x0, 0), min(x1, W), max(y0, 0), min(y1, H)
    xs = (np.arange(cx0, cx1) - x) / rx; ys = (np.arange(cy0, cy1) - y) / ry
    g = np.exp(-(ys[:, None] ** 2 + xs[None, :] ** 2) * 1.6).astype(np.float32)
    G[cy0:cy1, cx0:cx1] += g[..., None] * (np.array(col, np.float32) * inten)


# ---------------------------------------------------------------- renderer
class Renderer:
    def __init__(self, compiled, audio):
        self.story = compiled
        self.dur = len(audio) / SR
        self.n = int(math.ceil(self.dur * FPS))
        self.bass, self.en = audio_features(audio, self.n)
        self.P = [compiled.params(i / FPS) for i in range(self.n)]
        sp = np.array([p['speed'] for p in self.P]) * (0.92 + 0.16 * self.en)
        self.dist = np.cumsum(sp / FPS)
        fi = lambda tt: min(self.n - 1, int(tt * FPS))
        self.tunnels = [(self.dist[fi(a)], self.dist[fi(b)]) for a, b in compiled.tunnels]
        self.sil, self.emi, self.blinks, self.PW, self.SH = make_skyline()
        self.signs = make_signs()
        rng = np.random.default_rng(11)
        ns = 1500
        self.star_y = rng.integers(0, int(HZ * .93), ns); self.star_x = rng.integers(0, W, ns)
        self.star_b = rng.uniform(40, 255, ns) ** 1.0 * rng.uniform(0.2, 1, ns)
        self.star_ph = rng.uniform(0, 6.28, ns)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - CX) / CX) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        self.vig = (1 - 0.42 * np.clip(r / 1.3, 0, 1) ** 2.4)[..., None].astype(np.float32)
        self.grain = [rng.normal(0, 4.5, (H, W, 1)).astype(np.float32) for _ in range(6)]
        self.f_title = ImageFont.truetype(FONT_UI, 58 if W >= H else 34, index=5)
        self.f_title_b = ImageFont.truetype(FONT_UI, 64, index=5)
        self.f_jp = ImageFont.truetype(FONT_JP_LIGHT, 34, index=0)
        self.f_small = ImageFont.truetype(FONT_UI, 22, index=5)
        self.f_speed = ImageFont.truetype(FONT_UI, 40, index=2)

    # ------------------------------------------------------------ sky / far layer
    def sky(self, t, st, cam_off):
        F = np.empty((H, W, 3), np.float32)
        ky = (np.arange(HZ, dtype=np.float32) / HZ)[:, None] ** 1.6
        F[:HZ] = (np.array(st['skyT'], np.float32) * (1 - ky) + np.array(st['skyB'], np.float32) * ky)[:, None, :]
        kg = (np.arange(H - HZ, dtype=np.float32) / (H - HZ))[:, None] ** 0.5
        ground = np.array(st['fog'], np.float32) * 0.55 * (1 - kg) + np.array((5, 5, 8), np.float32) * kg
        F[HZ:] = ground[:, None, :]
        G = np.zeros_like(F)
        if st['stars'] > 0.01:
            tw = 0.6 + 0.4 * np.sin(t * 2.3 + self.star_ph)
            v = (self.star_b * tw * st['stars']).astype(np.float32)
            np.add.at(F, (self.star_y, self.star_x), v[:, None] * np.array([.85, .9, 1.], np.float32))
        if st['moon'] > 0.01:
            mx, my = W * 0.73, 150
            add_glow(G, mx, my, 150, 150, (120, 130, 200), 0.5 * st['moon'])
            add_glow(G, mx, my, 26, 26, (255, 255, 255), 3.0 * st['moon'])
        if st['sun'] > 0.01:
            sx, sy = W * 0.6 + cam_off * 0.3, HZ + 40 - 210 * st['sun']
            add_glow(G, sx, sy, 520, 230, (255, 120, 70), 0.75 * min(1, st['sun'] * 2))
            add_glow(G, sx, sy, 60, 60, (255, 230, 190), 3.5 * min(1, st['sun'] * 1.5))
        F += G
        # skyline
        ox = int(np.clip(W + cam_off, 0, self.PW - W))
        sil = self.sil[:, ox:ox + W][..., None]; emi = self.emi[:, ox:ox + W]
        y0 = HZ - self.SH
        silc = np.array(st['fog'], np.float32) * 0.42 + np.array(st['skyT'], np.float32) * 0.2
        haze = (np.linspace(0, 1, self.SH, dtype=np.float32) ** 2 * 0.35)[:, None, None]
        region = F[y0:HZ]
        region[:] = region * (1 - sil) + silc * sil
        region[:] = region * (1 - haze * sil) + np.array(st['fog'], np.float32) * haze * sil
        citylight = (1 - 0.65 * st['sun']) * (0.7 + 0.3 * st['glow'])
        region += emi * citylight
        for bx, by, ph in self.blinks:
            x = bx - ox
            if 0 <= x < W and ((t * 0.9 + ph) % 1) < 0.45:
                add_glow(F, x, y0 + by, 3, 3, (255, 40, 40), 1.2 * citylight)
        # water reflection
        if st['water'] > 0.01:
            R = H - HZ
            src = F[HZ - min(R, HZ):HZ][::-1]
            rows = src.shape[0]
            yy = np.arange(rows)
            shift = (np.sin(yy * 0.35 + t * 2.1) * (2 + yy * 0.05) + np.sin(yy * 0.11 - t * 1.3) * 3).astype(int)
            cols = (np.arange(W)[None, :] + shift[:, None]) % W
            refl = src[yy[:, None], cols] * 0.5
            fade = (1 - (yy / rows)) [:, None, None] ** 0.7
            water = np.array(st['skyB'], np.float32) * 0.18 + np.array((3, 5, 12), np.float32)
            wv = refl * fade + water * (1 - fade * 0.5)
            k = st['water']
            F[HZ:HZ + rows] = F[HZ:HZ + rows] * (1 - k) + wv * k
        return F

    # ------------------------------------------------------------ world
    def draw_world(self, img, cam, t, st, dist, Gout, bass, i):
        d = ImageDraw.Draw(img)
        fog, fd = st['fog'], st['fogd']
        # side buildings (far -> near)
        L = 26.0
        if st['city'] > 0.01:
            i0 = int((dist + NEAR - 40) // L); i1 = int((dist + 300) // L) + 1
            for side in (-1, 1):
                for bi in range(i1, i0 - 1, -1):
                    if h01(bi, side, 7) > st['city']: continue
                    z1 = bi * L - dist + h01(bi, side, 1) * 4
                    z2 = z1 + L - 3 - h01(bi, side, 2) * 6
                    if z2 < NEAR or z1 > 300: continue
                    hgt = 10 + h01(bi, side, 3) ** 1.5 * 45
                    xf = side * (10.5 + h01(bi, side, 4) * 3)
                    z1c = max(z1, NEAR)
                    zm = (z1c + z2) / 2; fz = fogf(zm, fd)
                    d.polygon(cam.quad(xf, xf, 0, hgt, z1c, z2), fill=mixc((16, 15, 26), fog, fz))
                    # shop front at street level
                    if h01(bi, side, 9) < 0.55:
                        sc = [(210, 235, 255), (255, 210, 150), (255, 120, 170), (140, 255, 210)][int(h01(bi, side, 10) * 4)]
                        d.polygon(cam.quad(xf, xf, 0.3, 2.6, z1c, min(z2, z1c + 14)),
                                  fill=mixc(scalec(sc, .5), fog, fz * .6))
                    # windows
                    nf = int(hgt / 3.4); nc = int((z2 - z1) / 3.2)
                    for fl in range(1, nf):
                        for c in range(nc):
                            if h01(bi, side, fl, c) > 0.42: continue
                            za = z1 + c * 3.2 + 0.8; zb = za + 1.4
                            if za < NEAR: continue
                            wc = (255, 205, 150) if h01(bi, side, fl, c, 3) < 0.65 else (170, 215, 255)
                            kk = 0.3 + 0.45 * h01(bi, side, fl, c, 5)
                            d.polygon(cam.quad(xf, xf, fl * 3.4 + 1.0, fl * 3.4 + 2.3, za, zb),
                                      fill=mixc(scalec(wc, kk), fog, fogf(za, fd) * .75))
                    if z1 > NEAR:
                        d.polygon(cam.quad(xf, xf + side * 14, 0, hgt, z1, z1), fill=mixc((24, 22, 36), fog, fogf(z1, fd)))
        # road surface + barriers
        zs = NEAR * (650 / NEAR) ** np.linspace(0, 1, 56)
        for za, zb in zip(zs[::-1][1:], zs[::-1][:-1]):  # far first
            zm = (za + zb) / 2; fz = fogf(zm, fd)
            d.polygon(cam.quad(-7.8, 7.8, 0, 0, za, zb), fill=mixc((19, 19, 26), fog, fz))
            for bx in (-7.8, 7.8):
                d.polygon(cam.quad(bx, bx, 0, 1.0, za, zb), fill=mixc((38, 38, 50), fog, fz))
            for lx, lc in ((-7.2, (200, 200, 210)), (7.2, (200, 200, 210)), (-0.15, (220, 170, 60)), (0.15, (220, 170, 60))):
                d.polygon(cam.quad(lx - .07, lx + .07, 0, 0, za, zb), fill=mixc(scalec(lc, .75), fog, fz))
        # dashes
        k0 = int((dist + NEAR) // 12); k1 = int((dist + 260) // 12) + 1
        for kk in range(k1, k0 - 1, -1):
            z1 = kk * 12 - dist; z2 = z1 + 5
            if z2 < NEAR: continue
            z1 = max(z1, NEAR); fz = fogf(z1, fd)
            for lx in (-3.5, 3.5):
                d.polygon(cam.quad(lx - .08, lx + .08, 0, 0, z1, z2), fill=mixc((160, 160, 170), fog, fz))
        # street lights
        wet = 0.35 + 0.65 * st['rain'] + 0.3 * st['water']
        lamp = st['lamp']
        k0 = int((dist + NEAR) // 38); k1 = int((dist + 360) // 38) + 1
        for kk in range(k1, k0 - 1, -1):
            z = kk * 38 - dist + 19
            if z < NEAR + 1.5 or z > 360: continue
            fz = fogf(z, fd); wpx = max(1, int(FOC * 0.22 / z))
            for s in (-1, 1):
                b = cam.P(s * 8.4, 0, z); top = cam.P(s * 8.4, 9.2, z); lp = cam.P(s * 6.0, 9.0, z)
                pc = mixc((26, 26, 34), fog, fz)
                d.line([b, top], fill=pc, width=wpx); d.line([top, lp], fill=pc, width=wpx)
                rad = FOC * 0.55 / z + 1.5; inten = (1 - fz * .8) * st['glow']
                add_glow(Gout, lp[0], lp[1], rad, rad, lamp, 1.6 * inten)
                add_glow(Gout, lp[0], lp[1], rad * 4, rad * 4, lamp, 0.18 * inten)
                rp = cam.P(s * 6.0, 0, z)
                add_glow(Gout, rp[0], rp[1] + rad * 3, rad * 0.9, rad * 5, lamp, 0.35 * inten * wet)
        # neon signs (billboards facing the camera)
        if st['neon'] > 0.01 and st['city'] > 0.01:
            items = []
            i0 = int((dist + NEAR) // L); i1 = int((dist + 240) // L) + 1
            for side in (-1, 1):
                for bi in range(i0, i1 + 1):
                    if h01(bi, side, 7) > st['city'] or h01(bi, side, 21) > st['neon'] * 0.75: continue
                    xf = side * (10.5 + h01(bi, side, 4) * 3)
                    hgt = 10 + h01(bi, side, 3) ** 1.5 * 45
                    z = bi * L - dist + h01(bi, side, 1) * 4 + 2.0
                    if z < NEAR + 2: continue
                    items.append((z, side, bi, xf, hgt))
            items.sort(key=lambda v: -v[0])
            for z, side, bi, xf, hgt in items:
                spr = self.signs[int(h01(bi, side, 22) * len(self.signs))]
                wm = 1.5; hm = wm * spr.height / spr.width
                yc = 3.5 + hm / 2 + h01(bi, side, 23) * max(0, min(hgt - hm - 4, 9))
                p = cam.P(xf - side * 1.3, yc, z)
                pw = FOC * wm / z; ph = pw * spr.height / spr.width
                if pw < 2: continue
                # occasional flicker
                if h01(bi, side, 24) < 0.15 and h01(bi, side, int(t * 12)) < 0.25: continue
                s2 = spr.resize((max(1, int(pw)), max(1, int(ph))), Image.BILINEAR)
                fz = fogf(z, st['fogd']) * 0.7
                if fz > 0.05:
                    a = s2.getchannel('A').point(lambda v: int(v * (1 - fz)))
                    s2.putalpha(a)
                img.paste(s2, (int(p[0] - pw / 2), int(p[1] - ph / 2)), s2)
                if z < 120:
                    col = SIGN_COLS[int(h01(bi, side, 22) * len(self.signs)) % len(SIGN_COLS)]
                    add_glow(Gout, p[0], p[1], pw * 1.2, ph * 0.6, col, 0.12 * (1 - fz) * (0.7 + 0.6 * bass * st['psy'] + 0.3 * bass))

    def tunnel(self, cam, t, st, dist, bass, za, zb):
        T = Image.new('RGB', (W, H), (14, 9, 6)); d = ImageDraw.Draw(T)
        G = np.zeros((H, W, 3), np.float32)
        tf = (16, 10, 6); fd = 85.
        psy = st['psy']
        def lightcol(zl):
            base = np.array((255, 150, 55), np.float32)
            hcol = np.array(colorsys.hsv_to_rgb((t * 0.06 + zl * 0.0035 + (dist - zl) * 0.0) % 1, 0.85, 1.0), np.float32) * 255
            hue2 = (t * 0.06 - (zl + dist) * 0.004) % 1
            hcol = np.array(colorsys.hsv_to_rgb(hue2, 0.85, 1.0), np.float32) * 255
            return base * (1 - psy) + hcol * psy
        z_lo = max(za, NEAR); z_hi = min(zb, 420.)
        if z_hi <= z_lo: return None
        amb = lightcol(z_lo + 10) * (0.18 + 0.12 * bass * psy)
        wall = tuple(int(v) for v in np.clip(amb * 0.4 + 20, 0, 255))
        ceil = tuple(int(v) for v in np.clip(amb * 0.25 + 12, 0, 255))
        zs = z_lo * (z_hi / z_lo) ** np.linspace(0, 1, 40)
        for z1, z2 in zip(zs[::-1][1:], zs[::-1][:-1]):
            fz = fogf((z1 + z2) / 2, fd)
            d.polygon(cam.quad(-8, -8, 0, 6.2, z1, z2), fill=mixc(wall, tf, fz))
            d.polygon(cam.quad(8, 8, 0, 6.2, z1, z2), fill=mixc(wall, tf, fz))
            d.polygon([cam.P(-8, 6.2, z1), cam.P(8, 6.2, z1), cam.P(8, 6.2, z2), cam.P(-8, 6.2, z2)], fill=mixc(ceil, tf, fz))
            d.polygon(cam.quad(-8, 8, 0, 0, z1, z2), fill=mixc((22, 20, 22), tf, fz))
            for lx in (-7.2, 7.2, -0.15, 0.15):
                d.polygon(cam.quad(lx - .07, lx + .07, 0, 0, z1, z2), fill=mixc((170, 160, 140), tf, fz))
            for bx in (-7.9, 7.9):  # lower wall stripe
                d.polygon(cam.quad(bx, bx, 0.9, 1.2, z1, z2), fill=mixc((150, 140, 120), tf, fz))
        k0 = int((dist + z_lo) // 12); k1 = int((dist + min(z_hi, 260)) // 12) + 1
        for kk in range(k1, k0 - 1, -1):
            z1 = kk * 12 - dist; z2 = z1 + 5
            if z2 < z_lo or z1 > z_hi: continue
            z1 = max(z1, z_lo)
            d.polygon(cam.quad(-3.58, -3.42, 0, 0, z1, min(z2, z_hi)), fill=mixc((200, 195, 185), tf, fogf(z1, fd)))
        # wall panel seams for motion
        k0 = int((dist + z_lo) // 6); k1 = int((dist + min(z_hi, 200)) // 6) + 1
        for kk in range(k1, k0 - 1, -1):
            zl = kk * 6 - dist
            if zl < z_lo or zl > z_hi: continue
            c = mixc((8, 6, 6), tf, fogf(zl, fd))
            for s in (-1, 1):
                d.line([cam.P(s * 8, 0, zl), cam.P(s * 8, 6.2, zl)], fill=c, width=max(1, int(FOC * 0.08 / zl)))
        # psychedelic portal rings
        if psy > 0.2:
            k0 = int((dist + z_lo) // 24); k1 = int((dist + z_hi) // 24) + 1
            for kk in range(k1, k0 - 1, -1):
                zl = kk * 24 - dist
                if zl < max(z_lo, 3) or zl > z_hi: continue
                col = lightcol(zl + 40); fz = fogf(zl, fd * 1.4)
                c = tuple(int(v) for v in np.clip(col * (0.6 + 0.8 * bass) * psy * (1 - fz) + np.array(tf) * fz, 0, 255))
                ring = [cam.P(-7.6, 0.4, zl), cam.P(-7.6, 5.9, zl), cam.P(7.6, 5.9, zl), cam.P(7.6, 0.4, zl)]
                d.line(ring, fill=c, width=max(1, int(FOC * 0.18 / zl)))
                if zl < 90:
                    for q in ring[1:3]:
                        add_glow(G, q[0], q[1], FOC * 1.2 / zl, FOC * 1.2 / zl, col, 0.25 * psy * (1 - fz) * (0.5 + bass))
        # light fixtures
        strobe = 0.75 + 0.6 * bass * psy
        k0 = int((dist + z_lo) // 5); k1 = int((dist + z_hi) // 5) + 1
        for kk in range(k1, k0 - 1, -1):
            zl = kk * 5 - dist
            if zl < z_lo or zl + 2.6 > z_hi: continue
            col = lightcol(zl); fz = fogf(zl, fd * 1.6)
            c = tuple(int(v) for v in np.clip(col * strobe * (1 - fz) + np.array(tf) * fz, 0, 255))
            wpx = max(1, int(FOC * 0.28 / zl))
            for s in (-1, 1):
                d.line([cam.P(s * 7.5, 5.6, zl), cam.P(s * 7.5, 5.6, zl + 2.6)], fill=c, width=wpx)
                if zl < 70:
                    p = cam.P(s * 7.5, 5.6, zl + 1.3)
                    r = FOC * 0.5 / zl
                    add_glow(G, p[0], p[1], r * 1.6, r, col, 0.35 * strobe * (1 - fz))
                    rp = cam.P(s * 7.0, 0, zl + 1.3)
                    add_glow(G, rp[0], rp[1] + r * 2, r * 0.8, r * 3.5, col, 0.12 * strobe * (1 - fz))
            if psy > 0.3 and kk % 2 == 0:  # centre ceiling strip during the psychedelic peak
                d.line([cam.P(0, 6.15, zl), cam.P(0, 6.15, zl + 2.6)], fill=c, width=wpx)
        mask = Image.new('L', (W, H), 0); dm = ImageDraw.Draw(mask)
        R = lambda z: [cam.P(-8, 0, z), cam.P(8, 0, z), cam.P(8, 6.2, z), cam.P(-8, 6.2, z)]
        if za <= NEAR: dm.rectangle([0, 0, W, H], fill=255)
        else: dm.polygon(R(za), fill=255)
        if zb < 420: dm.polygon(R(zb), fill=0)
        return T, mask, G

    def draw_cars(self, img, cam, t, st, dist, G, bass):
        d = ImageDraw.Draw(img); fog, fd = st['fog'], st['fogd']
        intunnel = any((di - dist) <= 10 and (do - dist) > 0 for di, do in self.tunnels)
        if intunnel: fog, fd = (16, 10, 6), 85.
        wet = 0.35 + 0.65 * st['rain'] + 0.3 * st['water']
        cars = []
        cars.append((CAMX + 0.15 * math.sin(t * 0.3), 24 + 5 * math.sin(t * 0.13), 'tail', 1.0))
        rel = 0.28 * dist
        for kk in range(int((rel + 3) // 85), int((rel + 320) // 85) + 1):
            z = kk * 85 - rel
            if 3 < z < 320 and h01(kk, 77) < 0.7: cars.append((-5.25, z, 'tail', 0.8))
        rel = 1.9 * dist
        for kk in range(int((rel + 3) // 110), int((rel + 420) // 110) + 1):
            z = kk * 110 - rel
            if 3 < z < 420 and h01(kk, 99) < 0.6:
                cars.append((1.75 if h01(kk, 98) < 0.5 else 5.25, z, 'head', 1.0))
        cars.sort(key=lambda c: -c[1])
        for x, z, kind, k in cars:
            fz = fogf(z, fd)
            if kind == 'tail':
                d.polygon(cam.quad(x - .9, x + .9, .25, 1.35, z, z), fill=mixc((12, 12, 16), fog, fz))
                d.polygon([cam.P(x - .78, 1.35, z), cam.P(x + .78, 1.35, z), cam.P(x + .6, 1.85, z), cam.P(x - .6, 1.85, z)],
                          fill=mixc((9, 9, 13), fog, fz))
                brake = (0.6 + 0.7 * bass) * k
                for s in (-1, 1):
                    d.polygon(cam.quad(x + s * .55, x + s * .86, .88, 1.02, z, z), fill=mixc((255, 70, 70), fog, fz * .5))
                    p = cam.P(x + s * .7, .95, z); r = FOC * 0.16 / z + 1
                    add_glow(G, p[0], p[1], r * 1.4, r, (255, 25, 35), 1.2 * brake * (1 - fz * .7))
                    rp = cam.P(x + s * .7, 0, z)
                    add_glow(G, rp[0], rp[1] + r * 2.5, r * .8, r * 4.5, (255, 30, 40), 0.35 * brake * wet * (1 - fz))
            else:
                for s in (-1, 1):
                    p = cam.P(x + s * .7, .7, z); r = FOC * 0.2 / z + 1
                    add_glow(G, p[0], p[1], r * 1.6, r * 1.2, (255, 240, 215), 1.6 * (1 - fz * .7))
                    add_glow(G, p[0], p[1], r * 9, r * .35, (190, 210, 255), 0.25 * (1 - fz))  # anamorphic flare
                    rp = cam.P(x + s * .7, 0, z)
                    add_glow(G, rp[0], rp[1] + r * 3, r, r * 6, (255, 235, 210), 0.3 * wet * (1 - fz))

    # ------------------------------------------------------------ frame
    def frame(self, i):
        t = i / FPS; st = self.P[i]; dist = float(self.dist[i]); bass = float(self.bass[i])
        curv = 0.00022 * math.sin(2 * math.pi * t / 47) + 0.00012 * math.sin(2 * math.pi * t / 19 + 1)
        camh = 1.25 + 0.012 * math.sin(dist * 1.7) + 0.008 * math.sin(dist * 0.53)
        sway = 0.0
        cam = Cam(curv, camh, sway)
        cam_off = -curv * FOC * 380 + 500 * math.sin(2 * math.pi * t / 240)
        F = self.sky(t, st, cam_off)
        O = Image.fromarray(np.clip(F, 0, 255).astype(np.uint8))
        Gout = np.zeros((H, W, 3), np.float32)
        self.draw_world(O, cam, t, st, dist, Gout, bass, i)
        za, zb = 1e9, -1e9
        for di, do in self.tunnels:  # the tunnel we are in or approaching
            if do - dist > NEAR and di - dist < 500:
                za, zb = di - dist, do - dist; break
        Gin = None; m = None
        if zb > NEAR and za < 500:
            if za > NEAR:  # portal facade
                fz = fogf(za, st['fogd'])
                ImageDraw.Draw(O).polygon(cam.quad(-34, 34, 0, 16, za, za), fill=mixc((30, 30, 38), st['fog'], fz))
                ImageDraw.Draw(O).polygon(cam.quad(-6, 6, 7.4, 9.4, za, za), fill=mixc((20, 95, 65), st['fog'], fz))
            res = self.tunnel(cam, t, st, dist, bass, za, zb)
            if res:
                T, mask, Gin = res
                O = Image.composite(T, O, mask)
                m = (np.asarray(mask, np.float32) / 255.)[..., None]
        if m is not None:
            Gout = Gout * (1 - m) + Gin
        self.draw_cars(O, cam, t, st, dist, Gout, bass)
        F = np.asarray(O, np.float32) + Gout
        # exposure: dark adaptation in tunnel, flash when exiting
        expo = 1.0
        if zb > 0: expo += 0.9 * math.exp(-max(zb, 0) / 10) * (1 if za < 0 else 0)
        F *= expo
        # bloom
        small = Image.fromarray(np.clip(F, 0, 255).astype(np.uint8)).resize((W // 4, H // 4), Image.BOX)
        s = np.asarray(small, np.float32)
        br = Image.fromarray(np.clip((s - 150) * 1.8, 0, 255).astype(np.uint8))
        b1 = np.asarray(br.filter(ImageFilter.GaussianBlur(5)), np.float32)
        b2 = np.asarray(br.resize((W // 16, H // 16), Image.BOX).filter(ImageFilter.GaussianBlur(6)).resize((W // 4, H // 4), Image.BILINEAR), np.float32)
        bloom = Image.fromarray(np.clip(b1 * 0.8 + b2 * 1.2, 0, 255).astype(np.uint8)).resize((W, H), Image.BILINEAR)
        F += np.asarray(bloom, np.float32) * st['glow'] * (0.5 + 0.6 * bass)
        # psychedelic zoom pulse + chromatic split on kicks
        pz = st['psy'] * bass
        if pz > 0.08:
            img = Image.fromarray(np.clip(F, 0, 255).astype(np.uint8))
            acc = F * 0.5
            for sc, wgt in ((1.025, 0.3), (1.05, 0.2)):
                sc = 1 + (sc - 1) * pz * 1.6
                cw, ch = int(W / sc), int(H / sc)
                z = img.crop(((W - cw) // 2, (H - ch) // 2, (W - cw) // 2 + cw, (H - ch) // 2 + ch)).resize((W, H), Image.BILINEAR)
                acc = acc + np.asarray(z, np.float32) * wgt
            F = F * (1 - pz) + acc * pz
            sh = int(6 * pz)
            if sh > 0:
                F[:, sh:, 0] = F[:, :-sh, 0].copy(); F[:, :-sh, 2] = F[:, sh:, 2].copy()
        # wet windshield softness
        if st['rain'] > 0.02:
            img = Image.fromarray(np.clip(F, 0, 255).astype(np.uint8))
            bl = img.resize((W // 2, H // 2), Image.BILINEAR).filter(ImageFilter.GaussianBlur(3)).resize((W, H), Image.BILINEAR)
            k = 0.45 * st['rain']
            F = F * (1 - k) + np.asarray(bl, np.float32) * k
        img = Image.fromarray(np.clip(F, 0, 255).astype(np.uint8)).convert('RGBA')
        self.overlay(img, t, st, i)
        F = np.asarray(img.convert('RGB'), np.float32)
        F = F * self.vig + self.grain[i % len(self.grain)]
        fade = min(1, t / 2.0, max(0, (self.dur - t) / 3.5))
        F *= fade
        return np.clip(F, 0, 255).astype(np.uint8)

    def overlay(self, img, t, st, i):
        ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
        # raindrops on the windshield
        rain = st['rain']
        if rain > 0.02:
            for k in range(420):
                if h01(k, 1) > rain: continue
                rate = 0.06 + 0.2 * h01(k, 2); p = (t * rate + h01(k, 3)) % 1
                env = math.sin(math.pi * p)
                x = h01(k, 4) * W; y = h01(k, 5) * (H - 160); r = 2 + 6 * h01(k, 6) ** 2
                if h01(k, 7) < 0.22:
                    trail = p * (60 + 220 * h01(k, 8)); y += trail
                    d.line([(x, y - trail), (x, y)], fill=(190, 200, 220, int(28 * env)), width=max(1, int(r * .7)))
                d.ellipse([x - r, y - r * 1.1, x + r, y + r * 1.1], fill=(200, 210, 235, int(34 * env)),
                          outline=(0, 0, 0, int(60 * env)))
                d.ellipse([x - r * .45, y - r * .7, x - r * .05, y - r * .3], fill=(255, 255, 255, int(150 * env)))
        # dashboard silhouette
        xs = np.linspace(0, W, 80)
        top = H - 70 - 75 * np.exp(-((xs - W * 0.52) / (W * 0.42)) ** 2)
        pts = [(0, H)] + list(zip(xs, top)) + [(W, H)]
        d.polygon(pts, fill=(5, 5, 7, 255))
        d.line(list(zip(xs, top)), fill=(48, 48, 64, 255), width=2)
        kmh = int(self.P[i]['speed'] * (0.92 + 0.16 * self.en[i]) * 3.6)
        d.text((W * 0.70, H - 58), f'{kmh}', font=self.f_speed, fill=(120, 220, 255, 220), anchor='rm')
        d.text((W * 0.70 + 8, H - 52), 'km/h', font=self.f_small, fill=(120, 220, 255, 160), anchor='lm')
        # titles
        title, sub = self.story.title, self.story.subtitle
        for (a, b) in ((2.5, 11.0), (self.dur - 16.0, self.dur - 3.5)):
            if title and a <= t <= b:
                k = min(1, (t - a) / 1.5, (b - t) / 1.5)
                al = int(255 * smooth(max(0, k)))
                d.rectangle([0, H * 0.40 - 110, W, H * 0.40 + 60], fill=(0, 0, 0, int(al * .28)))
                d.text((W / 2, H * 0.40 - 52), sub, font=self.f_jp, fill=(235, 225, 255, int(al * .85)), anchor='mm')
                d.text((W / 2, H * 0.40 + 10), '   '.join(' '.join(w) for w in title.upper().split()), font=self.f_title,
                       fill=(255, 255, 255, al), anchor='mm')
        img.alpha_composite(ov)
