#!/usr/bin/env python3
"""Turn storyboard stills into slow cinematic camera-move clips (push in, pull out, drift), and write a
companion storyboard that points story mode at them. Generated AI clips (shots/<id>.mp4) win when present.

  python3 kenburns.py stories/last-light.storyboard.json        # -> stories/last-light.animatic.json
"""
import json, os, subprocess, sys

MOVES = [  # (zoom from, zoom to, x drift, y drift) as fractions of the spare area
    (1.00, 1.12, 0.5, 0.5), (1.12, 1.00, 0.5, 0.45), (1.06, 1.06, 0.15, 0.5), (1.06, 1.06, 0.85, 0.5),
    (1.00, 1.10, 0.35, 0.4), (1.10, 1.02, 0.65, 0.55),
]


def clip(still, out, seconds=8.0, move=0, fps=30, w=1920, h=1080):
    z0, z1, fx, fy = MOVES[move % len(MOVES)]
    n = int(seconds * fps)
    big_w = w * 2
    # zoom over time; x/y keep the framing centred on (fx, fy) of the spare area; a drift move pans fx 0.15->0.85
    if z0 == z1:
        xexpr = f"(iw-iw/zoom)*({fx}+({1 - 2 * fx})*on/{n})"
    else:
        xexpr = f"(iw-iw/zoom)*{fx}"
    vf = (f"scale={big_w}:-2:flags=lanczos,"
          f"zoompan=z='{z0}+({z1}-{z0})*on/{n}':x='{xexpr}':y='(ih-ih/zoom)*{fy}':d={n}:s={w}x{h}:fps={fps},"
          f"format=yuv420p")
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-loop', '1', '-i', still, '-vf', vf, '-frames:v', str(n),
                    '-c:v', 'libx264', '-crf', '17', out], check=True)


def main():
    board_f = sys.argv[1]
    b = json.load(open(board_f))
    base = os.path.dirname(os.path.expanduser(b['shots_dir']))
    stills, ai = os.path.join(base, 'stills'), os.path.expanduser(b['shots_dir'])
    out_dir = os.path.join(base, 'animatic'); os.makedirs(out_dir, exist_ok=True)
    k = 0
    for e in b['timeline']:
        sid = e.get('shot')
        if not sid:
            continue
        dst = os.path.join(out_dir, sid + '.mp4')
        if os.path.exists(os.path.join(ai, sid + '.mp4')):
            os.path.exists(dst) and os.remove(dst)
            os.symlink(os.path.join(ai, sid + '.mp4'), dst); print(sid, 'AI clip'); continue
        src = os.path.join(stills, sid + '.png')
        if not os.path.exists(src):
            print(sid, 'no still yet'); continue
        clip(src, dst, move=k); k += 1
        print(sid, 'camera move', k % len(MOVES))
    b2 = dict(b); b2['shots_dir'] = out_dir.replace(os.path.expanduser('~'), '~')
    out_board = board_f.replace('.storyboard.json', '.animatic.json')
    json.dump(b2, open(out_board, 'w'), indent=2, ensure_ascii=False)
    print('->', out_board)


if __name__ == '__main__':
    main()
