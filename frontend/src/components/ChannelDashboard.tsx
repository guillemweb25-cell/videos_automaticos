import React, { useState, useEffect } from 'react';
import { api, type ChannelResponse, type YouTubeChannelInfo, type YouTubeVideo } from '../api';

interface ChannelDashboardProps {
  channel: ChannelResponse;
  onBack: () => void;
}

const ChannelDashboard: React.FC<ChannelDashboardProps> = ({ channel }) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'videos' | 'shorts' | 'youtube' | 'transcribe'>('overview');
  const [ytInfo, setYtInfo] = useState<YouTubeChannelInfo | null>(null);
  const [videos, setVideos] = useState<YouTubeVideo[]>([]);
  const [shorts, setShorts] = useState<YouTubeVideo[]>([]);
  const [downloads, setDownloads] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [ytUrl, setYtUrl] = useState('');
  const [error, setError] = useState('');

  // Local state for creds_dir editing
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

  return (
    <div className="channel-dashboard">
      <div className="dashboard-tabs">
        <button className={`tab-btn ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>General</button>
        <button className={`tab-btn ${activeTab === 'videos' ? 'active' : ''}`} onClick={() => setActiveTab('videos')}>Vídeos</button>
        <button className={`tab-btn ${activeTab === 'shorts' ? 'active' : ''}`} onClick={() => setActiveTab('shorts')}>Shorts</button>
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
    </div>
  );
};

export default ChannelDashboard;
