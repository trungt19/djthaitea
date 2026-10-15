"""Scenes and stories.

A story is a JSON file:
{
  "title": "Celestial Journey",
  "subtitle": "天空の旅",
  "sections": [
    {"start": 0,   "scene": "rain_city"},
    {"start": 60,  "scene": "expressway"},
    ...
  ]
}
Each section runs until the next one starts. Scene changes blend over `blend` seconds.
Consecutive tunnel / psy_tunnel sections form one tunnel you drive through; the outside
world quietly switches to the scene *after* the tunnel, so the exit reveals it.
"""
import json

SCENES = {
    'rain_city': dict(rain=1.0, city=1.0, neon=.8, water=0., stars=0., moon=0., sun=0., speed=14.,
                      psy=0., skyT=(5, 7, 20), skyB=(36, 22, 60), fog=(40, 26, 58), fogd=110.,
                      lamp=(255, 165, 80), glow=0.9),
    'expressway': dict(rain=.45, city=1.0, neon=1., water=0., stars=0., moon=0., sun=0., speed=27.,
                       psy=0., skyT=(5, 7, 20), skyB=(52, 18, 72), fog=(48, 22, 66), fogd=160.,
                       lamp=(255, 165, 80), glow=1.1),
    'bridge_stars': dict(rain=0., city=0., neon=0., water=1., stars=1., moon=1., sun=0., speed=22.,
                         psy=0., skyT=(3, 4, 18), skyB=(20, 26, 66), fog=(22, 28, 64), fogd=280.,
                         lamp=(205, 220, 255), glow=.9),
    'neon_downtown': dict(rain=.15, city=1., neon=1., water=0., stars=.15, moon=0., sun=0., speed=31.,
                          psy=.35, skyT=(6, 5, 22), skyB=(78, 16, 74), fog=(66, 20, 74), fogd=170.,
                          lamp=(255, 140, 190), glow=1.3),
    'tunnel': dict(speed=30., psy=0.),
    'psy_tunnel': dict(speed=34., psy=1.),
    'dawn_bay': dict(rain=0., city=0., neon=0., water=1., stars=0., moon=0., sun=.55, speed=28.,
                     psy=0., skyT=(34, 42, 108), skyB=(255, 140, 115), fog=(215, 130, 125), fogd=320.,
                     lamp=(255, 200, 150), glow=1.0),
}
TUNNEL_SCENES = {'tunnel', 'psy_tunnel'}
SCENE_HELP = {
    'rain_city': 'slow drive through rainy neon streets, raindrops on the windshield',
    'expressway': 'elevated expressway between towers, signs, light rain',
    'bridge_stars': 'open bay bridge under stars and moon, water reflections (breakdowns)',
    'neon_downtown': 'fast dense neon district, pink haze, lights pulse to the kick (drops)',
    'tunnel': 'underground tunnel with orange lights',
    'psy_tunnel': 'psychedelic tunnel: colour-cycling lights and portal rings, zoom pulse on kicks (peaks)',
    'dawn_bay': 'sunrise over the bay, ends in light (finales)',
}


def _lerp(a, b, k):
    if isinstance(a, (tuple, list)):
        return tuple(x + (y - x) * k for x, y in zip(a, b))
    return a + (b - a) * k


class Compiled:
    def __init__(self, keys, tunnels, title, subtitle):
        self.keys, self.tunnels, self.title, self.subtitle = keys, tunnels, title, subtitle

    def params(self, t):
        keys = self.keys
        if t <= keys[0][0]:
            return dict(keys[0][1])
        for (t0, a), (t1, b) in zip(keys, keys[1:]):
            if t0 <= t <= t1:
                k = (t - t0) / (t1 - t0) if t1 > t0 else 1.0
                k = k * k * (3 - 2 * k)
                return {key: _lerp(a[key], b[key], k) for key in a}
        return dict(keys[-1][1])


def load(path):
    with open(path) as f:
        return json.load(f)


def validate(story):
    secs = story.get('sections') or []
    if not secs:
        raise ValueError('story has no sections')
    for s in secs:
        if s['scene'] not in SCENES:
            raise ValueError(f"unknown scene {s['scene']!r}; choose from {', '.join(SCENES)}")
    starts = [s['start'] for s in secs]
    if starts != sorted(starts):
        raise ValueError('section starts must be in increasing order')
    if secs[-1]['scene'] in TUNNEL_SCENES:
        raise ValueError('story cannot end inside a tunnel; add a section after it')


def compile_story(story, duration):
    validate(story)
    secs = sorted(story['sections'], key=lambda s: s['start'])
    blend = float(story.get('blend', 6.0))
    ends = [s['start'] for s in secs[1:]] + [duration]

    def outside_after(i):
        for s in secs[i + 1:]:
            if s['scene'] not in TUNNEL_SCENES:
                return SCENES[s['scene']]
        return SCENES['dawn_bay']

    resolved = []
    for i, s in enumerate(secs):
        if s['scene'] in TUNNEL_SCENES:
            p = dict(outside_after(i)); p.update(SCENES[s['scene']])
        else:
            p = dict(SCENES[s['scene']])
        p.update(s.get('overrides', {}))
        resolved.append(p)

    keys = [(0.0, resolved[0])]
    for i in range(1, len(secs)):
        t0 = float(secs[i]['start'])
        keys.append((t0, keys[-1][1]))
        keys.append((min(t0 + blend, ends[i]), resolved[i]))
    # every journey ends in light: last section brightens and slows to a stop
    last = dict(resolved[-1])
    if last.get('sun', 0) > 0:
        last.update(sun=1.0, speed=9.0)
        keys.append((max(keys[-1][0], duration - 4), last))
    keys.append((duration + 10, keys[-1][1]))

    tunnels = []
    i = 0
    while i < len(secs):
        if secs[i]['scene'] in TUNNEL_SCENES:
            j = i
            while j + 1 < len(secs) and secs[j + 1]['scene'] in TUNNEL_SCENES:
                j += 1
            tunnels.append((float(secs[i]['start']), float(ends[j])))
            i = j + 1
        else:
            i += 1
    return Compiled(keys, tunnels, story.get('title', ''), story.get('subtitle', ''))
