import React, { useState, useEffect } from 'react';
import { api, type ChannelResponse, type YouTubeChannelInfo, type YouTubeVideo, type VideoResponse } from '../api';
import VideoCreator from './VideoCreator';
import ImageReviewer from './ImageReviewer';
import VideoUploadModal from './VideoUploadModal';

interface ChannelDashboardProps {
  channel: ChannelResponse;
  onBack: () => void;
}

type TabType = 'overview' | 'videos' | 'shorts' | 'create' | 'youtube' | 'transcribe' | 'generations';

const ChannelDashboard: React.FC<ChannelDashboardProps> = ({ channel }) => {
  const [activeTab, _setActiveTab] = useState<TabType>(() => {
    const saved = localStorage.getItem('activeTab');
    return (saved as TabType) || 'overview';
  });
  const setActiveTab = (tab: TabType) => {
    localStorage.setItem('activeTab', tab);
    _setActiveTab(tab);
  };

  const [reviewingVideoId, _setReviewingVideoId] = useState<number | null>(() => {
    const saved = localStorage.getItem('reviewingVideoId');
    return saved ? parseInt(saved) : null;
  });
  const setReviewingVideoId = (id: number | null) => {
    if (id) localStorage.setItem('reviewingVideoId', id.toString());
    else localStorage.removeItem('reviewingVideoId');
    _setReviewingVideoId(id);
  };

  const [selectedVideo, _setSelectedVideo] = useState<VideoResponse | null>(() => {
    const saved = localStorage.getItem('selectedVideo');
    return saved ? JSON.parse(saved) : null;
  });
  const setSelectedVideo = (v: VideoResponse | null) => {
    if (v) localStorage.setItem('selectedVideo', JSON.stringify(v));
    else localStorage.removeItem('selectedVideo');
    _setSelectedVideo(v);
  };

  const [uploadingVideoId, setUploadingVideoId] = useState<number | null>(null);
  const [ytInfo, setYtInfo] = useState<YouTubeChannelInfo | null>(null);
  const [videos, setVideos] = useState<YouTubeVideo[]>([]);
  const [shorts, setShorts] = useState<YouTubeVideo[]>([]);
  const [generations, setGenerations] = useState<VideoResponse[]>([]);
  const [downloads, setDownloads] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [ytUrl, setYtUrl] = useState('');
  const [error, setError] = useState('');
  const [updateStatus, setUpdateStatus] = useState<{msg: string, type: 'success' | 'error'} | null>(null);

  const [editCredsDir, setEditCredsDir] = useState(channel.creds_dir || '');
  const [editStylePrompt, setEditStylePrompt] = useState(channel.image_style_prompt || '');
  const [editNegativePrompt, setEditNegativePrompt] = useState(channel.negative_prompt || '');


  useEffect(() => {
    if (channel.creds_dir) {
      loadYouTubeData();
    } else {
      setYtInfo(null);
      setVideos([]);
      setShorts([]);
    }
    setEditCredsDir(channel.creds_dir || '');
    setEditStylePrompt(channel.image_style_prompt || '');
    setEditNegativePrompt(channel.negative_prompt || '');
    loadDownloads();
    loadGenerations();
    setSelectedVideo(null);
  }, [channel]);


  const loadYouTubeData = async () => {
    setLoading(true);
    setError('');
    try {
      // Add a timeout to prevent infinite loading on flaky mobile networks
      const timeoutPromise = new Promise((_, reject) => 
        setTimeout(() => reject(new Error('TIMEOUT')), 15000)
      );
      
      const loadPromise = Promise.all([
        api.getYouTubeChannelInfo(channel.id),
        api.getYouTubeVideos(channel.id),
        api.getYouTubeShorts(channel.id)
      ]);

      const [info, vids, shs] = await Promise.race([loadPromise, timeoutPromise]) as any;
      
      setYtInfo(info);
      setVideos(vids);
      setShorts(shs);
    } catch (err: any) {
      console.error(err);
      if (err.message === 'TIMEOUT') {
        setError('La carga de YouTube está tardando demasiado. Verifica tu conexión.');
      } else {
        setError('No se pudo cargar la información de YouTube. Verifica las credenciales.');
      }
    } finally {
      setLoading(false);
    }
  };

  const loadDownloads = async () => {
    try {
      const files = await api.getDownloadedFiles(channel.id);
      setDownloads(files);
    } catch (err) {
      console.error(err);
    }
  };

  const loadGenerations = async () => {
    try {
      const data = await api.getVideosByChannel(channel.id);
      setGenerations(data);
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteVideo = async (videoId: number) => {
    if (!confirm('¿Estás seguro de que quieres eliminar esta generación?')) return;
    try {
      await api.deleteVideo(videoId);
      loadGenerations();
    } catch (err: any) {
      alert('Error al eliminar: ' + err.message);
    }
  };

  const handleUpdateChannel = async () => {
    setLoading(true);
    setUpdateStatus(null);
    try {
      // Add timeout for channel update as well as it might hang on mobile
      const timeoutPromise = new Promise((_, reject) => 
        setTimeout(() => reject(new Error('TIMEOUT')), 15000)
      );

      const updatePromise = api.updateChannel(channel.id, { 
        creds_dir: editCredsDir,
        image_style_prompt: editStylePrompt,
        negative_prompt: editNegativePrompt
      });

      await Promise.race([updatePromise, timeoutPromise]);

      if (editCredsDir && editCredsDir !== channel.creds_dir) {
        await loadYouTubeData();
      }
      setUpdateStatus({ msg: 'Configuración actualizada correctamente', type: 'success' });
      setTimeout(() => setUpdateStatus(null), 3000);
    } catch (err: any) {
      setUpdateStatus({ msg: 'Error al actualizar: ' + err.message, type: 'error' });
    } finally {
      setLoading(false);
    }
  };


  const handleDownload = async () => {
    if (!ytUrl) return;
    setDownloading(true);
    try {
      await api.downloadYouTubeAudio(channel.id, ytUrl);
      setYtUrl('');
      await loadDownloads();
      alert('Descarga completada');
    } catch (err: any) {
      alert('Error en la descarga: ' + err.message);
    } finally {
      setDownloading(false);
    }
  };

  const VideoCard = ({ video, isShort = false }: { video: YouTubeVideo, isShort?: boolean }) => (
    <div className="video-card" onClick={() => setYtUrl(`https://www.youtube.com/watch?v=${video.id}`)}>
      <div className={`video-thumbnail ${isShort ? 'short-thumbnail' : ''}`}>
        <img src={video.thumbnail} alt={video.title} />
        <div className="view-badge">
          {video.view_count ? `${(parseInt(video.view_count) >= 1000 ? (parseInt(video.view_count)/1000).toFixed(1) + 'k' : video.view_count)} vistas` : new Date(video.published_at).toLocaleDateString()}
        </div>
      </div>
      <div className="video-info">
        <h4>{video.title}</h4>
      </div>
    </div>
  );

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'ready': return '#22c55e';
      case 'failed': return '#ef4444';
      case 'draft': return '#94a3b8';
      default: return '#eab308';
    }
  };

  return (
    <div className="channel-dashboard">
      <div className="dashboard-tabs">
        <button className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>General</button>
        <button className={`tab-btn ${activeTab === 'videos' ? 'active' : ''}`} onClick={() => setActiveTab('videos')}>Vídeos</button>
        <button className={`tab-btn ${activeTab === 'shorts' ? 'active' : ''}`} onClick={() => setActiveTab('shorts')}>Shorts</button>
        <button className={`tab-btn ${activeTab === 'generations' ? 'active' : ''}`} onClick={() => { setActiveTab('generations'); loadGenerations(); }}>📁 Mis Generaciones</button>
        <button className={`tab-btn ${activeTab === 'create' ? 'active' : ''}`} onClick={() => { setActiveTab('create'); setSelectedVideo(null); }}>✨ Crear Vídeo</button>
        <button className={`tab-btn ${activeTab === 'youtube' ? 'active' : ''}`} onClick={() => setActiveTab('youtube')}>YouTube a MP3</button>
        <button className={`tab-btn ${activeTab === 'transcribe' ? 'active' : ''}`} onClick={() => setActiveTab('transcribe')}>Transcripción</button>
      </div>

      <div className="dashboard-content">
        {error && <div className="error-text" style={{ marginBottom: '20px' }}>{error}</div>}

        {activeTab === 'overview' && (
          <div>
            <div className="stats-container">
              <div className="stat-card">
                <span className="stat-label">Suscriptores</span>
                <span className="stat-value">{ytInfo?.statistics.subscriberCount || '0'}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Vistas totales</span>
                <span className="stat-value">{ytInfo ? (parseInt(ytInfo.statistics.viewCount) / 1000).toFixed(1) + 'K' : '0'}</span>
              </div>
              <div className="stat-card">
                <span className="stat-label">Vídeos</span>
                <span className="stat-value">{ytInfo?.statistics.videoCount || '0'}</span>
              </div>
            </div>

            <div className="glass-panel">
              <h3>Configuración del Canal</h3>
              <p style={{ color: '#94a3b8', margin: '16px 0' }}>
                Indica el nombre de la carpeta en `backend/youtube_creds/` que contiene `client_secret.json` y `token.json`.
              </p>
              <div className="form-inline">
                <input 
                  type="text" 
                  value={editCredsDir} 
                  onChange={(e) => setEditCredsDir(e.target.value)}
                  placeholder="Ej: 0012-saludseniorpodcast"
                />
              </div>

              <div style={{ marginTop: '24px' }}>
                <h4 style={{ marginBottom: '8px' }}>Estilo Visual del Canal</h4>
                <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '12px' }}>
                  Define el prompt visual base que se usará para todas las imágenes de este canal. 
                  Si se deja vacío, se usará el estilo por defecto del vídeo.
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8', marginBottom: '4px' }}>Style Prompt</label>
                    <textarea 
                      style={{ width: '100%', minHeight: '80px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '12px', color: 'white', resize: 'vertical' }}
                      value={editStylePrompt}
                      onChange={(e) => setEditStylePrompt(e.target.value)}
                      placeholder="Ej: Cinematic photography, soft lighting, high detail..."
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8', marginBottom: '4px' }}>Negative Prompt</label>
                    <textarea 
                      style={{ width: '100%', minHeight: '60px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border-color)', borderRadius: '8px', padding: '12px', color: 'white', resize: 'vertical' }}
                      value={editNegativePrompt}
                      onChange={(e) => setEditNegativePrompt(e.target.value)}
                      placeholder="Ej: blurry, low quality, distorted hands..."
                    />
                  </div>
                </div>
              </div>

              <div style={{ marginTop: '24px' }}>
                <button className="btn btn-secondary" onClick={handleUpdateChannel} disabled={loading} style={{ width: '100%', position: 'relative' }}>
                  {loading ? 'Guardando...' : 'Guardar Configuración'}
                </button>
                {updateStatus && (
                  <div style={{ 
                    marginTop: '12px', 
                    padding: '8px', 
                    borderRadius: '6px', 
                    fontSize: '0.85rem',
                    textAlign: 'center',
                    backgroundColor: updateStatus.type === 'success' ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                    color: updateStatus.type === 'success' ? '#4ade80' : '#f87171',
                    border: `1px solid ${updateStatus.type === 'success' ? 'rgba(34, 197, 94, 0.2)' : 'rgba(239, 68, 68, 0.2)'}`
                  }}>
                    {updateStatus.msg}
                  </div>
                )}
              </div>

              {ytInfo && (
                <div style={{ marginTop: '24px', display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <img src={ytInfo.snippet.thumbnails.default.url} style={{ borderRadius: '50%' }} alt="avatar" />
                  <div>
                    <div style={{ fontWeight: 700 }}>{ytInfo.snippet.title}</div>
                    <div style={{ color: '#22c55e', fontSize: '0.9rem' }}>● Canal Vinculado</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'videos' && (
          <div className="video-grid">
            {loading ? <p>Cargando vídeos...</p> : videos.map(v => <VideoCard key={v.id} video={v} />)}
            {!loading && videos.length === 0 && <p>No se encontraron vídeos.</p>}
          </div>
        )}

        {activeTab === 'shorts' && (
          <div className="shorts-grid">
            {loading ? <p>Cargando shorts...</p> : shorts.map(v => <VideoCard key={v.id} video={v} isShort />)}
            {!loading && shorts.length === 0 && <p>No se encontraron shorts.</p>}
          </div>
        )}

        {activeTab === 'generations' && (
          <div className="glass-panel">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
              <h2>Mis Generaciones</h2>
              <button className="btn btn-secondary" onClick={loadGenerations}>Actualizar</button>
            </div>
            <div className="generations-list">
              {generations.length === 0 ? (
                <p style={{ color: '#94a3b8' }}>No has creado ningún vídeo todavía.</p>
              ) : (
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ textAlign: 'left', borderBottom: '1px solid var(--border-color)' }}>
                      <th style={{ padding: '12px' }}>Título</th>
                      <th style={{ padding: '12px' }}>Estado</th>
                      <th style={{ padding: '12px' }}>Fecha</th>
                      <th style={{ padding: '12px' }}>Acciones</th>
                    </tr>
                  </thead>
                  <tbody>
                    {generations.map(g => (
                      <tr key={g.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                        <td style={{ padding: '12px' }}>
                          <div style={{ fontWeight: 600 }}>{g.title}</div>
                          <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>ID: {g.id}</div>
                        </td>
                        <td style={{ padding: '12px' }}>
                          <span style={{ 
                            padding: '4px 8px', 
                            borderRadius: '4px', 
                            fontSize: '0.8rem', 
                            backgroundColor: `${getStatusColor(g.status)}22`,
                            color: getStatusColor(g.status),
                            border: `1px solid ${getStatusColor(g.status)}22`
                          }}>
                            {g.status.toUpperCase()}
                          </span>
                          {g.last_error && (
                            <div style={{ fontSize: '0.7rem', color: '#ef4444', marginTop: '4px', maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={g.last_error}>
                              Error: {g.last_error}
                            </div>
                          )}
                        </td>
                        <td style={{ padding: '12px', fontSize: '0.9rem' }}>
                          {new Date(g.created_at).toLocaleDateString()}
                        </td>
                        <td style={{ padding: '12px' }}>
                          <div style={{ display: 'flex', gap: '8px' }}>
                            {['images_ready', 'rendering', 'ready', 'failed'].includes(g.status) && (
                              <button className="btn-link" style={{ color: '#a855f7' }} onClick={() => setReviewingVideoId(g.id)}>Imágenes</button>
                            )}
                            {g.status === 'ready' ? (
                              <>
                                {g.is_uploaded ? (
                                  <>
                                    <button 
                                      className="btn-link" 
                                      style={{ color: '#4ade80' }} 
                                      onClick={() => setUploadingVideoId(g.id)}
                                    >
                                      Gestionar YouTube
                                    </button>
                                    <button 
                                      className="btn-link" 
                                      style={{ color: '#94a3b8', fontSize: '0.85em' }} 
                                      onClick={async () => {
                                        if(confirm('¿Seguro que quieres restablecer el estado para volver a subirlo?')) {
                                          try {
                                            await fetch(`/api/youtube/${g.id}/reset-upload`, { method: 'POST' });
                                            if (typeof window !== 'undefined') window.location.reload();
                                          } catch (e) {
                                            alert('Error al restablecer');
                                          }
                                        }
                                      }}
                                    >
                                      Volver a subir
                                    </button>
                                  </>
                                ) : (
                                  <button 
                                    className="btn-link" 
                                    style={{ color: '#ff4444' }} 
                                    onClick={() => setUploadingVideoId(g.id)}
                                  >
                                    Subir a YouTube
                                  </button>
                                )}
                                <button className="btn-link">Ver Carpeta</button>
                              </>
                            ) : (
                              <button className="btn-link" onClick={() => { setSelectedVideo(g); setActiveTab('create'); }}>Continuar</button>
                            )}
                            <button className="btn-link" style={{ color: '#ef4444' }} onClick={() => handleDeleteVideo(g.id)}>Eliminar</button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}

        {activeTab === 'create' && (
          <VideoCreator 
            channelId={channel.id} 
            initialVideo={selectedVideo} 
            onReviewImages={(id) => setReviewingVideoId(id)}
          />
        )}

        {activeTab === 'youtube' && (
          <div>
            <div className="glass-panel" style={{ marginBottom: '24px' }}>
              <h2>Descargar audio de YouTube</h2>
              <p style={{ color: '#94a3b8', marginBottom: '24px' }}>Extrae el audio en formato MP3 para empezar a crear tu nuevo vídeo.</p>
              <div className="form-inline">
                <input 
                  type="text" 
                  value={ytUrl}
                  onChange={(e) => setYtUrl(e.target.value)}
                  placeholder="https://www.youtube.com/watch?v=..." 
                  className="full-width" 
                />
                <button className="btn btn-primary" onClick={handleDownload} disabled={downloading}>
                  {downloading ? 'Descargando...' : 'Descargar'}
                </button>
              </div>
            </div>

            <div className="glass-panel">
              <h3>Descargas Recientes</h3>
              <div style={{ marginTop: '16px' }}>
                {downloads.length === 0 ? (
                  <p style={{ color: '#94a3b8' }}>No hay descargas todavía.</p>
                ) : (
                  <ul style={{ listStyle: 'none' }}>
                    {downloads.map((file, i) => (
                      <li key={i} style={{ padding: '8px 0', borderBottom: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between' }}>
                        <span>🎵 {file}</span>
                        <button className="btn-link" style={{ fontSize: '0.8rem' }}>Transcribir</button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'transcribe' && (
          <div className="glass-panel">
            <h2>Transcripción con AI</h2>
            <p style={{ color: '#94a3b8' }}>Selecciona uno de tus audios descargados para transcribirlo.</p>
          </div>
        )}
      </div>
      {/* Image Reviewer Modal */}
      {reviewingVideoId && (
        <ImageReviewer 
          videoId={reviewingVideoId} 
          onClose={() => setReviewingVideoId(null)} 
        />
      )}
      {uploadingVideoId && (
        <VideoUploadModal 
          videoId={uploadingVideoId} 
          onClose={() => setUploadingVideoId(null)} 
        />
      )}
    </div>
  );
};

export default ChannelDashboard;
