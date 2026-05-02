import React, { useEffect, useMemo, useState } from 'react';
import { api, type OrphanVideo } from '../api';

const fmtBytes = (n: number) => {
  if (!n) return '0 B';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
};

const fmtDate = (iso: string | null) => {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString('es-ES', { day: '2-digit', month: '2-digit', year: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch {
    return iso;
  }
};

const ageDays = (iso: string | null) => {
  if (!iso) return Infinity;
  const ms = Date.now() - new Date(iso).getTime();
  return ms / (1000 * 60 * 60 * 24);
};

const STATUS_LABEL: Record<string, string> = {
  draft: 'Borrador',
  audio_ready: 'Audio listo',
  images_ready: 'Imágenes listas',
  rendered: 'Renderizado',
  ready_to_upload: 'Listo para subir',
  failed: 'Fallido',
  generating_audio: 'Gen. audio',
  generating_images: 'Gen. imágenes',
  rendering: 'Renderizando',
};

type Toast = { kind: 'ok' | 'err'; msg: string };

const OrphansManager: React.FC = () => {
  const [items, setItems] = useState<OrphanVideo[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [toast, setToast] = useState<Toast | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const showToast = (t: Toast, ms = 3500) => {
    setToast(t);
    window.setTimeout(() => setToast(prev => prev === t ? null : prev), ms);
  };

  const [filterChannel, setFilterChannel] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterAge, setFilterAge] = useState<'all' | '3d' | '7d' | '30d'>('all');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await api.getOrphanVideos();
      setItems(data);
      setSelected(new Set());
    } catch (e: any) {
      setError(e.message || 'Error al cargar la lista');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const channels = useMemo(() => {
    if (!items) return [];
    const map = new Map<number, string>();
    items.forEach(v => map.set(v.channel_id, v.channel_name));
    return Array.from(map.entries()).map(([id, name]) => ({ id, name }));
  }, [items]);

  const statuses = useMemo(() => {
    if (!items) return [];
    return Array.from(new Set(items.map(v => v.status))).sort();
  }, [items]);

  const filtered = useMemo(() => {
    if (!items) return [];
    return items.filter(v => {
      if (filterChannel !== 'all' && String(v.channel_id) !== filterChannel) return false;
      if (filterStatus !== 'all' && v.status !== filterStatus) return false;
      if (filterAge !== 'all') {
        const days = ageDays(v.created_at);
        if (filterAge === '3d' && days < 3) return false;
        if (filterAge === '7d' && days < 7) return false;
        if (filterAge === '30d' && days < 30) return false;
      }
      return true;
    });
  }, [items, filterChannel, filterStatus, filterAge]);

  const totalSize = useMemo(() => filtered.reduce((acc, v) => acc + (v.cache_size_bytes || 0), 0), [filtered]);
  const selectedSize = useMemo(() => filtered.filter(v => selected.has(v.id)).reduce((acc, v) => acc + (v.cache_size_bytes || 0), 0), [filtered, selected]);

  const toggleOne = (id: number) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleAllVisible = () => {
    const visibleIds = filtered.map(v => v.id);
    const allSelected = visibleIds.every(id => selected.has(id));
    setSelected(prev => {
      const next = new Set(prev);
      if (allSelected) {
        visibleIds.forEach(id => next.delete(id));
      } else {
        visibleIds.forEach(id => next.add(id));
      }
      return next;
    });
  };

  const handleDeleteOne = async (v: OrphanVideo) => {
    if (!confirm(`¿Eliminar "${v.title}" (${v.channel_name}) y borrar ${fmtBytes(v.cache_size_bytes)} de disco?`)) return;
    setBusyId(v.id);
    try {
      const res = await api.purgeVideo(v.id);
      showToast({ kind: 'ok', msg: `#${v.id} eliminado · ${fmtBytes(res.deleted_size_bytes)} liberados` });
      await load();
    } catch (e: any) {
      showToast({ kind: 'err', msg: e.message || 'Error al eliminar' }, 6000);
    } finally {
      setBusyId(null);
    }
  };

  const handleRender = async (v: OrphanVideo) => {
    setBusyId(v.id);
    try {
      await api.renderVideo(v.id, true);
      showToast({ kind: 'ok', msg: `Render de #${v.id} lanzado` });
      await load();
    } catch (e: any) {
      showToast({ kind: 'err', msg: e.message || 'Error al lanzar render' }, 6000);
    } finally {
      setBusyId(null);
    }
  };

  const handleContinueImages = async (v: OrphanVideo) => {
    setBusyId(v.id);
    try {
      await api.autoAdvance(v.id);
      showToast({ kind: 'ok', msg: `Imágenes de #${v.id} en cola` });
      await load();
    } catch (e: any) {
      showToast({ kind: 'err', msg: e.message || 'Error al continuar imágenes' }, 6000);
    } finally {
      setBusyId(null);
    }
  };

  const handleMarkUploaded = async (v: OrphanVideo) => {
    setBusyId(v.id);
    try {
      await api.markVideoUploaded(v.id);
      showToast({ kind: 'ok', msg: `#${v.id} marcado como subido` });
      await load();
    } catch (e: any) {
      showToast({ kind: 'err', msg: e.message || 'Error al marcar como subido' }, 6000);
    } finally {
      setBusyId(null);
    }
  };

  const handleBulkDelete = async () => {
    const ids = Array.from(selected);
    if (ids.length === 0) return;
    if (!confirm(`¿Eliminar ${ids.length} vídeo(s) y liberar ~${fmtBytes(selectedSize)} de disco?`)) return;
    try {
      const res = await api.bulkPurgeVideos(ids);
      const failed = res.results.filter(r => !r.ok);
      const okCount = ids.length - failed.length;
      if (failed.length > 0) {
        showToast({
          kind: 'err',
          msg: `${okCount} eliminados, ${failed.length} fallidos: ${failed.map(f => `#${f.id} (${f.error})`).join(', ')}`,
        }, 8000);
      } else {
        showToast({ kind: 'ok', msg: `${okCount} vídeo(s) eliminado(s) · ${fmtBytes(res.total_deleted_bytes)} liberados` });
      }
      await load();
    } catch (e: any) {
      showToast({ kind: 'err', msg: e.message || 'Error en eliminación múltiple' }, 6000);
    }
  };

  if (loading) return <div className="empty-state"><p>Cargando vídeos huérfanos…</p></div>;

  if (error) return (
    <div className="empty-state">
      <p style={{ color: '#ef4444' }}>{error}</p>
      <button className="btn btn-secondary" onClick={load}>Reintentar</button>
    </div>
  );

  return (
    <div style={{ padding: '24px', maxWidth: '100%', position: 'relative' }}>
      {toast && (
        <div
          onClick={() => setToast(null)}
          style={{
            position: 'fixed',
            top: '72px',
            right: '24px',
            zIndex: 1000,
            padding: '10px 16px',
            borderRadius: '8px',
            background: toast.kind === 'ok' ? '#14532d' : '#7f1d1d',
            color: toast.kind === 'ok' ? '#bbf7d0' : '#fecaca',
            border: `1px solid ${toast.kind === 'ok' ? '#16a34a' : '#dc2626'}`,
            fontSize: '0.85rem',
            maxWidth: '420px',
            cursor: 'pointer',
            boxShadow: '0 6px 20px rgba(0,0,0,0.5)',
          }}
          title="Click para descartar"
        >
          {toast.kind === 'ok' ? '✅ ' : '⚠️ '}{toast.msg}
        </div>
      )}
      <div style={{ marginBottom: '16px' }}>
        <h2 style={{ marginBottom: '4px' }}>🧹 Vídeos huérfanos</h2>
        <p style={{ color: '#94a3b8', fontSize: '0.9rem' }}>
          Vídeos no subidos a YouTube. Útil para limpiar caché y la base de datos.
        </p>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', marginBottom: '16px', alignItems: 'center' }}>
        <select value={filterChannel} onChange={e => setFilterChannel(e.target.value)} style={{ padding: '6px 10px' }}>
          <option value="all">Todos los canales</option>
          {channels.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>

        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)} style={{ padding: '6px 10px' }}>
          <option value="all">Cualquier estado</option>
          {statuses.map(s => <option key={s} value={s}>{STATUS_LABEL[s] || s}</option>)}
        </select>

        <select value={filterAge} onChange={e => setFilterAge(e.target.value as any)} style={{ padding: '6px 10px' }}>
          <option value="all">Cualquier antigüedad</option>
          <option value="3d">Más de 3 días</option>
          <option value="7d">Más de 7 días</option>
          <option value="30d">Más de 30 días</option>
        </select>

        <button className="btn btn-secondary" onClick={load} style={{ padding: '6px 14px' }}>
          🔄 Recargar
        </button>

        <div style={{ marginLeft: 'auto', color: '#94a3b8', fontSize: '0.85rem' }}>
          {filtered.length} vídeo(s) — {fmtBytes(totalSize)} en disco
        </div>
      </div>

      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          background: '#1e293b',
          padding: '10px 16px',
          borderRadius: '8px',
          marginBottom: '12px',
          border: '1px solid #334155'
        }}>
          <strong>{selected.size} seleccionado(s)</strong>
          <span style={{ color: '#94a3b8' }}>~{fmtBytes(selectedSize)}</span>
          <button className="btn btn-delete" onClick={handleBulkDelete} style={{ marginLeft: 'auto' }}>
            🗑️ Eliminar seleccionados
          </button>
          <button className="btn-link" onClick={() => setSelected(new Set())}>
            Limpiar selección
          </button>
        </div>
      )}

      {filtered.length === 0 ? (
        <div className="empty-state" style={{ marginTop: '24px' }}>
          <div style={{ fontSize: '3rem', marginBottom: '12px' }}>✨</div>
          <h3>Nada que limpiar</h3>
          <p>No hay vídeos huérfanos con esos filtros.</p>
        </div>
      ) : (
        <div style={{ overflowX: 'auto', border: '1px solid #1f2937', borderRadius: '8px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead style={{ background: '#0f172a', position: 'sticky', top: 0 }}>
              <tr>
                <th style={{ padding: '10px', textAlign: 'left', width: '36px' }}>
                  <input
                    type="checkbox"
                    checked={filtered.length > 0 && filtered.every(v => selected.has(v.id))}
                    onChange={toggleAllVisible}
                  />
                </th>
                <th style={{ padding: '10px', textAlign: 'left' }}>ID</th>
                <th style={{ padding: '10px', textAlign: 'left' }}>Título</th>
                <th style={{ padding: '10px', textAlign: 'left' }}>Canal</th>
                <th style={{ padding: '10px', textAlign: 'left' }}>Estado</th>
                <th style={{ padding: '10px', textAlign: 'center' }}>Acciones</th>
                <th style={{ padding: '10px', textAlign: 'right' }}>Dur.</th>
                <th style={{ padding: '10px', textAlign: 'left' }}>Fecha</th>
                <th style={{ padding: '10px', textAlign: 'right' }}>Caché</th>
                <th style={{ padding: '10px', textAlign: 'center', width: '40px' }} title="Error">⚠️</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(v => {
                const isSel = selected.has(v.id);
                return (
                  <tr key={v.id} style={{
                    borderTop: '1px solid #1f2937',
                    background: isSel ? '#1e2a44' : 'transparent',
                  }}>
                    <td style={{ padding: '8px 10px' }}>
                      <input type="checkbox" checked={isSel} onChange={() => toggleOne(v.id)} />
                    </td>
                    <td style={{ padding: '8px 10px', color: '#94a3b8' }}>#{v.id}</td>
                    <td style={{ padding: '8px 10px', maxWidth: '260px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={v.title}>
                      {v.title}
                    </td>
                    <td style={{ padding: '8px 10px', maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={v.channel_name}>{v.channel_name}</td>
                    <td style={{ padding: '8px 10px' }}>
                      <span style={{
                        padding: '2px 8px',
                        borderRadius: '12px',
                        fontSize: '0.75rem',
                        background: v.status === 'failed' ? '#7f1d1d' : '#334155',
                        color: v.status === 'failed' ? '#fecaca' : '#cbd5e1',
                        whiteSpace: 'nowrap',
                      }}>
                        {STATUS_LABEL[v.status] || v.status}
                      </span>
                    </td>
                    <td style={{ padding: '8px 6px', textAlign: 'center', whiteSpace: 'nowrap' }}>
                      <div style={{ display: 'inline-flex', gap: '4px', flexWrap: 'nowrap', justifyContent: 'center' }}>
                        {v.status === 'audio_ready' && (
                          <button
                            disabled={busyId === v.id}
                            style={{ padding: '4px 8px', fontSize: '0.75rem', background: '#ca8a04', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', opacity: busyId === v.id ? 0.5 : 1 }}
                            onClick={() => handleContinueImages(v)}
                            title="Continuar generación de imágenes"
                          >
                            ▶ Imágenes
                          </button>
                        )}
                        {v.status === 'images_ready' && (
                          <button
                            disabled={busyId === v.id}
                            style={{ padding: '4px 8px', fontSize: '0.75rem', background: '#16a34a', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', opacity: busyId === v.id ? 0.5 : 1 }}
                            onClick={() => handleRender(v)}
                            title="Lanzar render"
                          >
                            🎬 Render
                          </button>
                        )}
                        <button
                          disabled={busyId === v.id}
                          style={{ padding: '4px 8px', fontSize: '0.75rem', background: '#2563eb', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', opacity: busyId === v.id ? 0.5 : 1 }}
                          onClick={() => handleMarkUploaded(v)}
                          title="Marcar como subido a YouTube"
                        >
                          ✅ Subido
                        </button>
                        <button
                          className="btn-delete"
                          disabled={busyId === v.id}
                          style={{ padding: '4px 8px', fontSize: '0.75rem', opacity: busyId === v.id ? 0.5 : 1 }}
                          onClick={() => handleDeleteOne(v)}
                        >
                          🗑️
                        </button>
                      </div>
                    </td>
                    <td style={{ padding: '8px 10px', textAlign: 'right', color: '#94a3b8', whiteSpace: 'nowrap' }}>
                      {v.duration_seconds ? `${Math.round(v.duration_seconds)}s` : '—'}
                    </td>
                    <td style={{ padding: '8px 10px', color: '#94a3b8', whiteSpace: 'nowrap' }}>{fmtDate(v.created_at)}</td>
                    <td style={{ padding: '8px 10px', textAlign: 'right', fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
                      {fmtBytes(v.cache_size_bytes)}
                    </td>
                    <td style={{ padding: '8px 6px', textAlign: 'center' }} title={v.last_error || ''}>
                      {v.last_error ? <span style={{ cursor: 'help', color: '#f87171' }}>⚠️</span> : ''}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default OrphansManager;
