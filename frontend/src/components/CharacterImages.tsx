import React, { useEffect, useRef, useState } from 'react';
import { api, type CharacterItem, type SceneHistoryItem } from '../api';
import Lightbox from './Lightbox';

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
  const [phone, setPhone] = useState(false);
  const [hq, setHq] = useState(false);
  const [lightbox, setLightbox] = useState<{ urls: string[]; i: number } | null>(null);
  const [preview, setPreview] = useState<{ pos: string; neg: string } | null>(null);
  const [previewing, setPreviewing] = useState(false);

  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [promptEn, setPromptEn] = useState('');
  const [imgs, setImgs] = useState<{ filename: string; url: string }[]>([]);

  // Historial de fotos generadas
  const [history, setHistory] = useState<SceneHistoryItem[]>([]);
  const [openHist, setOpenHist] = useState<Record<string, { filename: string; url: string }[]>>({});
  const [loadingHist, setLoadingHist] = useState<string | null>(null);

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
  const loadHistory = async () => {
    try { setHistory(await api.charScenes()); } catch { /* */ }
  };
  useEffect(() => {
    (async () => {
      try { const c = await api.charList(); setChars(c); if (c[0]) setCharId(c[0].id); } catch { /* */ }
    })();
    loadHistory();
    return () => stop();
  }, []);

  const selChar = chars.find((c) => c.id === charId);

  // Carga las poses del género del personaje seleccionado
  useEffect(() => {
    (async () => {
      try { setPoses(await api.charPoses(selChar?.gender || 'mujer')); setPose(''); } catch { /* */ }
    })();
  }, [charId, selChar?.gender]);

  // Invalida el preview si cambian los ajustes (para no enviar prompts obsoletos)
  useEffect(() => { setPreview(null); }, [charId, prompt, pose, phone, hq, num, ratio]);

  const doPreview = async () => {
    if (!charId || !prompt.trim() || previewing || busy) return;
    setPreviewing(true); setError('');
    const r0 = RATIOS[ratio];
    try {
      const r = await api.charScene({ character_id: charId, prompt: prompt.trim(), num_images: num, width: r0.w, height: r0.h, pose: pose || null, phone, hq, preview: true });
      setPreview({ pos: r.positive || '', neg: r.negative || '' });
    } catch (e: any) { setError(e.message); }
    finally { setPreviewing(false); }
  };

  const generate = async () => {
    if (!charId || !prompt.trim() || busy) return;
    setError(''); setStatus('Enviando…'); setBusy(true); setElapsed(0);
    imgs.forEach((i) => URL.revokeObjectURL(i.url)); setImgs([]);
    const r0 = RATIOS[ratio];
    try {
      const r = await api.charScene({ character_id: charId, prompt: prompt.trim(), num_images: num, width: r0.w, height: r0.h, pose: pose || null, phone, hq, positive: preview?.pos, negative: preview?.neg });
      setPromptEn(r.prompt_en || '');
      setStatus(`Generando ${r.expected} imagen(es)…`);
      loadHistory();   // muestra la entrada pendiente en el historial
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
        loadHistory();   // el hilo de fondo ya habrá guardado las imágenes
      } else if (s.status === 'error') { stop(); setError('Error en la generación'); setBusy(false); setStatus(''); }
    } catch { /* reintenta */ }
  };

  const viewHist = async (e: SceneHistoryItem) => {
    if (openHist[e.id]) { setOpenHist((p) => { const n = { ...p }; Object.values(n[e.id] || []).forEach((i) => { try { URL.revokeObjectURL(i.url); } catch { /* */ } }); delete n[e.id]; return n; }); return; }
    if (!e.images.length) return;
    setLoadingHist(e.id);
    try {
      const loaded = await Promise.all(e.images.map(async (f) => ({ filename: f, url: await api.charImageObjectUrl(f) })));
      setOpenHist((p) => ({ ...p, [e.id]: loaded }));
    } catch { alert('No se pudieron cargar (¿borradas del disco?).'); }
    finally { setLoadingHist(null); }
  };
  const delHist = async (e: SceneHistoryItem) => {
    if (!confirm('¿Borrar esta entrada del historial? (las imágenes en disco no se borran)')) return;
    try { await api.charSceneDelete(e.id); setOpenHist((p) => { const n = { ...p }; delete n[e.id]; return n; }); loadHistory(); } catch { alert('Error'); }
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

            <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, color: '#cbd5e1', fontSize: '0.85rem', cursor: 'pointer' }}>
              <input type="checkbox" checked={phone} onChange={(e) => setPhone(e.target.checked)} disabled={busy} />
              📱 Foto de móvil (look amateur/casual, menos "IA")
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6, color: '#cbd5e1', fontSize: '0.85rem', cursor: 'pointer' }}>
              <input type="checkbox" checked={hq} onChange={(e) => setHq(e.target.checked)} disabled={busy} />
              ✨ Alta calidad (mejora la cara + upscale 2x, más lento)
            </label>

            <div style={{ marginTop: 14, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <button className="btn btn-secondary" onClick={doPreview} disabled={previewing || busy || !prompt.trim()} title="Ver y editar el prompt positivo/negativo antes de generar">
                {previewing ? '⏳…' : '👁️ Ver/editar prompt'}
              </button>
              <button className="btn btn-primary" onClick={generate} disabled={busy || !prompt.trim()}>
                {busy ? '⏳ Generando…' : (preview ? '🖼️ Generar con estos prompts' : '🖼️ Generar imágenes')}
              </button>
              {status && <span style={{ color: '#94a3b8', fontSize: '0.9rem' }}>{status} {elapsed > 0 && `(${mmss(elapsed)})`}</span>}
            </div>
            {preview && (
              <div style={{ marginTop: 12, padding: 12, background: '#0b1220', border: '1px solid #334155', borderRadius: 8 }}>
                <label style={{ color: '#4ade80', fontSize: '0.8rem', fontWeight: 600 }}>Prompt POSITIVO (editable)</label>
                <textarea value={preview.pos} onChange={(e) => setPreview((p) => (p ? { ...p, pos: e.target.value } : p))} rows={4} disabled={busy}
                  style={{ width: '100%', marginTop: 4, padding: 9, borderRadius: 6, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0', fontSize: '0.8rem', fontFamily: 'monospace' }} />
                <label style={{ color: '#f87171', fontSize: '0.8rem', fontWeight: 600, display: 'block', marginTop: 8 }}>Prompt NEGATIVO (editable · nsfw/nude se mantienen siempre)</label>
                <textarea value={preview.neg} onChange={(e) => setPreview((p) => (p ? { ...p, neg: e.target.value } : p))} rows={3} disabled={busy}
                  style={{ width: '100%', marginTop: 4, padding: 9, borderRadius: 6, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0', fontSize: '0.8rem', fontFamily: 'monospace' }} />
                <div style={{ color: '#64748b', fontSize: '0.72rem', marginTop: 6 }}>Edita lo que quieras y pulsa "Generar con estos prompts". (Cambiar la escena o los ajustes de arriba recalcula el prompt.)</div>
              </div>
            )}
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
                <img src={im.url} onClick={() => setLightbox({ urls: imgs.map((x) => x.url), i: imgs.indexOf(im) })} style={{ width: '100%', display: 'block', cursor: 'zoom-in' }} />
                <div style={{ display: 'flex' }}>
                  <button className="btn btn-secondary" style={{ flex: 1, padding: '5px', fontSize: '0.72rem', borderRadius: 0 }} onClick={() => dl(im.url, im.filename)}>⬇️</button>
                  <button className="btn btn-primary" style={{ flex: 2, padding: '5px', fontSize: '0.72rem', borderRadius: 0 }} onClick={() => openAnim(im.filename)}>🎬 Animar</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ background: '#1e293b', borderRadius: 12, padding: 20, marginTop: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0 }}>🕘 Historial de fotos ({history.length})</h3>
          <button className="btn-link" onClick={loadHistory}>Refrescar</button>
        </div>
        {history.length === 0 ? (
          <p style={{ color: '#64748b', marginTop: 12 }}>Aún no has generado fotos.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12 }}>
            {history.map((e) => (
              <div key={e.id} style={{ background: '#0f172a', borderRadius: 8, padding: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ color: '#e2e8f0', fontWeight: 600 }}>{e.character_name || 'Personaje'} <span style={{ color: '#64748b', fontWeight: 400, fontSize: '0.8rem' }}>· {new Date(e.created_at * 1000).toLocaleString()} · {e.done ? `${e.images.length} img` : '⏳ generando…'}</span></div>
                    <div style={{ color: '#64748b', fontSize: '0.78rem', maxWidth: 560, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.prompt}</div>
                  </div>
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
                    <button className="btn btn-secondary" style={{ padding: '5px 10px', fontSize: '0.78rem' }} onClick={() => viewHist(e)} disabled={!e.done || !e.images.length || loadingHist === e.id}>
                      {loadingHist === e.id ? '⏳' : openHist[e.id] ? 'Ocultar' : '🖼️ Ver'}
                    </button>
                    <button className="btn btn-secondary" style={{ padding: '5px 10px', fontSize: '0.78rem' }} onClick={() => delHist(e)}>🗑️</button>
                  </div>
                </div>
                {openHist[e.id] && (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 8, marginTop: 10 }}>
                    {openHist[e.id].map((im) => (
                      <div key={im.filename} style={{ background: '#000', borderRadius: 6, overflow: 'hidden' }}>
                        <img src={im.url} onClick={() => setLightbox({ urls: openHist[e.id].map((x) => x.url), i: openHist[e.id].indexOf(im) })} style={{ width: '100%', display: 'block', cursor: 'zoom-in' }} />
                        <div style={{ display: 'flex' }}>
                          <button className="btn btn-secondary" style={{ flex: 1, padding: '4px', fontSize: '0.68rem', borderRadius: 0 }} onClick={() => dl(im.url, im.filename)}>⬇️</button>
                          <button className="btn btn-primary" style={{ flex: 2, padding: '4px', fontSize: '0.68rem', borderRadius: 0 }} onClick={() => openAnim(im.filename)}>🎬 Animar</button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

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

      {lightbox && <Lightbox urls={lightbox.urls} index={lightbox.i} onClose={() => setLightbox(null)} />}
    </div>
  );
}
