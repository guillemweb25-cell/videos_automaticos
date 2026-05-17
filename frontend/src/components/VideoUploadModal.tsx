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
  
  // SEO options
  const [seoLanguage, setSeoLanguage] = useState('auto');
  const [seoProvider, setSeoProvider] = useState('openai');

  // Thumbnail actions
  const [thumbnailBust, setThumbnailBust] = useState(Date.now());
  const [thumbBusy, setThumbBusy] = useState<string | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const loadMetadata = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await api.getVideoMetadata(videoId);
      setMetadata(res);
      setTitle(res.title || '');
      setDescription(res.description || '');
      setTags(res.tags || '');
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
      const res = await api.regenerateYoutubeTitle(videoId, seoLanguage, seoProvider);
      setTitle(res.title);
    } catch (err) {
      setUploadStatus("Error al regenerar el título");
    } finally {
      setRegenerating(null);
    }
  };

  const handleRegenerateDescription = async () => {
    setRegenerating('description');
    try {
      const res = await api.regenerateYoutubeDescription(videoId, seoLanguage, seoProvider);
      setDescription(res.description);
    } catch (err) {
      setUploadStatus("Error al regenerar la descripción");
    } finally {
      setRegenerating(null);
    }
  };

  const handleRegenerateTags = async () => {
    setRegenerating('tags');
    try {
      const res = await api.regenerateYoutubeTags(videoId, seoLanguage, seoProvider);
      setTags(res.tags);
    } catch (err) {
      setUploadStatus("Error al regenerar las etiquetas");
    } finally {
      setRegenerating(null);
    }
  };

  const handleRegenerateThumbnail = async () => {
    setThumbBusy('regen');
    try {
      await api.generateThumbnail(videoId);
      setThumbnailBust(Date.now());
    } catch (err: any) {
      setUploadStatus(`Error al regenerar miniatura: ${err.message || ''}`);
    } finally {
      setThumbBusy(null);
    }
  };

  const handleUploadThumbnailFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setThumbBusy('upload');
    try {
      await api.uploadThumbnail(videoId, file);
      setThumbnailBust(Date.now());
    } catch (err: any) {
      setUploadStatus(`Error al subir miniatura: ${err.message || ''}`);
    } finally {
      setThumbBusy(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
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
      // status already set above via setUploadStatus
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
                  <img src={`${API_URL}${metadata.thumbnail_url}?t=${thumbnailBust}`} alt="Thumbnail" />
                </div>
                <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                  <button
                    className="yt-regen-btn"
                    onClick={handleRegenerateThumbnail}
                    disabled={!!thumbBusy}
                    style={{ flex: 1, fontSize: '0.75rem' }}
                    title="Regenerar la miniatura con IA"
                  >
                    {thumbBusy === 'regen' ? 'Generando…' : '✨ Regenerar IA'}
                  </button>
                  <button
                    className="yt-regen-btn"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={!!thumbBusy}
                    style={{ flex: 1, fontSize: '0.75rem' }}
                    title="Subir una miniatura desde archivo"
                  >
                    {thumbBusy === 'upload' ? 'Subiendo…' : '📤 Subir archivo'}
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    onChange={handleUploadThumbnailFile}
                    style={{ display: 'none' }}
                  />
                </div>
                {metadata?.is_uploaded && (
                  <p style={{ fontSize: '0.7rem', color: '#94a3b8', marginTop: '6px', lineHeight: 1.3 }}>
                    Los cambios en la miniatura se enviarán a YouTube al pulsar "Sincronizar Cambios".
                  </p>
                )}
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
              <div style={{ display: 'flex', gap: '10px', marginBottom: '16px', padding: '10px', backgroundColor: 'rgba(255,255,255,0.03)', borderRadius: '8px' }}>
                <div style={{ flex: 1 }}>
                  <label className="yt-section-label" style={{ fontSize: '0.7rem' }}>Idioma SEO</label>
                  <select
                    className="yt-select"
                    value={seoLanguage}
                    onChange={(e) => setSeoLanguage(e.target.value)}
                  >
                    <option value="auto">Auto (detectar del guion)</option>
                    <option value="es">Español</option>
                    <option value="en">Inglés</option>
                    <option value="ko">Coreano (한국어)</option>
                    <option value="ja">Japonés (日本語)</option>
                    <option value="zh">Chino (中文)</option>
                    <option value="ru">Ruso (Русский)</option>
                    <option value="ar">Árabe (العربية)</option>
                    <option value="pt">Portugués</option>
                    <option value="fr">Francés</option>
                    <option value="de">Alemán</option>
                    <option value="it">Italiano</option>
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label className="yt-section-label" style={{ fontSize: '0.7rem' }}>Motor IA</label>
                  <select 
                    className="yt-select"
                    value={seoProvider}
                    onChange={(e) => setSeoProvider(e.target.value)}
                  >
                    <option value="openai">OpenAI (GPT-4o Mini)</option>
                    <option value="grok">Grok (xAI)</option>
                  </select>
                </div>
              </div>

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
