import React, { useEffect, useState } from 'react';
import { api, type Lora, type ChannelResponse } from '../api';

export function LoraManager() {
  const [loras, setLoras] = useState<Lora[]>([]);
  const [files, setFiles] = useState<string[]>([]);
  const [channels, setChannels] = useState<ChannelResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState('');

  // Catalog form (create/edit)
  const [editingId, setEditingId] = useState<number | null>(null);
  const [label, setLabel] = useState('');
  const [filename, setFilename] = useState('');
  const [trigger, setTrigger] = useState('');
  const [modelStrength, setModelStrength] = useState(1.0);
  const [clipStrength, setClipStrength] = useState(1.0);

  // Assignment
  const [assignChannelId, setAssignChannelId] = useState<number | null>(null);
  const [assignSelected, setAssignSelected] = useState<number[]>([]);

  useEffect(() => { load(); }, []);

  const load = async () => {
    setLoading(true);
    try {
      const [l, f, c] = await Promise.all([
        api.getLoras(),
        api.getAvailableLoraFiles().catch(() => [] as string[]),
        api.getChannels(),
      ]);
      setLoras(l); setFiles(f); setChannels(c);
    } catch (e: any) {
      flash(e.message || 'Error al cargar');
    } finally {
      setLoading(false);
    }
  };

  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(''), 2800); };

  const resetForm = () => {
    setEditingId(null); setLabel(''); setFilename(''); setTrigger('');
    setModelStrength(1.0); setClipStrength(1.0);
  };

  const submitForm = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!label.trim() || !filename.trim()) { flash('Falta etiqueta o fichero'); return; }
    const data = {
      label: label.trim(), filename: filename.trim(), trigger_words: trigger.trim(),
      model_strength: modelStrength, clip_strength: clipStrength,
    };
    try {
      if (editingId) { await api.updateLora(editingId, data); flash('LoRA actualizado'); }
      else { await api.createLora(data); flash('LoRA creado'); }
      resetForm();
      const l = await api.getLoras(); setLoras(l);
    } catch (e: any) { flash(e.message); }
  };

  const editLora = (l: Lora) => {
    setEditingId(l.id); setLabel(l.label); setFilename(l.filename);
    setTrigger(l.trigger_words || ''); setModelStrength(l.model_strength); setClipStrength(l.clip_strength);
  };

  const removeLora = async (id: number) => {
    if (!confirm('¿Eliminar este LoRA del registro? (No borra el fichero de ComfyUI)')) return;
    try {
      await api.deleteLora(id);
      if (editingId === id) resetForm();
      setLoras(prev => prev.filter(l => l.id !== id));
      flash('LoRA eliminado');
    } catch (e: any) { flash(e.message); }
  };

  const selectAssignChannel = (id: number) => {
    setAssignChannelId(id);
    const ch = channels.find(c => c.id === id);
    setAssignSelected(ch?.loras || []);
  };

  const toggleAssign = (loraId: number) => {
    setAssignSelected(prev => prev.includes(loraId) ? prev.filter(x => x !== loraId) : [...prev, loraId]);
  };

  const saveAssign = async () => {
    if (assignChannelId == null) return;
    try {
      const updated = await api.updateChannel(assignChannelId, { loras: assignSelected });
      setChannels(prev => prev.map(c => c.id === updated.id ? updated : c));
      flash('Asignación guardada');
    } catch (e: any) { flash(e.message); }
  };

  const card: React.CSSProperties = { background: '#1e293b', borderRadius: 12, padding: 20, marginBottom: 20 };
  const inputStyle: React.CSSProperties = { width: '100%', padding: 8, marginTop: 4, background: '#0f172a', border: '1px solid #334155', borderRadius: 6, color: '#e2e8f0' };

  if (loading) return <div style={{ padding: 24 }}>Cargando LoRAs…</div>;

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', padding: 8 }}>
      {toast && (
        <div style={{ position: 'fixed', top: 16, right: 16, background: '#334155', padding: '10px 16px', borderRadius: 8, zIndex: 50 }}>
          {toast}
        </div>
      )}

      {/* ── Catálogo ── */}
      <div style={card}>
        <h3 style={{ marginTop: 0 }}>🎛️ Catálogo de LoRAs</h3>
        <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginTop: 0 }}>
          Registra un LoRA con sus <strong>trigger words</strong>. Se inyectarán automáticamente al generar imágenes en los canales que lo usen.
        </p>

        {loras.length === 0 && <p style={{ color: '#64748b' }}>Aún no hay LoRAs registrados.</p>}
        {loras.map(l => (
          <div key={l.id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 0', borderBottom: '1px solid #334155' }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontWeight: 600 }}>{l.label}</div>
              <div style={{ color: '#94a3b8', fontSize: '0.78rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {l.filename} · m{l.model_strength}/c{l.clip_strength}
                {l.trigger_words ? ` · 🔑 ${l.trigger_words}` : ' · (sin trigger)'}
              </div>
            </div>
            <button className="btn btn-secondary" style={{ padding: '4px 10px' }} onClick={() => editLora(l)}>Editar</button>
            <button className="btn-delete" style={{ padding: '4px 10px' }} onClick={() => removeLora(l.id)}>✕</button>
          </div>
        ))}

        <form onSubmit={submitForm} style={{ marginTop: 16, borderTop: '1px solid #334155', paddingTop: 16 }}>
          <div style={{ fontWeight: 600, marginBottom: 8 }}>{editingId ? '✏️ Editar LoRA' : '➕ Nuevo LoRA'}</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <label style={{ fontSize: '0.85rem' }}>Etiqueta
              <input style={inputStyle} value={label} onChange={e => setLabel(e.target.value)} placeholder="Tarot (DUSK XL)" />
            </label>
            <label style={{ fontSize: '0.85rem' }}>Fichero (ComfyUI)
              {files.length > 0 ? (
                <select style={inputStyle} value={filename} onChange={e => setFilename(e.target.value)}>
                  <option value="">— elige un fichero —</option>
                  {files.map(f => <option key={f} value={f}>{f}</option>)}
                </select>
              ) : (
                <input style={inputStyle} value={filename} onChange={e => setFilename(e.target.value)} placeholder="sdxl\\mi_lora.safetensors (ComfyUI no responde)" />
              )}
            </label>
          </div>
          <label style={{ fontSize: '0.85rem', display: 'block', marginTop: 12 }}>Trigger words (se anteponen al prompt)
            <input style={inputStyle} value={trigger} onChange={e => setTrigger(e.target.value)} placeholder="tarot card, ornate border, ..." />
          </label>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
            <label style={{ fontSize: '0.85rem' }}>Fuerza modelo
              <input type="number" step="0.05" min="0" max="2" style={inputStyle} value={modelStrength} onChange={e => setModelStrength(parseFloat(e.target.value))} />
            </label>
            <label style={{ fontSize: '0.85rem' }}>Fuerza CLIP
              <input type="number" step="0.05" min="0" max="2" style={inputStyle} value={clipStrength} onChange={e => setClipStrength(parseFloat(e.target.value))} />
            </label>
          </div>
          <div style={{ marginTop: 14, display: 'flex', gap: 8 }}>
            <button type="submit" className="btn btn-primary">{editingId ? 'Guardar cambios' : 'Añadir LoRA'}</button>
            {editingId && <button type="button" className="btn btn-secondary" onClick={resetForm}>Cancelar</button>}
          </div>
        </form>
      </div>

      {/* ── Asignación por canal ── */}
      <div style={card}>
        <h3 style={{ marginTop: 0 }}>🔗 Asignar LoRAs a un canal</h3>
        <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginTop: 0 }}>
          Elige un canal y marca los LoRAs que quieres aplicar a sus imágenes (orden = orden de la cadena).
        </p>
        <select style={inputStyle} value={assignChannelId ?? ''} onChange={e => selectAssignChannel(parseInt(e.target.value))}>
          <option value="">— elige un canal —</option>
          {channels.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>

        {assignChannelId != null && (
          <div style={{ marginTop: 16 }}>
            {loras.length === 0 && <p style={{ color: '#64748b' }}>Registra algún LoRA primero.</p>}
            {loras.map(l => (
              <label key={l.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', cursor: 'pointer' }}>
                <input type="checkbox" checked={assignSelected.includes(l.id)} onChange={() => toggleAssign(l.id)} />
                <span>{l.label} <span style={{ color: '#64748b', fontSize: '0.78rem' }}>({l.filename})</span></span>
              </label>
            ))}
            <button className="btn btn-primary" style={{ marginTop: 12 }} onClick={saveAssign}>Guardar asignación</button>
          </div>
        )}
      </div>
    </div>
  );
}
