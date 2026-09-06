import React, { useEffect, useRef, useState } from 'react';
import { api, type CharacterItem } from '../api';
import Lightbox from './Lightbox';
import SceneHistory from './SceneHistory';

/** Genera un personaje en la MISMA pose que una foto de referencia:
 *  subes la foto -> se extrae su esqueleto (OpenPose) -> eliges personaje -> generas. */
export default function CharacterFromRef() {
  const [chars, setChars] = useState<CharacterItem[]>([]);
  const [charId, setCharId] = useState('');
  const [prompt, setPrompt] = useState('');
  const [provider, setProvider] = useState('openai');
  const [num, setNum] = useState(1);
  const [phone, setPhone] = useState(false);
  const [hq, setHq] = useState(false);

  const [refUrl, setRefUrl] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [skeleton, setSkeleton] = useState<string | null>(null);
  const [skelUrl, setSkelUrl] = useState<string | null>(null);
  const [extracting, setExtracting] = useState(false);

  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [imgs, setImgs] = useState<{ filename: string; url: string }[]>([]);
  const [lightbox, setLightbox] = useState<{ urls: string[]; i: number } | null>(null);
  const [histSignal, setHistSignal] = useState(0);

  const pollRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);
  const stop = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  };
  useEffect(() => {
    (async () => { try { const c = await api.charList(); setChars(c); if (c[0]) setCharId(c[0].id); } catch { /* */ } })();
    return () => stop();
  }, []);

  const onFile = (f: File | null) => {
    if (!f) return;
    if (refUrl) URL.revokeObjectURL(refUrl);
    setFile(f); setRefUrl(URL.createObjectURL(f));
    setSkeleton(null); if (skelUrl) { URL.revokeObjectURL(skelUrl); setSkelUrl(null); }
    setError('');
  };

  const extract = async () => {
    if (!file || extracting) return;
    setExtracting(true); setError(''); setStatus('Extrayendo pose y describiendo…');
    try {
      const r = await api.charPoseFromImage(file, provider);
      setSkeleton(r.skeleton);
      const url = await api.charImageObjectUrl(r.preview);
      if (skelUrl) URL.revokeObjectURL(skelUrl);
      setSkelUrl(url);
      if (r.suggested_prompt) setPrompt(r.suggested_prompt);   // auto-rellena el prompt desde la imagen
      setStatus('');
    } catch (e: any) { setError(e.message || 'Error al extraer la pose'); setStatus(''); }
    finally { setExtracting(false); }
  };

  const generate = async () => {
    if (!charId || !skeleton || busy) return;
    setError(''); setStatus('Enviando…'); setBusy(true); setElapsed(0);
    imgs.forEach((i) => URL.revokeObjectURL(i.url)); setImgs([]);
    try {
      const r = await api.charScene({ character_id: charId, prompt: prompt.trim() || 'retrato', num_images: num, width: 832, height: 1216, pose_image: skeleton, phone, hq, provider });
      setStatus(`Generando ${r.expected} imagen(es)…`);
      timerRef.current = window.setInterval(() => setElapsed((e) => e + 1), 1000);
      pollRef.current = window.setInterval(() => poll(r.prompt_id!), 4000);
    } catch (e: any) { setError(e.message); setBusy(false); setStatus(''); }
  };

  const poll = async (pid: string) => {
    try {
      const s = await api.charStatus(pid);
      if (s.status === 'done' && s.images?.length) {
        stop(); setStatus('Cargando…');
        const loaded = await Promise.all(s.images.map(async (f) => ({ filename: f, url: await api.charImageObjectUrl(f) })));
        setImgs(loaded); setStatus(''); setBusy(false);
        setHistSignal((n) => n + 1);   // refresca el historial
      } else if (s.status === 'error') { stop(); setError('Error en la generación'); setBusy(false); setStatus(''); }
    } catch { /* reintenta */ }
  };

  const dl = (url: string, filename: string) => {
    const a = document.createElement('a'); a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
  };
  const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
  const inp = { width: '100%', marginTop: 4, padding: 9, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' } as React.CSSProperties;

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <div style={{ background: '#1e293b', borderRadius: 12, padding: 20, marginBottom: 20 }}>
        <h2 style={{ marginTop: 0 }}>🎯 Generar desde una foto de referencia</h2>
        <p style={{ color: '#94a3b8', marginTop: 4 }}>
          Sube una foto, se extrae su <b>pose</b> (esqueleto) y se genera tu personaje en esa misma pose.
        </p>

        <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginTop: 8 }}>
          <div style={{ flex: '1 1 240px' }}>
            <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>1) Foto de referencia</label>
            <input type="file" accept="image/*" onChange={(e) => onFile(e.target.files?.[0] || null)} disabled={busy || extracting}
              style={{ ...inp, padding: 7 }} />
            {refUrl && <img src={refUrl} onClick={() => setLightbox({ urls: [refUrl], i: 0 })} style={{ width: '100%', marginTop: 8, borderRadius: 8, cursor: 'zoom-in' }} />}
            <button className="btn btn-secondary" style={{ marginTop: 8, width: '100%' }} onClick={extract} disabled={!file || extracting || busy}>
              {extracting ? '⏳ Extrayendo…' : '🦴 Extraer pose'}
            </button>
          </div>
          <div style={{ flex: '1 1 240px' }}>
            <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Pose extraída (esqueleto)</label>
            <div style={{ marginTop: 4, minHeight: 120, border: '1px dashed #334155', borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#000' }}>
              {skelUrl ? <img src={skelUrl} onClick={() => setLightbox({ urls: [skelUrl], i: 0 })} style={{ width: '100%', borderRadius: 8, cursor: 'zoom-in' }} />
                : <span style={{ color: '#64748b', fontSize: '0.85rem', padding: 20 }}>Aún sin pose</span>}
            </div>
          </div>
        </div>

        <div style={{ borderTop: '1px solid #334155', marginTop: 16, paddingTop: 14 }}>
          <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>2) Personaje y escena</label>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 6 }}>
            <div style={{ flex: '1 1 220px' }}>
              <select value={charId} onChange={(e) => setCharId(e.target.value)} disabled={busy} style={inp}>
                {chars.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.style})</option>)}
              </select>
            </div>
            <div style={{ flex: '0 1 110px' }}>
              <select value={num} onChange={(e) => setNum(+e.target.value)} disabled={busy} style={inp}>
                {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n} img</option>)}
              </select>
            </div>
            <div style={{ flex: '0 1 130px' }}>
              <select value={provider} onChange={(e) => setProvider(e.target.value)} disabled={busy} style={inp}>
                <option value="openai">🟢 OpenAI</option>
                <option value="grok">⚫ Grok</option>
              </select>
            </div>
          </div>
          <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={2} disabled={busy}
            placeholder="ropa / escena (ej: vestido rosa en un probador de tienda)"
            style={{ ...inp, marginTop: 10 }} />
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, color: '#cbd5e1', fontSize: '0.85rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={phone} onChange={(e) => setPhone(e.target.checked)} disabled={busy} /> 📱 Foto de móvil
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6, color: '#cbd5e1', fontSize: '0.85rem', cursor: 'pointer' }}>
            <input type="checkbox" checked={hq} onChange={(e) => setHq(e.target.checked)} disabled={busy} /> ✨ Alta calidad (cara + upscale)
          </label>

          <div style={{ marginTop: 14, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
            <button className="btn btn-primary" onClick={generate} disabled={busy || !charId || !skeleton}>
              {busy ? '⏳ Generando…' : '🎨 Generar en esta pose'}
            </button>
            {!skeleton && <span style={{ color: '#fbbf24', fontSize: '0.82rem' }}>Extrae una pose primero</span>}
            {status && <span style={{ color: '#94a3b8', fontSize: '0.9rem' }}>{status} {elapsed > 0 && `(${mmss(elapsed)})`}</span>}
          </div>
          {error && <div style={{ color: '#f87171', marginTop: 10 }}>⚠️ {error}</div>}
        </div>
      </div>

      {imgs.length > 0 && (
        <div style={{ background: '#0f221a', border: '1px solid #14532d', borderRadius: 12, padding: 20 }}>
          <h3 style={{ marginTop: 0, color: '#4ade80' }}>✅ Resultado ({imgs.length})</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, marginTop: 12 }}>
            {imgs.map((im) => (
              <div key={im.filename} style={{ background: '#000', borderRadius: 8, overflow: 'hidden' }}>
                <img src={im.url} onClick={() => setLightbox({ urls: imgs.map((x) => x.url), i: imgs.indexOf(im) })} style={{ width: '100%', display: 'block', cursor: 'zoom-in' }} />
                <button className="btn btn-secondary" style={{ width: '100%', padding: '5px', fontSize: '0.72rem', borderRadius: 0 }} onClick={() => dl(im.url, im.filename)}>⬇️</button>
              </div>
            ))}
          </div>
        </div>
      )}

      <SceneHistory reloadSignal={histSignal} />

      {lightbox && <Lightbox urls={lightbox.urls} index={lightbox.i} onClose={() => setLightbox(null)} />}
    </div>
  );
}
