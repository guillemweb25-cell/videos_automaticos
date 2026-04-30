import React, { useState, ChangeEvent, useRef } from 'react';
import { api, type VideoResponse } from '../api';
import VideoUploadModal from './VideoUploadModal';

interface VideoCreatorProps {
  channelId: number;
  initialVideo?: VideoResponse | null;
  onReviewImages?: (id: number) => void;
}

type GenerationStep = 'idle' | 'creating' | 'script' | 'audio' | 'generating_audio' | 'audio_ready' | 'images' | 'generating_images' | 'images_ready' | 'seo' | 'rendering' | 'completed' | 'error';

const VideoCreator: React.FC<VideoCreatorProps> = ({ channelId, initialVideo, onReviewImages }) => {
  const [title, setTitle] = useState(initialVideo?.title || '');
  const [script, setScript] = useState('');
  const [voice, setVoice] = useState('Dipemo');
  const [provider, setProvider] = useState<'tiktok' | 'elevenlabs' | 'local_xtts'>('elevenlabs');
  const [style, setStyle] = useState('epic');
  const [llmProvider, setLlmProvider] = useState('openai');
  const [status, setStatus] = useState<GenerationStep>('idle');
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState('');
  const [finalVideo, setFinalVideo] = useState('');
  const [videoId, setVideoId] = useState<number | null>(initialVideo?.id || null);
  const [isBusy, setIsBusy] = useState(false);
  const [showUploadModal, setShowUploadModal] = useState(false);

  const [availableVoices, setAvailableVoices] = useState<{ tiktok: any[], elevenlabs: any[], local_xtts: any[] }>({ tiktok: [], elevenlabs: [], local_xtts: [] });
  const [availableStyles, setAvailableStyles] = useState<{ id: string, name: string }[]>([]);
  const [orientation, setOrientation] = useState<'horizontal' | 'vertical'>('horizontal');
  const [maxImagesPerParagraph, setMaxImagesPerParagraph] = useState(0);
  const [shouldAutoRender, setShouldAutoRender] = useState(false);
  const [enableSubtitles, setEnableSubtitles] = useState(false);
  const [leonardoModels, setLeonardoModels] = useState<{ id: string, name: string }[]>([]);
  const [selectedModel, setSelectedModel] = useState('gpt-image-1.5'); // Default to GPT Image-1.5
  const [generationModes, setGenerationModes] = useState<{ id: string, name: string, cost: number }[]>([]);
  const [generationMode, setGenerationMode] = useState('FAST');
  const [availableOverlays, setAvailableOverlays] = useState<string[]>([]);
  const [selectedOverlay, setSelectedOverlay] = useState<string>('');
  const [availableWorkflows, setAvailableWorkflows] = useState<string[]>([]);
  const [selectedWorkflow, setSelectedWorkflow] = useState<string>('Comic-Horror.json');
  const stopRequested = useRef(false);

  // Persistence logic: Load draft on mount
  React.useEffect(() => {
    if (!initialVideo) {
      const draft = localStorage.getItem('yt_auto_creator_draft');
      if (draft) {
        try {
          const data = JSON.parse(draft);
          if (data.title) setTitle(data.title);
          if (data.script) setScript(data.script);
          if (data.voice) setVoice(data.voice);
          if (data.provider) setProvider(data.provider);
          if (data.style) setStyle(data.style);
          if (data.orientation) setOrientation(data.orientation);
          if (data.maxImagesPerParagraph) setMaxImagesPerParagraph(data.maxImagesPerParagraph);
          if (data.selectedModel) setSelectedModel(data.selectedModel);
          if (data.generationMode) setGenerationMode(data.generationMode);
          if (data.llmProvider) setLlmProvider(data.llmProvider);
        } catch (e) {
          console.error("Error loading draft", e);
        }
      }
    }
  }, [initialVideo]);

  // Persistence logic: Save draft on change
  React.useEffect(() => {
    if (!initialVideo && status === 'idle') {
      const draft = {
        title, script, voice, provider, style, orientation, 
        maxImagesPerParagraph, selectedModel, generationMode, selectedWorkflow, llmProvider
      };
      localStorage.setItem('yt_auto_creator_draft', JSON.stringify(draft));
    }
  }, [title, script, voice, provider, style, orientation, maxImagesPerParagraph, selectedModel, generationMode, status, initialVideo]);

  const addLog = (msg: string) => setLog(prev => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);

  React.useEffect(() => {
    const loadConfig = async () => {
      try {
        const config = await api.getConfig();
        // Ensure local_xtts voices are objects with id and name
        const xtts = (config.voices.local_xtts || []).map((v: string | any) => typeof v === 'string' ? {id: v, name: v} : v);
        setAvailableVoices({
          ...config.voices,
          local_xtts: xtts
        });
        setAvailableStyles(config.styles);
        setLeonardoModels(config.leonardo_models || []);
        setGenerationModes(config.generation_modes || []);
        
        try {
          const overlaysRes = await api.getOverlays();
          setAvailableOverlays(overlaysRes.overlays);
          
          const workflowsRes = await api.getWorkflows();
          setAvailableWorkflows(workflowsRes.workflows);
          if (!selectedWorkflow && workflowsRes.workflows.length > 0) {
            setSelectedWorkflow(workflowsRes.workflows[0]);
          }
        } catch (e) {
          console.error("Error loading config", e);
        }
        
        if (config.generation_modes?.length > 0 && !initialVideo) {
          setGenerationMode('FAST'); // Default
        }
        
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
          
          if (initialVideo.voice) {
             setVoice(initialVideo.voice);
             // Determine provider by checking if voice is in elevenlabs list
             // For now simple check: if it doesn't start with es_ it might be elevenlabs?
             // Or better, let's just make sure both possibilities are handled
             if (!initialVideo.voice.startsWith('es_') && !initialVideo.voice.startsWith('en_') && !initialVideo.voice.startsWith('br_')) {
               setProvider('elevenlabs');
             }
          }
          if (initialVideo.style) setStyle(initialVideo.style);
          if (initialVideo.max_images_per_paragraph) setMaxImagesPerParagraph(initialVideo.max_images_per_paragraph);
          if (initialVideo.llm_provider) setLlmProvider(initialVideo.llm_provider);
          
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
      // Prioritize Dipemo if it exists in the list
      const pin = availableVoices.elevenlabs.find(v => v.id === 'Dipemo' || v.name === 'Dipemo');
      if (pin) {
        setVoice(pin.id);
      } else {
        setVoice(availableVoices.elevenlabs[0].id);
      }
    }
  }, [provider, availableVoices]);

  const currentVoices = provider === 'tiktok' ? availableVoices.tiktok : (provider === 'local_xtts' ? availableVoices.local_xtts : availableVoices.elevenlabs);

  const handleResetImages = async () => {
    if (!videoId) return;
    if (!confirm("¿Seguro que quieres borrar todas las imágenes actuales y volver a generarlas desde cero?")) return;

    setIsBusy(true);
    setLog([]);
    setError('');
    setStatus('creating');
    addLog('Borrando imágenes previas y reiniciando estado...');
    
    try {
      // 1. Reset state on server
      await api.resetImages(videoId);
      addLog("Estado reiniciado. Relanzando pipeline...");
      
      // 2. Clear our "initialVideo.status" so the handleGenerate doesn't skip
      if (initialVideo) {
         initialVideo.status = 'audio_ready'; 
      }
      setStatus('audio_ready');
      
      // Give a tiny delay for React to settle, then run standard generate
      setTimeout(() => {
         setIsBusy(false);
         handleGenerate();
      }, 500);

    } catch (err: any) {
      addLog(`Error al reiniciar imágenes: ${err.message}`);
      setIsBusy(false);
    }
  };

  const handleGenerate = async () => {
    if (!title || !script) {
      alert('Por favor, indica un título y un guion.');
      return;
    }

    setIsBusy(true);
    setStatus('creating');
    setLog([]);
    setError('');
    stopRequested.current = false;
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
          height,
          voice,
          style,
          max_images_per_paragraph: maxImagesPerParagraph,
          llm_provider: llmProvider
        });
        currentId = video.id;
        setVideoId(currentId);
        addLog(`Registro creado con ID: ${currentId}`);
        // Clear draft since it's now saved on the server
        localStorage.removeItem('yt_auto_creator_draft');
      } else {
        addLog(`Usando registro existente ID: ${currentId}`);
        // Update existing record with current UI settings
        const width = orientation === 'horizontal' ? 1792 : 1024;
        const height = orientation === 'horizontal' ? 1024 : 1792;
        await api.updateVideo(currentId, {
            title,
            width,
            height,
            voice,
            style,
            max_images_per_paragraph: maxImagesPerParagraph,
            llm_provider: llmProvider
        });
        addLog('Registro actualizado con los ajustes actuales.');
      }
 
      if (stopRequested.current) throw new Error('Generación detenida por el usuario.');

      // Determine what to skip based on either the record or our current progress 
      let vStatus = (initialVideo?.status as any) || 'idle'; 
      if (['audio_ready', 'images_ready', 'seo', 'rendering', 'completed'].includes(status)) {
        vStatus = status;
      }

      // 2. Upload Script (Always do it if not already generating images/rendering to be safe, 
      // or if user might have edited it)
      const skipScript = ['audio_ready', 'generating_images', 'images_ready', 'seo', 'rendering', 'ready'].includes(vStatus);
      if (!skipScript) {
        if (stopRequested.current) throw new Error('Generación detenida por el usuario.');
        setStatus('script');
        addLog('Subiendo y procesando guion...');
        await api.uploadScript(currentId, script);
        addLog('Guion procesado correctamente.');
      } else {
        addLog('Saltando: Guion ya procesado.');
      }

      // 3. Generate Audio (background + polling)
      const skipAudio = ['audio_ready', 'generating_images', 'images_ready', 'seo', 'rendering', 'ready'].includes(vStatus);
      if (!skipAudio) {
        if (stopRequested.current) throw new Error('Generación detenida por el usuario.');
        setStatus('audio');
        addLog(`Generando audio con ${provider} (voz: ${voice})...`);
        await api.generateAudio(currentId, voice, provider);

        let lastLoggedAudioPct = -1;
        while (true) {
          if (stopRequested.current) throw new Error('Generación detenida por el usuario.');
          await new Promise(r => setTimeout(r, 2000));
          let p;
          try {
            p = await api.getAudioProgress(currentId);
          } catch (e) {
            continue;
          }
          if (p.progress > lastLoggedAudioPct && p.progress % 20 === 0) {
            addLog(`Audio ${p.progress}%`);
            lastLoggedAudioPct = p.progress;
          }
          if (p.status === 'audio_ready') {
            addLog('Audio generado con éxito.');
            break;
          }
          if (p.status === 'failed') {
            throw new Error(p.last_error || 'Audio falló');
          }
        }
      } else {
        addLog('Saltando: Audio ya generado.');
      }

      // 4. Generate Images (background + polling)
      const skipImages = ['images_ready', 'seo', 'rendering', 'ready'].includes(vStatus);
      if (!skipImages) {
        if (stopRequested.current) throw new Error('Generación detenida por el usuario.');
        setStatus('images');
        addLog(`Generando imágenes (${maxImagesPerParagraph} por párrafo) usando modelo: ${selectedModel} (${generationMode})...`);
        setStatus('generating_images');
        await api.generateImages(currentId!, style, maxImagesPerParagraph, selectedModel, generationMode, selectedWorkflow);

        let lastLoggedImagesPct = -1;
        let lastLoggedParagraph = -1;
        while (true) {
          if (stopRequested.current) throw new Error('Generación detenida por el usuario.');
          await new Promise(r => setTimeout(r, 3000));
          let p;
          try {
            p = await api.getImagesProgress(currentId!);
          } catch (e) {
            continue;
          }
          // Log every new paragraph completed (more granular than %)
          if (p.paragraphs_done > lastLoggedParagraph && p.total_paragraphs > 0) {
            addLog(`Imágenes: párrafo ${p.paragraphs_done}/${p.total_paragraphs} (${p.total_images} imágenes generadas)`);
            lastLoggedParagraph = p.paragraphs_done;
          } else if (p.progress > lastLoggedImagesPct && p.progress % 20 === 0) {
            addLog(`Imágenes ${p.progress}%`);
            lastLoggedImagesPct = p.progress;
          }
          if (p.status === 'images_ready' || p.status === 'audio_ready') {
            // images_ready = explicit done; audio_ready can happen if reset-images was called
            if (p.status === 'images_ready') {
              addLog(`Imágenes generadas con éxito (${p.total_images} totales).`);
              break;
            }
          }
          if (p.status === 'images_ready') {
            break;
          }
          if (p.status === 'failed') {
            throw new Error(p.last_error || 'Generación de imágenes falló');
          }
          // If status changed past images_ready (e.g. seo, rendering, ready) we're past this step
          if (['seo', 'rendering', 'ready', 'completed'].includes(p.status)) {
            addLog('Imágenes generadas con éxito.');
            break;
          }
        }
      } else {
        addLog('Saltando: Imágenes ya generadas.');
      }

      // 5. Generate SEO
      const skipSEO = ['ready'].includes(vStatus); // SEO is usually fast, but we can skip if ready
      if (!skipSEO) {
        if (stopRequested.current) throw new Error('Generación detenida por el usuario.');
        setStatus('seo');
        addLog('Generando metadatos SEO...');
        await api.generateSEO(currentId);
        addLog('SEO completado.');
      }

      // 6. Rendering
      if (shouldAutoRender || vStatus === 'rendering') {
        if (stopRequested.current) throw new Error('Generación detenida por el usuario.');
        setStatus('rendering');
        addLog('Iniciando renderizado del vídeo final (esto puede tardar)...');
        const overlayArg = selectedOverlay === '' ? undefined : selectedOverlay;
        await api.renderVideo(currentId, enableSubtitles, overlayArg);

        // Poll progress until ready or failed (background render on backend)
        let lastLoggedPct = -1;
        while (true) {
          if (stopRequested.current) throw new Error('Generación detenida por el usuario.');
          await new Promise(r => setTimeout(r, 2000));
          let p;
          try {
            p = await api.getRenderProgress(currentId);
          } catch (e) {
            continue;
          }
          if (p.progress > lastLoggedPct && p.progress % 10 === 0) {
            addLog(`Render ${p.progress}%`);
            lastLoggedPct = p.progress;
          }
          if (p.status === 'ready') {
            addLog('¡Renderizado completado!');
            setFinalVideo(`output/final_video.mp4`);
            setStatus('completed');
            break;
          }
          if (p.status === 'failed') {
            throw new Error(p.last_error || 'Render falló');
          }
        }
      } else {
        addLog('Pipeline pausado. Revisa las imágenes antes de renderizar.');
        setStatus('images_ready');
      }
    } catch (err: any) {
      console.error(err);
      if (err.message?.includes('créditos') || err.message === 'INSUFFICIENT_CREDITS') {
        setError('Saldo insuficiente. Por favor, recarga tus créditos en la sección de Pagos.');
        addLog('ERROR: Saldo insuficiente para generar el vídeo.');
      } else {
        setError(err.message || 'Error desconocido durante la generación');
        addLog('ERROR: ' + err.message);
      }
      setStatus('error');
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

        <div className="form-grid">
          <div className="form-group">
            <label>Proveedor TTS</label>
            <select value={provider} onChange={(e: ChangeEvent<HTMLSelectElement>) => setProvider(e.target.value as any)} disabled={isBusy}>
              <option value="tiktok">TikTok (Gratis)</option>
              <option value="elevenlabs">ElevenLabs (Premium/Lento)</option>
              <option value="local_xtts">Local XTTS (Gratis/Clonación)</option>
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
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-300">Estilo Visual</label>
            <select
              value={style}
              onChange={(e) => setStyle(e.target.value)}
              className="w-full bg-slate-700 border border-slate-600 rounded-md px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isBusy || isLocked}
            >
              {availableStyles.map(s => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-300">Motor de Prompts (IA)</label>
            <select
              value={llmProvider}
              onChange={(e) => setLlmProvider(e.target.value)}
              className="w-full bg-slate-700 border border-slate-600 rounded-md px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isBusy || isLocked}
            >
              <option value="openai">OpenAI (GPT-4o Mini)</option>
              <option value="grok">Grok (xAI)</option>
            </select>
            <p className="text-xs text-gray-400">IA que redactará los prompts de imagen y SEO.</p>
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-300">Modelo Leonardo</label>
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="w-full bg-slate-700 border border-slate-600 rounded-md px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isBusy || isLocked}
            >
              {leonardoModels.map(m => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
            <p className="text-xs text-gray-400">Selecciona el modelo para la generación inicial.</p>
          </div>
          <div className="space-y-2">
            <label className="block text-sm font-medium text-gray-300">Calidad / Coste</label>
            <select
              value={generationMode}
              onChange={(e) => setGenerationMode(e.target.value)}
              className="w-full bg-slate-700 border border-slate-600 rounded-md px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isBusy || isLocked}
            >
              {generationModes.map(m => (
                <option key={m.id} value={m.id}>{m.name}</option>
              ))}
            </select>
            <p className="text-xs text-gray-400">Elige entre rapidez o máxima fidelidad visual.</p>
          </div>
          {generationMode === 'COMFYUI' && (
            <div className="space-y-2 border-l-2 border-blue-500 pl-4 bg-blue-500/5 py-2">
              <label className="block text-sm font-medium text-blue-400">Workflow ComfyUI</label>
              <select
                value={selectedWorkflow}
                onChange={(e) => setSelectedWorkflow(e.target.value)}
                className="w-full bg-slate-700 border border-slate-600 rounded-md px-3 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={isBusy || isLocked}
              >
                {availableWorkflows.map(wf => (
                  <option key={wf} value={wf}>{wf}</option>
                ))}
              </select>
              <p className="text-xs text-blue-300/70">Usando instancia local de ComfyUI</p>
            </div>
          )}
          <div className="form-group">
            <label className="block text-sm font-medium text-gray-400 mb-2">Máx. Imágenes por Párrafo</label>
            <select
              value={maxImagesPerParagraph}
              onChange={(e) => setMaxImagesPerParagraph(parseInt(e.target.value))}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={isBusy || isLocked}
            >
              <option value={0}>Automático (Recomendado)</option>
              <option value={1}>Fijo: 1 Imagen</option>
              <option value={2}>Máx: 2 Imágenes</option>
              <option value={3}>Máx: 3 Imágenes</option>
              <option value={4}>Máx: 4 Imágenes</option>
              <option value={5}>Máx: 5 Imágenes</option>
            </select>
            <p className="text-xs text-gray-500 mt-1">
              {maxImagesPerParagraph === 0 
                ? "El sistema calculará las fotos necesarias según la duración (1 cada 10s)." 
                : "Se generarán como máximo las fotos indicadas por cada párrafo."}
            </p>
          </div>
          <div className="form-group">
            <label>Orientación / Tamaño</label>
            <select value={orientation} onChange={(e: ChangeEvent<HTMLSelectElement>) => setOrientation(e.target.value as 'horizontal' | 'vertical')} disabled={isBusy || isLocked}>
              <option value="vertical">Vertical (1024x1792) - Shorts/TikTok</option>
              <option value="horizontal">Horizontal (1792x1024) - YouTube</option>
            </select>
          </div>
          <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingTop: '28px' }}>
            <input 
              type="checkbox" 
              id="autoRender" 
              checked={shouldAutoRender} 
              onChange={(e) => setShouldAutoRender(e.target.checked)} 
              disabled={isBusy}
            />
            <label htmlFor="autoRender" style={{ margin: 0, cursor: 'pointer' }}>Auto-Renderizar</label>
          </div>
          <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingTop: '28px' }}>
            <input 
              type="checkbox" 
              id="enableSubtitles" 
              checked={enableSubtitles} 
              onChange={(e) => setEnableSubtitles(e.target.checked)} 
              disabled={isBusy}
            />
            <label htmlFor="enableSubtitles" style={{ margin: 0, cursor: 'pointer' }}>Subtítulos Karaoke</label>
          </div>
          <div className="form-group" style={{ display: 'flex', flexDirection: 'column', gap: '8px', paddingTop: '10px' }}>
            <label>Efecto Overlay</label>
            <select value={selectedOverlay} onChange={(e) => setSelectedOverlay(e.target.value)} disabled={isBusy || isLocked} style={{ padding: '8px', borderRadius: '4px', background: '#334155', color: '#fff', border: '1px solid #475569' }}>
              <option value="">Ninguno (Vídeo Limpio)</option>
              {availableOverlays.map(opt => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
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

        <div style={{ textAlign: 'right', display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          {isBusy && (
            <button 
              className="btn" 
              style={{ background: '#ef4444', color: 'white', minWidth: '120px' }}
              onClick={() => {
                stopRequested.current = true;
                addLog('⚠️ Detención solicitada...');
              }}
            >
              Detener ⛔
            </button>
          )}
          {initialVideo && !isBusy && status !== 'idle' && (
            <button 
              className="btn" 
              style={{ background: '#f59e0b', color: 'white', minWidth: '150px' }}
              onClick={handleResetImages}
              title="Borra las imágenes actuales y fuerza su regeneración"
            >
              🔄 Forzar Regenerar Imágenes
            </button>
          )}
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

          {error && (
            <div className="error-text" style={{ padding: '12px', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '8px', marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>{error}</span>
              {error.includes('Saldo insuficiente') && (
                <button 
                  className="btn btn-primary" 
                  style={{ fontSize: '0.8rem', padding: '4px 12px' }}
                  onClick={() => window.location.hash = '#/payments'}
                >
                  Recargar 💳
                </button>
              )}
            </div>
          )}

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

          {['images_ready', 'seo', 'completed'].includes(status) && videoId && (
            <div style={{ marginTop: '24px', display: 'flex', gap: '12px', justifyContent: 'center' }}>
              <button 
                className="btn btn-secondary" 
                style={{ background: '#a855f7' }}
                onClick={() => onReviewImages?.(videoId)}
              >
                🎨 Revisar Imágenes y Tiempos
              </button>
              {status !== 'completed' && (
                <button 
                  className="btn btn-primary" 
                  onClick={() => { setShouldAutoRender(true); setTimeout(handleGenerate, 100); }}
                >
                  🎬 Renderizar Vídeo Final
                </button>
              )}
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
