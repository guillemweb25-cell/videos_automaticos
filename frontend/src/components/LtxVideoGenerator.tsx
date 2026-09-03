import React, { useEffect, useRef, useState } from 'react';
import { api, type LtxHistoryItem } from '../api';

const RES_PRESETS = [
  { label: 'Vertical 9:16 (512×896)', w: 512, h: 896 },
  { label: 'Vertical 2:3 (512×768) — más rápido', w: 512, h: 768 },
  { label: 'Vertical 9:16 HD (576×1024) — más pesado', w: 576, h: 1024 },
];
const LEN_PRESETS = [
  { label: '~2.6 s (65 frames)', n: 65 },
  { label: '~3.9 s (97 frames)', n: 97 },
  { label: '~4.8 s (121 frames)', n: 121 },
];

export default function LtxVideoGenerator() {
  const [prompt, setPrompt] = useState('');
  const [negative, setNegative] = useState('');
  const [resIdx, setResIdx] = useState(1); // 512×768 por defecto (más rápido)
  const [lenIdx, setLenIdx] = useState(1); // 97 frames
  const [seed, setSeed] = useState<string>('');

  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [videoUrl, setVideoUrl] = useState<string | null>(null);
  const [lastFile, setLastFile] = useState<string | null>(null);
  const [promptUsed, setPromptUsed] = useState('');

  const [history, setHistory] = useState<LtxHistoryItem[]>([]);
  const [openVideos, setOpenVideos] = useState<Record<string, string>>({});
  const [loadingVid, setLoadingVid] = useState<string | null>(null);

  const pollRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);
  const genRef = useRef<{ w: number; h: number; length: number; fps: number; seed: number; promptOrig: string } | null>(null);

  const loadHistory = async () => {
    try { setHistory(await api.ltxHistory()); } catch { /* vacío */ }
  };
  useEffect(() => { loadHistory(); }, []);

  const stopTimers = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  };
  useEffect(() => () => { stopTimers(); if (videoUrl) URL.revokeObjectURL(videoUrl); }, []);

  const generate = async () => {
    if (!prompt.trim() || busy) return;
    setError(''); setStatus('Enviando a ComfyUI…'); setBusy(true); setElapsed(0);
    if (videoUrl) { URL.revokeObjectURL(videoUrl); setVideoUrl(null); }
    const res = RES_PRESETS[resIdx], len = LEN_PRESETS[lenIdx];
    try {
      const r = await api.ltxGenerate({
        prompt: prompt.trim(),
        negative: negative.trim() || undefined,
        width: res.w, height: res.h, length: len.n, fps: 25,
        seed: seed.trim() ? parseInt(seed.trim()) : undefined,
      });
      setPromptUsed(r.prompt_used || '');
      genRef.current = { w: r.width, h: r.height, length: r.length, fps: r.fps, seed: r.seed, promptOrig: prompt.trim() };
      setStatus('Generando… (puede tardar varios minutos)');
      timerRef.current = window.setInterval(() => setElapsed((e) => e + 1), 1000);
      pollRef.current = window.setInterval(() => poll(r.prompt_id), 4000);
    } catch (err: any) {
      setError(err.message || 'Error'); setBusy(false); setStatus('');
    }
  };

  const poll = async (pid: string) => {
    try {
      const s = await api.ltxStatus(pid);
      if (s.status === 'done' && s.filename) {
        stopTimers(); setStatus('Descargando vídeo…');
        const url = await api.ltxVideoObjectUrl(s.filename, s.subfolder || '');
        setVideoUrl(url); setLastFile(s.filename); setStatus(''); setBusy(false);
        // Guardar en el historial
        const g = genRef.current;
        try {
          await api.ltxSave({
            prompt: g?.promptOrig || '', prompt_used: promptUsed,
            filename: s.filename, subfolder: s.subfolder || '',
            width: g?.w || 0, height: g?.h || 0, length: g?.length || 0, fps: g?.fps || 25, seed: g?.seed ?? null,
          });
          loadHistory();
        } catch { /* no bloquea */ }
      } else if (s.status === 'error') {
        stopTimers(); setError(s.error || 'Error en la generación'); setBusy(false); setStatus('');
      } else {
        setStatus(s.status === 'pending' ? 'En cola…' : 'Generando… (puede tardar varios minutos)');
      }
    } catch { /* reintenta en el siguiente tick */ }
  };

  const download = () => {
    if (!videoUrl) return;
    const a = document.createElement('a');
    a.href = videoUrl; a.download = lastFile || 'ltx_video.mp4';
    document.body.appendChild(a); a.click(); a.remove();
  };

  const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

  const openHistoryVideo = async (item: LtxHistoryItem) => {
    if (openVideos[item.id]) return;
    setLoadingVid(item.id);
    try {
      const url = await api.ltxVideoObjectUrl(item.filename, item.subfolder || '');
      setOpenVideos((prev) => ({ ...prev, [item.id]: url }));
    } catch { alert('No se pudo cargar el vídeo (quizá se borró del disco).'); }
    finally { setLoadingVid(null); }
  };
  const downloadHistory = async (item: LtxHistoryItem) => {
    try {
      const url = openVideos[item.id] || await api.ltxVideoObjectUrl(item.filename, item.subfolder || '');
      const a = document.createElement('a'); a.href = url; a.download = item.filename;
      document.body.appendChild(a); a.click(); a.remove();
    } catch { alert('No se pudo descargar.'); }
  };
  const deleteHistory = async (item: LtxHistoryItem) => {
    if (!confirm('¿Quitar del historial? (el fichero en disco no se borra)')) return;
    try { await api.ltxHistoryDelete(item.id); loadHistory(); } catch { alert('Error al borrar.'); }
  };
  const reusePrompt = (item: LtxHistoryItem) => {
    setPrompt(item.prompt || item.prompt_used || '');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };
  const fmtWhen = (t: number) => new Date(t * 1000).toLocaleString('es-ES', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });

  return (
    <div style={{ maxWidth: 820, margin: '0 auto' }}>
      <div style={{ background: '#1e293b', borderRadius: 12, padding: 20, marginBottom: 20 }}>
        <h2 style={{ marginTop: 0 }}>🎬 Generador de vídeo vertical (LTX 2.5)</h2>
        <p style={{ color: '#94a3b8', marginTop: 4 }}>
          Texto → vídeo vertical corto para colgar (Shorts/TikTok/Reels). Corre en tu ComfyUI local
          con LTX 2.5. Los primeros renders tardan varios minutos.
        </p>

        <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Prompt (escribe en español; se traduce a inglés solo)</label>
        <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} disabled={busy}
          placeholder="un cachorro de corgi corriendo por una playa al atardecer, cinematográfico"
          style={{ width: '100%', marginTop: 4, padding: 10, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }} />

        <div style={{ display: 'flex', gap: 12, marginTop: 12, flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 240px' }}>
            <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Formato</label>
            <select value={resIdx} onChange={(e) => setResIdx(+e.target.value)} disabled={busy}
              style={{ width: '100%', marginTop: 4, padding: 9, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }}>
              {RES_PRESETS.map((r, i) => <option key={i} value={i}>{r.label}</option>)}
            </select>
          </div>
          <div style={{ flex: '1 1 180px' }}>
            <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Duración</label>
            <select value={lenIdx} onChange={(e) => setLenIdx(+e.target.value)} disabled={busy}
              style={{ width: '100%', marginTop: 4, padding: 9, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }}>
              {LEN_PRESETS.map((l, i) => <option key={i} value={i}>{l.label}</option>)}
            </select>
          </div>
          <div style={{ flex: '0 1 140px' }}>
            <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Seed (opcional)</label>
            <input value={seed} onChange={(e) => setSeed(e.target.value.replace(/[^0-9]/g, ''))} disabled={busy}
              placeholder="aleatorio"
              style={{ width: '100%', marginTop: 4, padding: 9, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }} />
          </div>
        </div>

        <details style={{ marginTop: 12 }}>
          <summary style={{ color: '#94a3b8', fontSize: '0.85rem', cursor: 'pointer' }}>Negativo (avanzado)</summary>
          <input value={negative} onChange={(e) => setNegative(e.target.value)} disabled={busy}
            placeholder="worst quality, blurry, distorted…"
            style={{ width: '100%', marginTop: 6, padding: 9, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#cbd5e1' }} />
        </details>

        <div style={{ marginTop: 16, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={generate} disabled={busy || !prompt.trim()}>
            {busy ? '⏳ Generando…' : '🎬 Generar vídeo'}
          </button>
          {status && <span style={{ color: '#94a3b8', fontSize: '0.9rem' }}>{status} {elapsed > 0 && `(${mmss(elapsed)})`}</span>}
        </div>
        {promptUsed && (
          <div style={{ color: '#64748b', fontSize: '0.78rem', marginTop: 8, fontStyle: 'italic' }}>
            Prompt enviado (EN): {promptUsed}
          </div>
        )}
        {error && <div style={{ color: '#f87171', marginTop: 10 }}>⚠️ {error}</div>}
        {busy && (
          <div style={{ color: '#64748b', fontSize: '0.78rem', marginTop: 8 }}>
            Tu GPU (16 GB) va justa: si falla por memoria, prueba 512×768 y 65 frames.
          </div>
        )}
      </div>

      {videoUrl && (
        <div style={{ background: '#0f221a', border: '1px solid #14532d', borderRadius: 12, padding: 20, textAlign: 'center' }}>
          <h3 style={{ marginTop: 0, color: '#4ade80' }}>✅ Vídeo listo</h3>
          <video src={videoUrl} controls autoPlay loop
            style={{ maxWidth: 360, width: '100%', borderRadius: 10, background: '#000' }} />
          <div style={{ marginTop: 12 }}>
            <button className="btn btn-primary" onClick={download}>⬇️ Descargar MP4</button>
          </div>
        </div>
      )}

      {/* Historial */}
      <div style={{ background: '#1e293b', borderRadius: 12, padding: 20, marginTop: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0 }}>🎞️ Historial de vídeos ({history.length})</h3>
          <button className="btn-link" onClick={loadHistory}>Refrescar</button>
        </div>
        {history.length === 0 ? (
          <p style={{ color: '#64748b', marginTop: 12 }}>Aún no has generado ningún vídeo. Los que generes aparecerán aquí.</p>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 14, marginTop: 14 }}>
            {history.map((item) => (
              <div key={item.id} style={{ background: '#0f172a', borderRadius: 10, padding: 10, border: '1px solid #1e293b' }}>
                {openVideos[item.id] ? (
                  <video src={openVideos[item.id]} controls loop style={{ width: '100%', borderRadius: 8, background: '#000', aspectRatio: `${item.width}/${item.height}` }} />
                ) : (
                  <button onClick={() => openHistoryVideo(item)} disabled={loadingVid === item.id}
                    style={{ width: '100%', aspectRatio: `${item.width || 9}/${item.height || 16}`, borderRadius: 8, background: '#000', color: '#94a3b8', border: '1px dashed #334155', cursor: 'pointer' }}>
                    {loadingVid === item.id ? '⏳ Cargando…' : '▶ Ver'}
                  </button>
                )}
                <div style={{ color: '#cbd5e1', fontSize: '0.8rem', marginTop: 8, maxHeight: 54, overflow: 'hidden' }} title={item.prompt}>{item.prompt}</div>
                <div style={{ color: '#64748b', fontSize: '0.7rem', marginTop: 4 }}>
                  {item.width}×{item.height} · {item.length}f · {fmtWhen(item.created_at)}
                </div>
                <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                  <button className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: '0.75rem' }} onClick={() => downloadHistory(item)}>⬇️</button>
                  <button className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: '0.75rem' }} onClick={() => reusePrompt(item)}>♻️ Prompt</button>
                  <button className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: '0.75rem' }} onClick={() => deleteHistory(item)}>🗑️</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
