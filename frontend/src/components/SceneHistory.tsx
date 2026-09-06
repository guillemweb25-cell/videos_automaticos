import React, { useEffect, useState } from 'react';
import { api, type SceneHistoryItem } from '../api';
import Lightbox from './Lightbox';

/** Historial de fotos generadas (compartido por las pestañas Imágenes y Desde
 *  referencia). Se recarga cuando cambia `reloadSignal`. */
export default function SceneHistory({ reloadSignal = 0 }: { reloadSignal?: number }) {
  const [history, setHistory] = useState<SceneHistoryItem[]>([]);
  const [openHist, setOpenHist] = useState<Record<string, { filename: string; url: string }[]>>({});
  const [loading, setLoading] = useState<string | null>(null);
  const [lightbox, setLightbox] = useState<{ urls: string[]; i: number } | null>(null);

  const load = async () => { try { setHistory(await api.charScenes()); } catch { /* */ } };
  useEffect(() => { load(); }, [reloadSignal]);

  const view = async (e: SceneHistoryItem) => {
    if (openHist[e.id]) { setOpenHist((p) => { const n = { ...p }; (n[e.id] || []).forEach((i) => { try { URL.revokeObjectURL(i.url); } catch { /* */ } }); delete n[e.id]; return n; }); return; }
    if (!e.images.length) return;
    setLoading(e.id);
    try {
      const loaded = await Promise.all(e.images.map(async (f) => ({ filename: f, url: await api.charImageObjectUrl(f) })));
      setOpenHist((p) => ({ ...p, [e.id]: loaded }));
    } catch { alert('No se pudieron cargar (¿borradas del disco?).'); }
    finally { setLoading(null); }
  };
  const del = async (e: SceneHistoryItem) => {
    if (!confirm('¿Borrar esta entrada del historial? (las imágenes en disco no se borran)')) return;
    try { await api.charSceneDelete(e.id); setOpenHist((p) => { const n = { ...p }; delete n[e.id]; return n; }); load(); } catch { alert('Error'); }
  };
  const dl = (url: string, filename: string) => {
    const a = document.createElement('a'); a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); a.remove();
  };

  return (
    <div style={{ background: '#1e293b', borderRadius: 12, padding: 20, marginTop: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ margin: 0 }}>🕘 Historial de fotos ({history.length})</h3>
        <button className="btn-link" onClick={load}>Refrescar</button>
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
                  <button className="btn btn-secondary" style={{ padding: '5px 10px', fontSize: '0.78rem' }} onClick={() => view(e)} disabled={!e.done || !e.images.length || loading === e.id}>
                    {loading === e.id ? '⏳' : openHist[e.id] ? 'Ocultar' : '🖼️ Ver'}
                  </button>
                  <button className="btn btn-secondary" style={{ padding: '5px 10px', fontSize: '0.78rem' }} onClick={() => del(e)}>🗑️</button>
                </div>
              </div>
              {openHist[e.id] && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 8, marginTop: 10 }}>
                  {openHist[e.id].map((im) => (
                    <div key={im.filename} style={{ background: '#000', borderRadius: 6, overflow: 'hidden' }}>
                      <img src={im.url} onClick={() => setLightbox({ urls: openHist[e.id].map((x) => x.url), i: openHist[e.id].indexOf(im) })} style={{ width: '100%', display: 'block', cursor: 'zoom-in' }} />
                      <button className="btn btn-secondary" style={{ width: '100%', padding: '4px', fontSize: '0.68rem', borderRadius: 0 }} onClick={() => dl(im.url, im.filename)}>⬇️</button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {lightbox && <Lightbox urls={lightbox.urls} index={lightbox.i} onClose={() => setLightbox(null)} />}
    </div>
  );
}
