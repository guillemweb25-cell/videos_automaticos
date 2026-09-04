import React, { useEffect, useRef, useState } from 'react';
import { api, type CharacterItem } from '../api';

const RATIOS = [
  { label: 'Vertical 2:3 (832×1216)', w: 832, h: 1216 },
  { label: 'Cuadrado 1:1 (1024×1024)', w: 1024, h: 1024 },
  { label: 'Horizontal 3:2 (1216×832)', w: 1216, h: 832 },
];

/** Genera imágenes nuevas de un personaje guardado en la escena/pose del prompt. */
export default function CharacterImages() {
  const [chars, setChars] = useState<CharacterItem[]>([]);
  const [charId, setCharId] = useState('');
  const [prompt, setPrompt] = useState('');
  const [num, setNum] = useState(2);
  const [ratio, setRatio] = useState(0);
  const [poses, setPoses] = useState<{ key: string; label: string }[]>([]);
  const [pose, setPose] = useState('');

  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [promptEn, setPromptEn] = useState('');
  const [imgs, setImgs] = useState<{ filename: string; url: string }[]>([]);

  // Animar (I2V)
  const [animFor, setAnimFor] = useState<string | null>(null);
  const [animPrompt, setAnimPrompt] = useState('');
  const [animBusy, setAnimBusy] = useState(false);
  const [animStatus, setAnimStatus] = useState('');
  const [animElapsed, setAnimElapsed] = useState(0);
  const [animVideo, setAnimVideo] = useState<string | null>(null);

  const pollRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);
  const aPollRef = useRef<number | null>(null);
  const aTimerRef = useRef<number | null>(null);
  const stop = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  };
  useEffect(() => {
    (async () => {
      try { const c = await api.charList(); setChars(c); if (c[0]) setCharId(c[0].id); } catch { /* */ }
    })();
    return () => stop();
  }, []);

  const selChar = chars.find((c) => c.id === charId);

  // Carga las poses del género del personaje seleccionado
  useEffect(() => {
    (async () => {
      try { setPoses(await api.charPoses(selChar?.gender || 'mujer')); setPose(''); } catch { /* */ }
    })();
  }, [charId, selChar?.gender]);

  const generate = async () => {
    if (!charId || !prompt.trim() || busy) return;
    setError(''); setStatus('Enviando…'); setBusy(true); setElapsed(0);
    imgs.forEach((i) => URL.revokeObjectURL(i.url)); setImgs([]);
    const r0 = RATIOS[ratio];
    try {
      const r = await api.charScene({ character_id: charId, prompt: prompt.trim(), num_images: num, width: r0.w, height: r0.h, pose: pose || null });
      setPromptEn(r.prompt_en || '');
      setStatus(`Generando ${r.expected} imagen(es)…`);
      timerRef.current = window.setInterval(() => setElapsed((e) => e + 1), 1000);
      pollRef.current = window.setInterval(() => poll(r.prompt_id), 4000);
    } catch (e: any) { setError(e.message); setBusy(false); setStatus(''); }
  };

  const poll = async (pid: string) => {
    try {
      const s = await api.charStatus(pid);
      if (s.status === 'done' && s.images?.length) {
        stop(); setStatus('Cargando…');
        const loaded = await Promise.all(s.images.map(async (f) => ({ filename: f, url: await api.charImageObjectUrl(f) })));
        setImgs(loaded); setStatus(''); setBusy(false);
      } else if (s.status === 'error') { stop(); setError('Error en la generación'); setBusy(false); setStatus(''); }
    } catch { /* reintenta */ }
  };

  const dl = (url: string, filename: string) => {
    const a = document.createElement('a'); a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
  };
  const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

  const stopAnim = () => {
    if (aPollRef.current) { clearInterval(aPollRef.current); aPollRef.current = null; }
    if (aTimerRef.current) { clearInterval(aTimerRef.current); aTimerRef.current = null; }
  };
  const openAnim = (filename: string) => {
    if (animVideo) URL.revokeObjectURL(animVideo);
    setAnimFor(filename); setAnimPrompt(''); setAnimVideo(null); setAnimStatus(''); setAnimBusy(false); setAnimElapsed(0);
  };
  const closeAnim = () => { stopAnim(); if (animVideo) URL.revokeObjectURL(animVideo); setAnimFor(null); setAnimVideo(null); setAnimBusy(false); setAnimStatus(''); };
  const animate = async () => {
    if (!animFor || animBusy) return;
    setAnimBusy(true); setAnimStatus('Enviando…'); setAnimElapsed(0);
    if (animVideo) { URL.revokeObjectURL(animVideo); setAnimVideo(null); }
    const r0 = RATIOS[ratio];
    try {
      const r = await api.ltxI2V({ image_filename: animFor, prompt: animPrompt.trim(), width: r0.w, height: r0.h, length: 97 });
      setAnimStatus('Generando vídeo… (puede tardar varios minutos)');
      aTimerRef.current = window.setInterval(() => setAnimElapsed((e) => e + 1), 1000);
      aPollRef.current = window.setInterval(async () => {
        try {
          const s = await api.ltxStatus(r.prompt_id);
          if (s.status === 'done' && s.filename) {
            stopAnim(); setAnimStatus('Descargando…');
            const url = await api.ltxVideoObjectUrl(s.filename, s.subfolder || '');
            setAnimVideo(url); setAnimStatus(''); setAnimBusy(false);
          } else if (s.status === 'error') { stopAnim(); setAnimStatus('Error en la generación'); setAnimBusy(false); }
        } catch { /* reintenta */ }
      }, 4000);
    } catch (e: any) { setAnimStatus(e.message || 'Error'); setAnimBusy(false); }
  };

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <div style={{ background: '#1e293b', borderRadius: 12, padding: 20, marginBottom: 20 }}>
        <h2 style={{ marginTop: 0 }}>🖼️ Crear imágenes de un personaje</h2>
        <p style={{ color: '#94a3b8', marginTop: 4 }}>
          Elige un personaje guardado y genera imágenes nuevas de él en cualquier escena o pose
          (mantiene la cara vía IPAdapter). El vídeo, después.
        </p>

        {chars.length === 0 ? (
          <div style={{ color: '#fbbf24', marginTop: 8 }}>Primero crea y guarda un personaje en la pestaña 🧑‍🎨 Personajes.</div>
        ) : (
          <>
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 8 }}>
              <div style={{ flex: '1 1 220px' }}>
                <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Personaje</label>
                <select value={charId} onChange={(e) => setCharId(e.target.value)} disabled={busy}
                  style={{ width: '100%', marginTop: 4, padding: 9, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }}>
                  {chars.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.style})</option>)}
                </select>
              </div>
              <div style={{ flex: '1 1 200px' }}>
                <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Formato</label>
                <select value={ratio} onChange={(e) => setRatio(+e.target.value)} disabled={busy}
                  style={{ width: '100%', marginTop: 4, padding: 9, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }}>
                  {RATIOS.map((r, i) => <option key={i} value={i}>{r.label}</option>)}
                </select>
              </div>
              <div style={{ flex: '0 1 110px' }}>
                <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Nº imágenes</label>
                <select value={num} onChange={(e) => setNum(+e.target.value)} disabled={busy}
                  style={{ width: '100%', marginTop: 4, padding: 9, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }}>
                  {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}</option>)}
                </select>
              </div>
              {poses.length > 0 && (
                <div style={{ flex: '0 1 150px' }}>
                  <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Pose (opcional)</label>
                  <select value={pose} onChange={(e) => setPose(e.target.value)} disabled={busy}
                    style={{ width: '100%', marginTop: 4, padding: 9, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }}>
                    <option value="">Libre (sin control)</option>
                    {poses.map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}
                  </select>
                </div>
              )}
            </div>

            {selChar && <div style={{ color: '#64748b', fontSize: '0.78rem', marginTop: 8 }}>Referencia: {selChar.description.slice(0, 90)}…</div>}

            <label style={{ color: '#94a3b8', fontSize: '0.85rem', display: 'block', marginTop: 12 }}>Escena / pose (en español; se traduce sola)</label>
            <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} disabled={busy}
              placeholder="de pie en una azotea de noche con la ciudad iluminada de fondo, plano general cinematográfico"
              style={{ width: '100%', marginTop: 4, padding: 10, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }} />

            <div style={{ marginTop: 14, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <button className="btn btn-primary" onClick={generate} disabled={busy || !prompt.trim()}>
                {busy ? '⏳ Generando…' : '🖼️ Generar imágenes'}
              </button>
              {status && <span style={{ color: '#94a3b8', fontSize: '0.9rem' }}>{status} {elapsed > 0 && `(${mmss(elapsed)})`}</span>}
            </div>
            {promptEn && <div style={{ color: '#64748b', fontSize: '0.78rem', marginTop: 8, fontStyle: 'italic' }}>Escena (EN): {promptEn}</div>}
            {error && <div style={{ color: '#f87171', marginTop: 10 }}>⚠️ {error}</div>}
          </>
        )}
      </div>

      {imgs.length > 0 && (
        <div style={{ background: '#0f221a', border: '1px solid #14532d', borderRadius: 12, padding: 20 }}>
          <h3 style={{ marginTop: 0, color: '#4ade80' }}>✅ Imágenes ({imgs.length})</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, marginTop: 12 }}>
            {imgs.map((im) => (
              <div key={im.filename} style={{ background: '#000', borderRadius: 8, overflow: 'hidden' }}>
                <img src={im.url} style={{ width: '100%', display: 'block' }} />
                <div style={{ display: 'flex' }}>
                  <button className="btn btn-secondary" style={{ flex: 1, padding: '5px', fontSize: '0.72rem', borderRadius: 0 }} onClick={() => dl(im.url, im.filename)}>⬇️</button>
                  <button className="btn btn-primary" style={{ flex: 2, padding: '5px', fontSize: '0.72rem', borderRadius: 0 }} onClick={() => openAnim(im.filename)}>🎬 Animar</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {animFor && (
        <div onClick={closeAnim} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: 16 }}>
          <div onClick={(e) => e.stopPropagation()} style={{ background: '#1e293b', borderRadius: 12, padding: 20, maxWidth: 460, width: '100%', maxHeight: '90vh', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0 }}>🎬 Animar imagen (vídeo)</h3>
              <button className="btn-link" onClick={closeAnim}>✕</button>
            </div>
            <p style={{ color: '#94a3b8', fontSize: '0.82rem', marginTop: 6 }}>
              Convierte esta imagen en un clip vertical manteniendo su apariencia. Describe el
              movimiento (en español).
            </p>
            <textarea value={animPrompt} onChange={(e) => setAnimPrompt(e.target.value)} rows={2} disabled={animBusy}
              placeholder="gira la cabeza despacio, ligera brisa moviendo la ropa, cámara lenta"
              style={{ width: '100%', padding: 10, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }} />
            <div style={{ marginTop: 12, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <button className="btn btn-primary" onClick={animate} disabled={animBusy}>
                {animBusy ? '⏳ Generando…' : '🎬 Generar vídeo'}
              </button>
              {animStatus && <span style={{ color: '#94a3b8', fontSize: '0.85rem' }}>{animStatus} {animElapsed > 0 && `(${mmss(animElapsed)})`}</span>}
            </div>
            {animBusy && <div style={{ color: '#64748b', fontSize: '0.75rem', marginTop: 6 }}>Los primeros clips tardan varios minutos.</div>}
            {animVideo && (
              <div style={{ marginTop: 14, textAlign: 'center' }}>
                <video src={animVideo} controls autoPlay loop style={{ maxWidth: 300, width: '100%', borderRadius: 10, background: '#000' }} />
                <div style={{ marginTop: 10 }}>
                  <button className="btn btn-primary" onClick={() => { const a = document.createElement('a'); a.href = animVideo!; a.download = 'ltx_i2v.mp4'; document.body.appendChild(a); a.click(); a.remove(); }}>⬇️ Descargar MP4</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
