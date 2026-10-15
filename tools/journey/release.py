#!/usr/bin/env python3
"""One command from a new Suno song to a release package.

  python3 release.py ~/Downloads/"New Song.mp3" --title "Above the Clouds" --subtitle "雲の上"

Steps (each is skipped when its output already exists; --force redoes everything):
  1. stems + per-instrument features (Demucs)
  2. analysis: sections, key, drops, breakdowns, where the ending starts
  3. story draft (scenes per section, chapters, warning)
  4. enhancement: sonic logo, vocal throws, risers + impacts, ghost chops, your choir (if recorded), clean ending
  5. master (-9.5 LUFS, true peak <= -1 dB) + DJ Extended Mix
  6. psychedelic visualizer (Trip) from the clip library, enhanced audio swapped in, 4K upload copy
  7. three vertical Shorts at the biggest drops
  8. thumbnail + YouTube description (chapters, credits)

Everything lands in ~/Movies/Journey/<slug>/release/.
"""
import argparse, json, math, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
OUT_ROOT = os.path.expanduser('~/Movies/Journey')
VOICE_MAP = os.path.join(OUT_ROOT, 'voice', 'voice_map.json')
MASTER_CHAIN = ("highpass=f=25,equalizer=f=60:t=q:w=0.9:g=1.5,equalizer=f=280:t=q:w=1.2:g=-1.2,"
                "equalizer=f=3200:t=q:w=1.0:g=0.8,highshelf=f=10000:g=1.8,"
                "acompressor=threshold=0.125:ratio=2:attack=25:release=250:knee=6:makeup=1,volume={g}dB,"
                "aresample=192000,alimiter=limit={lim}:attack=2:release=60:level=disabled,aresample=48000")


def slug(path):
    return re.sub(r'[^a-z0-9]+', '-', os.path.splitext(os.path.basename(path))[0].lower()).strip('-')


def fmt(t):
    return f'{int(t // 60)}:{int(t % 60):02d}'


def run(cmd, **kw):
    print('  $', ' '.join(str(c) for c in cmd[:6]), '...' if len(cmd) > 6 else '', flush=True)
    return subprocess.run(cmd, check=True, **kw)


def step(title):
    print(f'\n== {title}', flush=True)


# ---------------------------------------------------------------- analysis
def estimate_key(stems_dir):
    import numpy as np, enhance as E
    x = E.load(os.path.join(stems_dir, 'other.wav'), mono=True) + E.load(os.path.join(stems_dir, 'bass.wav'), mono=True)
    SR = E.SR; x = x[int(len(x) * 0.15):int(len(x) * 0.85)]
    N = 8192; f = np.fft.rfftfreq(N, 1 / SR); valid = (f > 60) & (f < 2000)
    pcs = np.round(69 + 12 * np.log2(f[valid] / 440)).astype(int) % 12; chroma = np.zeros(12)
    for i in range(0, len(x) - N, N * 4):
        np.add.at(chroma, pcs, np.abs(np.fft.rfft(x[i:i + N] * np.hanning(N)))[valid] ** 2)
    chroma /= chroma.sum() + 1e-12
    maj = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
    mnr = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    best = max([(np.corrcoef(np.roll(maj, k), chroma)[0, 1], names[k], 'major') for k in range(12)] +
               [(np.corrcoef(np.roll(mnr, k), chroma)[0, 1], names[k], 'minor') for k in range(12)])
    return best[1], best[2]


def plan_song(song, stems_dir):
    """Sections with energy, drops (big jumps into high energy), breakdowns, and the ending start."""
    import numpy as np, analyze, enhance as E
    a = E.load(song, mono=True)
    import numpy as np
    a22 = a[::2].astype(np.float32)                       # analyze.py works at 22.05 kHz
    secs = analyze.sections(a22)
    dur = len(a) / E.SR
    sec_drops, breakdowns = [], []
    for prev, cur in zip(secs, secs[1:]):
        if cur['energy'] >= 0.45 and cur['energy'] - prev['energy'] >= 0.25:
            sec_drops.append(cur['start'])
        if cur['energy'] <= prev['energy'] - 0.25 and cur['end'] - cur['start'] >= 12 and cur['end'] < dur - 10:
            breakdowns.append((cur['start'], cur['end']))
    last = secs[-1]
    end_from = last['start'] if last['energy'] < 0.5 and dur - last['start'] < 45 else max(dur - 24, 0)
    # drums slamming back in after a 2 s gap: the exact re-entry is the drop
    drums = E.load(os.path.join(stems_dir, 'drums.wav'), mono=True)
    hop = 0.05; h = int(hop * E.SR)
    env = np.array([np.sqrt(np.mean(drums[i:i + h] ** 2)) for i in range(0, len(drums) - h, h)])
    med = np.median(env[env > 0]) if np.any(env > 0) else 0
    drum_drops = []
    w = int(2.0 / hop)
    for i in range(w, len(env) - w):
        before, after = env[i - w:i].mean(), env[i:i + w // 2].mean()
        if after > med and after > 6 * (before + 1e-6) and env[i] > 3 * (before + 1e-6) and 20 < i * hop < end_from - 15:
            if not drum_drops or i * hop - drum_drops[-1] > 10:
                drum_drops.append(i * hop)
    inside = lambda d: any(b0 + 2 < d < b1 - 1 for b0, b1 in breakdowns)      # fills inside a breakdown aren't drops
    energy_at = lambda t: next((x['energy'] for x in secs if x['start'] <= t < x['end']), 0)
    cands = [(round(E.drop_downbeat(drums, d, window=0.4), 2), 0) for d in drum_drops
             if not inside(d) and energy_at(d + 2) >= 0.4]
    cands += [(round(E.drop_downbeat(drums, d, window=1.5), 2), 1) for d in sec_drops if d < end_from - 15]
    cands.sort()
    exact = []
    for t, src in cands:                                  # within 10 s, the drum re-entry wins
        if exact and t - exact[-1][0] <= 10:
            if src < exact[-1][1]:
                exact[-1] = (t, src)
            continue
        exact.append((t, src))
    exact = [t for t, _ in exact][:6]
    if not exact:
        exact = sorted(s['start'] for s in sorted(secs, key=lambda s: -s['energy'])[:3])
    return dict(duration=dur, sections=secs, drops=exact, breakdowns=breakdowns, end_from=end_from)


# ---------------------------------------------------------------- mastering
def master(src, dst):
    import enhance as E
    g, lim = 7.0, 0.84
    for _ in range(6):
        run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-af', MASTER_CHAIN.format(g=g, lim=lim), '-c:a', 'pcm_s24le', dst])
        o = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', dst, '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                           capture_output=True, text=True).stderr
        I = float(re.findall(r'I:\s+(-?[\d.]+) LUFS', o)[-1]); TP = float(re.findall(r'Peak:\s+(-?[\d.]+) dBFS', o)[-1])
        if TP > -1.0:
            lim *= 10 ** ((-1.1 - TP) / 20); continue
        if abs(I + 9.5) < 0.35:
            break
        g += -9.5 - I
    print(f'  master: {I:.1f} LUFS, true peak {TP:.1f} dBFS')
    return I, TP


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('song'); ap.add_argument('--title'); ap.add_argument('--subtitle', default='')
    ap.add_argument('--artist', default='TOKYO THAI'); ap.add_argument('--key', help='override the detected key, e.g. G')
    ap.add_argument('--no-voice', action='store_true', help="don't add your recorded choir")
    ap.add_argument('--drops', type=float, nargs='+', help='override the detected drop times (seconds)')
    ap.add_argument('--skip-video', action='store_true'); ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    song = os.path.abspath(os.path.expanduser(a.song)); name = os.path.splitext(os.path.basename(song))[0]
    title = a.title or name; sl = slug(song)
    wd = os.path.join(OUT_ROOT, sl); rel = os.path.join(wd, 'release'); os.makedirs(rel, exist_ok=True)
    plan_f = os.path.join(wd, 'release_plan.json')

    step('1. Stems and per-instrument features')
    import engine, stems
    audio = engine.decode_audio(song, wd)
    n = int(math.ceil(len(audio) / engine.SR * engine.FPS))
    stems.features(song, wd, n, engine.FPS)
    stems_dir = os.path.join(wd, 'stems', 'htdemucs', name)

    step('2. Analysis')
    if os.path.exists(plan_f) and not a.force:
        P = json.load(open(plan_f))
    else:
        P = plan_song(song, stems_dir)
        k, mode = estimate_key(stems_dir); P['key'], P['mode'] = k, mode
        json.dump(P, open(plan_f, 'w'), indent=1)
    if a.drops:
        P['drops'] = a.drops; json.dump(P, open(plan_f, 'w'), indent=1)
    key = a.key or P['key']
    print(f"  {fmt(P['duration'])}, key {key} {P.get('mode', '')}, drops at {', '.join(fmt(d) for d in P['drops'])}, "
          f"breakdowns {', '.join(fmt(b[0]) for b in P['breakdowns']) or 'none'}, ending from {fmt(P['end_from'])}")

    step('3. Story draft')
    import analyze
    story_f = os.path.join(HERE, 'stories', sl + '.json')
    if not os.path.exists(story_f) or a.force:
        secs = [dict(start=s['start'], end=s['end'], energy=s['energy']) for s in P['sections']]
        st = analyze.draft_story(secs, title, a.subtitle)
        st['warning'] = True
        jp = {'rain_city': ('雨の東京', 'Rain over Tokyo'), 'expressway': ('首都高', 'Shuto Expressway'),
              'bridge_stars': ('隅田川', 'Sumida River'), 'neon_downtown': ('渋谷', 'Shibuya'),
              'tunnel': ('トンネル', 'The Tunnel'), 'psy_tunnel': ('トンネル', 'The Tunnel'), 'dawn_bay': ('富士山', 'Mount Fuji')}
        chapters, seen = [], set()
        for s in st['sections']:
            if s['scene'] in seen and s['scene'] != 'dawn_bay':
                continue
            seen.add(s['scene'])
            if s['scene'] == 'dawn_bay' and any(c['en'] == 'Mount Fuji' for c in chapters):
                continue
            j, e = jp[s['scene']]
            chapters.append(dict(at=max(13.0, s['start'] + 1.5), time='', jp=j, en=e))
        st['chapters'] = chapters
        json.dump(st, open(story_f, 'w'), indent=2, ensure_ascii=False)
    story = json.load(open(story_f))
    print(f'  {story_f}: ' + ' → '.join(s['scene'] for s in story['sections']))

    step('4. Enhancement')
    enh = os.path.join(wd, 'enhanced'); pre = os.path.join(enh, 'album_enhanced_premaster.wav')
    if not os.path.exists(pre) or a.force:
        cmd = [sys.executable, os.path.join(HERE, 'enhance.py'), song, '--key', key,
               '--drops', *[f'{d:.2f}' for d in P['drops']], '--end-from', f"{P['end_from']:.2f}"]
        if os.path.exists(VOICE_MAP) and not a.no_voice:
            vm = json.load(open(VOICE_MAP))
            vm['drops'] = {str(i + 1): 'vowels' for i in range(1, len(P['drops']))}
            choir = [list(b) for b in P['breakdowns'][:2]]
            if P['drops']:
                last = P['drops'][-1]; choir.append([last + 0.5, min(P['end_from'] - 0.5, last + 45)])
            vm.setdefault('extra', {})['choir_at'] = [c for c in choir if c[1] - c[0] > 8]
            vm['calls'] = []; vm.pop('tag', None)
            for k_ in ('whisper', 'whisper_at', 'line', 'line_at'):
                vm['extra'].pop(k_, None)
            song_vm = os.path.join(wd, 'voice_map.json'); json.dump(vm, open(song_vm, 'w'), indent=1)
            cmd += ['--voice', song_vm]
        run(cmd)

    step('5. Master + Extended Mix')
    mst = os.path.join(rel, f'{a.artist} - {title} (Master).wav')
    ext = os.path.join(rel, f'{a.artist} - {title} (Extended Mix).wav')
    if not os.path.exists(mst) or a.force:
        master(pre, mst)
        master(os.path.join(enh, 'extended_mix_premaster.wav'), ext)
    for f in ('sonic_logo.wav',):
        if os.path.exists(os.path.join(enh, f)):
            shutil.copy(os.path.join(enh, f), os.path.join(rel, f'{a.artist} - Sonic Logo.wav'))

    if a.skip_video:
        print('\nDone (audio only):', rel); return

    step('6. Psychedelic visualizer')
    wide = os.path.join(wd, f'{sl}_trip_wide.mp4')
    if not os.path.exists(wide) or a.force:
        run([sys.executable, os.path.join(HERE, 'journey.py'), 'footage', song, '--story', story_f, '--style', 'trip', '--replan'])
    vis = os.path.join(rel, f'{a.artist} - {title} (Psychedelic Visualizer) 4K.mp4')
    run(['ffmpeg', '-v', 'error', '-y', '-i', wide, '-i', mst, '-map', '0:v', '-map', '1:a',
         '-vf', 'scale=3840:2160:flags=lanczos', '-c:v', 'hevc_videotoolbox', '-b:v', '45M', '-tag:v', 'hvc1',
         '-pix_fmt', 'yuv420p', '-af', 'volume=-1.3dB', '-c:a', 'aac', '-b:a', '320k', '-shortest', '-movflags', '+faststart', vis])

    step('7. Shorts')
    for i, d in enumerate(P['drops'][:3], 1):
        s0 = max(0, d - 12); s1 = min(P['duration'], d + 18)
        tmp = os.path.join(wd, f'short_{i}.mp4')
        run([sys.executable, os.path.join(HERE, 'journey.py'), 'footage', song, '--story', story_f, '--style', 'trip',
             '--vertical', '--start', f'{s0:.2f}', '--end', f'{s1:.2f}', '--out', tmp])
        run(['ffmpeg', '-v', 'error', '-y', '-i', tmp, '-ss', f'{s0:.3f}', '-t', f'{s1 - s0:.3f}', '-i', mst,
             '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-af', 'volume=-1.3dB,afade=t=in:d=0.5,afade=t=out:st=' + f'{s1 - s0 - 1.5:.2f}' + ':d=1.5',
             '-c:a', 'aac', '-b:a', '256k', '-shortest', '-movflags', '+faststart',
             os.path.join(rel, f'{a.artist} - {title} (Short {i}).mp4')])

    step('8. Thumbnail + description')
    peak = P['drops'][min(1, len(P['drops']) - 1)] + 6
    frame = os.path.join(wd, 'thumb_src.png')
    run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{peak:.2f}', '-i', wide, '-frames:v', '1', frame])
    make_thumbnail(frame, os.path.join(rel, 'thumbnail.jpg'), title, a.artist)
    write_description(os.path.join(rel, 'YouTube_description.txt'), title, a.subtitle, a.artist, story, wd)
    print('\nRelease package ready:', rel)


def make_thumbnail(src, dst, title, artist):
    from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageOps
    import numpy as np
    bg = Image.open(src).convert('RGB').resize((1280, 720), Image.LANCZOS)
    bg.paste(ImageOps.mirror(bg.crop((0, 560, 420, 720))), (860, 560))          # hide the frame's own corner logo
    bg = ImageEnhance.Contrast(ImageEnhance.Color(bg).enhance(1.25)).enhance(1.1)
    g = np.zeros((720, 1280), np.uint8)
    for y in range(720):
        g[y, :] = int(max(0, (y - 330) / 390) * 200)
    bg = Image.composite(Image.new('RGB', (1280, 720), (5, 0, 15)), bg, Image.fromarray(g))
    ui = '/System/Library/Fonts/Avenir Next.ttc'; jp = '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'
    def glow(xy, text, font, col, anchor='mm', r=10):
        layer = Image.new('RGBA', bg.size, (0, 0, 0, 0)); ImageDraw.Draw(layer).text(xy, text, font=font, fill=col + (255,), anchor=anchor)
        layer = layer.filter(ImageFilter.GaussianBlur(r)); bg.paste(layer, (0, 0), layer); bg.paste(layer, (0, 0), layer)
        ImageDraw.Draw(bg).text(xy, text, font=font, fill=(255, 255, 255), anchor=anchor)
    size = 104
    while ImageFont_len(ui, size, title.upper()) > 1180 and size > 50:
        size -= 6
    from PIL import ImageFont
    glow((640, 520), title.upper(), ImageFont.truetype(ui, size, index=8), (255, 60, 200), r=14)
    mid = ImageFont.truetype(ui, 40, index=5); j = ImageFont.truetype(jp, 38)
    a_ = '   '.join(' '.join(w) for w in artist.split()); b_ = '東 京 タ イ' if artist == 'TOKYO THAI' else ''
    wa = mid.getlength(a_); wb = j.getlength(b_) if b_ else 0; x0 = 640 - (wa + (46 + wb if b_ else 0)) / 2
    glow((x0, 610), a_, mid, (120, 200, 255), anchor='lm', r=8)
    if b_:
        glow((x0 + wa + 23, 610), '·', mid, (120, 200, 255), r=8); glow((x0 + wa + 46, 612), b_, j, (120, 200, 255), anchor='lm', r=8)
    glow((640, 60), '  '.join('PSYCHEDELIC VISUALIZER'), ImageFont.truetype(ui, 30, index=5), (255, 60, 200), r=6)
    bg.save(dst, quality=95)


def ImageFont_len(path, size, text):
    from PIL import ImageFont
    return ImageFont.truetype(path, size, index=8).getlength(text)


def write_description(dst, title, subtitle, artist, story, wd):
    plan = json.load(open(os.path.join(wd, 'footage_plan.json')))
    credits = sorted({re.search(r'_(\d+)\.mp4$', os.path.basename(os.path.realpath(s['clip']))).group(1)
                      for s in plan if re.search(r'_(\d+)\.mp4$', os.path.basename(os.path.realpath(s['clip'])))})
    chap = [f'0:00 {story["chapters"][0]["en"]} · {story["chapters"][0]["jp"]}'] if story.get('chapters') else ['0:00 Intro']
    for c in story.get('chapters', [])[1:]:
        chap.append(f"{fmt(c['at'] - 1.5)} {c['en']} · {c['jp']}")
    txt = f"""{artist} — {title} (Psychedelic Visualizer)
{subtitle}

A night journey through Tokyo that turns into a trip and ends in light. Every cut, pulse and colour in this video moves with the music: the kick, the bassline, the melody and the voices each drive their own part of the picture.

Headphones on. Lights off. Let it take you somewhere.

PHOTOSENSITIVITY WARNING: this video contains flashing lights and rapidly changing psychedelic imagery.

CHAPTERS
""" + '\n'.join(chap) + f"""

Music: {artist}
Visuals: {artist}, edited and animated with a custom audio-reactive engine

Footage: Pexels (pexels.com), used under the Pexels License. Thank you to the creators:
""" + '\n'.join(f'https://www.pexels.com/video/{c}/' for c in credits) + f"""

#{artist.replace(' ', '')} #progressivehouse #psytrance #melodictechno #visualizer #tokyo #nightdrive #psychedelic
"""
    open(dst, 'w').write(txt)


if __name__ == '__main__':
    main()
