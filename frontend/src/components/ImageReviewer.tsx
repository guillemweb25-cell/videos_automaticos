import React, { useState, useEffect } from 'react';
import { api, API_URL } from '../api';

interface ImageReviewerProps {
  videoId: number;
  onClose: () => void;
}

const ImageReviewer: React.FC<ImageReviewerProps> = ({ videoId, onClose }) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [regenerating, setRegenerating] = useState<string | null>(null);
  const [rendering, setRendering] = useState(false);
  const [prompts, setPrompts] = useState<{ [key: string]: string }>({});
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
  const [thumbnailHook, setThumbnailHook] = useState('');
  const [thumbnailVisualPrompt, setThumbnailVisualPrompt] = useState('');
  const [thumbnailRegenerating, setThumbnailRegenerating] = useState(false);
  const [leonardoModels, setLeonardoModels] = useState<any[]>([]);
  const [selectedModel, setSelectedModel] = useState('de7d3faf-762f-48e0-b3b7-9d0ac3a3fcf3'); // Default Phoenix
  const [uploading, setUploading] = useState(false);

  const loadData = async () => {
    try {
      setLoading(true);
      const res = await api.getImagesData(videoId);
      setData(res);
      
      // Initialize prompts state
      const initialPrompts: { [key: string]: string } = {};
      res.items?.forEach((item: any) => {
        item.prompts?.forEach((p: any) => {
          initialPrompts[`${item.paragraph_id}_${p.id}`] = p.prompt;
        });
      });
      setPrompts(initialPrompts);
      setThumbnailUrl(res.thumbnail_url || null);
      setThumbnailHook(res.thumbnail?.hook || '');
      setThumbnailVisualPrompt(res.thumbnail?.visual_prompt || '');

      // Load models
      const config = await api.getConfig() as any;
      setLeonardoModels(config.leonardo_models || []);
    } catch (err) {
      console.error("Error loading data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [videoId]);

  const handleRegeneratePrompt = async (paraId: number, imgId: number) => {
    const key = `${paraId}_${imgId}`;
    setRegenerating(key);
    try {
      const res = await api.regeneratePrompt(videoId, paraId, imgId);
      if (res.ok) {
        setPrompts({ ...prompts, [key]: res.prompt });
      }
    } catch (error) {
      console.error("Error regenerating prompt:", error);
      alert("Error al regenerar el prompt con IA");
    } finally {
      setRegenerating(null);
    }
  };

  const handleRegenerate = async (paraId: number, imgId: number) => {
    const key = `${paraId}_${imgId}`;
    const prompt = prompts[key];
    setRegenerating(key);
    try {
      const res = await api.regenerateImage(videoId, paraId, imgId, prompt, selectedModel);
      if (res.ok) {
        const newData = { ...data };
        for (const item of newData.items) {
          if (item.paragraph_id === paraId) {
            for (const p of item.prompts) {
              if (p.id === imgId) {
                p.url = res.url;
              }
            }
          }
        }
        setData(newData);
      }
    } catch (error) {
      console.error("Error regenerating image:", error);
      alert("Error al regenerar la imagen");
    } finally {
      setRegenerating(null);
    }
  };

  const handleRender = async () => {
    try {
      setRendering(true);
      await api.renderVideo(videoId);
      alert("Vídeo renderizado correctamente con las nuevas imágenes.");
      onClose();
    } catch (err) {
      alert("Error al renderizar: " + err);
    } finally {
      setRendering(false);
    }
  };

  const handleRegenerateThumbnailHook = async () => {
    setThumbnailRegenerating(true);
    try {
      const res = await api.regenerateThumbnailHook(videoId);
      if (res.ok) {
        setThumbnailHook(res.hook);
      }
    } catch (error) {
      console.error("Error regenerating hook:", error);
      alert("Error al regenerar el gancho AI");
    } finally {
      setThumbnailRegenerating(false);
    }
  };

  const handleRegenerateThumbnailVisualPrompt = async () => {
    setThumbnailRegenerating(true);
    try {
      const res = await api.regenerateThumbnailVisualPrompt(videoId);
      if (res.ok) {
        setThumbnailVisualPrompt(res.visual_prompt);
      }
    } catch (error) {
      console.error("Error regenerating visual prompt:", error);
      alert("Error al regenerar el prompt visual");
    } finally {
      setThumbnailRegenerating(false);
    }
  };

  const handleGenerateThumbnailImage = async () => {
    setThumbnailRegenerating(true);
    try {
      const res = await api.generateThumbnail(videoId, thumbnailHook, thumbnailVisualPrompt, selectedModel);
      if (res.ok) {
        setThumbnailUrl(res.url);
      }
    } catch (error) {
      console.error("Error generating thumbnail:", error);
      alert("Error al generar la miniatura");
    } finally {
      setThumbnailRegenerating(false);
    }
  };

  const handleUploadThumbnail = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const res = await api.uploadThumbnail(videoId, file);
      if (res.ok) {
        setThumbnailUrl(res.url);
        alert("Miniatura subida correctamente");
      }
    } catch (error) {
      console.error("Error uploading thumbnail:", error);
      alert("Error al subir la miniatura");
    } finally {
      setUploading(false);
    }
  };

  if (loading) return <div style={{ padding: '80px', textAlign: 'center', color: 'white' }}>Cargando imágenes...</div>;

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      zIndex: 100,
      backgroundColor: 'rgba(0,0,0,0.95)',
      padding: '40px',
      overflowY: 'auto',
      color: 'white',
      fontFamily: 'sans-serif'
    }}>
      <div style={{ maxWidth: '1100px', margin: '0 auto' }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '32px',
          paddingBottom: '16px',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
          position: 'sticky',
          top: 0,
          backgroundColor: 'rgba(0,0,0,0.9)',
          zIndex: 10
        }}>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 'bold' }}>Revisión de Imágenes - Vídeo #{videoId}</h2>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.7rem', color: '#9ca3af', fontWeight: 'bold' }}>MODELO LEONARDO</label>
              <select 
                value={selectedModel}
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setSelectedModel(e.target.value)}
                style={{
                  backgroundColor: '#1f2937',
                  color: 'white',
                  border: '1px solid #a855f7',
                  borderRadius: '6px',
                  padding: '4px 8px',
                  fontSize: '0.8rem',
                  outline: 'none'
                }}
              >
                {leonardoModels.map((m: any) => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
            </div>
            <button 
              onClick={handleRender}
              disabled={rendering}
              style={{
                backgroundColor: '#16a34a',
                color: 'white',
                padding: '8px 20px',
                borderRadius: '8px',
                fontWeight: 'bold',
                border: 'none',
                cursor: 'pointer',
                opacity: rendering ? 0.5 : 1
              }}
            >
              {rendering ? 'Renderizando...' : 'Finalizar y Renderizar'}
            </button>
            <button 
              onClick={onClose}
              style={{
                backgroundColor: '#374151',
                color: 'white',
                padding: '8px 20px',
                borderRadius: '8px',
                fontWeight: 'bold',
                border: 'none',
                cursor: 'pointer'
              }}
            >
              Cerrar
            </button>
          </div>
        </div>

        {data?.items?.map((item: any) => (
          <div key={item.paragraph_id} style={{ marginBottom: '48px', paddingLeft: '24px', borderLeft: '4px solid #a855f7' }}>
            <h3 style={{ fontSize: '1.25rem', color: '#d8b4fe', marginBottom: '16px' }}>Párrafo {item.paragraph_id} ({item.seconds.toFixed(1)}s)</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '32px' }}>
              {item.prompts?.map((p: any) => {
                const key = `${item.paragraph_id}_${p.id}`;
                return (
                  <div key={p.id} style={{ 
                    backgroundColor: 'rgba(255,255,255,0.05)', 
                    borderRadius: '12px', 
                    padding: '16px',
                    border: '1px solid rgba(255,255,255,0.1)'
                  }}>
                    <div style={{ 
                      backgroundColor: '#1f2937', 
                      borderRadius: '8px', 
                      overflow: 'hidden', 
                      position: 'relative',
                      marginBottom: '16px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      minHeight: '300px',
                      maxHeight: '600px'
                    }}>
                      <img 
                        src={`${API_URL}${p.url}`} 
                        alt={`Paragraph ${item.paragraph_id} Image ${p.id}`}
                        style={{ 
                          maxWidth: '100%', 
                          maxHeight: '600px', 
                          objectFit: 'contain',
                          display: 'block'
                        }}
                      />
                      {regenerating === key && (
                        <div style={{
                          position: 'absolute',
                          inset: 0,
                          backgroundColor: 'rgba(0,0,0,0.6)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center'
                        }}>
                          <div className="spinner"></div>
                          <span style={{fontWeight: 'bold'}}>Procesando...</span>
                        </div>
                      )}
                    </div>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <label style={{ fontSize: '0.75rem', color: '#9ca3af', fontWeight: 'bold' }}>Prompt Personalizado</label>
                        <button
                          onClick={() => handleRegeneratePrompt(item.paragraph_id, p.id)}
                          disabled={!!regenerating}
                          style={{
                            background: 'none',
                            color: '#a855f7',
                            border: 'none',
                            fontSize: '0.75rem',
                            fontWeight: 'bold',
                            cursor: 'pointer',
                            textDecoration: 'underline'
                          }}
                        >
                          Generar nuevo con IA
                        </button>
                      </div>
                      <textarea
                        value={prompts[key] || ''}
                        onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setPrompts({ ...prompts, [key]: e.target.value })}
                        style={{
                          backgroundColor: 'rgba(0,0,0,0.3)',
                          border: '1px solid rgba(255,255,255,0.1)',
                          borderRadius: '8px',
                          padding: '12px',
                          color: '#e5e7eb',
                          fontSize: '0.875rem',
                          height: '100px',
                          resize: 'none',
                          outline: 'none'
                        }}
                      />
                      <button
                        onClick={() => handleRegenerate(item.paragraph_id, p.id)}
                        disabled={!!regenerating}
                        style={{
                          backgroundColor: '#9333ea',
                          color: 'white',
                          padding: '10px',
                          borderRadius: '8px',
                          fontWeight: 'bold',
                          cursor: 'pointer',
                          border: 'none',
                          opacity: regenerating ? 0.5 : 1,
                          marginTop: '8px'
                        }}
                      >
                        Regenerar esta imagen
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}

        {/* Thumbnail Section */}
        <div style={{ marginTop: '64px', padding: '32px', backgroundColor: 'rgba(168, 85, 247, 0.1)', borderRadius: '16px', border: '2px dashed #a855f7' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
            <h3 style={{ fontSize: '1.5rem', color: '#d8b4fe', margin: 0 }}>🖼️ Miniatura del Vídeo</h3>
            <span style={{ fontSize: '0.875rem', color: '#9ca3af' }}>Se usará como pantalla final y para Shorts</span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '32px' }}>
            <div style={{ 
              backgroundColor: '#1f2937', 
              borderRadius: '12px', 
              overflow: 'hidden', 
              minHeight: '400px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '1px solid rgba(255,255,255,0.1)',
              position: 'relative'
            }}>
              {thumbnailUrl ? (
                <img 
                  src={`${API_URL}${thumbnailUrl}`} 
                  alt="Video Thumbnail"
                  style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                />
              ) : (
                <div style={{ textAlign: 'center', color: '#6b7280' }}>
                  <p>No se ha generado miniatura aún</p>
                </div>
              )}
              {thumbnailRegenerating && (
                <div style={{
                  position: 'absolute',
                  inset: 0,
                  backgroundColor: 'rgba(0,0,0,0.7)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexDirection: 'column',
                  gap: '12px'
                }}>
                  <div className="spinner"></div>
                  <span style={{fontWeight: 'bold'}}>Generando con Leonardo Phoenix 1.0...</span>
                </div>
              )}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <label style={{ fontSize: '0.875rem', color: '#d8b4fe', fontWeight: 'bold' }}>Gancho / Título en Miniatura</label>
                <button
                  onClick={handleRegenerateThumbnailHook}
                  disabled={thumbnailRegenerating}
                  style={{
                    background: 'none',
                    color: '#a855f7',
                    border: 'none',
                    fontSize: '0.875rem',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    textDecoration: 'underline'
                  }}
                >
                  Regenerar Gancho AI
                </button>
              </div>
              <input
                type="text"
                value={thumbnailHook}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setThumbnailHook(e.target.value)}
                placeholder="Ej: ¡EL SECRETO MEJOR GUARDADO!"
                style={{
                  backgroundColor: 'rgba(0,0,0,0.3)',
                  border: '1px solid #a855f7',
                  borderRadius: '12px',
                  padding: '12px',
                  color: 'white',
                  fontSize: '1rem',
                  outline: 'none'
                }}
              />

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '8px' }}>
                <label style={{ fontSize: '0.875rem', color: '#d8b4fe', fontWeight: 'bold' }}>Descripción Visual (Contexto)</label>
                <button
                  onClick={handleRegenerateThumbnailVisualPrompt}
                  disabled={thumbnailRegenerating}
                  style={{
                    background: 'none',
                    color: '#a855f7',
                    border: 'none',
                    fontSize: '0.875rem',
                    fontWeight: 'bold',
                    cursor: 'pointer',
                    textDecoration: 'underline'
                  }}
                >
                  Regenerar Contexto IA
                </button>
              </div>
              <textarea
                value={thumbnailVisualPrompt}
                onChange={(e) => setThumbnailVisualPrompt(e.target.value)}
                placeholder="Describe la escena visual..."
                style={{
                  backgroundColor: 'rgba(0,0,0,0.3)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '12px',
                  padding: '12px',
                  color: '#e5e7eb',
                  fontSize: '0.875rem',
                  height: '80px',
                  resize: 'none',
                  outline: 'none'
                }}
              />
              
              <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
                <button
                  onClick={handleGenerateThumbnailImage}
                  disabled={thumbnailRegenerating || (!thumbnailHook && !thumbnailVisualPrompt)}
                  style={{
                    flex: 2,
                    backgroundColor: '#a855f7',
                    color: 'white',
                    padding: '14px',
                    borderRadius: '12px',
                    fontWeight: 'bold',
                    fontSize: '1rem',
                    cursor: 'pointer',
                    border: 'none',
                    opacity: (thumbnailRegenerating || (!thumbnailHook && !thumbnailVisualPrompt)) ? 0.5 : 1
                  }}
                >
                  {thumbnailUrl ? '🔄 Regenerar Miniatura' : '✨ Generar Miniatura'}
                </button>
                
                <label style={{
                  flex: 1,
                  backgroundColor: '#374151',
                  color: 'white',
                  padding: '14px',
                  borderRadius: '12px',
                  fontWeight: 'bold',
                  fontSize: '0.9rem',
                  cursor: 'pointer',
                  textAlign: 'center',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  opacity: uploading ? 0.5 : 1
                }}>
                  {uploading ? 'Subiendo...' : '📤 Subir propia'}
                  <input type="file" hidden accept="image/*" onChange={handleUploadThumbnail} disabled={uploading} />
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ImageReviewer;
