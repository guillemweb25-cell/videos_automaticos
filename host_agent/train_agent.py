"""Agente de entrenamiento de LoRAs en el HOST (Windows) para Videos Automáticos.

Corre en la máquina con GPU (fuera de Docker) y expone un HTTP mínimo (stdlib) que
el backend llama para entrenar una LoRA de personaje con kohya sd-scripts.

  POST /train    {job_id, output_name, images:[comfy_output_fnames], captions:[...],
                  steps?, rank?, alpha?}
  GET  /status?job_id=...
  GET  /health

Flujo de un job (hilo de fondo):
  1) prepara dataset: copia imágenes del output de ComfyUI a D:\\AI\\datasets\\<name>\\img
     + captions .txt + dataset.toml
  2) apaga ComfyUI (libera VRAM)
  3) lanza kohya (accelerate launch sdxl_train_network.py ...), parsea el progreso
  4) reenciende ComfyUI
  5) marca done con el nombre del .safetensors

Arrancar en el host (una vez):
  D:\\AI\\sd-scripts\\venv\\Scripts\\python.exe host_agent\\train_agent.py

Sin auth (uso en LAN interna). Escucha en 0.0.0.0:8600.
Rutas configurables por variables de entorno (ver constantes abajo).
"""
import os, re, json, time, shutil, threading, subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

PORT = int(os.getenv("TRAIN_AGENT_PORT", "8600"))
SD = os.getenv("SD_SCRIPTS_DIR", r"D:\AI\sd-scripts")
ACCEL = os.path.join(SD, "venv", "Scripts", "accelerate.exe")
ACCEL_CFG = os.path.join(SD, "accelerate_config.yaml")
COMFY_DIR = os.getenv("COMFY_DIR", r"D:\AI\ComfyUI")
COMFY_OUT = os.path.join(COMFY_DIR, "output")
COMFY_START = os.path.join(COMFY_DIR, "start.bat")
LORA_DIR = os.path.join(COMFY_DIR, "models", "loras")
DATASETS = os.getenv("DATASETS_DIR", r"D:\AI\datasets")
CKPT = os.getenv("TRAIN_CKPT",
                 r"D:/AI/ComfyUI/models/checkpoints/SDXL/RealVisXL_V5.0_fp16.safetensors")

JOBS = {}          # job_id -> dict(state, step, total, message, lora_filename)
JOBS_LOCK = threading.Lock()


def _set(job_id, **kw):
    with JOBS_LOCK:
        JOBS.setdefault(job_id, {}).update(kw)


def _kill_comfy():
    subprocess.run(["powershell", "-NoProfile", "-Command",
        "Get-NetTCPConnection -LocalPort 8188 -State Listen -ErrorAction SilentlyContinue | "
        "Select-Object -Expand OwningProcess -Unique | "
        "ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"],
        capture_output=True)
    time.sleep(3)


def _start_comfy():
    out = os.path.join(COMFY_DIR, "comfyui_startup.log")
    err = os.path.join(COMFY_DIR, "comfyui_startup.err.log")
    subprocess.Popen(["powershell", "-NoProfile", "-Command",
        f"Start-Process -FilePath '{COMFY_START}' -WorkingDirectory '{COMFY_DIR}' "
        f"-WindowStyle Hidden -RedirectStandardOutput '{out}' -RedirectStandardError '{err}'"])


def _prepare_dataset(name, images, captions):
    img_dir = os.path.join(DATASETS, name, "img")
    if os.path.isdir(img_dir):
        for f in os.listdir(img_dir):
            try: os.remove(os.path.join(img_dir, f))
            except Exception: pass
    os.makedirs(img_dir, exist_ok=True)
    n = 0
    for i, fname in enumerate(images):
        src = os.path.join(COMFY_OUT, os.path.basename(fname))
        if not os.path.exists(src):
            continue
        base = f"{name}_{i:02d}"
        shutil.copy(src, os.path.join(img_dir, base + ".png"))
        cap = captions[i] if i < len(captions) else ""
        with open(os.path.join(img_dir, base + ".txt"), "w", encoding="utf-8") as fh:
            fh.write(cap)
        n += 1
    toml = os.path.join(DATASETS, name, "dataset.toml")
    with open(toml, "w", encoding="utf-8") as fh:
        fh.write(
            "[general]\nenable_bucket = true\ncaption_extension = \".txt\"\n"
            "shuffle_caption = false\nkeep_tokens = 1\n\n"
            "[[datasets]]\nresolution = [768, 768]\nbatch_size = 2\n"
            "min_bucket_reso = 512\nmax_bucket_reso = 1024\nbucket_no_upscale = true\n\n"
            "  [[datasets.subsets]]\n"
            f"  image_dir = \"{img_dir.replace(os.sep, '/')}\"\n"
            "  num_repeats = 10\n")
    return img_dir, toml, n


def _run_job(spec):
    job_id = spec["job_id"]
    name = spec["output_name"]
    steps = int(spec.get("steps", 1600))
    rank = int(spec.get("rank", 32))
    alpha = int(spec.get("alpha", 16))
    log = os.path.join(SD, f"train_{name}.log")
    try:
        _set(job_id, state="preparing", step=0, total=steps, message="Preparando dataset…")
        img_dir, toml, n = _prepare_dataset(name, spec["images"], spec["captions"])
        if n < 4:
            _set(job_id, state="error", message=f"Dataset insuficiente ({n} imágenes)")
            return
        _set(job_id, message=f"Dataset listo ({n} imgs). Liberando GPU…")
        _kill_comfy()

        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", CUDA_VISIBLE_DEVICES="0")
        cmd = [ACCEL, "launch", "--config_file", ACCEL_CFG, "--num_cpu_threads_per_process", "2",
               "sdxl_train_network.py",
               "--pretrained_model_name_or_path", CKPT,
               "--dataset_config", toml,
               "--output_dir", LORA_DIR, "--output_name", name,
               "--save_model_as", "safetensors",
               "--network_module", "networks.lora",
               "--network_dim", str(rank), "--network_alpha", str(alpha),
               "--learning_rate", "1e-4", "--unet_lr", "1e-4", "--text_encoder_lr", "5e-5",
               "--optimizer_type", "AdamW8bit",
               "--lr_scheduler", "cosine", "--lr_warmup_steps", "0",
               "--max_train_steps", str(steps),
               "--mixed_precision", "bf16", "--save_precision", "bf16",
               "--cache_latents", "--cache_latents_to_disk",
               "--gradient_checkpointing", "--sdpa", "--no_half_vae",
               "--min_snr_gamma", "5", "--seed", "42",
               "--max_data_loader_n_workers", "2", "--persistent_data_loader_workers",
               "--caption_extension", ".txt"]
        _set(job_id, state="training", message="Entrenando…")
        with open(log, "w", encoding="utf-8") as lf:
            proc = subprocess.Popen(cmd, cwd=SD, env=env, stdout=lf, stderr=subprocess.STDOUT)
        rx = re.compile(r"steps:\s+\d+%\|.*?\|\s*(\d+)/(\d+)")  # solo la barra de 'steps' (no caching)
        while proc.poll() is None:
            time.sleep(4)
            try:
                txt = open(log, encoding="utf-8", errors="ignore").read().replace("\r", "\n")
                m = None
                for m in rx.finditer(txt):
                    pass
                if m:
                    _set(job_id, step=int(m.group(1)), total=int(m.group(2)))
            except Exception:
                pass
        rc = proc.returncode
        lora_path = os.path.join(LORA_DIR, name + ".safetensors")
        if rc == 0 and os.path.exists(lora_path):
            _set(job_id, state="done", step=steps, message="LoRA lista", lora_filename=name + ".safetensors")
        else:
            tail = ""
            try: tail = open(log, encoding="utf-8", errors="ignore").read()[-800:]
            except Exception: pass
            _set(job_id, state="error", message=f"kohya salió con código {rc}. {tail[-400:]}")
    except Exception as e:
        _set(job_id, state="error", message=f"Excepción: {e}")
    finally:
        _start_comfy()


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):  # silencioso
        pass

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/health":
            return self._json(200, {"ok": True})
        if u.path == "/status":
            jid = parse_qs(u.query).get("job_id", [""])[0]
            with JOBS_LOCK:
                st = dict(JOBS.get(jid, {"state": "unknown"}))
            return self._json(200, st)
        self._json(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/train":
            return self._json(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            spec = json.loads(self.rfile.read(n) or b"{}")
        except Exception as e:
            return self._json(400, {"error": f"bad json: {e}"})
        jid = spec.get("job_id") or str(int(time.time()))
        spec["job_id"] = jid
        if not spec.get("output_name") or not spec.get("images"):
            return self._json(400, {"error": "faltan output_name/images"})
        _set(jid, state="queued", step=0, total=int(spec.get("steps", 1600)), message="En cola")
        threading.Thread(target=_run_job, args=(spec,), daemon=True).start()
        self._json(200, {"ok": True, "job_id": jid})


if __name__ == "__main__":
    print(f"Training agent en http://0.0.0.0:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
