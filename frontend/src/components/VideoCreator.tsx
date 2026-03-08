import React, { useState, ChangeEvent } from 'react';
import { api, type VideoResponse } from '../api';
import VideoUploadModal from './VideoUploadModal';

interface VideoCreatorProps {
  channelId: number;
  initialVideo?: VideoResponse | null;
}

type GenerationStep = 'idle' | 'creating' | 'script' | 'audio' | 'generating_audio' | 'audio_ready' | 'images' | 'generating_images' | 'images_ready' | 'seo' | 'rendering' | 'completed' | 'error';

const VideoCreator: React.FC<VideoCreatorProps> = ({ channelId, initialVideo }) => {
  const [title, setTitle] = useState(initialVideo?.title || '');
  const [script, setScript] = useState('');
  const [voice, setVoice] = useState('es_mx_002');
  const [provider, setProvider] = useState<'tiktok' | 'elevenlabs'>('tiktok');
  const [style, setStyle] = useState('realistic');
  const [status, setStatus] = useState<GenerationStep>('idle');
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [finalVideo, setFinalVideo] = useState('');
  const [videoId, setVideoId] = useState<number | null>(initialVideo?.id || null);
  const [isBusy, setIsBusy] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);

  const [availableVoices, setAvailableVoices] = useState<{ tiktok: any[], elevenlabs: any[] }>({ tiktok: [], elevenlabs: [] });
  const [availableStyles, setAvailableStyles] = useState<{ id: string, name: string }[]>([]);
  const [orientation, setOrientation] = useState<'horizontal' | 'vertical'>('vertical');
  const [maxImagesPerParagraph, setMaxImagesPerParagraph] = useState(2);

  const addLog = (msg: string) => setLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);

  React.useEffect(() => {
    const loadConfig = async () => {
      try {
        const config = await api.getConfig();
        setAvailableVoices(config.voices);
        setAvailableStyles(config.styles);
        
        if (!initialVideo) {
          setTitle('');
          setScript('');
          setStatus('idle');
          setLog([]);
          setError('');
          setVideoId(null);
          if (config.styles.length > 0) {
            setStyle(config.styles[0].id);
          }
        } else {
          setTitle(initialVideo.title);
          setVideoId(initialVideo.id);
          setStatus('idle'); // Default status, will be updated below if needed
          setError('');
          setLog([]);
          
          addLog(`Cargando vídeo existente ID: ${initialVideo.id}...`);
          const scriptRes = await api.getVideoScript(initialVideo.id);
          setScript(scriptRes.script);
          
          if (initialVideo.width === 1792) {
            setOrientation('horizontal');
          } else {
            setOrientation('vertical');
          }
          
          // Determine starting step based on status
          if (initialVideo.status === 'generating_audio') {
            setStatus('audio');
            addLog('Continuando: Generación de audio interrumpida.');
          } else if (initialVideo.status === 'audio_ready') {
            setStatus('images');
            addLog('Continuando desde: Audio ya generado.');
          } else if (initialVideo.status === 'generating_images') {
            setStatus('images');
            addLog('Continuando: Generación de imágenes interrumpida.');
          } else if (initialVideo.status === 'images_ready') {
             setStatus('seo');
             addLog('Continuando desde: Imágenes ya generadas.');
          } else if (initialVideo.status === 'rendering') {
            setStatus('rendering');
            addLog('Continuando: Renderizado interrumpido.');
          } else if (initialVideo.status === 'seo') {
            setStatus('seo');
            addLog('Continuando: SEO interrumpido.');
          } else if (initialVideo.status === 'ready') {
            setStatus('completed');
            addLog('Vídeo ya está listo.');
          } else if (initialVideo.status === 'failed') {
            setStatus('error');
            setError(initialVideo.last_error || 'Error desconocido');
            addLog(`Error detectado: ${initialVideo.last_error}`);
          }
        }
      } catch (err) {
        console.error("Error loading config:", err);
      }
    };
    loadConfig();
  }, [initialVideo]);

  // Update default voice when provider changes
  React.useEffect(() => {
    if (provider === 'tiktok' && availableVoices.tiktok.length > 0) {
      setVoice(availableVoices.tiktok[0].id);
    } else if (provider === 'elevenlabs' && availableVoices.elevenlabs.length > 0) {
      setVoice(availableVoices.elevenlabs[0].id);
    }
  }, [provider, availableVoices]);

  const currentVoices = provider === 'tiktok' ? availableVoices.tiktok : availableVoices.elevenlabs;

  const handleGenerate = async () => {
    if (!title || !script) {
      alert('Por favor, indica un título y un guion.');
      return;
    }

    setIsBusy(true);
    setStatus('creating');
    setLog([]);
    setError('');
    addLog('Iniciando proceso de generación...');

    try {
      let currentId = videoId;

      // 1. Create Video Record (only if not already created)
      if (!currentId) {
        addLog('Creando registro del vídeo...');
        const width = orientation === 'horizontal' ? 1792 : 1024;
        const height = orientation === 'horizontal' ? 1024 : 1792;
        const video = await api.createVideo({ 
          title, 
          channel_id: channelId,
          width,
          height
        });
        currentId = video.id;
        setVideoId(currentId);
        addLog(`Registro creado con ID: ${currentId}`);
      } else {
        addLog(`Usando registro existente ID: ${currentId}`);
      }
 
      const vStatus = initialVideo?.status || 'idle';

      // 2. Upload Script (Always do it if not already generating images/rendering to be safe, 
      // or if user might have edited it)
      const skipScript = ['audio_ready', 'generating_images', 'images_ready', 'seo', 'rendering', 'ready'].includes(vStatus);
      if (!skipScript) {
        setStatus('script');
        addLog('Subiendo y procesando guion...');
        await api.uploadScript(currentId, script);
        addLog('Guion procesado correctamente.');
      } else {
        addLog('Saltando: Guion ya procesado.');
      }

      // 3. Generate Audio
      const skipAudio = ['audio_ready', 'generating_images', 'images_ready', 'seo', 'rendering', 'ready'].includes(vStatus);
      if (!skipAudio) {
        setStatus('audio');
        addLog(`Generando audio con ${provider} (voz: ${voice})...`);
        await api.generateAudio(currentId, voice, provider);
        addLog('Audio generado con éxito.');
      } else {
        addLog('Saltando: Audio ya generado.');
      }

      // 4. Generate Images
      const skipImages = ['images_ready', 'seo', 'rendering', 'ready'].includes(vStatus);
      if (!skipImages) {
        setStatus('images');
        addLog('Generando imágenes para cada párrafo...');
        setStatus('generating_images');
        await api.generateImages(currentId, style, maxImagesPerParagraph);
        addLog('Imágenes generadas correctamente.');
      } else {
        addLog('Saltando: Imágenes ya generadas.');
      }

      // 5. Generate SEO
      const skipSEO = ['ready'].includes(vStatus); // SEO is usually fast, but we can skip if ready
      if (!skipSEO) {
        setStatus('seo');
        addLog('Generando metadatos SEO...');
        await api.generateSEO(currentId);
        addLog('SEO completado.');
      }

      // 6. Rendering
      const skipRender = ['ready'].includes(vStatus);
      if (!skipRender) {
        setStatus('rendering');
        addLog('Iniciando renderizado del vídeo final (esto puede tardar)...');
        const renderRes = await api.renderVideo(currentId);
        addLog('¡Renderizado completado!');
        setFinalVideo(renderRes.output);
      }

      setStatus('completed');
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Error desconocido durante la generación');
      setStatus('error');
      addLog('ERROR: ' + err.message);
    } finally {
      setIsBusy(false);
    }
  };

  const isLocked = !!initialVideo?.is_uploaded;

  return (
    <div className="video-creator">
      {isLocked && (
        <div className="glass-panel" style={{ borderLeft: '4px solid #4ade80', marginBottom: '16px', background: 'rgba(74, 222, 128, 0.05)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '1.5rem' }}>✅</span>
            <div>
              <h4 style={{ margin: 0, color: '#4ade80' }}>Vídeo Publicado en YouTube</h4>
              <p style={{ margin: '4px 0 0 0', fontSize: '0.9rem', color: '#94a3b8' }}>
                Este vídeo ya está en vivo. Para mantener la consistencia, la edición de audio, guion y estilo está bloqueada. 
                Puedes gestionar la miniatura y el SEO desde el botón de YouTube.
              </p>
            </div>
            <button 
              className="btn btn-primary" 
              style={{ marginLeft: 'auto', background: '#dc2626' }}
              onClick={() => setShowUploadModal(true)}
            >
              🚀 Gestionar YouTube
            </button>
          </div>
        </div>
      )}

      <div className="glass-panel" style={{ marginBottom: '24px', opacity: isLocked ? 0.8 : 1 }}>
        <h2>{initialVideo ? 'Continuar Vídeo' : 'Crear Nuevo Vídeo'}</h2>
        <p style={{ color: '#94a3b8', marginBottom: '24px' }}>
          {initialVideo ? `Continuando con ID: ${initialVideo.id}` : 'Configura los parámetros iniciales y lanza el pipeline automático.'}
        </p>

        <div className="form-group">
          <label>Título del Vídeo</label>
          <input 
            type="text" 
            placeholder="Ej: Curiosidades sobre el espacio" 
            value={title}
            onChange={(e: ChangeEvent<HTMLInputElement>) => setTitle(e.target.value)}
            disabled={isBusy || isLocked}
          />
        </div>

        <div className="form-grid" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: '16px', marginBottom: '24px' }}>
          <div className="form-group">
            <label>Proveedor TTS</label>
            <select value={provider} onChange={(e: ChangeEvent<HTMLSelectElement>) => setProvider(e.target.value as any)} disabled={isBusy}>
              <option value="tiktok">TikTok (Gratis)</option>
              <option value="elevenlabs">ElevenLabs (Premium/Lento)</option>
            </select>
          </div>
          <div className="form-group">
            <label>Voz</label>
            <select value={voice} onChange={(e: ChangeEvent<HTMLSelectElement>) => setVoice(e.target.value)} disabled={isBusy || isLocked}>
              {currentVoices.map((v: any) => (
                <option key={v.id} value={v.id}>{v.name}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Estilo Visual</label>
            <select value={style} onChange={(e: ChangeEvent<HTMLSelectElement>) => setStyle(e.target.value)} disabled={isBusy || isLocked}>
              {availableStyles.map((s: any) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label className="block text-sm font-medium text-gray-400 mb-2">Máx. Imágenes por Párrafo</label>
            <input
              type="number"
              min="1"
              max="5"
              value={maxImagesPerParagraph}
              onChange={(e) => setMaxImagesPerParagraph(parseInt(e.target.value) || 1)}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isBusy || isLocked}
            />
            <p className="text-xs text-gray-500 mt-1">Si el párrafo dura menos de 10s, se generará solo 1.</p>
          </div>
          <div className="form-group">
            <label>Orientación / Tamaño</label>
            <select value={orientation} onChange={(e: ChangeEvent<HTMLSelectElement>) => setOrientation(e.target.value as 'horizontal' | 'vertical')} disabled={isBusy || isLocked}>
              <option value="vertical">Vertical (1024x1792) - Shorts/TikTok</option>
              <option value="horizontal">Horizontal (1792x1024) - YouTube</option>
            </select>
          </div>
        </div>

        <div className="form-group">
          <label>Guion (Script)</label>
          <textarea 
            rows={10}
            placeholder="Escribe aquí el contenido del vídeo..." 
            value={script}
            onChange={(e: ChangeEvent<HTMLTextAreaElement>) => setScript(e.target.value)}
            disabled={isBusy || isLocked}
          />
        </div>

        <div style={{ textAlign: 'right' }}>
          <button 
            className="btn btn-primary" 
            style={{ minWidth: '200px' }}
            onClick={handleGenerate}
            disabled={isBusy || isLocked}
          >
            {status === 'idle' && !initialVideo ? 'Lanzar Generación 🚀' : 'Reintentar / Continuar'}
          </button>
        </div>
      </div>

      {(status !== 'idle') && (
        <div className="glass-panel">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h3 style={{ margin: 0 }}>Estado del Pipeline</h3>
            <div className={`status-badge ${status}`}>
              {status.toUpperCase()}
            </div>
          </div>

          <div className="pipeline-steps" style={{ display: 'flex', gap: '8px', marginBottom: '24px' }}>
             {['creating', 'script', 'audio', 'images', 'seo', 'rendering'].map((s) => (
               <div key={s} className={`p-step ${status === s ? 'active' : ''} ${log.some(l => l.toLowerCase().includes(s)) ? 'done' : ''}`}>
                 {s.toUpperCase()}
               </div>
             ))}
          </div>

          {error && <div className="error-text" style={{ padding: '12px', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '8px', marginBottom: '16px' }}>{error}</div>}

          <div className="log-console" style={{ background: '#0f172a', padding: '16px', borderRadius: '8px', fontFamily: 'monospace', fontSize: '0.85rem', maxHeight: '200px', overflowY: 'auto' }}>
            {log.map((line, i) => (
              <div key={i} style={{ color: line.includes('ERROR') ? '#ef4444' : '#94a3b8', marginBottom: '4px' }}>{line}</div>
            ))}
            {status !== 'completed' && status !== 'error' && <div className="blink">_</div>}
          </div>

          {status === 'completed' && finalVideo && (
            <div style={{ marginTop: '24px', padding: '16px', background: 'rgba(34, 197, 94, 0.1)', borderRadius: '8px', textAlign: 'center' }}>
               <h4 style={{ color: '#22c55e', margin: '0 0 8px 0' }}>¡Vídeo Generado con Éxito!</h4>
               <p style={{ fontSize: '0.9rem', marginBottom: '16px' }}>Localización: {finalVideo}</p>
            </div>
          )}
        </div>
      )}

      {showUploadModal && videoId && (
        <VideoUploadModal 
          videoId={videoId} 
          onClose={() => setShowUploadModal(false)} 
        />
      )}
    </div>
  );
};

export default VideoCreator;
