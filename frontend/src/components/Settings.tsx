import React, { useEffect, useState } from 'react';
import { api } from '../api';

export const Settings: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  const [keys, setKeys] = useState<{
    openai_api_key?: string;
    leonardo_api_key?: string;
    assemblyai_api_key?: string;
    elevenlabs_api_key?: string;
  }>({});
  
  const [status, setStatus] = useState({
    has_openai: false,
    has_leonardo: false,
    has_assemblyai: false,
    has_elevenlabs: false,
  });

  const [globalStatus, setGlobalStatus] = useState({
    registration_enabled: false
  });
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    loadSettings();
    checkAdmin();
  }, []);

  const checkAdmin = async () => {
    try {
      const me = await api.getMe();
      if ((me as any).is_admin) {
        setIsAdmin(true);
        const gs = await api.getPublicSettings();
        setGlobalStatus(gs);
      }
    } catch(err) {}
  };

  const loadSettings = async () => {
    try {
      setLoading(true);
      const data = await api.getSettings();
      setStatus(data);
    } catch (err: any) {
      setError(err.message || 'Error al cargar ajustes');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSuccess('');
    
    try {
      const data = await api.updateSettings(keys);
      setStatus(data);
      setSuccess('Ajustes guardados correctamente.');
      // Limpiar los inputs porque solo son write-only por seguridad
      setKeys({});
    } catch (err: any) {
      setError(err.message || 'Error al guardar ajustes');
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setKeys({
      ...keys,
      [e.target.name]: e.target.value
    });
  };

  if (loading) return <div className="loading-screen">Cargando Ajustes...</div>;

  return (
    <div className="glass-panel">
      <h2>Ajustes de Usuario</h2>
      <p style={{ color: 'var(--text-muted)', marginBottom: '24px' }}>
        Configura tus API Keys. Las claves se guardan de forma segura y nunca se muestran completas por privacidad. 
        Solo introdúcelas si deseas actualizarlas.
      </p>

      {error && <div className="error-text" style={{ marginBottom: '16px' }}>{error}</div>}
      {success && <div style={{ color: '#22c55e', marginBottom: '16px', fontSize: '0.875rem' }}>{success}</div>}

      <form onSubmit={handleSave} style={{ maxWidth: '600px' }}>
        <div className="form-group">
          <label>OpenAI API Key</label>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <input 
              type="password" 
              name="openai_api_key" 
              value={keys.openai_api_key || ''} 
              onChange={handleChange}
              placeholder={status.has_openai ? "•••••••••••••••••••••••• (Configurada)" : "sk-..."}
            />
            {status.has_openai && <span style={{ color: '#22c55e', fontSize: '1.2rem' }}>✓</span>}
          </div>
        </div>

        <div className="form-group">
          <label>Leonardo.ai API Key</label>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <input 
              type="password" 
              name="leonardo_api_key" 
              value={keys.leonardo_api_key || ''} 
              onChange={handleChange}
              placeholder={status.has_leonardo ? "•••••••••••••••••••••••• (Configurada)" : ""}
            />
            {status.has_leonardo && <span style={{ color: '#22c55e', fontSize: '1.2rem' }}>✓</span>}
          </div>
        </div>

        <div className="form-group">
          <label>AssemblyAI API Key (Subtítulos)</label>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <input 
              type="password" 
              name="assemblyai_api_key" 
              value={keys.assemblyai_api_key || ''} 
              onChange={handleChange}
              placeholder={status.has_assemblyai ? "•••••••••••••••••••••••• (Configurada)" : ""}
            />
            {status.has_assemblyai && <span style={{ color: '#22c55e', fontSize: '1.2rem' }}>✓</span>}
          </div>
        </div>

        <div className="form-group">
          <label>ElevenLabs API Key (Opcional - para voces ElevenLabs)</label>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <input 
              type="password" 
              name="elevenlabs_api_key" 
              value={keys.elevenlabs_api_key || ''} 
              onChange={handleChange}
              placeholder={status.has_elevenlabs ? "•••••••••••••••••••••••• (Configurada)" : ""}
            />
            {status.has_elevenlabs && <span style={{ color: '#22c55e', fontSize: '1.2rem' }}>✓</span>}
          </div>
        </div>

        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? 'Guardando...' : 'Guardar Ajustes'}
        </button>
      </form>

      {isAdmin && (
        <div style={{ marginTop: '48px', paddingTop: '24px', borderTop: '1px solid var(--border-color)' }}>
          <h2 style={{ color: '#ef4444' }}>Ajustes de Sistema</h2>
          <p style={{ color: 'var(--text-muted)', marginBottom: '24px' }}>
            Opciones globales del servidor. Solo visibles para administradores.
          </p>

          <div className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <label style={{ margin: 0, padding: 0 }}>Permitir Registro de Usuarios</label>
            <button 
              className={`btn ${globalStatus.registration_enabled ? 'btn-primary' : 'btn-secondary'}`}
              onClick={async () => {
                const newVal = !globalStatus.registration_enabled;
                try {
                  const res = await api.updateGlobalSettings({ registration_enabled: newVal });
                  setGlobalStatus(res);
                  setSuccess(res.registration_enabled ? 'Registro activado' : 'Registro cerrado');
                } catch(e: any) {
                  setError(e.message);
                }
              }}
            >
              {globalStatus.registration_enabled ? 'Activado' : 'Desactivado'}
            </button>
          </div>

          <div className="form-group" style={{ marginTop: '24px' }}>
            <label>Mantenimiento de Caché</label>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '12px' }}>
              Elimina vídeos de más de 15 días y optimiza imágenes pesadas para liberar espacio en disco.
            </p>
            <button 
              className="btn btn-secondary"
              disabled={saving}
              onClick={async () => {
                if (!confirm('¿Quieres iniciar la limpieza de caché? Esto borrará vídeos antiguos y optimizará imágenes.')) return;
                setSaving(true);
                setError('');
                try {
                  const res = await api.cleanupCache();
                  setSuccess(`Limpieza completada: ${res.deleted_videos} vídeos borrados (${res.freed_space_mb}MB) y ${res.optimized_images} imágenes optimizadas (${res.image_reduction_mb}MB liberados).`);
                } catch(e: any) {
                  setError(e.message);
                } finally {
                  setSaving(false);
                }
              }}
            >
              {saving ? 'Procesando...' : '🔥 Limpiar Carpetas y Optimizar'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
