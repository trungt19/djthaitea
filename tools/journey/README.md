# Journey Video Studio

Turns a song into an audio-reactive night-drive music video: dark rainy city → expressway →
neon downtown → psychedelic tunnel → sunrise. Every journey ends in light.

Needs Python 3 with `numpy` and `Pillow`, plus `ffmpeg`. Videos and caches go to `~/Movies/Journey/<song>/`.

```bash
cd tools/journey

python3 journey.py scenes                                   # list the scene types
python3 journey.py analyze  ~/Downloads/Song.mp3 --subtitle "夜の旅"   # find sections, draft stories/song.json
python3 journey.py preview  ~/Downloads/Song.mp3            # contact sheet, one frame per section
python3 journey.py render   ~/Downloads/Song.mp3            # full 1920x1080 video with audio
python3 journey.py render   ~/Downloads/Song.mp3 --vertical --start 210 --end 240   # 9:16 Short
```

## Footage mode (real clips)

Put clips into scene folders under `~/Movies/Journey/clips/` (`rain_city/`, `expressway/`, `bridge_stars/`,
`neon_downtown/`, `tunnel/`, `psy_tunnel/`, `dawn_bay/`, plus `car/` for hero car shots). Cuts land on
detected kicks, and every frame is graded per scene with audio-reactive glow, flashes and zoom.
Widescreen renders skip vertical and very dark clips automatically (results are cached in `.quality.json`).

```bash
python3 journey.py footage ~/Downloads/Song.mp3 --style drive        # real footage, beat-cut
python3 journey.py footage ~/Downloads/Song.mp3 --style trip         # psychedelic: warp, kaleidoscope, trails
python3 journey.py footage ~/Downloads/Song.mp3 --vertical --start 210 --end 240   # Short
```

## Story mode (a music video that tells a story)

A storyboard (`stories/last-light.storyboard.json`) lists shots in order with their start times, image and
motion prompts. Shots that exist as `<shots_dir>/<id>.mp4` play where the story says. Shots that don't
exist yet are filled with stock from their `fallback` scene, so the whole edit can be previewed right away.
Entries with `"fill"` beat-cut stock between story shots. `"fx": "trip"` turns on the psychedelic effects,
and `"drop": true` flashes the logo.

```bash
python3 journey.py footage ~/Downloads/Song.mp3 --board stories/last-light.storyboard.json
```

## Generating shots locally (ComfyUI)

`generate` sends each storyboard shot to a local ComfyUI (`~/ComfyUI`). It makes an SDXL still
(2 variants, saved to `stills/`), then animates `stills/<id>.png` into a 5 s clip with Wan 2.2. To use a
different variant, copy it over `stills/<id>.png` and run again with `--only <id>`.

```bash
python3 journey.py generate stories/last-light.storyboard.json --only S01
python3 journey.py generate stories/last-light.storyboard.json --stills-only   # just the stills, fast
```

## Logo

Every footage render overlays the artist wordmark (default **TOKYO THAI / 東京タイ**). It pulses with the
kick in the corner and flashes large in the centre on drops. Set `"logo": {"text": ..., "sub": ...,
"image": "path.png"}` in a story or storyboard, or `"logo": false` to turn it off.

## Stories

`stories/<song>.json` decides which scene plays when. `analyze` writes a draft; edit the
`start` times and `scene` names, then `preview` again.

```json
{
  "title": "Celestial Journey",
  "subtitle": "天空の旅",
  "sections": [
    {"start": 0,   "scene": "rain_city"},
    {"start": 60,  "scene": "expressway"},
    {"start": 210, "scene": "tunnel"},
    {"start": 216, "scene": "psy_tunnel"},
    {"start": 334, "scene": "dawn_bay"}
  ]
}
```

- Tunnel sections that follow each other form one tunnel. The world outside switches to the
  scene after the tunnel, so you exit into it.
- A section can tweak its scene with `"overrides": {"rain": 0.3, "speed": 40}`.
- If the last scene has a sun, it rises fully and the car slows to a stop.

## Files

- `engine.py`: the renderer (geometry, lights, bloom, rain, psychedelic effects)
- `story.py`: scene presets and the story compiler
- `analyze.py`: section detection and a rough BPM estimate
- `footage.py`: footage mode: clip scanning, beat-cut planning, Drive/Trip finishing, logo, storyboards
- `comfy.py`: local ComfyUI client (SDXL stills and Wan 2.2 image-to-video)
- `journey.py`: the CLI, including parallel chunked rendering
