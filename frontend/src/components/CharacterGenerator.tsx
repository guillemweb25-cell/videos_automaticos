import React, { useEffect, useRef, useState } from 'react';
import { api, type CharacterItem } from '../api';

const STYLES = [
  { key: 'anime', label: '🎌 Anime / Manga' },
  { key: 'realista', label: '📷 Realista' },
  { key: 'cartoon', label: '🧸 Cartoon 3D' },
];

export default function CharacterGenerator() {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [style, setStyle] = useState('anime');
  const [numPoses, setNumPoses] = useState(4);

  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [resultImgs, setResultImgs] = useState<{ filename: string; url: string }[]>([]);
  const [saved, setSaved] = useState(false);

  const [chars, setChars] = useState<CharacterItem[]>([]);
  const [openImgs, setOpenImgs] = useState<Record<string, { filename: string; url: string }[]>>({});
  const [loadingChar, setLoadingChar] = useState<string | null>(null);

  const pollRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);
  const metaRef = useRef<{ description_en: string; seed: number } | null>(null);

  const stop = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  };
  const loadChars = async () => { try { setChars(await api.charList()); } catch { /* */ } };
  useEffect(() => { loadChars(); return () => stop(); }, []);

  const generate = async () => {
    if (!description.trim() || busy) return;
    setError(''); setStatus('Enviando…'); setBusy(true); setElapsed(0); setSaved(false);
    resultImgs.forEach((i) => URL.revokeObjectURL(i.url)); setResultImgs([]);
    try {
      const r = await api.charGenerate({ description: description.trim(), style, num_poses: numPoses });
      metaRef.current = { description_en: r.description_en, seed: r.seed };
      setStatus(`Generando ${r.expected} imágenes… (base + poses)`);
      timerRef.current = window.setInterval(() => setElapsed((e) => e + 1), 1000);
      pollRef.current = window.setInterval(() => poll(r.prompt_id), 4000);
    } catch (e: any) { setError(e.message); setBusy(false); setStatus(''); }
  };

  const poll = async (pid: string) => {
    try {
      const s = await api.charStatus(pid);
      if (s.status === 'done' && s.images?.length) {
        stop(); setStatus('Cargando imágenes…');
        const imgs = await Promise.all(s.images.map(async (f) => ({ filename: f, url: await api.charImageObjectUrl(f) })));
        setResultImgs(imgs); setStatus(''); setBusy(false);
      } else if (s.status === 'error') {
        stop(); setError('Error en la generación'); setBusy(false); setStatus('');
      }
    } catch { /* reintenta */ }
  };

  const saveCharacter = async () => {
    if (!resultImgs.length) return;
    try {
      await api.charSave({
        name: name.trim() || 'Personaje', description: description.trim(),
        description_en: metaRef.current?.description_en || '', style,
        seed: metaRef.current?.seed ?? null, images: resultImgs.map((i) => i.filename),
      });
      setSaved(true); loadChars();
    } catch (e: any) { alert(e.message); }
  };

  const dl = (url: string, filename: string) => {
    const a = document.createElement('a'); a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
  };
  const viewChar = async (c: CharacterItem) => {
    if (openImgs[c.id]) { setOpenImgs((p) => { const n = { ...p }; delete n[c.id]; return n; }); return; }
    setLoadingChar(c.id);
    try {
      const imgs = await Promise.all(c.images.map(async (f) => ({ filename: f, url: await api.charImageObjectUrl(f) })));
      setOpenImgs((p) => ({ ...p, [c.id]: imgs }));
    } catch { alert('No se pudieron cargar las imágenes (¿borradas del disco?).'); }
    finally { setLoadingChar(null); }
  };
  const delChar = async (c: CharacterItem) => {
    if (!confirm(`¿Borrar "${c.name}" del listado? (los ficheros en disco no se borran)`)) return;
    try { await api.charDelete(c.id); loadChars(); } catch { alert('Error'); }
  };
  const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <div style={{ background: '#1e293b', borderRadius: 12, padding: 20, marginBottom: 20 }}>
        <h2 style={{ marginTop: 0 }}>🧑‍🎨 Generador de personajes consistentes</h2>
        <p style={{ color: '#94a3b8', marginTop: 4 }}>
          Crea un personaje y su set de imágenes (misma cara en varias poses, vía IPAdapter-face).
          Sirve para reutilizarlo o como dataset para entrenar una LoRA.
        </p>

        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 8 }}>
          <div style={{ flex: '1 1 200px' }}>
            <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Nombre</label>
            <input value={name} onChange={(e) => setName(e.target.value)} disabled={busy} placeholder="Aiko, la guerrera"
              style={{ width: '100%', marginTop: 4, padding: 9, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }} />
          </div>
          <div style={{ flex: '1 1 160px' }}>
            <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Estilo</label>
            <select value={style} onChange={(e) => setStyle(e.target.value)} disabled={busy}
              style={{ width: '100%', marginTop: 4, padding: 9, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }}>
              {STYLES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
            </select>
          </div>
          <div style={{ flex: '0 1 140px' }}>
            <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Poses</label>
            <select value={numPoses} onChange={(e) => setNumPoses(+e.target.value)} disabled={busy}
              style={{ width: '100%', marginTop: 4, padding: 9, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }}>
              {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n} + base</option>)}
            </select>
          </div>
        </div>

        <label style={{ color: '#94a3b8', fontSize: '0.85rem', display: 'block', marginTop: 12 }}>Descripción (en español; se traduce sola)</label>
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} disabled={busy}
          placeholder="una guerrera joven de pelo azul y ojos verdes, armadura ligera, expresión decidida"
          style={{ width: '100%', marginTop: 4, padding: 10, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }} />

        <div style={{ marginTop: 14, display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <button className="btn btn-primary" onClick={generate} disabled={busy || !description.trim()}>
            {busy ? '⏳ Generando…' : '✨ Generar personaje'}
          </button>
          {status && <span style={{ color: '#94a3b8', fontSize: '0.9rem' }}>{status} {elapsed > 0 && `(${mmss(elapsed)})`}</span>}
        </div>
        {error && <div style={{ color: '#f87171', marginTop: 10 }}>⚠️ {error}</div>}
      </div>

      {resultImgs.length > 0 && (
        <div style={{ background: '#0f221a', border: '1px solid #14532d', borderRadius: 12, padding: 20, marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
            <h3 style={{ margin: 0, color: '#4ade80' }}>✅ Personaje generado ({resultImgs.length} imágenes)</h3>
            <button className="btn btn-primary" onClick={saveCharacter} disabled={saved}>
              {saved ? '✅ Guardado' : '💾 Guardar personaje'}
            </button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 10, marginTop: 14 }}>
            {resultImgs.map((im, i) => (
              <div key={im.filename} style={{ background: '#000', borderRadius: 8, overflow: 'hidden' }}>
                <img src={im.url} style={{ width: '100%', display: 'block' }} />
                <button className="btn btn-secondary" style={{ width: '100%', padding: '4px', fontSize: '0.72rem', borderRadius: 0 }}
                  onClick={() => dl(im.url, im.filename)}>{i === 0 ? '⬇️ base' : `⬇️ pose ${i}`}</button>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ background: '#1e293b', borderRadius: 12, padding: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0 }}>👥 Mis personajes ({chars.length})</h3>
          <button className="btn-link" onClick={loadChars}>Refrescar</button>
        </div>
        {chars.length === 0 ? (
          <p style={{ color: '#64748b', marginTop: 12 }}>Aún no has guardado personajes.</p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12 }}>
            {chars.map((c) => (
              <div key={c.id} style={{ background: '#0f172a', borderRadius: 8, padding: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
                  <div>
                    <div style={{ color: '#e2e8f0', fontWeight: 600 }}>{c.name} <span style={{ color: '#64748b', fontWeight: 400, fontSize: '0.8rem' }}>· {c.style} · {c.images.length} img</span></div>
                    <div style={{ color: '#64748b', fontSize: '0.78rem', maxWidth: 560, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.description}</div>
                  </div>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button className="btn btn-secondary" style={{ padding: '5px 10px', fontSize: '0.78rem' }} onClick={() => viewChar(c)} disabled={loadingChar === c.id}>
                      {loadingChar === c.id ? '⏳' : openImgs[c.id] ? 'Ocultar' : '🖼️ Ver'}
                    </button>
                    <button className="btn btn-secondary" style={{ padding: '5px 10px', fontSize: '0.78rem' }} onClick={() => delChar(c)}>🗑️</button>
                  </div>
                </div>
                {openImgs[c.id] && (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 8, marginTop: 10 }}>
                    {openImgs[c.id].map((im, i) => (
                      <div key={im.filename} style={{ background: '#000', borderRadius: 6, overflow: 'hidden' }}>
                        <img src={im.url} style={{ width: '100%', display: 'block' }} />
                        <button className="btn btn-secondary" style={{ width: '100%', padding: '3px', fontSize: '0.68rem', borderRadius: 0 }} onClick={() => dl(im.url, im.filename)}>⬇️ {i === 0 ? 'base' : i}</button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
