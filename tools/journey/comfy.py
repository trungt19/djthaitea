"""Generate storyboard shots with a local ComfyUI: SDXL still -> Wan 2.2 image-to-video -> mp4.

Models (commercial-use licences) expected in ~/ComfyUI/models:
  checkpoints/sd_xl_base_1.0.safetensors
  diffusion_models/wan2.2_ti2v_5B_fp16.safetensors
  text_encoders/umt5_xxl_fp16.safetensors
  vae/wan2.2_vae.safetensors
"""
import glob, json, os, random, shutil, subprocess, sys, time, urllib.parse, urllib.request, uuid

COMFY_DIR = os.path.expanduser('~/ComfyUI')
URL = 'http://127.0.0.1:8188'


def _req(path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(URL + path, data=body, headers={'Content-Type': 'application/json'} if body else {})
    with urllib.request.urlopen(r, timeout=30) as f:
        return json.loads(f.read() or b'{}')


def server_up():
    try:
        _req('/system_stats'); return True
    except OSError:
        return False


def ensure_server():
    if server_up():
        return
    log = open(os.path.join(COMFY_DIR, 'server.log'), 'a')
    subprocess.Popen([os.path.join(COMFY_DIR, '.venv/bin/python'), 'main.py', '--listen', '127.0.0.1', '--port', '8188'],
                     cwd=COMFY_DIR, stdout=log, stderr=log, start_new_session=True)
    for _ in range(120):
        time.sleep(2)
        if server_up():
            return
    sys.exit(f'ComfyUI did not start; see {COMFY_DIR}/server.log')


def run(workflow, timeout=7200):
    """Queue a workflow and wait; returns the list of output image file paths."""
    cid = str(uuid.uuid4())
    pid = _req('/prompt', {'prompt': workflow, 'client_id': cid})['prompt_id']
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(3)
        h = _req(f'/history/{pid}')
        if pid in h:
            st = h[pid].get('status', {})
            if st.get('status_str') == 'error':
                raise RuntimeError(json.dumps(st.get('messages', []))[:2000])
            files = []
            for node in h[pid].get('outputs', {}).values():
                for im in node.get('images', []):
                    files.append(os.path.join(COMFY_DIR, 'output', im.get('subfolder', ''), im['filename']))
            return files
    raise TimeoutError('ComfyUI job timed out')


def upload(path):
    """Copy an image into ComfyUI's input folder and return its name."""
    name = f'journey_{uuid.uuid4().hex[:8]}_{os.path.basename(path)}'
    shutil.copy(path, os.path.join(COMFY_DIR, 'input', name))
    return name


def sdxl_still(prompt, negative, seed, prefix, w=1344, h=768, steps=32, ref=None, ref_weight=0.7):
    wf = {
        '1': {'class_type': 'CheckpointLoaderSimple', 'inputs': {'ckpt_name': 'sd_xl_base_1.0.safetensors'}},
        '2': {'class_type': 'CLIPTextEncode', 'inputs': {'text': prompt, 'clip': ['1', 1]}},
        '3': {'class_type': 'CLIPTextEncode', 'inputs': {'text': negative, 'clip': ['1', 1]}},
        '4': {'class_type': 'EmptyLatentImage', 'inputs': {'width': w, 'height': h, 'batch_size': 1}},
        '5': {'class_type': 'KSampler', 'inputs': {'model': ['1', 0], 'positive': ['2', 0], 'negative': ['3', 0],
                                                   'latent_image': ['4', 0], 'seed': seed, 'steps': steps, 'cfg': 6.5,
                                                   'sampler_name': 'dpmpp_2m', 'scheduler': 'karras', 'denoise': 1.0}},
        '6': {'class_type': 'VAEDecode', 'inputs': {'samples': ['5', 0], 'vae': ['1', 2]}},
        '7': {'class_type': 'SaveImage', 'inputs': {'images': ['6', 0], 'filename_prefix': prefix}},
    }
    if ref:   # keep the character's face: IP-Adapter Plus Face (SDXL) with a reference still
        wf['20'] = {'class_type': 'LoadImage', 'inputs': {'image': upload(ref)}}
        wf['21'] = {'class_type': 'IPAdapterUnifiedLoader', 'inputs': {'model': ['1', 0], 'preset': 'PLUS FACE (portraits)'}}
        wf['22'] = {'class_type': 'IPAdapter', 'inputs': {'model': ['21', 0], 'ipadapter': ['21', 1], 'image': ['20', 0],
                                                          'weight': ref_weight, 'start_at': 0.0, 'end_at': 1.0,
                                                          'weight_type': 'standard'}}
        wf['5']['inputs']['model'] = ['22', 0]
    return run(wf)[0]


def wan_i2v(image, prompt, negative, seed, prefix, w=1280, h=704, length=121, steps=20):
    wf = {
        '1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'wan2.2_ti2v_5B_fp16.safetensors', 'weight_dtype': 'default'}},
        '2': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': 'umt5_xxl_fp16.safetensors', 'type': 'wan'}},
        '3': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'wan2.2_vae.safetensors'}},
        '4': {'class_type': 'ModelSamplingSD3', 'inputs': {'model': ['1', 0], 'shift': 8.0}},
        '5': {'class_type': 'CLIPTextEncode', 'inputs': {'text': prompt, 'clip': ['2', 0]}},
        '6': {'class_type': 'CLIPTextEncode', 'inputs': {'text': negative, 'clip': ['2', 0]}},
        '7': {'class_type': 'LoadImage', 'inputs': {'image': upload(image)}},
        '8': {'class_type': 'Wan22ImageToVideoLatent', 'inputs': {'vae': ['3', 0], 'width': w, 'height': h, 'length': length,
                                                                  'batch_size': 1, 'start_image': ['7', 0]}},
        '9': {'class_type': 'KSampler', 'inputs': {'model': ['4', 0], 'positive': ['5', 0], 'negative': ['6', 0],
                                                   'latent_image': ['8', 0], 'seed': seed, 'steps': steps, 'cfg': 5.0,
                                                   'sampler_name': 'uni_pc', 'scheduler': 'simple', 'denoise': 1.0}},
        '10': {'class_type': 'VAEDecode', 'inputs': {'samples': ['9', 0], 'vae': ['3', 0]}},
        '11': {'class_type': 'SaveImage', 'inputs': {'images': ['10', 0], 'filename_prefix': prefix}},
    }
    return run(wf)


def frames_to_mp4(frames, out, fps=24):
    tmp = out + '.frames'
    os.makedirs(tmp, exist_ok=True)
    for k, f in enumerate(sorted(frames)):
        shutil.copy(f, os.path.join(tmp, f'{k:05d}.png'))
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-framerate', str(fps), '-i', os.path.join(tmp, '%05d.png'),
                    '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', out], check=True)
    shutil.rmtree(tmp)
    for f in frames:
        try: os.remove(f)
        except OSError: pass


def fill(template, board):
    return template.replace('{character}', board.get('character', '')).replace('{car}', board.get('car', ''))


def generate(board, only=None, variants=2, stills_only=False, length=121, w=1280, h=704):
    ensure_server()
    base = os.path.dirname(os.path.expanduser(board['shots_dir']))
    stills_dir = os.path.join(base, 'stills'); shots_dir = os.path.expanduser(board['shots_dir'])
    os.makedirs(stills_dir, exist_ok=True); os.makedirs(shots_dir, exist_ok=True)
    neg = board.get('negative', '')
    ref = os.path.expanduser(board['character_ref']) if board.get('character_ref') else None
    if ref and not os.path.exists(ref):
        ref = None
    for e in board['timeline']:
        sid = e.get('shot')
        if not sid or (only and sid not in only):
            continue
        out = os.path.join(shots_dir, sid + '.mp4')
        if os.path.exists(out) and not only:
            print(f'{sid}: done already'); continue
        img_prompt = fill(e['image'], board) + ', ' + e.get('style', board.get('style', ''))
        # stills: keep any you already picked (named <id>.png), otherwise make variants and use the first
        pick = os.path.join(stills_dir, sid + '.png')
        if not os.path.exists(pick):
            seeds = [random.randint(1, 2**31) for _ in range(variants)]
            for v, sd in enumerate(seeds, 1):
                t = time.time()
                use_ref = ref if '{character}' in e['image'] and os.path.basename(ref or '') != sid + '.png' else None
                f = sdxl_still(img_prompt, neg, sd, f'journey/{sid}_v{v}', ref=use_ref, ref_weight=e.get('ref_weight', 0.7))
                dst = os.path.join(stills_dir, f'{sid}_v{v}.png'); shutil.move(f, dst)
                print(f'{sid}: still v{v} ({time.time() - t:.0f}s) -> {dst}', flush=True)
            shutil.copy(os.path.join(stills_dir, f'{sid}_v1.png'), pick)
        if stills_only:
            continue
        t = time.time()
        motion = fill(e.get('motion', ''), board) + ', ' + fill(e['image'], board) + ', ' + e.get('style', board.get('style', ''))
        frames = wan_i2v(pick, motion, neg, random.randint(1, 2**31), f'journey/{sid}_vid', w=w, h=h, length=length)
        frames_to_mp4(frames, out)
        score = similarity(pick, out)
        if score < 0.5:                               # broken render (noise): keep it out of the edit
            bad = os.path.join(base, 'failed'); os.makedirs(bad, exist_ok=True)
            shutil.move(out, os.path.join(bad, f'{sid}_score{score:.2f}.mp4'))
            print(f'{sid}: video FAILED the still check (similarity {score:.2f}); moved to failed/', flush=True)
            continue
        print(f'{sid}: video ({time.time() - t:.0f}s, similarity {score:.2f}) -> {out}', flush=True)


def similarity(still, video):
    """Correlation between the still and the video's first and middle frames (small greyscale); 1 = same."""
    import numpy as np
    def grab(args):
        raw = subprocess.run(['ffmpeg', '-v', 'error', *args, '-vf', 'scale=64:36', '-frames:v', '1', '-f', 'rawvideo',
                              '-pix_fmt', 'gray', '-'], capture_output=True).stdout
        return np.frombuffer(raw, np.uint8).astype(float) if raw else None
    a = grab(['-i', still]); scores = []
    for ss in ('0', '1'):
        b = grab(['-ss', ss, '-i', video])
        if a is not None and b is not None and len(a) == len(b):
            scores.append(np.corrcoef(a, b)[0, 1])
    return float(min(scores)) if scores else 0.0
