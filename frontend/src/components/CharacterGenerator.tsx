import React, { useEffect, useRef, useState } from 'react';
import { api, type CharacterItem, type LoraJob } from '../api';
import Lightbox from './Lightbox';

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
  const [neutralBg, setNeutralBg] = useState(true);
  const [gender, setGender] = useState('mujer');
  const [poseControl, setPoseControl] = useState(false);
  const [provider, setProvider] = useState('openai');

  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [resultImgs, setResultImgs] = useState<{ filename: string; url: string }[]>([]);
  const [saved, setSaved] = useState(false);

  const [chars, setChars] = useState<CharacterItem[]>([]);
  const [openImgs, setOpenImgs] = useState<Record<string, { filename: string; url: string }[]>>({});
  const [loadingChar, setLoadingChar] = useState<string | null>(null);
  const [regenId, setRegenId] = useState<string | null>(null);
  const [genderSel, setGenderSel] = useState<Record<string, string>>({});
  const [loraFiles, setLoraFiles] = useState<string[]>([]);
  const [loraPanel, setLoraPanel] = useState<string | null>(null);
  const [loraDraft, setLoraDraft] = useState<Record<string, { filename: string; trigger: string; strength: number }>>({});
  const [loraSaving, setLoraSaving] = useState<string | null>(null);
  const [trainJobs, setTrainJobs] = useState<Record<string, LoraJob>>({});
  const trainJobsRef = useRef<Record<string, LoraJob>>({});
  const [lightbox, setLightbox] = useState<{ urls: string[]; i: number } | null>(null);

  const pollRef = useRef<number | null>(null);
  const timerRef = useRef<number | null>(null);
  const metaRef = useRef<{ description_en: string; seed: number; entry_id?: string } | null>(null);

  const stop = () => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  };
  const loadChars = async () => {
    try { setChars(await api.charList()); } catch { /* */ }
    setOpenImgs((prev) => { Object.values(prev).flat().forEach((i) => { try { URL.revokeObjectURL(i.url); } catch { /* */ } }); return {}; });
  };
  useEffect(() => { loadChars(); return () => stop(); }, []);
  useEffect(() => { api.getAvailableLoraFiles().then(setLoraFiles).catch(() => { /* */ }); }, []);

  const toggleLoraPanel = (c: CharacterItem) => {
    if (loraPanel === c.id) { setLoraPanel(null); return; }
    setLoraDraft((p) => ({ ...p, [c.id]: {
      filename: c.lora_filename || '', trigger: c.lora_trigger || '', strength: c.lora_strength ?? 0.9,
    } }));
    setLoraPanel(c.id);
  };
  const saveLora = async (c: CharacterItem) => {
    const d = loraDraft[c.id]; if (!d) return;
    setLoraSaving(c.id);
    try {
      await api.charSetLora(c.id, { lora_filename: d.filename || null, lora_trigger: d.trigger, lora_strength: d.strength });
      setLoraPanel(null); loadChars();
    } catch (e: any) { alert(e.message || 'Error al asignar LoRA'); }
    finally { setLoraSaving(null); }
  };

  // ---- Entrenamiento de LoRA por personaje ----
  useEffect(() => { trainJobsRef.current = trainJobs; }, [trainJobs]);
  const ACTIVE = ['queued', 'dataset', 'training'];
  const fetchTrain = async (ids: string[]) => {
    const entries = await Promise.all(ids.map(async (id) => [id, await api.charTrainLoraStatus(id)] as const));
    setTrainJobs((p) => { const n = { ...p }; for (const [id, j] of entries) n[id] = j; return n; });
    if (entries.some(([, j]) => j.state === 'done')) loadChars();  // refresca badge 🎭
  };
  // Carga inicial de estados cuando llegan los personajes
  useEffect(() => { if (chars.length) fetchTrain(chars.map((c) => c.id)); /* eslint-disable-next-line */ }, [chars.length]);
  // Poller estable: refresca solo los que tengan job activo
  useEffect(() => {
    const iv = window.setInterval(() => {
      const active = chars.filter((c) => ACTIVE.includes(trainJobsRef.current[c.id]?.state || '')).map((c) => c.id);
      if (active.length) fetchTrain(active);
    }, 6000);
    return () => clearInterval(iv);
    /* eslint-disable-next-line */
  }, [chars]);
  const startTrain = async (c: CharacterItem) => {
    if (!confirm(`¿Entrenar una LoRA para "${c.name}"?\n\nGenera ~20 imágenes y entrena (~1–1,5 h). Ocupará la GPU y ComfyUI se reiniciará solo al terminar.`)) return;
    try {
      const r = await api.charTrainLora(c.id);
      setTrainJobs((p) => ({ ...p, [c.id]: { state: 'queued', message: 'En cola', output_name: r.output_name, trigger: r.trigger, step: 0, total: r.steps } }));
    } catch (e: any) { alert(e.message || 'Error al iniciar el entrenamiento'); }
  };

  const generate = async () => {
    if (!description.trim() || busy) return;
    setError(''); setStatus('Enviando…'); setBusy(true); setElapsed(0); setSaved(false);
    resultImgs.forEach((i) => URL.revokeObjectURL(i.url)); setResultImgs([]);
    try {
      const r = await api.charGenerate({ description: description.trim(), style, num_poses: numPoses, neutral_bg: neutralBg, gender, pose_control: poseControl, name: name.trim(), provider });
      metaRef.current = { description_en: r.description_en, seed: r.seed, entry_id: r.entry_id };
      setStatus(`Generando ${r.expected} imágenes… (se guarda solo al terminar)`);
      loadChars();   // el personaje ya existe (auto-guardado); aparece en la lista
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
        description_en: metaRef.current?.description_en || '', style, gender,
        seed: metaRef.current?.seed ?? null, images: resultImgs.map((i) => i.filename),
        entry_id: metaRef.current?.entry_id,
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
  const regenChar = async (c: CharacterItem) => {
    if (regenId) return;
    const g = genderSel[c.id] || c.gender || 'mujer';
    if (!confirm(`Regenerar "${c.name}" como ${g === 'hombre' ? 'HOMBRE' : 'MUJER'} con las poses nuevas? Reemplazará sus imágenes.`)) return;
    setRegenId(c.id);
    try {
      const r = await api.charRegen(c.id, g);
      // sondear hasta que termine (7 imágenes con ControlNet pueden tardar ~12 min)
      let images: string[] | null = null;
      for (let i = 0; i < 260; i++) {
        await new Promise((res) => setTimeout(res, 4000));
        let s;
        try { s = await api.charStatus(r.prompt_id); } catch { continue; }
        if (s.status === 'done' && s.images?.length) { images = s.images; break; }
        if (s.status === 'error') throw new Error('Error en la generación');
      }
      if (!images) throw new Error('Tiempo de espera agotado (sigue generándose; pulsa Refrescar en unos minutos)');
      await api.charUpdateImages(c.id, images);
      // limpiar caché de imágenes abiertas de ese personaje
      setOpenImgs((prev) => { const n = { ...prev }; delete n[c.id]; return n; });
      loadChars();
    } catch (e: any) { alert(e.message || 'Error al regenerar'); }
    finally { setRegenId(null); }
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
          <div style={{ flex: '1 1 150px' }}>
            <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Estilo</label>
            <select value={style} onChange={(e) => setStyle(e.target.value)} disabled={busy}
              style={{ width: '100%', marginTop: 4, padding: 9, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }}>
              {STYLES.map((s) => <option key={s.key} value={s.key}>{s.label}</option>)}
            </select>
          </div>
          <div style={{ flex: '0 1 130px' }}>
            <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Género</label>
            <select value={gender} onChange={(e) => setGender(e.target.value)} disabled={busy}
              style={{ width: '100%', marginTop: 4, padding: 9, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }}>
              <option value="mujer">👩 Mujer</option>
              <option value="hombre">👨 Hombre</option>
            </select>
          </div>
          <div style={{ flex: '0 1 140px' }}>
            <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Poses</label>
            <select value={numPoses} onChange={(e) => setNumPoses(+e.target.value)} disabled={busy}
              style={{ width: '100%', marginTop: 4, padding: 9, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }}>
              {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n} + base</option>)}
            </select>
          </div>
          <div style={{ flex: '0 1 130px' }}>
            <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Traductor</label>
            <select value={provider} onChange={(e) => setProvider(e.target.value)} disabled={busy}
              style={{ width: '100%', marginTop: 4, padding: 9, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }}>
              <option value="openai">🟢 OpenAI</option>
              <option value="grok">⚫ Grok</option>
            </select>
          </div>
        </div>

        <label style={{ color: '#94a3b8', fontSize: '0.85rem', display: 'block', marginTop: 12 }}>Descripción (en español; se traduce sola)</label>
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} disabled={busy}
          placeholder="una guerrera joven de pelo azul y ojos verdes, armadura ligera, expresión decidida"
          style={{ width: '100%', marginTop: 4, padding: 10, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }} />

        <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 10, color: '#cbd5e1', fontSize: '0.85rem', cursor: 'pointer' }}>
          <input type="checkbox" checked={neutralBg} onChange={(e) => setNeutralBg(e.target.checked)} disabled={busy} />
          Fondo neutro (blanco/simple) — recomendado para dataset de LoRA
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 6, color: '#cbd5e1', fontSize: '0.85rem', cursor: 'pointer' }}>
          <input type="checkbox" checked={poseControl} onChange={(e) => setPoseControl(e.target.checked)} disabled={busy} />
          Poses controladas (ControlNet OpenPose, {gender}) — mismas poses exactas
        </label>

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
                <img src={im.url} onClick={() => setLightbox({ urls: resultImgs.map((x) => x.url), i })} style={{ width: '100%', display: 'block', cursor: 'zoom-in' }} />
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
                  <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
                    <button className="btn btn-secondary" style={{ padding: '5px 10px', fontSize: '0.78rem' }} onClick={() => viewChar(c)} disabled={loadingChar === c.id}>
                      {loadingChar === c.id ? '⏳' : openImgs[c.id] ? 'Ocultar' : '🖼️ Ver'}
                    </button>
                    <select value={genderSel[c.id] ?? (c.gender || 'mujer')} onChange={(e) => setGenderSel((p) => ({ ...p, [c.id]: e.target.value }))} disabled={!!regenId}
                      title="Género para las poses" style={{ padding: '5px 6px', fontSize: '0.75rem', borderRadius: 6, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }}>
                      <option value="mujer">👩 Mujer</option>
                      <option value="hombre">👨 Hombre</option>
                    </select>
                    <button className="btn btn-secondary" style={{ padding: '5px 10px', fontSize: '0.78rem' }} onClick={() => regenChar(c)} disabled={!!regenId} title="Regenerar con las poses nuevas">
                      {regenId === c.id ? '⏳ Regenerando…' : '🔄 Regenerar poses'}
                    </button>
                    <button className="btn btn-secondary" style={{ padding: '5px 10px', fontSize: '0.78rem', ...(c.lora_filename ? { borderColor: '#a855f7', color: '#d8b4fe' } : {}) }} onClick={() => toggleLoraPanel(c)} title="LoRA propia (identidad píxel-perfecta)">
                      {c.lora_filename ? '🎭 LoRA ✓' : '🎭 LoRA'}
                    </button>
                    {(() => {
                      const j = trainJobs[c.id];
                      if (j && ['queued', 'dataset', 'training'].includes(j.state)) {
                        const pct = j.total ? Math.round(((j.step || 0) / j.total) * 100) : 0;
                        const label = j.state === 'dataset' ? `📸 Dataset ${j.step || 0}/${j.total || 0}`
                          : j.state === 'training' ? `🎓 Entrenando ${pct}%`
                            : '⏳ En cola';
                        return <span title={j.message} style={{ fontSize: '0.75rem', color: '#c4b5fd', padding: '5px 8px', background: '#2e1065', borderRadius: 6, whiteSpace: 'nowrap' }}>{label}</span>;
                      }
                      const isErr = j && j.state === 'error';
                      return (
                        <button className="btn btn-secondary" style={{ padding: '5px 10px', fontSize: '0.78rem', ...(isErr ? { borderColor: '#ef4444', color: '#fca5a5' } : {}) }}
                          onClick={() => startTrain(c)} title={isErr ? j!.message : 'Genera dataset y entrena una LoRA propia (~1–1,5 h)'}>
                          {isErr ? '⚠️ Reintentar LoRA' : '🎓 Entrenar LoRA'}
                        </button>
                      );
                    })()}
                    <button className="btn btn-secondary" style={{ padding: '5px 10px', fontSize: '0.78rem' }} onClick={() => delChar(c)}>🗑️</button>
                  </div>
                </div>
                {loraPanel === c.id && (
                  <div style={{ marginTop: 10, padding: 10, background: '#1a1030', border: '1px solid #6b21a8', borderRadius: 8, display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
                    <div style={{ flex: '1 1 240px' }}>
                      <label style={{ color: '#c4b5fd', fontSize: '0.75rem' }}>Fichero LoRA</label>
                      <select value={loraDraft[c.id]?.filename || ''} onChange={(e) => setLoraDraft((p) => ({ ...p, [c.id]: { ...p[c.id], filename: e.target.value } }))}
                        style={{ width: '100%', marginTop: 4, padding: 7, borderRadius: 6, border: '1px solid #4c1d95', background: '#0f172a', color: '#e2e8f0', fontSize: '0.8rem' }}>
                        <option value="">— ninguna (usar IPAdapter) —</option>
                        {loraFiles.map((f) => <option key={f} value={f}>{f}</option>)}
                      </select>
                    </div>
                    <div style={{ flex: '1 1 160px' }}>
                      <label style={{ color: '#c4b5fd', fontSize: '0.75rem' }}>Trigger word</label>
                      <input value={loraDraft[c.id]?.trigger || ''} onChange={(e) => setLoraDraft((p) => ({ ...p, [c.id]: { ...p[c.id], trigger: e.target.value } }))}
                        placeholder="ohwx woman"
                        style={{ width: '100%', marginTop: 4, padding: 7, borderRadius: 6, border: '1px solid #4c1d95', background: '#0f172a', color: '#e2e8f0', fontSize: '0.8rem' }} />
                    </div>
                    <div style={{ flex: '0 1 90px' }}>
                      <label style={{ color: '#c4b5fd', fontSize: '0.75rem' }}>Fuerza</label>
                      <input type="number" min={0} max={1.5} step={0.05} value={loraDraft[c.id]?.strength ?? 0.9} onChange={(e) => setLoraDraft((p) => ({ ...p, [c.id]: { ...p[c.id], strength: +e.target.value } }))}
                        style={{ width: '100%', marginTop: 4, padding: 7, borderRadius: 6, border: '1px solid #4c1d95', background: '#0f172a', color: '#e2e8f0', fontSize: '0.8rem' }} />
                    </div>
                    <button className="btn btn-primary" style={{ padding: '7px 12px', fontSize: '0.78rem' }} onClick={() => saveLora(c)} disabled={loraSaving === c.id}>
                      {loraSaving === c.id ? '⏳' : '💾 Guardar LoRA'}
                    </button>
                  </div>
                )}
                {openImgs[c.id] && (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(120px, 1fr))', gap: 8, marginTop: 10 }}>
                    {openImgs[c.id].map((im, i) => (
                      <div key={im.filename} style={{ background: '#000', borderRadius: 6, overflow: 'hidden' }}>
                        <img src={im.url} onClick={() => setLightbox({ urls: openImgs[c.id].map((x) => x.url), i })} style={{ width: '100%', display: 'block', cursor: 'zoom-in' }} />
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

      {lightbox && <Lightbox urls={lightbox.urls} index={lightbox.i} onClose={() => setLightbox(null)} />}
    </div>
  );
}
