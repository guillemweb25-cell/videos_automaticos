import React, { useState, useEffect } from 'react';
import { api, type ChannelResponse, type YouTubeChannelInfo, type YouTubeVideo, type VideoResponse } from '../api';
import VideoCreator from './VideoCreator';
import ImageReviewer from './ImageReviewer';
import VideoUploadModal from './VideoUploadModal';

interface ChannelDashboardProps {
  channel: ChannelResponse;
  onBack: () => void;
}

const ChannelDashboard: React.FC<ChannelDashboardProps> = ({ channel }) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'videos' | 'shorts' | 'create' | 'youtube' | 'transcribe' | 'generations'>('overview');
  const [ytInfo, setYtInfo] = useState<YouTubeChannelInfo | null>(null);
  const [videos, setVideos] = useState<YouTubeVideo[]>([]);
  const [shorts, setShorts] = useState<YouTubeVideo[]>([]);
  const [generations, setGenerations] = useState<VideoResponse[]>([]);
  const [downloads, setDownloads] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [ytUrl, setYtUrl] = useState('');
  const [error, setError] = useState('');
  const [selectedVideo, setSelectedVideo] = useState<VideoResponse | null>(null);
  const [reviewingVideoId, setReviewingVideoId] = useState<number | null>(null);
  const [uploadingVideoId, setUploadingVideoId] = useState<number | null>(null);

  const [editCredsDir, setEditCredsDir] = useState(channel.creds_dir || '');

  useEffect(() => {
    if (channel.creds_dir) {
      loadYouTubeData();
    } else {
      setYtInfo(null);
      setVideos([]);
      setShorts([]);
    }
    setEditCredsDir(channel.creds_dir || '');
    loadDownloads();
    loadGenerations();
    setSelectedVideo(null);
  }, [channel]);

  const loadYouTubeData = async () => {
    setLoading(true);
    setError('');
    try {
      const [info, vids, shs] = await Promise.all([
        api.getYouTubeChannelInfo(channel.id),
        api.getYouTubeVideos(channel.id),
        api.getYouTubeShorts(channel.id)
      ]);
      setYtInfo(info);
      setVideos(vids);
      setShorts(shs);
    } catch (err: any) {
      console.error(err);
      setError('No se pudo cargar la información de YouTube. Verifica las credenciales.');
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

  const handleUpdateCreds = async () => {
    setLoading(true);
    try {
      await api.updateChannel(channel.id, { creds_dir: editCredsDir });
      await loadYouTubeData();
      alert('Credenciales activadas correctamente');
    } catch (err: any) {
      alert('Error al actualizar: ' + err.message);
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
                <button className="btn btn-secondary" onClick={handleUpdateCreds} disabled={loading}>
                  {loading ? 'Guardando...' : 'Activar Credenciales'}
                </button>
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
                                <button className="btn-link" style={{ color: '#ff4444' }} onClick={() => setUploadingVideoId(g.id)}>Subir a YouTube</button>
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
          <VideoCreator channelId={channel.id} initialVideo={selectedVideo} />
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
