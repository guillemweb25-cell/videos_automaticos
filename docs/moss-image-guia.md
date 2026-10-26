# MOSS-Image en ComfyUI: guía práctica

Esta guía resume lo que funciona en este equipo: RTX 4060 Ti con 16 GB de VRAM, 32 GB de RAM y ComfyUI en `D:\AI\ComfyUI` (puerto 8188). Los tiempos son medidos aquí, en octubre de 2026. Su objetivo es usar MOSS-Image desde otro proyecto (vídeos automáticos de YouTube) llamando a la API HTTP de ComfyUI.

## 1. Qué es y para qué sirve

- **MOSS-Image SFT** (OpenMOSS) es un modelo de imagen de 5B con licencia Apache 2.0, así que se puede usar comercialmente.
- Como codificador de texto usa **Qwen3.5 9B**, un LLM. Por eso entiende prompts largos y detallados mucho mejor que SD 1.5 o SDXL.
- **Su punto fuerte es escribir texto dentro de la imagen**: títulos, carteles o rótulos. Viene muy bien para miniaturas de YouTube y portadas de episodios.
- **Puntos débiles:**
  - Hay pocos LoRAs de estilo y no tiene ControlNet ni IPAdapter.
  - Para mantener el mismo personaje en varias imágenes hay que apoyarse en prompts muy descriptivos y en semillas fijas.

## 2. Requisitos

- **ComfyUI 0.42 o posterior.** Aquí está la v0.42.5; las versiones anteriores no traen el tipo de CLIP `moss_image`.
- **Modelos:**

| Carpeta en `D:\AI\ComfyUI\models\` | Archivo | Origen |
|---|---|---|
| `diffusion_models/` | `moss_image_sft_int8_convrot.safetensors` | Comfy-Org/MOSS-Image |
| `text_encoders/` | `qwen3.5_9b_w4a8_gptq.safetensors` | Comfy-Org/MOSS-Image |
| `vae/` | `flux2-vae_small.safetensors` | Comfy-Org/MOSS-Image |
| `loras/` | `MossImage_turbo_8step_dmd.safetensors` | `lora_latest.safetensors` de [lodestones/MOSS-Image-SFT-8-steps-dmd](https://huggingface.co/lodestones/MOSS-Image-SFT-8-steps-dmd), renombrado |

## 3. Modos recomendados

| Modo | LoRA turbo | Pasos | CFG | Sampler / scheduler | Negativo y SLG | Tiempo (~1 MP) |
|---|---|---|---|---|---|---|
| **Turbo (por defecto)** | sí, fuerza **0.7** | 8 | **1.0** | `euler` / `simple` | no tienen efecto | **~22–30 s** |
| Rápido (plantilla oficial) | no | 25 | 2.5 | `er_sde` / `simple` | sí, SLG en la capa 22 | ~2 min 15 s |
| Máxima calidad (model card) | no | 50 | 3.0 | `er_sde` / `simple` | sí | ~4–5 min (estimado) |

- **Turbo** da una calidad prácticamente igual que el modo rápido en ilustración y estilo anime. Es el que conviene para producir en serie.
- **Sampler en turbo:** `dpmpp_sde_gpu` con `beta57` (necesita RES4LYF) también funciona, pero tarda el doble (~46 s) sin una mejora clara.
- **Fuerza de la LoRA:** `lora_latest.safetensors` va a 0.7. Si se usa `lora.safetensors`, va a 1.0.
- **Primera imagen del lote:** tarda bastante más (~3 min) porque carga los modelos. Si antes se generó un vídeo con MiniMax H3, ComfyUI tiene que descargarlo de la VRAM y cargar MOSS. Conviene **agrupar las imágenes** y no alternarlas con vídeos.
- **Mejorador de prompt** (nodo `TextGenerate` con el propio Qwen3.5): reescribe el prompt con más detalle, pero añade **~8 min** por imagen. No compensa en automático. Es mejor que el LLM del pipeline escriba directamente el prompt detallado (ver la sección 5).

## 4. Tamaños

- El modelo está entrenado entre 1 y 2 MP. **Los lados tienen que ser múltiplos de 16.**

| Uso | Tamaño de generación | Después |
|---|---|---|
| Shorts / vertical 9:16 | 768×1344 (o 1088×1920) | — |
| Vídeo / miniatura 16:9 | 1344×768 (o 1920×1088) | Miniatura: redimensionar a 1280×720 |
| Cuadrado | 1024×1024 (o 1440×1440) | — |
| 3:4 / 4:3 | 880×1168 / 1168×880 | — |

- **El ~2 MP** tarda más del doble. Para miniaturas es mejor generar a ~1 MP y escalar.

## 5. Cómo escribir los prompts

- **Prompts en inglés, largos y descriptivos.** Funcionan mejor párrafos de 60–150 palabras que listas de etiquetas al estilo SD.
- **Estructura recomendada:**
  1. **Tipo de imagen y estilo:** por ejemplo "Cinematic digital illustration, vibrant anime style, soft cel shading…".
  2. **Sujeto principal**, con su aspecto concreto: colores, ropa, rasgos y expresión.
  3. **Acción o pose, y composición:** "full body", "close-up", "centered with space on the left for text"…
  4. **Fondo y luz.**
  5. **Texto, si lo hay:** entre comillas y diciendo dónde va, por ejemplo `Large bold title text at the top reads "EPISODIO 3: EL VOLCÁN"`. Con 1–6 palabras acierta casi siempre; con frases largas puede fallar alguna letra.
  6. **Lo que NO quieres:** en modo turbo no hay prompt negativo, así que va en positivo dentro del prompt. Por ejemplo: "No text, no watermark, no frame".
- **Estilo coherente en una serie:** define un **bloque de estilo fijo** y ponlo al principio de todos los prompts, igual que hace el generador de cartas.
- **Mismo personaje en varias escenas:** usa siempre la **misma descripción literal** del personaje, palabra por palabra, por ejemplo "a small round red fox cub with a white-tipped flaming tail and amber eyes, wearing a green scarf".
  - Fijar la semilla ayuda a repetir composición, pero no garantiza el mismo personaje si cambia el resto del prompt.
- **Pipeline con LLM:** pide al LLM que genere el prompt siguiendo la estructura de arriba. Que no use palabras como "masterpiece, best quality, 8k": aquí no aportan nada.
- **Derechos:** evita nombres de personajes, marcas o artistas con copyright. Además el modelo los imita, y en YouTube eso puede dar problemas. Describe a personajes originales.

## 6. Workflow para la API (formato "API" de ComfyUI)

Workflow mínimo en modo turbo. Se cambian `text`, `width`, `height`, `seed` y `filename_prefix`:

```json
{
  "1":  {"class_type": "UNETLoader", "inputs": {"unet_name": "moss_image_sft_int8_convrot.safetensors", "weight_dtype": "default"}},
  "2":  {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen3.5_9b_w4a8_gptq.safetensors", "type": "moss_image", "device": "default"}},
  "3":  {"class_type": "VAELoader", "inputs": {"vae_name": "flux2-vae_small.safetensors"}},
  "14": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": "MossImage_turbo_8step_dmd.safetensors", "strength_model": 0.7}},
  "4":  {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": "PROMPT AQUÍ"}},
  "5":  {"class_type": "CLIPTextEncode", "inputs": {"clip": ["2", 0], "text": ""}},
  "6":  {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": 1344, "height": 768, "batch_size": 1}},
  "7":  {"class_type": "KSampler", "inputs": {"model": ["14", 0], "seed": 123456, "steps": 8, "cfg": 1.0,
          "sampler_name": "euler", "scheduler": "simple", "positive": ["4", 0], "negative": ["5", 0],
          "latent_image": ["6", 0], "denoise": 1.0}},
  "8":  {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
  "9":  {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "youtube/ep03_thumb"}}
}
```

**Modo rápido o de calidad (sin turbo):**
- Quita el nodo `14` y conecta el KSampler a `["15", 0]`.
- Pon `steps` 25 o 50, `cfg` 2.5 o 3.0 y `sampler_name` `er_sde`.
- Pon como negativo `"nsfw, worst quality, bad anatomy, watermark, jpeg artifact"`.
- Añade el nodo SLG:

```json
"15": {"class_type": "SkipLayerGuidanceDiTSimple", "inputs": {"model": ["1", 0], "double_layers": "", "single_layers": "22", "start_percent": 0.0, "end_percent": 0.5}}
```

## 7. Llamarlo desde Python

```python
import json, time, urllib.request, urllib.parse

COMFY = "http://127.0.0.1:8188"   # desde Docker: http://host.docker.internal:8188

def generate(workflow: dict, out_path: str, timeout_s: int = 900) -> str:
    req = urllib.request.Request(f"{COMFY}/prompt", data=json.dumps({"prompt": workflow}).encode(),
                                 headers={"Content-Type": "application/json"})
    prompt_id = json.load(urllib.request.urlopen(req))["prompt_id"]
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        hist = json.load(urllib.request.urlopen(f"{COMFY}/history/{prompt_id}")).get(prompt_id)
        if hist and hist.get("status", {}).get("completed") is not None:
            if hist["status"].get("status_str") != "success":
                raise RuntimeError(f"ComfyUI falló: {hist['status']}")
            img = next(i for o in hist["outputs"].values() for i in o.get("images", []))
            q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img["subfolder"], "type": img["type"]})
            with urllib.request.urlopen(f"{COMFY}/view?{q}") as r, open(out_path, "wb") as f:
                f.write(r.read())
            return out_path
        time.sleep(2)
    raise TimeoutError(prompt_id)
```

- **Errores:** si `POST /prompt` devuelve 400, el cuerpo dice qué nodo o qué modelo falta.
- **Progreso en vivo:** se puede escuchar el websocket `ws://…:8188/ws?clientId=<id>`, mandando el mismo `client_id` en el POST. Los eventos `progress` traen `value` y `max` del KSampler.
- **Caché:** si se envía exactamente el mismo workflow (mismo prompt y misma semilla), ComfyUI devuelve el resultado en caché en ~2 s sin regenerar. Para variar, cambia la semilla.
- **Cola:** ComfyUI procesa los trabajos de uno en uno. Si otra app (The Lamb Studio) también le envía trabajos, se encolan, no fallan.

## 8. Combinarlo con vídeo (MiniMax H3)

- **Buena receta:** generar con MOSS-Image el **primer fotograma** de cada escena, que da composición, personaje y texto controlados, y pasarlo a MiniMax H3 en modo imagen a vídeo (`MiniMaxH3ImageToVideo`, entrada `first_frame`).
- **Pasos:**
  1. Sube la imagen con `POST /upload/image` (multipart: `image`, `type=input`, `subfolder`).
  2. Usa el nombre devuelto en un nodo `LoadImage`.
- **Mismo tamaño que el vídeo:** genera la imagen ya con el formato del vídeo, por ejemplo 768×1344 para Shorts, o recórtala a la resolución del vídeo antes de subirla.
- **Agrupar por tipo:** primero todas las imágenes de un episodio y luego todos los vídeos. Cada cambio de modelo cuesta 1–3 min de carga.

## 9. Problemas conocidos

- **`clip type moss_image not found`** o nodo desconocido: ComfyUI es anterior a la 0.42. Hay que actualizar.
- **Imágenes quemadas o sobresaturadas en turbo:** CFG por encima de 1, o la LoRA a más de 0.7 con `lora_latest`.
- **Imágenes borrosas o "a medio hacer" en turbo:** menos de 6 pasos, o un sampler SDE con un scheduler que no toca. Lo seguro es `euler` + `simple`.
- **Falta de VRAM al alternar con vídeo:** reinicia ComfyUI o llama a `POST /free` con `{"unload_models": true, "free_memory": true}` antes de cambiar de modelo.
- **El custom node `teacache` da error al importar:** no afecta a MOSS-Image.
