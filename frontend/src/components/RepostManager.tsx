import React, { useEffect, useState } from 'react';
import { api, type ChannelResponse, type RepostVideo, type RepostInfo } from '../api';

type ScannedVideo = {
  video_id: string;
  title: string;
  view_count: number | null;
  duration_seconds: number | null;
  upload_date: string | null;
  url: string | null;
};

const fmtSize = (b?: number | null) => b ? `${(b / 1048576).toFixed(1)} MB` : '';
const fmtViews = (n?: number | null) => n == null ? '' : `${n.toLocaleString('es-ES')} vistas`;
const fmtDate = (d: string | null) => d && d.length === 8 ? `${d.slice(6, 8)}/${d.slice(4, 6)}/${d.slice(0, 4)}` : '';
const fmtDur = (s?: number | null) => {
  if (!s) return '';
  const m = Math.floor(s / 60), sec = s % 60;
  return `${m}:${String(sec).padStart(2, '0')}`;
};

/**
 * Flujo "mirror": lista los vídeos de tu canal (escaneo público), abre una
 * FICHA por vídeo con miniatura descargable, descarga del MP4 y descripción
 * copiable — para subir a mano a bilibili.com.
 */
export default function RepostManager({ channel }: { channel: ChannelResponse }) {
  const [files, setFiles] = useState<RepostVideo[]>([]);
  const [copied, setCopied] = useState('');

  // Escáner del canal
  const [url, setUrl] = useState('');
  const [scanned, setScanned] = useState<ScannedVideo[]>([]);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState('');
  const [sortBy, setSortBy] = useState<'views' | 'date'>('views');
  const [doneIds, setDoneIds] = useState<Set<string>>(new Set());

  // Ficha del vídeo
  const [detailUrl, setDetailUrl] = useState<string | null>(null);
  const [detail, setDetail] = useState<RepostInfo | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const [vidBusy, setVidBusy] = useState(false);
  const [thumbBusy, setThumbBusy] = useState(false);

  const handle = channel.youtube_handle || '';

  const loadFiles = async () => {
    try { const res = await api.repostList(channel.id); setFiles(res.files || []); }
    catch { /* la carpeta puede no existir aún */ }
  };
  useEffect(() => { loadFiles(); setScanned([]); setDoneIds(new Set()); closeDetail(); }, [channel.id]);

  const scanChannel = async () => {
    if (!handle) { setScanError('Este canal no tiene handle de YouTube configurado.'); return; }
    setScanning(true); setScanError('');
    try {
      const res = await api.scanPublicChannel(handle, 200);
      setScanned(res.videos || []);
      if (!res.videos?.length) setScanError('No se encontraron vídeos públicos.');
    } catch (err: any) { setScanError(err.message || 'Error al escanear el canal'); }
    finally { setScanning(false); }
  };

  const openDetail = async (videoUrl: string) => {
    setDetailUrl(videoUrl); setDetail(null); setDetailError(''); setDetailLoading(true);
    try { setDetail(await api.repostInfo(channel.id, videoUrl)); }
    catch (err: any) { setDetailError(err.message || 'Error al leer el vídeo'); }
    finally { setDetailLoading(false); }
  };
  const closeDetail = () => { setDetailUrl(null); setDetail(null); setDetailError(''); };

  const openDetailFromUrl = (e: React.FormEvent) => { e.preventDefault(); if (url.trim()) openDetail(url.trim()); };
  const openDetailFromScan = (v: ScannedVideo) => openDetail(v.url || `https://www.youtube.com/watch?v=${v.video_id}`);

  const downloadVideo = async () => {
    if (!detailUrl) return;
    setVidBusy(true);
    try {
      const r = await api.repostDownload(channel.id, detailUrl);
      await api.repostSaveFile(channel.id, r.rel_path, r.filename);
      if (detail?.id) setDoneIds(prev => new Set(prev).add(detail.id));
      loadFiles();
    } catch (err: any) { alert(err.message || 'Error al descargar el vídeo'); }
    finally { setVidBusy(false); }
  };

  const downloadThumb = async () => {
    if (!detail?.thumbnail) return;
    setThumbBusy(true);
    try {
      // El backend convierte la miniatura a PNG (Bilibili no acepta webp).
      await api.repostSaveThumbnail(channel.id, detail.thumbnail, `${detail.id}_miniatura.png`);
    } catch (err: any) { alert(err.message || 'Error al descargar la miniatura'); }
    finally { setThumbBusy(false); }
  };

  const copy = (label: string, text: string) =>
    navigator.clipboard.writeText(text || '').then(() => { setCopied(label); setTimeout(() => setCopied(''), 1500); });
  const save = (f: RepostVideo) => api.repostSaveFile(channel.id, f.rel_path, f.filename).catch((e: any) => alert(e.message));
  const tagsStr = (t?: string[]) => (t || []).join(', ');

  const sortedScanned = [...scanned].sort((a, b) =>
    sortBy === 'views' ? (b.view_count ?? -1) - (a.view_count ?? -1) : (b.upload_date || '').localeCompare(a.upload_date || '')
  );

  // ---------- FICHA DEL VÍDEO ----------
  if (detailUrl) {
    return (
      <div style={{ maxWidth: 900, margin: '0 auto' }}>
        <button className="btn btn-secondary" onClick={closeDetail} style={{ marginBottom: 16 }}>← Volver</button>

        {detailLoading && <div style={{ color: '#94a3b8' }}>Cargando ficha del vídeo…</div>}
        {detailError && <div style={{ color: '#f87171' }}>⚠️ {detailError}</div>}

        {detail && (
          <div style={{ background: '#1e293b', borderRadius: 12, padding: 20 }}>
            <h2 style={{ marginTop: 0 }}>{detail.title}</h2>
            <div style={{ color: '#64748b', fontSize: '0.85rem', marginBottom: 16 }}>
              {[fmtDur(detail.duration), fmtViews(detail.view_count)].filter(Boolean).join(' · ')}
            </div>

            {/* Miniatura */}
            {detail.thumbnail && (
              <div style={{ marginBottom: 18 }}>
                <img
                  src={detail.thumbnail}
                  alt="miniatura"
                  style={{ width: '100%', maxWidth: 640, borderRadius: 10, display: 'block', border: '1px solid #334155' }}
                />
                <button className="btn btn-secondary" style={{ marginTop: 10 }} onClick={downloadThumb} disabled={thumbBusy}>
                  {thumbBusy ? 'Descargando…' : '🖼️ Descargar miniatura'}
                </button>
              </div>
            )}

            {/* Vídeo */}
            <div style={{ marginBottom: 18 }}>
              <button className="btn btn-primary" onClick={downloadVideo} disabled={vidBusy}>
                {vidBusy ? '⏳ Descargando vídeo…' : '⬇️ Descargar vídeo (MP4)'}
              </button>
              {detail.id && doneIds.has(detail.id) && (
                <span style={{ color: '#4ade80', marginLeft: 10, fontSize: '0.85rem' }}>✅ Descargado</span>
              )}
              <div style={{ color: '#64748b', fontSize: '0.8rem', marginTop: 6 }}>
                Se baja en mejor calidad y se guarda en tu navegador.
              </div>
            </div>

            {/* Descripción */}
            <div style={{ marginBottom: 12 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label style={{ color: '#94a3b8', fontSize: '0.9rem', fontWeight: 600 }}>Descripción</label>
                <button className="btn btn-secondary" style={{ padding: '4px 12px', fontSize: '0.8rem' }}
                  onClick={() => copy('desc', detail.description || '')}>
                  {copied === 'desc' ? '✅ ¡Copiada!' : '📋 Copiar descripción'}
                </button>
              </div>
              <textarea readOnly value={detail.description || ''} rows={8}
                style={{ width: '100%', marginTop: 6, padding: 12, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#cbd5e1', fontSize: '0.85rem', lineHeight: 1.5 }} />
            </div>

            {/* Etiquetas */}
            {!!(detail.tags && detail.tags.length) && (
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <label style={{ color: '#94a3b8', fontSize: '0.85rem' }}>Etiquetas ({detail.tags.length})</label>
                  <button className="btn-link" onClick={() => copy('tags', tagsStr(detail.tags))}>
                    {copied === 'tags' ? '¡Copiado!' : 'Copiar'}
                  </button>
                </div>
                <input readOnly value={tagsStr(detail.tags)}
                  style={{ width: '100%', marginTop: 6, padding: 10, borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0', fontSize: '0.85rem' }} />
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  // ---------- LISTA + BÚSQUEDA ----------
  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <div style={{ background: '#1e293b', borderRadius: 12, padding: 20, marginBottom: 20 }}>
        <h2 style={{ marginTop: 0 }}>📥 Reubir a Bilibili — {channel.name}</h2>
        <p style={{ color: '#94a3b8', marginTop: 4 }}>
          Lista los vídeos de <strong>{handle || 'tu canal'}</strong> y abre la ficha de cada uno para
          descargar miniatura, vídeo y copiar la descripción. Luego lo subes a mano a bilibili.com.
        </p>

        <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
          <button className="btn btn-secondary" onClick={scanChannel} disabled={scanning || !handle}>
            {scanning ? 'Escaneando…' : `📺 Ver vídeos de ${handle || 'mi canal'}`}
          </button>
          <span style={{ color: '#64748b', fontSize: '0.8rem', alignSelf: 'center' }}>(público, no necesita el secret)</span>
        </div>
        {scanError && <div style={{ color: '#fbbf24', marginTop: 8, fontSize: '0.85rem' }}>⚠️ {scanError}</div>}

        <form onSubmit={openDetailFromUrl} style={{ display: 'flex', gap: 8, marginTop: 14 }}>
          <input type="text" value={url} onChange={(e) => setUrl(e.target.value)}
            placeholder="…o pega una URL de YouTube concreta"
            style={{ flex: 1, padding: '10px 12px', borderRadius: 8, border: '1px solid #334155', background: '#0f172a', color: '#e2e8f0' }} />
          <button type="submit" className="btn btn-primary" disabled={!url.trim()}>Abrir ficha</button>
        </form>
      </div>

      {scanned.length > 0 && (
        <div style={{ background: '#1e293b', borderRadius: 12, padding: 20, marginBottom: 20 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
            <h3 style={{ margin: 0 }}>📺 Vídeos de tu canal ({scanned.length})</h3>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <span style={{ color: '#64748b', fontSize: '0.8rem' }}>Ordenar:</span>
              <button className={`btn ${sortBy === 'views' ? 'btn-primary' : 'btn-secondary'}`} style={{ padding: '4px 10px', fontSize: '0.8rem' }} onClick={() => setSortBy('views')}>👁️ Más vistos</button>
              <button className={`btn ${sortBy === 'date' ? 'btn-primary' : 'btn-secondary'}`} style={{ padding: '4px 10px', fontSize: '0.8rem' }} onClick={() => setSortBy('date')}>🕒 Más recientes</button>
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 12, maxHeight: 460, overflowY: 'auto' }}>
            {sortedScanned.map((v) => (
              <div key={v.video_id}
                onClick={() => openDetailFromScan(v)}
                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, padding: '10px 12px', background: '#0f172a', borderRadius: 8, cursor: 'pointer' }}
                title="Abrir ficha">
                <div style={{ overflow: 'hidden' }}>
                  <div style={{ color: '#e2e8f0', fontSize: '0.9rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {doneIds.has(v.video_id) && '✅ '}{v.title}
                  </div>
                  <div style={{ color: '#64748b', fontSize: '0.75rem' }}>
                    {[fmtDur(v.duration_seconds), fmtViews(v.view_count), fmtDate(v.upload_date)].filter(Boolean).join(' · ')}
                  </div>
                </div>
                <span className="btn btn-secondary" style={{ padding: '6px 12px', flexShrink: 0 }}>Abrir ▸</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{ background: '#1e293b', borderRadius: 12, padding: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ margin: 0 }}>🎞️ Descargados en el servidor ({files.length})</h3>
          <button className="btn-link" onClick={loadFiles}>Refrescar</button>
        </div>
        {files.length === 0 ? (
          <p style={{ color: '#64748b', marginTop: 12 }}>Todavía no has descargado ningún vídeo.</p>
        ) : (
          <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {files.map((f) => (
              <div key={f.rel_path} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10, padding: '10px 12px', background: '#0f172a', borderRadius: 8 }}>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#cbd5e1', fontSize: '0.9rem' }} title={f.filename}>{f.filename}</span>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexShrink: 0 }}>
                  <span style={{ color: '#64748b', fontSize: '0.8rem' }}>{fmtSize(f.size_bytes)}</span>
                  <button className="btn btn-secondary" style={{ padding: '6px 12px' }} onClick={() => save(f)}>⬇️ MP4</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
