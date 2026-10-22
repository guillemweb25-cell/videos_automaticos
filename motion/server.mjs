// Servicio de render "motion" (HyperFrames) — corre en el HOST Windows, fuera de Docker,
// como ComfyUI y el TTS: así Chrome usa la GPU (≈1,3× tiempo real a 1344x768).
// Escucha SOLO en 127.0.0.1; el contenedor api llega por host.docker.internal.
//   POST /render {projectDir, output, fps}  → {id}
//   GET  /status/:id                        → {state: queued|running|done|error, progress, error}
//   GET  /health
// El backend manda rutas del contenedor (/app/cache/...); aquí se traducen a la ruta del
// host con MOTION_PATH_MAP ("/app/cache=D:/videos_automaticos/cache").
// Un render a la vez (Chrome + encoder ya usan todos los núcleos); el resto espera en cola.
import http from "node:http";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.MOTION_PORT || 8610);
const [FROM_ROOT, TO_ROOT] = (process.env.MOTION_PATH_MAP || "/app/cache=D:/videos_automaticos/cache").split("=");
const CLI = path.join(HERE, "node_modules", "hyperframes", "bin", "hyperframes.mjs");

// Solo se aceptan rutas bajo /app/cache, sin "..", traducidas a la carpeta cache del host.
function toHost(p) {
  if (typeof p !== "string" || !p.startsWith(FROM_ROOT + "/") || p.includes("..")) return null;
  return path.normalize(TO_ROOT + p.slice(FROM_ROOT.length));
}

const jobs = new Map();
const queue = [];
let running = false;

function runNext() {
  if (running || queue.length === 0) return;
  const job = queue.shift();
  running = true;
  job.state = "running";
  const args = [CLI, "render", "--output", job.output, "--fps", String(job.fps), "--quality", "standard"];
  const child = spawn(process.execPath, args, { cwd: job.projectDir, env: process.env });
  let tail = "";
  const onData = (buf) => {
    const text = buf.toString();
    tail = (tail + text).slice(-4000);
    for (const line of text.split("\n")) {
      const m = line.match(/@hf-progress (\{.*\})/);
      if (m) {
        try { job.progress = Math.max(job.progress, JSON.parse(m[1]).pct || 0); } catch {}
      }
    }
  };
  child.stdout.on("data", onData);
  child.stderr.on("data", onData);
  child.on("close", (code) => {
    if (code === 0 && existsSync(job.output)) {
      job.state = "done";
      job.progress = 100;
    } else {
      job.state = "error";
      job.error = `hyperframes render exit ${code}: ${tail.slice(-1500)}`;
    }
    console.log(`[motion] job ${job.id} ${job.state} (${Math.round((Date.now() - job.t0) / 1000)}s)`);
    running = false;
    runNext();
  });
}

function send(res, code, body) {
  res.writeHead(code, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}

http.createServer((req, res) => {
  if (req.method === "POST" && req.url === "/render") {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      let p;
      try { p = JSON.parse(body); } catch { return send(res, 400, { error: "JSON inválido" }); }
      const projectDir = toHost(p.projectDir);
      const output = toHost(p.output);
      if (!projectDir || !output) return send(res, 400, { error: `rutas fuera de ${FROM_ROOT}` });
      if (!existsSync(path.join(projectDir, "index.html"))) return send(res, 400, { error: "falta index.html" });
      const job = { id: randomUUID(), projectDir, output, fps: Number(p.fps) || 24,
                    state: "queued", progress: 0, error: null, t0: Date.now() };
      jobs.set(job.id, job);
      queue.push(job);
      console.log(`[motion] job ${job.id} en cola: ${projectDir}`);
      runNext();
      send(res, 200, { id: job.id });
    });
    return;
  }
  const m = req.url.match(/^\/status\/([\w-]+)$/);
  if (req.method === "GET" && m) {
    const job = jobs.get(m[1]);
    if (!job) return send(res, 404, { error: "job desconocido" });
    return send(res, 200, { state: job.state, progress: job.progress, error: job.error });
  }
  if (req.method === "GET" && req.url === "/health") return send(res, 200, { ok: true, running, queued: queue.length });
  send(res, 404, { error: "not found" });
}).listen(PORT, "127.0.0.1", () => console.log(`[motion] escuchando en 127.0.0.1:${PORT} (${FROM_ROOT} → ${TO_ROOT})`));
