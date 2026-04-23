import React, { useState, useEffect } from 'react';
import { api, API_URL } from '../api';

interface ImageReviewerProps {
  videoId: number;
  onClose: () => void;
}

const ImageReviewer: React.FC<ImageReviewerProps> = ({ videoId, onClose }) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [addingImage, setAddingImage] = useState<number | null>(null);
  const [regenerating, setRegenerating] = useState<string | null>(null);
  const [converting, setConverting] = useState<string | null>(null);
  const [rendering, setRendering] = useState(false);
  const [prompts, setPrompts] = useState<{ [key: string]: string }>({});
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
  const [thumbnailHook, setThumbnailHook] = useState('');
  const [thumbnailVisualPrompt, setThumbnailVisualPrompt] = useState('');
  const [thumbnailRegenerating, setThumbnailRegenerating] = useState(false);
  const [leonardoModels, setLeonardoModels] = useState<any[]>([]);
  const [selectedModel, setSelectedModel] = useState('7b592283-e8a7-4c5a-9ba6-d18c31f258b9'); // Default to Lucid Origin
  const [availableStyles, setAvailableStyles] = useState<any[]>([]);
  const [selectedStyle, setSelectedStyle] = useState('epic');
  const [generationModes, setGenerationModes] = useState<any[]>([]);
  const [generationMode, setGenerationMode] = useState('QUALITY');
  const [uploading, setUploading] = useState(false);
  const [enableSubtitles, setEnableSubtitles] = useState(false);
  const [availableOverlays, setAvailableOverlays] = useState<string[]>([]);
  const [selectedOverlay, setSelectedOverlay] = useState<string>('');
  const [availableWorkflows, setAvailableWorkflows] = useState<string[]>([]);
  const [selectedWorkflow, setSelectedWorkflow] = useState<string>('Comic-Horror.json');

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

      // Load models and styles
      const config = await api.getConfig() as any;
      setLeonardoModels(config.leonardo_models || []);
      setAvailableStyles(config.styles || []);
      setGenerationModes(config.generation_modes || []);
      
      try {
        const overlaysRes = await api.getOverlays();
        setAvailableOverlays(overlaysRes.overlays);
        
        const workflowsRes = await api.getWorkflows();
        setAvailableWorkflows(workflowsRes.workflows);
        if (res.workflow_name) {
          setSelectedWorkflow(res.workflow_name);
        } else if (workflowsRes.workflows.length > 0 && !selectedWorkflow) {
          setSelectedWorkflow(workflowsRes.workflows[0]);
        }
      } catch (e) {
        console.error("Error loading config", e);
      }

      if (res.style) {
        setSelectedStyle(res.style);
      }
      if (res.generation_mode) {
        setGenerationMode(res.generation_mode);
      }
      if (res.model_id) {
        setSelectedModel(res.model_id);
      }
      if (res.workflow_name) {
        setSelectedWorkflow(res.workflow_name);
      }
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
      const res = await api.regenerateImage(videoId, paraId, imgId, prompt, selectedModel, generationMode, selectedWorkflow);
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

  const handleConvertToVideo = async (paraId: number, imgId: number) => {
    const key = `${paraId}_${imgId}`;
    setConverting(key);
    try {
      const res = await api.convertImageToVideo(videoId, paraId, imgId, 8, "VEO3FAST", prompts[key]);
      if (res.ok) {
        const newData = { ...data };
        for (const item of newData.items) {
          if (item.paragraph_id === paraId) {
            for (const p of item.prompts) {
              if (p.id === imgId) {
                p.url = res.url;
                p.is_video = true;
              }
            }
          }
        }
        setData(newData);
      }
    } catch (error) {
      console.error("Error converting image to video:", error);
      alert("Error al convertir a vídeo");
    } finally {
      setConverting(null);
    }
  };

  const handleAddImage = async (paraId: number) => {
    setAddingImage(paraId);
    try {
      const res = await api.addImage(videoId, paraId, selectedStyle, selectedModel, generationMode, selectedWorkflow);
      if (res.ok) {
        // Refresh data or update locally
        await loadData();
      }
    } catch (error) {
      console.error("Error adding image:", error);
      alert("Error al añadir imagen");
    } finally {
      setAddingImage(null);
    }
  };

  const handleRemoveImage = async (paraId: number, imgId: number) => {
    if (!confirm("¿Seguro que quieres eliminar esta imagen? Se recalcularán los tiempos del párrafo.")) return;
    
    setRegenerating(`${paraId}_${imgId}`);
    try {
      const res = await api.removeImage(videoId, paraId, imgId);
      if (res.ok) {
        await loadData();
      }
    } catch (error) {
      console.error("Error removing image:", error);
      alert("Error al eliminar imagen");
    } finally {
      setRegenerating(null);
    }
  };

  const handleRender = async () => {
    try {
      setRendering(true);
      const overlayArg = selectedOverlay === '' ? undefined : selectedOverlay;
      await api.renderVideo(videoId, enableSubtitles, overlayArg);
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
      const res = await api.generateThumbnail(videoId, thumbnailHook, thumbnailVisualPrompt, selectedModel, generationMode);
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
    <div className="modal-overlay">
      <div style={{ maxWidth: '1100px', margin: '0 auto' }}>
        <div className="modal-header">
          <h2 style={{ fontSize: '1.5rem', fontWeight: 'bold', margin: 0 }}>Revisión de Imágenes - Vídeo #{videoId}</h2>
          <div className="header-actions" style={{ display: 'flex', gap: '15px', alignItems: 'flex-end', flexWrap: 'wrap', backgroundColor: '#1f2937', padding: '12px', borderRadius: '8px', border: '1px solid #374151', marginTop: '10px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.7rem', color: '#9ca3af', fontWeight: 'bold' }}>MODELO LEONARDO</label>
              <select 
                value={selectedModel}
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setSelectedModel(e.target.value)}
                style={{
                  backgroundColor: '#111827',
                  color: 'white',
                  border: '1px solid #4b5563',
                  borderRadius: '6px',
                  padding: '6px 10px',
                  fontSize: '0.85rem',
                  outline: 'none',
                  minWidth: '150px'
                }}
              >
                {leonardoModels.map((m: any) => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.7rem', color: '#9ca3af', fontWeight: 'bold' }}>ESTILO VISUAL</label>
              <select 
                value={selectedStyle}
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setSelectedStyle(e.target.value)}
                style={{
                  backgroundColor: '#111827',
                  color: 'white',
                  border: '1px solid #4b5563',
                  borderRadius: '6px',
                  padding: '6px 10px',
                  fontSize: '0.85rem',
                  outline: 'none',
                  minWidth: '130px'
                }}
              >
                {availableStyles.map((s: any) => (
                  <option key={s.id} value={s.id}>{s.name || s.id}</option>
                ))}
              </select>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.7rem', color: '#3b82f6', fontWeight: 'bold' }}>CALIDAD / COSTE</label>
              <select 
                value={generationMode}
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setGenerationMode(e.target.value)}
                style={{
                  backgroundColor: '#111827',
                  color: 'white',
                  border: '2px solid #3b82f6',
                  borderRadius: '6px',
                  padding: '6px 10px',
                  fontSize: '0.85rem',
                  fontWeight: 'bold',
                  outline: 'none',
                  minWidth: '200px',
                  cursor: 'pointer'
                }}
              >
                {generationModes.length > 0 ? (
                  generationModes.map((m: any) => (
                    <option key={m.id} value={m.id}>{m.name}</option>
                  ))
                ) : (
                  <>
                    <option value="QUALITY">Modo Calidad ($0.0852)</option>
                    <option value="FAST">Modo Rápido ($0.012)</option>
                    <option value="COMFYUI">ComfyUI (Local/Gratis)</option>
                  </>
                )}
              </select>
            </div>

            {generationMode === 'COMFYUI' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', borderLeft: '2px solid #ef4444', paddingLeft: '12px' }}>
                <label style={{ fontSize: '0.7rem', color: '#ef4444', fontWeight: 'bold' }}>WORKFLOW COMFY</label>
                <select 
                  value={selectedWorkflow}
                  onChange={(e) => setSelectedWorkflow(e.target.value)}
                  style={{
                    backgroundColor: '#111827',
                    color: 'white',
                    border: '1px solid #ef4444',
                    borderRadius: '6px',
                    padding: '6px 10px',
                    fontSize: '0.85rem',
                    outline: 'none',
                    minWidth: '180px'
                  }}
                >
                  {availableWorkflows.map(wf => (
                    <option key={wf} value={wf}>{wf}</option>
                  ))}
                </select>
              </div>
            )}

            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <label style={{ fontSize: '0.7rem', color: '#9ca3af', fontWeight: 'bold' }}>OVERLAY VISUAL</label>
              <select 
                value={selectedOverlay}
                onChange={(e: React.ChangeEvent<HTMLSelectElement>) => setSelectedOverlay(e.target.value)}
                disabled={rendering}
                style={{
                  backgroundColor: '#111827',
                  color: 'white',
                  border: '1px solid #475569',
                  borderRadius: '6px',
                  padding: '6px 10px',
                  fontSize: '0.85rem',
                  outline: 'none',
                  minWidth: '120px'
                }}
              >
                <option value="">Ninguno</option>
                {availableOverlays.map(opt => (
                  <option key={opt} value={opt}>{opt}</option>
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
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'white', cursor: 'pointer', fontSize: '13px' }}>
              <input 
                type="checkbox" 
                checked={enableSubtitles} 
                onChange={(e) => setEnableSubtitles(e.target.checked)} 
                disabled={rendering}
              />
              Subtítulos Karaoke
            </label>
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
          <div key={item.paragraph_id} style={{ marginBottom: '64px', paddingBottom: '32px', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
            <div className="paragraph-header">
              <div>
                <h3 style={{ fontSize: '1.5rem', color: '#d8b4fe', margin: '0 0 8px 0' }}>📦 Párrafo {item.paragraph_id}</h3>
                <span style={{ fontSize: '0.9rem', color: '#9ca3af', backgroundColor: 'rgba(255,255,255,0.05)', padding: '2px 8px', borderRadius: '4px' }}>
                  🕒 Duración: {item.seconds.toFixed(1)}s
                </span>
              </div>
              
              <div style={{ flex: 1, margin: '0 40px', padding: '16px', backgroundColor: 'rgba(168, 85, 247, 0.05)', borderRadius: '12px', border: '1px solid rgba(168, 85, 247, 0.2)' }}>
                <label style={{ display: 'block', fontSize: '0.7rem', color: '#a855f7', fontWeight: 'bold', textTransform: 'uppercase', marginBottom: '8px', letterSpacing: '0.05em' }}>
                  Transcripción del Párrafo
                </label>
                <p style={{ margin: 0, fontSize: '0.95rem', lineHeight: '1.5', color: '#e5e7eb', fontStyle: 'italic' }}>
                  "{item.spoken || 'Sin transcripción disponible'}"
                </p>
                
                <div style={{ marginTop: '16px', display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <label style={{ fontSize: '0.7rem', color: '#9ca3af', fontWeight: 'bold' }}>AUDIO:</label>
                  <audio 
                    controls 
                    src={`${API_URL}${item.audio_url}`} 
                    style={{ height: '32px', flex: 1, filter: 'invert(1) hue-rotate(180deg) brightness(1.5)' }} 
                  />
                </div>
              </div>
            </div>

            <div className="responsive-grid">
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
                      {/* Cost Badge */}
                      {p.cost && (
                        <div style={{
                          position: 'absolute',
                          top: '12px',
                          left: '12px',
                          backgroundColor: 'rgba(22, 163, 74, 0.9)',
                          color: 'white',
                          padding: '4px 8px',
                          borderRadius: '6px',
                          fontSize: '0.75rem',
                          fontWeight: 'bold',
                          boxShadow: '0 2px 4px rgba(0,0,0,0.3)',
                          zIndex: 5
                        }}>
                          💰 ${parseFloat(p.cost.amount).toFixed(4)}
                        </div>
                      )}

                      {p.is_video ? (
                        <video 
                          src={`${API_URL}${p.url}`} 
                          controls
                          loop
                          autoPlay
                          muted
                          style={{ 
                            maxWidth: '100%', 
                            maxHeight: '600px', 
                            objectFit: 'contain',
                            display: 'block'
                          }}
                        />
                      ) : (
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
                      )}
                      
                      {/* Delete Button */}
                      <button
                        onClick={() => handleRemoveImage(item.paragraph_id, p.id)}
                        style={{
                          position: 'absolute',
                          top: '12px',
                          right: '12px',
                          backgroundColor: 'rgba(239, 68, 68, 0.9)',
                          color: 'white',
                          border: 'none',
                          borderRadius: '50%',
                          width: '32px',
                          height: '32px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          cursor: 'pointer',
                          fontWeight: 'bold',
                          fontSize: '1.2rem',
                          boxShadow: '0 4px 6px rgba(0,0,0,0.3)',
                          zIndex: 5
                        }}
                        title="Eliminar esta imagen"
                      >
                        ×
                      </button>

                      {(regenerating === key || converting === key || addingImage === item.paragraph_id) && (
                        <div style={{
                          position: 'absolute',
                          inset: 0,
                          backgroundColor: 'rgba(0,0,0,0.6)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexDirection: 'column',
                          gap: '12px',
                          zIndex: 6
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
                        disabled={!!regenerating || !!converting}
                        style={{
                          backgroundColor: '#9333ea',
                          color: 'white',
                          padding: '10px',
                          borderRadius: '8px',
                          fontWeight: 'bold',
                          cursor: 'pointer',
                          border: 'none',
                          opacity: (regenerating || converting) ? 0.5 : 1,
                          marginTop: '8px'
                        }}
                      >
                        Regenerar esta imagen
                      </button>
                      {!p.is_video && (
                        <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                          <button
                            onClick={() => handleConvertToVideo(item.paragraph_id, p.id)}
                            disabled={!!converting || !!regenerating}
                            style={{
                              flex: 1,
                              backgroundColor: '#f59e0b',
                              color: 'white',
                              padding: '10px',
                              borderRadius: '8px',
                              fontWeight: 'bold',
                              cursor: 'pointer',
                              border: 'none',
                              opacity: (converting || regenerating) ? 0.5 : 1
                            }}
                          >
                            🎞️ Convertir a Vídeo
                          </button>
                          
                          <button
                            onClick={async () => {
                              const link = prompt("Pega el enlace de Leonardo AI:");
                              if (!link) return;
                              setConverting(key);
                              try {
                                const res = await api.linkClip(videoId, item.paragraph_id, p.id, link);
                                if (res.ok) {
                                  const newData = { ...data };
                                  for (const it of newData.items) {
                                    if (it.paragraph_id === item.paragraph_id) {
                                      for (const pr of it.prompts) {
                                        if (pr.id === p.id) {
                                          pr.url = res.url;
                                          pr.is_video = true;
                                        }
                                      }
                                    }
                                  }
                                  setData(newData);
                                }
                              } catch(err: any) {
                                alert("Error al vincular clip: " + (err.message || "Desconocido"));
                              } finally {
                                setConverting(null);
                              }
                            }}
                            disabled={!!converting || !!regenerating}
                            style={{
                              backgroundColor: '#3b82f6',
                              color: 'white',
                              padding: '10px',
                              borderRadius: '8px',
                              fontWeight: 'bold',
                              cursor: 'pointer',
                              border: 'none',
                              opacity: (converting || regenerating) ? 0.5 : 1
                            }}
                            title="Vincular desde URL de Leonardo AI"
                          >
                            🔗 Vincular
                          </button>
                        </div>
                      )}
                      
                      {/* Upload MP4 Button */}
                      <label style={{
                        backgroundColor: '#374151',
                        color: 'white',
                        padding: '10px',
                        borderRadius: '8px',
                        fontWeight: 'bold',
                        cursor: 'pointer',
                        border: 'none',
                        fontSize: '0.85rem',
                        marginTop: '8px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        opacity: (converting || regenerating) ? 0.5 : 1,
                      }}>
                        📤 Subir MP4 Propio
                        <input 
                          type="file" 
                          accept="video/mp4,video/*" 
                          hidden 
                          disabled={!!converting || !!regenerating}
                          onChange={async (e) => {
                            const file = e.target.files?.[0];
                            if (file) {
                              setConverting(key);
                              try {
                                const res = await api.uploadClip(videoId, item.paragraph_id, p.id, file);
                                if (res.ok) {
                                  const newData = { ...data };
                                  for (const it of newData.items) {
                                    if (it.paragraph_id === item.paragraph_id) {
                                      for (const pr of it.prompts) {
                                        if (pr.id === p.id) {
                                          pr.url = res.url;
                                          pr.is_video = true;
                                        }
                                      }
                                    }
                                  }
                                  setData(newData);
                                }
                              } catch(err) {
                                alert('Error al subir vídeo');
                              } finally {
                                setConverting(null);
                              }
                            }
                          }} 
                        />
                      </label>
                    </div>
                  </div>
                );
              })}
              
              {/* Add Image Button */}
              <button
                onClick={() => handleAddImage(item.paragraph_id)}
                disabled={addingImage === item.paragraph_id}
                style={{
                  backgroundColor: 'rgba(168, 85, 247, 0.1)',
                  border: '2px dashed rgba(168, 85, 247, 0.4)',
                  borderRadius: '12px',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  minHeight: '400px',
                  color: '#d8b4fe',
                  gap: '12px',
                  transition: 'all 0.2s ease'
                }}
                onMouseOver={(e) => e.currentTarget.style.backgroundColor = 'rgba(168, 85, 247, 0.2)'}
                onMouseOut={(e) => e.currentTarget.style.backgroundColor = 'rgba(168, 85, 247, 0.1)'}
              >
                <span style={{ fontSize: '3rem' }}>+</span>
                <span style={{ fontWeight: 'bold' }}>Añadir Imagen Continua</span>
                <small style={{ color: '#9ca3af' }}>Usará la IA para seguir la historia</small>
              </button>
            </div>
          </div>
        ))}

        {/* Thumbnail Section */}
        <div style={{ marginTop: '64px', padding: '32px', backgroundColor: 'rgba(168, 85, 247, 0.1)', borderRadius: '16px', border: '2px dashed #a855f7' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
            <h3 style={{ fontSize: '1.5rem', color: '#d8b4fe', margin: 0 }}>🖼️ Miniatura del Vídeo</h3>
            <span style={{ fontSize: '0.875rem', color: '#9ca3af' }}>Se usará como pantalla final y para Shorts</span>
          </div>

          <div className="thumbnail-grid" style={{ marginBottom: '32px' }}>
            <div style={{
              backgroundColor: '#1f2937', 
              borderRadius: '12px', 
              overflow: 'hidden', 
              aspectRatio: data?.orientation === 'horizontal' ? '16/9' : '9/16',
              maxWidth: '100%',
              maxHeight: '70vh',
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
