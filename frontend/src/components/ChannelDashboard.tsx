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
  const [videoSort, setVideoSort] = useState<'date' | 'views'>('date');
  const [videoView, setVideoView] = useState<'grid' | 'list' | 'text'>('grid');
  const [titlesCopied, setTitlesCopied] = useState(false);
  const [videosLoadedExtended, setVideosLoadedExtended] = useState(false);
  const [generations, setGenerations] = useState<VideoResponse[]>([]);
  const [downloads, setDownloads] = useState<string[]>([]);
  const [musicFiles, setMusicFiles] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploadingMusic, setUploadingMusic] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [ytUrl, setYtUrl] = useState('');
  const [error, setError] = useState('');
  const [updateStatus, setUpdateStatus] = useState<{msg: string, type: 'success' | 'error'} | null>(null);

  const [styleGuideExists, setStyleGuideExists] = useState(false);
  const [uploadingStyleGuide, setUploadingStyleGuide] = useState(false);

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
    loadMusicFiles();
    loadStyleGuideStatus();
    setSelectedVideo(null);

    // Check for OAuth callback in URL
    const urlParams = new URLSearchParams(window.location.search);
    const code = urlParams.get('code');
    if (code) {
      // Clear URL params immediately
      window.history.replaceState({}, document.title, window.location.pathname);
      handleOAuthCallback(code);
    }
  }, [channel]);

  const handleOAuthCallback = async (code: string) => {
    setLoading(true);
    try {
      // Use the origin as a predictable redirect URI (with trailing slash)
      const redirectUri = window.location.origin + "/";
      console.log("Finishing OAuth with redirectUri:", redirectUri);
      await api.finishYouTubeOAuth(channel.id, code, redirectUri);
      setUpdateStatus({msg: '¡Cuenta vinculada correctamente!', type: 'success'});
      loadYouTubeData();
    } catch (err: any) {
      setError('Error al vincular cuenta: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleStartOAuth = async () => {
    try {
        // We use the origin to make it easier to configure in Google Cloud
        const redirectUri = window.location.origin + "/";
        console.log("Starting OAuth with redirectUri:", redirectUri);
        const res = await api.getYouTubeAuthUrl(channel.id, redirectUri);
        window.location.href = res.auth_url;
    } catch (err: any) {
        setError("Error al iniciar OAuth. Asegúrate de haber subido el client_secret.json correcto.");
    }
  };

  const handleUploadClientSecret = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    setLoading(true);
    try {
      await api.uploadYouTubeClientSecret(channel.id, file);
      setUpdateStatus({msg: 'Archivo client_secret.json subido correctamente!', type: 'success'});
    } catch (err: any) {
      setError('Error al subir el archivo: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const loadStyleGuideStatus = async () => {
    try {
      const res = await api.checkStyleGuide(channel.id);
      setStyleGuideExists(res.exists);
    } catch(err) {
      console.error(err);
    }
  };


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
      setVideosLoadedExtended(false);
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

  const loadVideosExtended = async () => {
    setLoading(true);
    setError('');
    try {
      const vids = await api.getYouTubeVideos(channel.id, { maxResults: 500, minSeconds: 180 });
      setVideos(vids);
      setVideosLoadedExtended(true);
    } catch (err: any) {
      console.error(err);
      setError('No se pudieron cargar los vídeos extendidos.');
    } finally {
      setLoading(false);
    }
  };

  const handleVideoSortChange = (next: 'date' | 'views') => {
    setVideoSort(next);
    if (next === 'views' && !videosLoadedExtended) {
      loadVideosExtended();
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

  const loadMusicFiles = async () => {
    try {
      const files = await api.getChannelMusic(channel.id);
      setMusicFiles(files);
    } catch (err) {
      console.error(err);
    }
  };

  const handleMusicUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    if (!file.name.toLowerCase().endsWith('.mp3')) {
      alert("Solo se permiten archivos MP3.");
      return;
    }
    setUploadingMusic(true);
    try {
      await api.uploadChannelMusic(channel.id, file);
      await loadMusicFiles();
    } catch (err: any) {
      alert("Error subiendo música: " + err.message);
    } finally {
      setUploadingMusic(false);
      e.target.value = ''; // clear input
    }
  };

  const handleMusicDelete = async (filename: string) => {
    if (!confirm(`¿Eliminar ${filename}?`)) return;
    try {
      await api.deleteChannelMusic(channel.id, filename);
      await loadMusicFiles();
    } catch (err: any) {
      alert("Error al eliminar: " + err.message);
    }
  };

  const handleStyleGuideUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    setUploadingStyleGuide(true);
    try {
      await api.uploadStyleGuide(channel.id, file);
      await loadStyleGuideStatus();
    } catch (err: any) {
      alert("Error subiendo style-guide: " + err.message);
    } finally {
      setUploadingStyleGuide(false);
      e.target.value = '';
    }
  };

  const handleStyleGuideDelete = async () => {
    if (!confirm(`¿Eliminar el style-guide actual para este canal?`)) return;
    try {
      await api.deleteStyleGuide(channel.id);
      await loadStyleGuideStatus();
    } catch(err: any) {
      alert("Error al eliminar: " + err.message);
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

  const formatViews = (n: number) => {
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
    return String(n);
  };

  const formatDuration = (sec?: number) => {
    if (!sec || sec <= 0) return '';
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return h > 0
      ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
      : `${m}:${String(s).padStart(2, '0')}`;
  };

  const VideoCard = ({ video, isShort = false }: { video: YouTubeVideo, isShort?: boolean }) => {
    const views = typeof video.view_count === 'number' ? video.view_count : 0;
    return (
      <div className="video-card" onClick={() => setYtUrl(`https://www.youtube.com/watch?v=${video.id}`)}>
        <div className={`video-thumbnail ${isShort ? 'short-thumbnail' : ''}`}>
          <img src={video.thumbnail} alt={video.title} />
          <div className="view-badge">
            {video.view_count !== undefined
              ? `${formatViews(views)} vistas`
              : new Date(video.published_at).toLocaleDateString()}
          </div>
        </div>
        <div className="video-info">
          <h4>{video.title}</h4>
        </div>
      </div>
    );
  };

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
              <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '20px', marginTop: '20px' }}>
                <div style={{ backgroundColor: 'rgba(37, 99, 235, 0.05)', padding: '24px', borderRadius: '12px', border: '1px solid rgba(37, 99, 235, 0.2)' }}>
                  <h4 style={{ marginBottom: '12px', fontSize: '1.1rem', color: '#60a5fa', fontWeight: 'bold' }}>Vincular cuenta de YouTube</h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                    <div>
                      <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: '8px' }}>1. Selecciona tu archivo <b>client_secret.json</b>:</p>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <label className="btn btn-secondary" style={{ cursor: 'pointer', margin: 0 }}>
                           {loading ? 'Subiendo...' : 'Seleccionar archivo'}
                           <input 
                            type="file" 
                            accept=".json" 
                            onChange={handleUploadClientSecret}
                            style={{ display: 'none' }}
                          />
                        </label>
                        <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                           {ytInfo ? '✅ Cuenta vinculada: ' + ytInfo.snippet.title : 'No vinculado'}
                        </span>
                      </div>
                    </div>
                    <div style={{ paddingTop: '20px', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
                      <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginBottom: '16px' }}>2. Una vez subido, autoriza la cuenta:</p>
                      <button
                        onClick={handleStartOAuth}
                        className="btn"
                        style={{ 
                          backgroundColor: '#fff', 
                          color: '#000', 
                          fontWeight: 'bold',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '10px',
                          padding: '12px 24px',
                          borderRadius: '10px',
                          width: 'fit-content'
                        }}
                      >
                        <svg viewBox="0 0 24 24" width="20" height="20" xmlns="http://www.w3.org/2000/svg"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-1 .67-2.28 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.66l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/><path d="M1 1h22v22H1z" fill="none"/></svg>
                        Vincular con Google
                      </button>
                    </div>
                  </div>
                </div>
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
                <h4 style={{ marginBottom: '8px' }}>Guía de Estilo (.md)</h4>
                <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '12px' }}>
                  Sube un archivo de texto con las guías de estilo. Será renombrado a <b>style-guide.md</b> automáticamente.
                </p>
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    {styleGuideExists ? (
                      <span style={{ color: '#4ade80' }}>✅ <b>style-guide.md</b> subido y activo.</span>
                    ) : (
                      <span style={{ color: '#94a3b8' }}>❌ No hay guía de estilo configurada.</span>
                    )}
                  </div>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <label className="btn btn-secondary" style={{ cursor: 'pointer', display: 'inline-block', margin: 0 }}>
                      {uploadingStyleGuide ? 'Subiendo...' : 'Subir o Reemplazar (.md)'}
                      <input type="file" accept=".md,.txt" style={{ display: 'none' }} onChange={handleStyleGuideUpload} disabled={uploadingStyleGuide} />
                    </label>
                    {styleGuideExists && (
                      <button className="btn-link" style={{ color: '#ef4444', marginLeft: '12px' }} onClick={handleStyleGuideDelete}>Eliminar</button>
                    )}
                  </div>
                </div>
              </div>

              <div style={{ marginTop: '24px' }}>
                <h4 style={{ marginBottom: '8px' }}>Música de Fondo (MP3)</h4>
                <p style={{ color: '#94a3b8', fontSize: '0.9rem', marginBottom: '12px' }}>
                  Sube archivos MP3 que se utilizarán aleatoriamente como música de fondo al renderizar los vídeos de este canal.
                </p>
                <div style={{ background: 'rgba(0,0,0,0.2)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                  <div style={{ marginBottom: '16px' }}>
                    <label className="btn btn-secondary" style={{ cursor: 'pointer', display: 'inline-block' }}>
                      {uploadingMusic ? 'Subiendo...' : 'Subir MP3'}
                      <input type="file" accept=".mp3" style={{ display: 'none' }} onChange={handleMusicUpload} disabled={uploadingMusic} />
                    </label>
                  </div>
                  {musicFiles.length === 0 ? (
                    <div style={{ fontSize: '0.85rem', color: '#94a3b8' }}>No hay música de fondo configurada para este canal.</div>
                  ) : (
                    <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
                      {musicFiles.map(file => (
                        <li key={file} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: '1px solid rgba(255,255,255,0.05)', fontSize: '0.9rem' }}>
                          <span style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            🎵 {file}
                            <audio controls style={{ height: '30px' }} src={api.getChannelMusicUrl(channel.id, file)} preload="none" />
                          </span>
                          <button className="btn-link" style={{ color: '#ef4444', padding: 0, fontSize: '0.85rem' }} onClick={() => handleMusicDelete(file)}>Eliminar</button>
                        </li>
                      ))}
                    </ul>
                  )}
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

        {activeTab === 'videos' && (() => {
          const sortedVideos = videoSort === 'views'
            ? [...videos].sort((a, b) => (b.view_count ?? 0) - (a.view_count ?? 0))
            : videos;
          return (
            <div>
              <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
                <span style={{ fontSize: '0.9rem', opacity: 0.8 }}>Ordenar:</span>
                <button
                  className={`btn ${videoSort === 'date' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => handleVideoSortChange('date')}
                >
                  📅 Recientes
                </button>
                <button
                  className={`btn ${videoSort === 'views' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => handleVideoSortChange('views')}
                >
                  👁 Más vistos
                </button>

                <span style={{ fontSize: '0.9rem', opacity: 0.8, marginLeft: '16px' }}>Vista:</span>
                <button
                  className={`btn ${videoView === 'grid' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setVideoView('grid')}
                >
                  🔲 Cuadrícula
                </button>
                <button
                  className={`btn ${videoView === 'list' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setVideoView('list')}
                >
                  📋 Lista
                </button>
                <button
                  className={`btn ${videoView === 'text' ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setVideoView('text')}
                >
                  📝 Texto
                </button>

                {videoSort === 'views' && videosLoadedExtended && (
                  <span style={{ fontSize: '0.85rem', opacity: 0.7, marginLeft: 'auto' }}>
                    Mostrando {videos.length} vídeos largos (≥180s)
                  </span>
                )}
              </div>

              {loading ? (
                <p>Cargando vídeos...</p>
              ) : videos.length === 0 ? (
                <p>No se encontraron vídeos.</p>
              ) : videoView === 'grid' ? (
                <div className="video-grid">
                  {sortedVideos.map(v => <VideoCard key={v.id} video={v} />)}
                </div>
              ) : videoView === 'list' ? (
                <div className="video-list">
                  {sortedVideos.map((v, idx) => (
                    <div
                      key={v.id}
                      className="video-row"
                      onClick={() => window.open(`https://www.youtube.com/watch?v=${v.id}`, '_blank')}
                    >
                      {videoSort === 'views' && <div className="rank">#{idx + 1}</div>}
                      <div className="thumb">
                        <img src={v.thumbnail} alt={v.title} />
                      </div>
                      <div className="meta">
                        <div className="title">{v.title}</div>
                        <div className="stats">
                          <span>👁 {formatViews(v.view_count ?? 0)} vistas</span>
                          {v.duration_seconds ? <span>⏱ {formatDuration(v.duration_seconds)}</span> : null}
                          <span>📅 {new Date(v.published_at).toLocaleDateString()}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (() => {
                const textBlock = sortedVideos
                  .map((v, i) => `${i + 1}. ${v.title} — ${formatViews(v.view_count ?? 0)} vistas`)
                  .join('\n');
                return (
                  <div>
                    <div style={{ marginBottom: '12px', display: 'flex', gap: '8px', alignItems: 'center' }}>
                      <button
                        className="btn btn-primary"
                        onClick={async () => {
                          try {
                            await navigator.clipboard.writeText(textBlock);
                            setTitlesCopied(true);
                            setTimeout(() => setTitlesCopied(false), 2000);
                          } catch {
                            alert('No se pudo copiar al portapapeles');
                          }
                        }}
                      >
                        {titlesCopied ? '✅ Copiado' : '📋 Copiar lista'}
                      </button>
                      <span style={{ fontSize: '0.85rem', opacity: 0.7 }}>
                        {sortedVideos.length} títulos · ordenados {videoSort === 'views' ? 'por vistas' : 'por fecha'}
                      </span>
                    </div>
                    <textarea
                      readOnly
                      value={textBlock}
                      style={{
                        width: '100%',
                        minHeight: '420px',
                        padding: '12px',
                        background: 'var(--card-bg)',
                        border: '1px solid var(--border-color)',
                        borderRadius: '8px',
                        color: 'inherit',
                        fontFamily: 'monospace',
                        fontSize: '0.9rem',
                        lineHeight: '1.6',
                        resize: 'vertical',
                      }}
                      onFocus={e => e.currentTarget.select()}
                    />
                  </div>
                );
              })()}
            </div>
          );
        })()}

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
                                            await api.resetUploadState(g.id);
                                            if (typeof window !== 'undefined') window.location.reload();
                                          } catch (e: any) {
                                            alert(e.message || 'Error al restablecer');
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
