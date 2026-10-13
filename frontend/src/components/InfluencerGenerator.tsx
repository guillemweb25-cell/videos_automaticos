import { useState, useRef, useEffect } from 'react';
import { api } from '../api';

// Pestaña "Influencers": genera fotos realistas tipo influencer (SFW) con las
// técnicas del tutorial (candid / cámara 2006, variación de cuerpo/altura/escena).
// No usa personaje guardado: es txt→imagen puro para probar.
export default function InfluencerGenerator() {
  const [prompt, setPrompt] = useState('');
  const [look, setLook] = useState<'candid' | 'vintage' | 'clean'>('candid');
  const [format, setFormat] = useState<'vertical' | 'square' | 'horizontal'>('vertical');
  const [num, setNum] = useState(2);
  const [hq, setHq] = useState(false);
  const [seed, setSeed] = useState('');
  const [busy, setBusy] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');
  const [images, setImages] = useState<string[]>([]);  // object URLs
  const pollRef = useRef<number | null>(null);

  useEffect(() => () => { if (pollRef.current) window.clearInterval(pollRef.current); }, []);

  const dims = format === 'square' ? { width: 1024, height: 1024 }
    : format === 'horizontal' ? { width: 1216, height: 832 }
    : { width: 832, height: 1216 };

  const generate = async () => {
    setBusy(true);
    setStatusMsg('Enviando a ComfyUI…');
    setImages([]);
    try {
      const res = await api.charInfluencer({
        prompt: prompt.trim(),
        num_images: num,
        width: dims.width,
        height: dims.height,
        seed: seed.trim() ? Number(seed.trim()) : null,
        look,
        hq,
      });
      const pid = res.prompt_id;
      if (!pid) throw new Error('No se recibió prompt_id');
      setStatusMsg('Generando imágenes… (puede tardar un poco)');
      pollRef.current = window.setInterval(async () => {
        try {
          const st = await api.charStatus(pid);
          if (st.status === 'done' && st.images?.length) {
            if (pollRef.current) window.clearInterval(pollRef.current);
            const urls = await Promise.all(st.images.map(f => api.charImageObjectUrl(f)));
            setImages(urls);
            setStatusMsg(`✅ ${urls.length} imagen(es) generada(s)`);
            setBusy(false);
          } else if (st.status === 'error') {
            if (pollRef.current) window.clearInterval(pollRef.current);
            setStatusMsg('❌ Error en la generación (ComfyUI). Revisa que esté encendido.');
            setBusy(false);
          }
        } catch {
          /* reintenta en el siguiente tick */
        }
      }, 2500);
    } catch (e: any) {
      setStatusMsg('❌ ' + (e?.message || e));
      setBusy(false);
    }
  };

  const input: React.CSSProperties = { width: '100%', background: '#0f172a', border: '1px solid #334155', borderRadius: '8px', padding: '8px 12px', color: '#e2e8f0' };
  const label: React.CSSProperties = { display: 'block', fontSize: '0.78rem', color: '#94a3b8', marginBottom: '4px' };

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <div style={{ background: '#111827', border: '1px solid #1f2937', borderRadius: '14px', padding: '24px' }}>
        <h2 style={{ margin: '0 0 4px' }}>🧍‍♀️ Generador de influencers (realista)</h2>
        <p style={{ color: '#94a3b8', margin: '0 0 16px', fontSize: '0.9rem' }}>
          Fotos realistas tipo influencer (estilo candid/Instagram). Déjalo vacío para una persona y escena
          <b> aleatorias</b>, o describe tú a la persona/escena. Corre en tu ComfyUI local. <b>Solo contenido SFW</b> (vestido).
        </p>

        <label style={label}>Descripción (opcional, en español)</label>
        <textarea
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          placeholder="ej. chica morena con chaqueta vaquera en una cafetería  ·  (vacío = aleatorio)"
          rows={2}
          style={{ ...input, resize: 'vertical', marginBottom: '14px' }}
        />

        <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap', marginBottom: '14px' }}>
          <div style={{ flex: '1 1 180px' }}>
            <label style={label}>Look</label>
            <select value={look} onChange={e => setLook(e.target.value as any)} style={input}>
              <option value="candid">📱 Candid móvil (amateur)</option>
              <option value="vintage">📷 Vintage 2006 (flash)</option>
              <option value="clean">✨ Natural limpio</option>
            </select>
          </div>
          <div style={{ flex: '1 1 160px' }}>
            <label style={label}>Formato</label>
            <select value={format} onChange={e => setFormat(e.target.value as any)} style={input}>
              <option value="vertical">Vertical 2:3</option>
              <option value="square">Cuadrado 1:1</option>
              <option value="horizontal">Horizontal 3:2</option>
            </select>
          </div>
          <div style={{ flex: '0 0 110px' }}>
            <label style={label}>Nº imágenes</label>
            <select value={num} onChange={e => setNum(Number(e.target.value))} style={input}>
              {[1, 2, 3, 4].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </div>
          <div style={{ flex: '0 0 130px' }}>
            <label style={label}>Seed (opcional)</label>
            <input value={seed} onChange={e => setSeed(e.target.value)} placeholder="aleatorio" style={input} />
          </div>
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#cbd5e1', fontSize: '0.85rem', marginBottom: '16px', cursor: 'pointer' }}>
          <input type="checkbox" checked={hq} onChange={e => setHq(e.target.checked)} />
          Alta calidad (FaceDetailer + upscale 2x · más lento)
        </label>

        <button
          onClick={generate}
          disabled={busy}
          style={{ background: busy ? '#334155' : '#0e7490', color: '#fff', border: 'none', borderRadius: '10px', padding: '12px 24px', fontWeight: 700, cursor: busy ? 'default' : 'pointer' }}
        >
          {busy ? 'Generando…' : '✨ Generar influencer'}
        </button>
        {statusMsg && <span style={{ marginLeft: '14px', color: '#94a3b8', fontSize: '0.85rem' }}>{statusMsg}</span>}
      </div>

      {images.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '14px', marginTop: '20px' }}>
          {images.map((url, i) => (
            <a key={i} href={url} download={`influencer_${i + 1}.png`} title="Clic para descargar">
              <img src={url} alt={`influencer ${i + 1}`} style={{ width: '100%', borderRadius: '10px', display: 'block', border: '1px solid #1f2937' }} />
            </a>
          ))}
        </div>
      )}
    </div>
  );
}
