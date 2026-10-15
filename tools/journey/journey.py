#!/usr/bin/env python3
"""Journey Video Studio — turn a song into an audio-reactive night-drive music video.

  python3 journey.py scenes
  python3 journey.py analyze  SONG.mp3 [--title T] [--subtitle S]      # draft a story
  python3 journey.py preview  SONG.mp3 [--story S] [--at 10 70 ...]     # contact sheet
  python3 journey.py render   SONG.mp3 [--story S] [--vertical] [--start 200 --end 230]

Outputs and caches go to ~/Movies/Journey/<song>/.
"""
import argparse, json, math, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_ROOT = os.path.expanduser('~/Movies/Journey')


def slug(path):
    return re.sub(r'[^a-z0-9]+', '-', os.path.splitext(os.path.basename(path))[0].lower()).strip('-')


def workdir(song):
    d = os.path.join(OUT_ROOT, slug(song)); os.makedirs(d, exist_ok=True); return d


def story_path(song, given=None):
    return given or os.path.join(HERE, 'stories', slug(song) + '.json')


def load_audio(song):
    import engine
    return engine.decode_audio(song, workdir(song))


def make_renderer(song, story_file, w, h):
    import engine, story as st
    engine.configure(w, h)
    audio = load_audio(song)
    if not os.path.exists(story_file):
        sys.exit(f'No story at {story_file}. Run: python3 journey.py analyze "{song}"')
    compiled = st.compile_story(st.load(story_file), len(audio) / engine.SR)
    return engine.Renderer(compiled, audio)


def fmt(t):
    return f'{int(t // 60)}:{int(t % 60):02d}'


# ---------------------------------------------------------------- commands
def cmd_scenes(a):
    from story import SCENE_HELP
    for k, v in SCENE_HELP.items():
        print(f'  {k:<14} {v}')


def cmd_analyze(a):
    import analyze
    audio = load_audio(a.song)
    secs = analyze.sections(audio)
    bpm = analyze.estimate_bpm(audio)
    title = a.title or os.path.splitext(os.path.basename(a.song))[0]
    draft = analyze.draft_story(secs, title, a.subtitle or '')
    out = story_path(a.song, a.story)
    print(f'{title}: {fmt(len(audio) / analyze.SR)}, ~{bpm:.0f} BPM (intro estimate)\n')
    print('  start   energy  scene')
    for s in draft['sections']:
        print(f"  {fmt(s['start']):>5}   {s['energy']:.2f}    {s['scene']}")
    if os.path.exists(out) and not a.force:
        print(f'\nStory already exists at {out} (kept; use --force to overwrite).')
    else:
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, 'w') as f:
            json.dump(draft, f, indent=2, ensure_ascii=False)
        print(f'\nWrote {out} — edit scenes/starts there, then run preview.')


def cmd_preview(a):
    from PIL import Image
    import story as st
    w, h = (1080, 1920) if a.vertical else (1920, 1080)
    R = make_renderer(a.song, story_path(a.song, a.story), w, h)
    times = a.at
    if not times:  # one frame from the middle of each section
        secs = st.load(story_path(a.song, a.story))['sections']
        ends = [s['start'] for s in secs[1:]] + [R.dur]
        times = [min(R.dur - 1, s['start'] + min(12, (e - s['start']) / 2)) for s, e in zip(secs, ends)]
    tw, th = (640, 360) if w >= h else (270, 480)
    cols = 3 if w >= h else 5
    rows = math.ceil(len(times) / cols)
    from PIL import ImageDraw
    sheet = Image.new('RGB', (tw * cols, th * rows))
    for j, t in enumerate(times):
        im = Image.fromarray(R.frame(int(t * 30))).resize((tw, th), Image.LANCZOS)
        ImageDraw.Draw(im).text((8, 6), fmt(t), fill=(255, 255, 255))
        sheet.paste(im, ((j % cols) * tw, (j // cols) * th))
    out = os.path.join(workdir(a.song), 'preview_vertical.png' if a.vertical else 'preview.png')
    sheet.save(out)
    print(out)


def cmd_chunk(a):
    """Internal: render frames [a.fa, a.fb) to a.out."""
    R = make_renderer(a.song, a.story, a.w, a.h)
    import engine
    p = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo',
                          '-pix_fmt', 'rgb24', '-s', f'{a.w}x{a.h}', '-r', str(engine.FPS), '-i', '-',
                          '-c:v', 'libx264', '-preset', 'medium', '-crf', str(a.crf), '-pix_fmt', 'yuv420p',
                          a.out], stdin=subprocess.PIPE)
    prog = a.out + '.progress'
    for k, i in enumerate(range(a.fa, min(a.fb, R.n))):
        p.stdin.write(R.frame(i).tobytes())
        if k % 30 == 0:
            with open(prog, 'w') as f: f.write(str(k))
    p.stdin.close(); p.wait()
    with open(prog, 'w') as f: f.write('done')
    sys.exit(p.returncode)


def cmd_render(a):
    import engine
    story_file = story_path(a.song, a.story)
    w, h = (1080, 1920) if a.vertical else (1920, 1080)
    audio = load_audio(a.song)
    dur = len(audio) / engine.SR
    t0 = a.start or 0.0; t1 = min(a.end or dur, dur)
    fa, fb = int(t0 * engine.FPS), int(math.ceil(t1 * engine.FPS))
    wd = workdir(a.song)
    tag = ('vertical' if a.vertical else 'wide') + ('' if (t0 == 0 and t1 == dur) else f'_{int(t0)}-{int(t1)}')
    chunks_dir = os.path.join(wd, 'chunks_' + tag); os.makedirs(chunks_dir, exist_ok=True)
    n = max(1, min(a.workers, (fb - fa) // 60 or 1))
    per = math.ceil((fb - fa) / n)
    procs = []
    print(f'Rendering {fmt(t1 - t0)} ({fb - fa} frames, {w}x{h}) on {n} workers...')
    start = time.time()
    for k in range(n):
        ca, cb = fa + k * per, min(fb, fa + (k + 1) * per)
        out = os.path.join(chunks_dir, f'chunk_{k:02d}.mp4')
        procs.append((out, subprocess.Popen([sys.executable, __file__, '_chunk', a.song, story_file,
                                             str(ca), str(cb), str(w), str(h), str(a.crf), out])))
    while any(p.poll() is None for _, p in procs):
        time.sleep(10)
        done = 0
        for out, _ in procs:
            try:
                v = open(out + '.progress').read().strip()
                done += per if v == 'done' else int(v or 0)
            except (OSError, ValueError):
                pass
        pct = min(100, 100 * done / (fb - fa))
        el = time.time() - start
        eta = el / max(pct, 1e-3) * (100 - pct)
        print(f'  {pct:5.1f}%  elapsed {fmt(el)}  eta {fmt(eta)}', flush=True)
    if any(p.returncode for _, p in procs):
        sys.exit('A render worker failed; see errors above.')
    lst = os.path.join(chunks_dir, 'list.txt')
    with open(lst, 'w') as f:
        for out, _ in procs:
            f.write(f"file '{out}'\n")
    final = a.out or os.path.join(wd, f'{slug(a.song)}_{tag}.mp4')
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst,
                    '-ss', str(t0), '-t', str(t1 - t0), '-i', a.song, '-map', '0:v', '-map', '1:a',
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '320k', '-shortest', '-movflags', '+faststart', final],
                   check=True)
    for out, _ in procs:
        for p in (out, out + '.progress'):
            if os.path.exists(p): os.remove(p)
    os.remove(lst)
    print(f'Done in {fmt(time.time() - start)}: {final}')


CLIPS_DIR = os.path.join(OUT_ROOT, 'clips')


def cmd_fchunk(a):
    """Internal: render footage frames [a.fa, a.fb) for one style."""
    import engine, footage
    audio = load_audio(a.song)
    dur = len(audio) / engine.SR
    n = int(math.ceil(dur * engine.FPS))
    bass, en = engine.audio_features(audio, n)
    with open(a.plan) as f:
        shots = json.load(f)
    story = json.load(open(a.story))
    drive = footage.Finisher(a.w, a.h, story, dur, bass, en, engine.FPS)
    trip = footage.TripFinisher(a.w, a.h, story, dur, bass, en, engine.FPS)
    try:                                   # per-instrument features (Demucs stems), if available
        import stems
        drive.feat = trip.feat = stems.features(a.song, workdir(a.song), n, engine.FPS)
    except SystemExit as e:
        print(f'(no stems: {e}; using the mix)', file=sys.stderr)
    lg = story.get('logo', {})
    if lg is not False:
        logo = footage.Logo(a.w, a.h, text=lg.get('text', 'TOKYO THAI'), sub=lg.get('sub', '東京タイ'),
                            image=lg.get('image'))
        drive.logo = trip.logo = logo
    fin = lambda fr, fi, shot, _: (trip if (a.style == 'trip' or shot.get('fx') == 'trip') else drive)(fr, fi, shot, 0)
    p = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                          '-s', f'{a.w}x{a.h}', '-r', str(engine.FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'medium',
                          '-crf', str(a.crf), '-pix_fmt', 'yuv420p', a.out], stdin=subprocess.PIPE)
    prog = a.out + '.progress'
    warm = 20           # prime feedback trails across chunk seams
    i = max(0, a.fa - warm); written = 0
    while i < a.fb:
        si = next(k for k, s in enumerate(shots) if s['t0'] * engine.FPS <= i < s['t1'] * engine.FPS + 1e-6
                  or k == len(shots) - 1)
        shot = shots[si]
        s_end = min(a.fb, int(math.ceil(shot['t1'] * engine.FPS)))
        if s_end <= i:
            s_end = i + 1
        skip = i - int(round(shot['t0'] * engine.FPS))
        rd = footage.Reader(shot, a.w, a.h, engine.FPS, max(0, skip), s_end - i)
        for fi in range(i, s_end):
            out = fin(rd.read(), fi, shot, 0)
            if fi >= a.fa:
                p.stdin.write(out.tobytes()); written += 1
                if written % 30 == 0:
                    with open(prog, 'w') as f: f.write(str(written))
        rd.close()
        i = s_end
    p.stdin.close(); p.wait()
    with open(prog, 'w') as f: f.write('done')
    sys.exit(p.returncode)


def cmd_footage(a):
    import engine, footage
    story_file = os.path.expanduser(a.board) if a.board else story_path(a.song, a.story)
    story = json.load(open(story_file))
    audio = load_audio(a.song)
    dur = len(audio) / engine.SR
    wd = workdir(a.song)
    plan_file = os.path.join(wd, ('board_' if a.board else 'footage_') + 'plan.json')
    if a.replan or a.board or not os.path.exists(plan_file):
        lib = footage.scan_clips(a.clips, wide=not a.vertical)
        print('Clips: ' + ', '.join(f'{k} {len(v)}' for k, v in lib.items() if v))
        if a.board:
            shots = footage.plan_storyboard(story, lib, audio, dur, seed=a.seed)
            have = sorted({s['shot_id'] for s in shots if s.get('shot_id') and 'storyboards' in s['clip']})
            print(f'Storyboard: {len(have)} generated shots in place: {", ".join(have) or "none yet (stock stand-ins)"}')
        else:
            shots = footage.annotate(footage.plan(story, lib, audio, dur, seed=a.seed))
        with open(plan_file, 'w') as f:
            json.dump(shots, f, indent=1)
        print(f'Planned {len(shots)} shots -> {plan_file}')
    w, h = (1080, 1920) if a.vertical else (1920, 1080)
    t0 = a.start or 0.0; t1 = min(a.end or dur, dur)
    fa, fb = int(t0 * engine.FPS), int(math.ceil(t1 * engine.FPS))
    tag = ('story_' if a.board else '') + f"{a.style}_{'vertical' if a.vertical else 'wide'}" + ('' if (t0 == 0 and t1 == dur) else f'_{int(t0)}-{int(t1)}')
    chunks_dir = os.path.join(wd, 'chunks_' + tag); os.makedirs(chunks_dir, exist_ok=True)
    n = max(1, min(a.workers, (fb - fa) // 60 or 1)); per = math.ceil((fb - fa) / n)
    print(f'Rendering {a.style} {fmt(t1 - t0)} ({fb - fa} frames, {w}x{h}) on {n} workers...')
    start = time.time(); procs = []
    for k in range(n):
        ca, cb = fa + k * per, min(fb, fa + (k + 1) * per)
        out = os.path.join(chunks_dir, f'chunk_{k:02d}.mp4')
        procs.append((out, subprocess.Popen([sys.executable, __file__, '_fchunk', a.song, story_file, plan_file,
                                             a.style, str(ca), str(cb), str(w), str(h), str(a.crf), out])))
    while any(p.poll() is None for _, p in procs):
        time.sleep(15)
        done = 0
        for out, _ in procs:
            try:
                v = open(out + '.progress').read().strip(); done += per if v == 'done' else int(v or 0)
            except (OSError, ValueError):
                pass
        pct = min(100, 100 * done / (fb - fa)); el = time.time() - start
        print(f'  {pct:5.1f}%  elapsed {fmt(el)}  eta {fmt(el / max(pct, 1e-3) * (100 - pct))}', flush=True)
    if any(p.returncode for _, p in procs):
        sys.exit('A render worker failed; see errors above.')
    lst = os.path.join(chunks_dir, 'list.txt')
    with open(lst, 'w') as f:
        for out, _ in procs: f.write(f"file '{out}'\n")
    final = a.out or os.path.join(wd, f'{slug(a.song)}_{tag}.mp4')
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst,
                    '-ss', str(t0), '-t', str(t1 - t0), '-i', a.song, '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
                    '-c:a', 'aac', '-b:a', '320k', '-shortest', '-movflags', '+faststart', final], check=True)
    for out, _ in procs:
        for q in (out, out + '.progress'):
            if os.path.exists(q): os.remove(q)
    os.remove(lst)
    print(f'Done in {fmt(time.time() - start)}: {final}')



def cmd_generate(a):
    import comfy
    board = json.load(open(os.path.expanduser(a.board)))
    only = set(a.only.split(',')) if a.only else None
    comfy.generate(board, only=only, variants=a.variants, stills_only=a.stills_only, length=a.frames,
                   w=a.width, h=a.height)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('scenes')
    p = sub.add_parser('analyze'); p.add_argument('song'); p.add_argument('--story')
    p.add_argument('--title'); p.add_argument('--subtitle'); p.add_argument('--force', action='store_true')
    p = sub.add_parser('preview'); p.add_argument('song'); p.add_argument('--story')
    p.add_argument('--at', type=float, nargs='*'); p.add_argument('--vertical', action='store_true')
    p = sub.add_parser('render'); p.add_argument('song'); p.add_argument('--story')
    p.add_argument('--vertical', action='store_true'); p.add_argument('--start', type=float)
    p.add_argument('--end', type=float); p.add_argument('--out')
    p.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 4) - 2))
    p.add_argument('--crf', type=int, default=19)
    p = sub.add_parser('footage'); p.add_argument('song'); p.add_argument('--story')
    p.add_argument('--style', choices=['drive', 'trip'], default='drive'); p.add_argument('--clips', default=CLIPS_DIR)
    p.add_argument('--vertical', action='store_true'); p.add_argument('--start', type=float)
    p.add_argument('--end', type=float); p.add_argument('--out'); p.add_argument('--replan', action='store_true')
    p.add_argument('--seed', type=int, default=7); p.add_argument('--crf', type=int, default=19)
    p.add_argument('--board', help='storyboard JSON: shots in story order (story mode)')
    p.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 4) - 2))
    p = sub.add_parser('generate', help='make storyboard shots with local ComfyUI (SDXL still -> Wan 2.2 video)')
    p.add_argument('board'); p.add_argument('--only', help='comma list of shot ids, e.g. S01,S02')
    p.add_argument('--variants', type=int, default=2); p.add_argument('--stills-only', action='store_true')
    p.add_argument('--frames', type=int, default=121); p.add_argument('--width', type=int, default=1280)
    p.add_argument('--height', type=int, default=704)
    p = sub.add_parser('_fchunk')
    for k in ('song', 'story', 'plan', 'style'): p.add_argument(k)
    for k in ('fa', 'fb', 'w', 'h', 'crf'): p.add_argument(k, type=int)
    p.add_argument('out')
    p = sub.add_parser('_chunk')
    for k in ('song', 'story'): p.add_argument(k)
    for k in ('fa', 'fb', 'w', 'h', 'crf'): p.add_argument(k, type=int)
    p.add_argument('out')
    a = ap.parse_args()
    sys.path.insert(0, HERE)
    {'scenes': cmd_scenes, 'analyze': cmd_analyze, 'preview': cmd_preview,
     'render': cmd_render, '_chunk': cmd_chunk, 'footage': cmd_footage, '_fchunk': cmd_fchunk, 'generate': cmd_generate}[a.cmd](a)


if __name__ == '__main__':
    main()
