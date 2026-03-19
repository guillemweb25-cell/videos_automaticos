import React, { useState, useEffect } from 'react';
import { api, API_URL } from '../api';
import './VideoUploadModal.css';

interface VideoUploadModalProps {
  videoId: number;
  onClose: () => void;
}

const VideoUploadModal: React.FC<VideoUploadModalProps> = ({ videoId, onClose }) => {
  const [metadata, setMetadata] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [regenerating, setRegenerating] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);

  // Form states
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState('');
  const [privacyStatus, setPrivacyStatus] = useState('private');
  const [publishAt, setPublishAt] = useState('');

  // Thumbnail regeneration states
  const [thumbPrompt, setThumbPrompt] = useState('');
  const [thumbModel, setThumbModel] = useState('gpt-image-1.5');
  const [models, setModels] = useState<any[]>([]);
  const [regeneratingThumb, setRegeneratingThumb] = useState<'prompt' | 'image' | null>(null);

  const loadMetadata = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getVideoMetadata(videoId);
      setMetadata(res);
      setTitle(res.title || '');
      setDescription(res.description || '');
      setTags(res.tags || '');

      if (res.thumbnail && res.thumbnail.visual_prompt) {
        setThumbPrompt(res.thumbnail.visual_prompt);
      }
      
      try {
        const conf = await api.getConfig();
        if (conf.leonardo_models) {
          setModels(conf.leonardo_models);
        }
      } catch (e) {
        console.error("Error loading config:", e);
      }
    } catch (err: any) {
      console.error("Error loading video metadata:", err);
      setError("No se pudo cargar la información del vídeo. Asegúrate de que el vídeo esté renderizado.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMetadata();
  }, [videoId]);

  const handleRegenerateTitle = async () => {
    setRegenerating('title');
    try {
      const res = await api.regenerateYoutubeTitle(videoId);
      setTitle(res.title);
    } catch (err) {
      alert("Error al regenerar el título");
    } finally {
      setRegenerating(null);
    }
  };

  const handleRegenerateDescription = async () => {
    setRegenerating('description');
    try {
      const res = await api.regenerateYoutubeDescription(videoId);
      setDescription(res.description);
    } catch (err) {
      alert("Error al regenerar la descripción");
    } finally {
      setRegenerating(null);
    }
  };

  const handleRegenerateTags = async () => {
    setRegenerating('tags');
    try {
      const res = await api.regenerateYoutubeTags(videoId);
      setTags(res.tags);
    } catch (err) {
      alert("Error al regenerar las etiquetas");
    } finally {
      setRegenerating(null);
    }
  };

  const handleRegenerateThumbPrompt = async () => {
    setRegeneratingThumb('prompt');
    try {
      const res = await api.regenerateThumbnailVisualPrompt(videoId);
      setThumbPrompt(res.visual_prompt);
    } catch (err: any) {
      alert("Error al regenerar prompt de miniatura");
    } finally {
      setRegeneratingThumb(null);
    }
  };

  const handleGenerateThumbnail = async () => {
    setRegeneratingThumb('image');
    try {
      const res = await api.generateThumbnail(
        videoId,
        metadata?.thumbnail?.hook || '',
        thumbPrompt,
        thumbModel,
        'QUALITY'
      );
      // Reload metadata to update thumbnail_url
      loadMetadata();
    } catch (err: any) {
      alert(err.message || 'Error al regenerar miniatura');
    } finally {
      setRegeneratingThumb(null);
    }
  };

  const handleUpload = async () => {
    setUploading(true);
    const isSync = metadata?.is_uploaded;
    setUploadStatus(isSync ? "Sincronizando con YouTube..." : "Subiendo vídeo a YouTube...");
    try {
      if (isSync) {
        await api.updateYouTubeMetadata(videoId, {
          title,
          description,
          tags
        });
        setUploadStatus("¡YouTube actualizado correctamente!");
      } else {
        const res = await api.uploadToYouTube(videoId, {
          title,
          description,
          tags,
          privacy_status: privacyStatus,
          publish_at: publishAt || undefined
        });
        setUploadStatus(`¡Vídeo subido con éxito! ID: ${res.youtube_id}`);
      }
      setTimeout(() => onClose(), 2000);
    } catch (err: any) {
      console.error(err);
      setUploadStatus(isSync ? "Error al sincronizar" : "Error al subir el vídeo");
      alert(isSync ? "Error al sincronizar con YouTube" : "Error al subir el vídeo a YouTube");
    } finally {
      setUploading(false);
    }
  };

  if (loading) return (
    <div className="yt-modal-overlay">
      <div className="yt-modal-container" style={{ maxWidth: '400px' }}>
        <div className="yt-loading-overlay">
          <div className="yt-spinner"></div>
          <p>Preparando información del vídeo...</p>
        </div>
      </div>
    </div>
  );

  if (error || !metadata) return (
    <div className="yt-modal-overlay">
      <div className="yt-modal-container" style={{ maxWidth: '400px' }}>
        <div className="yt-modal-header">
          <h2>Error</h2>
          <button className="yt-modal-close" onClick={onClose}>×</button>
        </div>
        <div className="yt-modal-content" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '3rem', marginBottom: '16px' }}>⚠️</div>
          <p style={{ color: '#ef4444', marginBottom: '20px' }}>{error || "No se encontraron metadatos."}</p>
          <button className="btn btn-secondary" onClick={onClose} style={{ width: '100%' }}>Cerrar</button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="yt-modal-overlay">
      <div className="yt-modal-container">
        {/* Header */}
        <div className="yt-modal-header" style={{ background: 'linear-gradient(to right, rgba(220, 38, 38, 0.1), transparent)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <svg style={{ width: '32px', height: '32px', color: '#dc2626' }} fill="currentColor" viewBox="0 0 24 24">
              <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z"/>
            </svg>
            <h2>{metadata?.is_uploaded ? 'Gestionar en YouTube' : 'Publicar en YouTube'}</h2>
          </div>
          <button className="yt-modal-close" onClick={onClose} title="Cerrar">×</button>
        </div>

        {/* Content */}
        <div className="yt-modal-content">
          <p style={{ color: '#94a3b8', marginBottom: '24px' }}>
            {metadata?.is_uploaded 
              ? `Este vídeo ya está en YouTube (ID: ${metadata.youtube_video_id}). Sincroniza los cambios de SEO y miniatura.`
              : 'Configura el SEO y la visibilidad de tu vídeo antes de subirlo.'}
          </p>

          <div className="yt-modal-grid">
            {/* Left Column */}
            <div className="yt-preview-section">
              <div>
                <span className="yt-section-label">Miniatura Final</span>
                <div className="yt-thumbnail-wrapper">
                  <img src={`${API_URL}${metadata.thumbnail_url}?t=${Date.now()}`} alt="Thumbnail" />
                </div>
                
                {/* Thumbnail regeneration controls */}
                <div style={{ marginTop: '16px', background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', alignItems: 'center' }}>
                    <span className="yt-section-label" style={{ fontSize: '0.75rem', marginBottom: 0 }}>Prompt Miniatura</span>
                    <button 
                      className={`yt-action-btn ${regeneratingThumb === 'prompt' ? 'loading' : ''}`}
                      onClick={handleRegenerateThumbPrompt}
                      disabled={!!regeneratingThumb}
                      style={{ fontSize: '0.7rem', padding: '2px 8px' }}
                    >
                      {regeneratingThumb === 'prompt' ? '...' : '✨ Generar con IA'}
                    </button>
                  </div>
                  <textarea
                    className="yt-textarea"
                    value={thumbPrompt}
                    onChange={(e) => setThumbPrompt(e.target.value)}
                    rows={3}
                    style={{ fontSize: '0.8rem', minHeight: '60px', padding: '8px' }}
                    placeholder="Describe la miniatura..."
                  />
                  <div style={{ marginTop: '12px' }}>
                    <select
                      className="yt-select"
                      value={thumbModel}
                      onChange={(e) => setThumbModel(e.target.value)}
                      style={{ fontSize: '0.8rem', padding: '6px', marginBottom: '12px', width: '100%' }}
                    >
                      {models.map(m => (
                        <option key={m.id} value={m.id}>{m.name}</option>
                      ))}
                    </select>
                    <button 
                      className="btn" 
                      onClick={handleGenerateThumbnail}
                      disabled={!!regeneratingThumb || !thumbPrompt}
                      style={{ width: '100%', padding: '8px', fontSize: '0.85rem' }}
                    >
                      {regeneratingThumb === 'image' ? 'Generando miniatura...' : '🎨 Renderizar Miniatura'}
                    </button>
                  </div>
                </div>
              </div>

              <div className="yt-form-group" style={{ padding: '16px', backgroundColor: 'rgba(255,255,255,0.03)', borderRadius: '12px' }}>
                <span className="yt-section-label" style={{ color: '#fff', fontSize: '0.8rem', marginBottom: '16px' }}>⚙️ Ajustes de Publicación</span>
                <div className="yt-settings-row" style={{ opacity: metadata?.is_uploaded ? 0.5 : 1, pointerEvents: metadata?.is_uploaded ? 'none' : 'auto' }}>
                  <div>
                    <label className="yt-section-label" style={{ fontSize: '0.7rem' }}>Visibilidad</label>
                    <select 
                      className="yt-select"
                      value={privacyStatus}
                      onChange={(e) => setPrivacyStatus(e.target.value)}
                    >
                      <option value="private">Privado</option>
                      <option value="unlisted">Oculto</option>
                      <option value="public">Público</option>
                    </select>
                  </div>
                  <div>
                    <label className="yt-section-label" style={{ fontSize: '0.7rem' }}>Programar</label>
                    <input 
                      type="datetime-local" 
                      className="yt-input"
                      value={publishAt}
                      onChange={(e) => setPublishAt(e.target.value)}
                      title="Opcional"
                    />
                  </div>
                </div>
                {metadata?.is_uploaded && (
                  <p style={{ fontSize: '0.65rem', color: '#fbbf24', marginTop: '10px' }}>
                    * Los ajustes de visibilidad ya no se pueden cambiar desde aquí.
                  </p>
                )}
                <p style={{ fontSize: '0.65rem', color: '#64748b', marginTop: '10px' }}>
                  * La programación publicará el vídeo automáticamente en la fecha elegida.
                </p>
              </div>
            </div>

            {/* Right Column */}
            <div className="yt-metadata-section">
              <div className="yt-form-group">
                <div className="yt-input-header">
                  <label className="yt-section-label">Título (SEO)</label>
                  <button 
                    className="yt-regen-btn"
                    onClick={handleRegenerateTitle}
                    disabled={!!regenerating}
                  >
                    {regenerating === 'title' ? 'Generando...' : '✨ IA: Título Gancho'}
                  </button>
                </div>
                <input 
                  className="yt-input"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  maxLength={100}
                />
                <div style={{ fontSize: '10px', textAlign: 'right', color: '#64748b', marginTop: '4px' }}>{title.length}/100</div>
              </div>

              <div className="yt-form-group">
                <div className="yt-input-header">
                  <label className="yt-section-label">Descripción (Puntos Clave)</label>
                  <button 
                    className="yt-regen-btn"
                    onClick={handleRegenerateDescription}
                    disabled={!!regenerating}
                  >
                    {regenerating === 'description' ? 'Generando...' : '✨ IA: Resumir'}
                  </button>
                </div>
                <textarea 
                  className="yt-textarea"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  style={{ height: '140px' }}
                />
              </div>

              <div className="yt-form-group">
                <div className="yt-input-header">
                  <label className="yt-section-label">Etiquetas (Preguntas)</label>
                  <button 
                    className="yt-regen-btn"
                    onClick={handleRegenerateTags}
                    disabled={!!regenerating}
                  >
                    {regenerating === 'tags' ? 'Generando...' : '✨ IA: Etiquetas'}
                  </button>
                </div>
                <input 
                  className="yt-input"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  maxLength={500}
                />
                <div style={{ fontSize: '10px', textAlign: 'right', color: '#64748b', marginTop: '4px' }}>{tags.length}/500</div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="yt-modal-footer">
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {uploadStatus && (
              <span style={{ fontSize: '0.85rem', color: uploadStatus.includes('Error') ? '#f87171' : '#4ade80' }}>
                {uploadStatus}
              </span>
            )}
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            <button className="tab-btn" onClick={onClose} disabled={uploading}>
              Cancelar
            </button>
            <button 
              className="yt-upload-btn"
              onClick={handleUpload}
              disabled={uploading || !title}
            >
              {uploading ? (
                <>
                  <div className="yt-spinner" style={{ width: '18px', height: '18px', borderTopColor: '#fff' }}></div>
                  <span>Subiendo...</span>
                </>
              ) : (
                <>
                  <span>{metadata?.is_uploaded ? '🔄 Sincronizar Cambios' : '🚀 Publicar en YouTube'}</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VideoUploadModal;
