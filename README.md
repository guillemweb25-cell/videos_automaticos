# Videos Automáticos

A self-hosted, full-stack AI video factory: drop in a script, get a finished YouTube Short with AI voiceover, AI imagery, music ducking, subtitles, thumbnail and one-click upload — across multiple channels, each with its own visual identity, voice and prompt rules.

Built and operated solo. Currently driving 7 production YouTube channels (spirituality, dream interpretation, biblical messages, senior health, Grabovoi codes, mystical kabbalah, and a separate adult-content channel) with real videos shipping every week.

> **Status:** Production · ~170 commits · ~50 source files · 17 ComfyUI workflows · 3 image backends · 3 TTS backends · running 24/7

---

## What it does

```
upload script  →  segment by paragraph
              →  TTS per paragraph (ElevenLabs / TikTok / local XTTSv2)
              →  align timing from real audio durations
              →  LLM generates contextual image prompts (with rolling history)
              →  diffusion images per paragraph (Leonardo / Grok / ComfyUI local)
              →  optional image-to-video (Grok grok-imagine-video / Leonardo VEO3)
              →  Ken Burns slideshow render (MoviePy)
              →  FFmpeg post: particle overlay + EBU R128 loudnorm
              →  burn-in subtitles (AssemblyAI)
              →  AI title / description / tags / thumbnail (per-channel rules)
              →  YouTube upload via OAuth
```

Each step is a discrete state on the video record. The pipeline is resumable: any failure leaves the video in the safe state right before the failed step, with an actionable error message and a button to retry.

---

## Why it's interesting

Three things make this more than a "wrap an LLM in a UI" project:

### 1. Three AI backends behind every primitive — swappable at runtime

|             | Cloud (paid)              | Cloud (paid)        | Self-hosted (free)            |
| ----------- | ------------------------- | ------------------- | ----------------------------- |
| **Images**  | Leonardo (VEO models)     | Grok / xAI          | ComfyUI + SDXL Juggernaut     |
| **TTS**     | ElevenLabs                | TikTok TTS          | Coqui XTTSv2 (voice cloning)  |
| **LLM**     | OpenAI GPT-4o-mini        | xAI Grok            | —                             |
| **STT**     | AssemblyAI                | —                   | —                             |

The user picks per-video. Self-hosted backends are the cost floor; cloud backends are the quality ceiling. The same UI; the same pipeline.

### 2. Two physical machines, one product

The API runs on a Linux VPS. ComfyUI and the XTTSv2 voice-cloning service run on a Windows 11 box with a consumer GPU sitting on the LAN. The orchestration is async HTTP across both, with the queueing, polling and retries handled by a small `comfy_service` client. SSH from Linux drives the Windows box for ops.

### 3. Multi-channel by design

Channels aren't just a label. Each channel has its own:
- Default ComfyUI workflow and visual style
- Image style prompt + negative prompt baked into every generation
- TTS voice (including custom-cloned voices via XTTSv2 seeds)
- Branding overlays, end-card logo and intro music
- Style guide (Markdown) with niche-specific rules (e.g. enforce "fully clothed" + child-safety on the religious channel)
- Independent OAuth credentials and YouTube account
- Independent prompt history for the LLM (no cross-channel contamination)

Adding a new channel is a form, a workflow JSON, a few seed audio clips and a logo.

---

## Engineering case studies

A few war stories worth reading, condensed.

### Render truncated to 80 seconds (silent corruption)

**Symptom:** Eight already-published videos across multiple channels froze mid-playback at exactly 1:20 while audio kept playing. No errors in logs. Discovered only when manually watching one.

**Root cause:** the FFmpeg `filter_complex` for the particle overlay used `[0:v][ovl]overlay=shortest=1[v_out]`. The overlay file happened to be 80 seconds long. `shortest=1` truncated the entire output to the shorter input — which was the overlay, not the main render.

**Fix:** add `-stream_loop -1` before the overlay input so it loops infinitely. `shortest=1` now correctly terminates on the main render's actual length.

[`backend/app/services/rendering_engine.py`](backend/app/services/rendering_engine.py)

### Frontend hung at "Loading..." during image generation

**Symptom:** Reloading the web app while a video was generating in the background would leave the page stuck on the loading screen indefinitely.

**Root cause:** the background task was declared `async` but called synchronous functions (`engine.generate_prompts`, `seo.generate_thumbnail_hook`, etc.) that internally do `requests.post` to OpenAI/Grok. Each call blocked uvicorn's only event loop for 5–10 seconds per paragraph. While blocked, no other request — including `GET /auth/me` from the reloading frontend — could be served.

**Fix:** wrap blocking sync calls with `await asyncio.to_thread(...)` so they run in a worker thread and the event loop stays free. Same pattern was applied to the audio pipeline (`run_in_executor`).

[`backend/app/routers/video_gen.py`](backend/app/routers/video_gen.py)

### Background tasks vanishing on every restart

**Symptom:** Any `docker compose restart` killed in-flight tasks and left videos pinned in `generating_audio` / `generating_images` / `rendering` states forever, requiring manual SQL cleanup.

**Fix:** a `@app.on_event("startup")` hook detects stuck videos at boot and demotes each to the safe state immediately preceding the failed phase, with a `last_error` message instructing the user exactly which button to press to resume. Combined with hash-keyed paragraph caching, resumes are nearly free.

[`backend/app/main.py`](backend/app/main.py)

### NSFW slip on a religious channel

**Symptom:** "St. Joseph the carpenter" generated with a nude minor in the workshop.

**Fix:** per-channel `style-guide.md` files loaded into prompt construction at runtime, with priority for protective clauses (NSFW + minors) and "fully clothed" weight reinforcement on sensitive channels. Negative prompts and image-style prompts are merged from three layers: global → channel → workflow.

[`backend/app/services/style_service.py`](backend/app/services/style_service.py)

### Voice selection silently overwritten by useEffect

**Symptom:** the voice picker reset to the first available option every time the voice list refreshed, regardless of what the user had picked.

**Fix:** the `useEffect` only writes the default when the current selection is invalid for the active provider, instead of writing on every render.

[`frontend/src/components/VideoCreator.tsx`](frontend/src/components/VideoCreator.tsx)

---

## Notable product calls

- **Vite preview, not Vite dev, in production.** Power users keep the image reviewer tab open for hours; HMR resets occasionally lose state. A static build served by `vite preview` keeps tabs stable.
- **Aggressive paragraph-level caching.** Prompt + style + workflow are hashed; if any of them haven't changed, the prompt and image are reused. Regenerating a single image doesn't re-run the LLM for the rest.
- **Auto-advance.** A single endpoint resumes a video from `audio_ready` to `images_ready` using the channel's defaults, bypassing the form for the common case.
- **Per-channel defaults pre-fill the new-video form.** The user doesn't pick voice + style + workflow every time — they're set once on the channel.
- **Inline toasts, never `alert()`.** Reversible actions (render, mark-as-uploaded, continue images) execute immediately with a toast confirmation. Browser `confirm()` is reserved for irreversible actions (DB + disk purges).
- **Cross-channel orphans manager.** Single panel listing every unuploaded video across all channels with cache size, status, age. Bulk-delete + per-row "render / continue / mark uploaded / purge" actions. Non-trivial savings on disk over time.

---

## Stack

**Backend** — Python 3.12 · FastAPI · SQLAlchemy + Alembic · MariaDB · Pydantic · uvicorn · MoviePy · FFmpeg · Pillow

**Frontend** — React 19 · TypeScript · Vite (preview mode in prod)

**AI / generation** — OpenAI · xAI Grok (LLM + grok-imagine-video) · Leonardo AI (VEO3 / VEO3FAST) · ComfyUI with SDXL Juggernaut XL Ragnarok · ElevenLabs · TikTok TTS · Coqui XTTSv2 · AssemblyAI

**Integrations** — YouTube Data API v3 (OAuth 2.0 per channel) · Stripe (checkout + prepaid credits)

**Infra** — Docker Compose (api · frontend · db · local TTS service) · reverse-proxy with HTTPS · LAN bridge to GPU host on Windows 11 · persistent volumes for generation cache and OAuth credentials

---

## Repo layout

```
backend/app/
  routers/      auth, channels, videos, youtube, payments, admin, settings
  services/     image_engine, audio_engine, rendering_engine, seo_engine,
                style_service, comfy_service, subtitle_engine,
                youtube_api, youtube_dl, maintenance_service
  models/       User, Channel, Video, UserSettings, GlobalSettings
  schemas/      Pydantic request/response shapes
  alembic/      DB migrations

frontend/src/
  components/   ChannelDashboard, VideoCreator, ImageReviewer,
                OrphansManager, AdminDashboard, Settings, Payments
  api.ts        typed HTTP client
  App.tsx       sidebar + routing

workflows/      17 ComfyUI workflow JSONs, one per visual style
local_tts_api/  separate Docker service running Coqui XTTSv2 on the GPU host
overlay/        particle MP4 overlays for the post-process step
docs/           architecture, setup, pipelines, API reference, env vars
```

---

## Quick start

Requires Docker + a `.env` with API keys (see [`docs/ENVIRONMENT.md`](docs/ENVIRONMENT.md)). ComfyUI must be reachable on its configured host:port for local image generation.

```bash
cp .env.example .env
# edit .env with your keys

docker compose up -d
# frontend → http://localhost:8501
# api      → http://localhost:8500
```

For the full architecture, the resumable pipeline state machine and the ComfyUI integration details, see:

- [Project Architecture](docs/PROJECT_ARCHITECTURE.md)
- [Setup Guide](docs/SETUP_GUIDE.md)
- [Workflows & Pipelines](docs/WORKFLOWS_AND_PIPELINES.md)
- [API Reference](docs/API_REFERENCE.md)
- [Environment Variables](docs/ENVIRONMENT.md)

---

## What this project demonstrates

- End-to-end ownership of a non-trivial production system: pipeline with temporal dependencies, persisted state machine, multiple paid integrations.
- Multimodal generative AI integration with three swappable backends per primitive — kept honest by really running cloud and self-hosted side by side.
- Self-hosting on consumer GPU (ComfyUI + XTTSv2) bridged from a Linux VPS over LAN.
- Diagnosing subtle bugs: blocked event loops, FFmpeg `filter_complex` truncating outputs, background tasks lost on restart, race-y `useEffect` overrides.
- UX sensitivity: real-time progress, recovery without losing work, no-alerts rule, sensible per-channel defaults, cross-channel cleanup.
- Solo operation of a real product — published videos exist, bugs were found *in production* and fixed without losing previously published content.
