import React, { useState, useEffect } from 'react'
import { api, type UserResponse, type ChannelResponse } from './api'
import ChannelDashboard from './components/ChannelDashboard'
import { Settings } from './components/Settings'
import { Payments } from './components/Payments'
import { AdminDashboard } from './components/AdminDashboard'
import OrphansManager from './components/OrphansManager'

function App() {
  const [user, setUser] = useState<UserResponse | null>(null)
  const [channels, setChannels] = useState<ChannelResponse[]>([])
  const [isLogin, setIsLogin] = useState(true)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [registrationEnabled, setRegistrationEnabled] = useState(false)

  // Selected Channel State
  const [selectedChannel, setSelectedChannel] = useState<ChannelResponse | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showPayments, setShowPayments] = useState(false)
  const [showAdmin, setShowAdmin] = useState(false)
  const [showOrphans, setShowOrphans] = useState(false)

  // Channel Form State
  const [channelName, setChannelName] = useState('')
  const [channelHandle, setChannelHandle] = useState('')

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (token) {
      api.getMe()
        .then((data) => {
          setUser(data)
          localStorage.setItem('cached_user', JSON.stringify(data))
        })
        .catch((err) => {
          // Only clear token if it's actually expired/invalid (401)
          if (err.message === 'TOKEN_EXPIRED') {
            setUser(null)
            localStorage.removeItem('cached_user')
            localStorage.removeItem('token')
          } else {
            // Network error or other, try to use cache so the app doesn't go back to login
            console.warn('Network error checking auth, trying cache:', err.message)
            const cached = localStorage.getItem('cached_user')
            if (cached) {
              try {
                setUser(JSON.parse(cached))
              } catch (e) {
                console.error("Error parsing cached user", e)
              }
            }
          }
        })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }

    api.getPublicSettings().then(res => setRegistrationEnabled(res.registration_enabled)).catch(console.error)
  }, [])

  useEffect(() => {
    if (user) {
      loadChannels()
      const savedChannelId = localStorage.getItem('selectedChannelId')
      if (savedChannelId) {
        // We'll set it once channels are loaded or if they are already there
      }
    }
  }, [user])

  const loadChannels = async () => {
    try {
      const data = await api.getChannels()
      setChannels(data)
      
      const savedChannelId = localStorage.getItem('selectedChannelId')
      if (savedChannelId) {
        const found = data.find(c => c.id === parseInt(savedChannelId))
        if (found) setSelectedChannel(found)
      }
    } catch (err) {
      console.error('Error loading channels:', err)
    }
  }

  const handleShowPayments = () => {
    setShowPayments(true)
    setShowSettings(false)
    setShowAdmin(false)
    setShowOrphans(false)
    setSelectedChannel(null)
    setSidebarOpen(false)
  }

  const handleShowAdmin = () => {
    setShowAdmin(true)
    setShowSettings(false)
    setShowPayments(false)
    setShowOrphans(false)
    setSelectedChannel(null)
    setSidebarOpen(false)
  }

  const handleShowOrphans = () => {
    setShowOrphans(true)
    setShowSettings(false)
    setShowPayments(false)
    setShowAdmin(false)
    setSelectedChannel(null)
    setSidebarOpen(false)
  }

  const handleSelectChannel = (channel: ChannelResponse | null) => {
    setSelectedChannel(channel)
    setShowSettings(false)
    setShowPayments(false)
    setShowAdmin(false)
    setShowOrphans(false)
    if (channel) {
      localStorage.setItem('selectedChannelId', channel.id.toString())
    } else {
      localStorage.removeItem('selectedChannelId')
    }
    setSidebarOpen(false)
  }

  const handleShowSettings = () => {
    setShowSettings(true)
    setShowPayments(false)
    setShowAdmin(false)
    setShowOrphans(false)
    setSelectedChannel(null)
    setSidebarOpen(false)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      if (isLogin) {
        await api.login(email, password)
        const me = await api.getMe()
        setUser(me)
      } else {
        await api.register(email, password)
        await api.login(email, password)
        const me = await api.getMe()
        setUser(me)
      }
      setEmail('')
      setPassword('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateChannel = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!channelName) return
    try {
      await api.createChannel(channelName, channelHandle)
      setChannelName('')
      setChannelHandle('')
      loadChannels()
    } catch (err: any) {
      alert(err.message)
    }
  }

  const handleDeleteChannel = async (id: number) => {
    if (!confirm('¿Seguro que quieres eliminar este canal?')) return
    try {
      await api.deleteChannel(id)
      if (selectedChannel?.id === id) setSelectedChannel(null)
      loadChannels()
    } catch (err: any) {
      alert(err.message)
    }
  }

  const handleLogout = () => {
    api.logout()
    setUser(null)
    setChannels([])
    setSelectedChannel(null)
  }

  if (loading && !user) return <div className="loading-screen">Cargando...</div>

  if (!user) {
    return (
      <div className="auth-wrapper">
        <div className="auth-card">
          <h1 style={{ textAlign: 'center', marginBottom: '8px' }}>🎬 VideoBot</h1>
          <p style={{ textAlign: 'center', color: '#94a3b8', marginBottom: '32px' }}>
            {isLogin ? 'Bienvenido de nuevo' : 'Crea tu cuenta'}
          </p>
          
          <form onSubmit={handleSubmit}>
            <div className="input-group">
              <label>Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="tu@email.com"
                required
              />
            </div>
            <div className="input-group">
              <label>Contraseña</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                minLength={6}
              />
            </div>
            {error && <div className="error-text">{error}</div>}
            <button className="btn btn-primary" style={{ width: '100%', marginTop: '16px' }} type="submit">
              {isLogin ? 'Entrar' : 'Registrarse'}
            </button>
            
            {registrationEnabled && (
              <div style={{ textAlign: 'center', marginTop: '16px' }}>
                <button 
                  type="button" 
                  className="btn-link" 
                  onClick={() => { setIsLogin(!isLogin); setError(''); }}
                >
                  {isLogin ? '¿No tienes cuenta? Regístrate' : '¿Ya tienes cuenta? Inicia sesión'}
                </button>
              </div>
            )}
          </form>
        </div>
      </div>
    )
  }

  return (
    <div className="app-layout">
      {/* Mobile Backdrop */}
      {sidebarOpen && (
        <div className="sidebar-backdrop" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <h1>🎬 VideoBot</h1>
        </div>
        
        <div className="sidebar-nav">
          <p className="nav-section-title">Canales</p>
          {channels.map(channel => (
            <div 
              key={channel.id} 
              className={`channel-link ${selectedChannel?.id === channel.id ? 'active' : ''}`}
              onClick={() => handleSelectChannel(channel)}
            >
              <div className="channel-icon">{channel.name[0].toUpperCase()}</div>
              <span>{channel.name}</span>
            </div>
          ))}
          
          <div 
            className={`channel-link ${showSettings ? 'active' : ''}`}
            onClick={handleShowSettings}
            style={{ marginTop: '16px' }}
          >
            <div className="channel-icon" style={{ background: '#334155' }}>⚙️</div>
            <span>Ajustes</span>
          </div>

          <div
            className={`channel-link ${showPayments ? 'active' : ''}`}
            onClick={handleShowPayments}
            style={{ marginTop: '4px' }}
          >
            <div className="channel-icon" style={{ background: '#1e293b' }}>💳</div>
            <span>Créditos</span>
            <span className="balance-badge">{((user.credits ?? 0) / 100).toFixed(2)}€</span>
          </div>

          <div
            className={`channel-link ${showOrphans ? 'active' : ''}`}
            onClick={handleShowOrphans}
            style={{ marginTop: '4px' }}
          >
            <div className="channel-icon" style={{ background: '#7c2d12' }}>🧹</div>
            <span>Limpieza</span>
          </div>

          {user.is_admin && (
            <div 
              className={`channel-link ${showAdmin ? 'active' : ''}`}
              onClick={handleShowAdmin}
              style={{ marginTop: '4px' }}
            >
              <div className="channel-icon" style={{ background: '#3b82f6' }}>🛡️</div>
              <span>Administración</span>
            </div>
          )}
          
          <div style={{ padding: '12px' }}>
            <form onSubmit={handleCreateChannel}>
              <input 
                size={1}
                style={{ fontSize: '0.8rem', padding: '8px', marginBottom: '8px' }}
                placeholder="Nuevo canal..." 
                value={channelName} 
                onChange={(e) => setChannelName(e.target.value)}
                required 
              />
              <button type="submit" className="btn btn-secondary" style={{ width: '100%', padding: '6px', fontSize: '0.8rem' }}>
                Añadir Canal
              </button>
            </form>
          </div>
        </div>
        
        <div className="sidebar-footer">
          <div className="user-profile-small">
            <div className="user-avatar-small">{user.email[0].toUpperCase()}</div>
            <div className="user-email-small">{user.email}</div>
          </div>
          <button onClick={handleLogout} className="btn-link" style={{ marginTop: '12px', fontSize: '0.8rem', color: '#94a3b8' }}>
            Cerrar sesión
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-wrapper">
        <header className="top-header">
          <button className="menu-toggle" onClick={() => setSidebarOpen(true)}>
            ☰
          </button>
          <div style={{ fontWeight: 600 }}>
            {showSettings ? 'Ajustes' : showPayments ? 'Créditos y Pagos' : showAdmin ? 'Panel de Administración' : showOrphans ? 'Limpieza de vídeos' : selectedChannel ? `Dashboard: ${selectedChannel.name}` : 'Selecciona un canal'}
          </div>
          {selectedChannel && (
            <button className="btn-delete" onClick={() => handleDeleteChannel(selectedChannel.id)}>
              Eliminar Canal
            </button>
          )}
        </header>
        
        <div className="content-area">
          {showSettings ? (
            <Settings />
          ) : showPayments ? (
            <Payments user={user} onUpdateUser={(updated) => setUser(updated)} />
          ) : showAdmin ? (
            <AdminDashboard onUserUpdate={(updated) => {
              if (updated.id === user.id) setUser(updated);
            }} />
          ) : showOrphans ? (
            <OrphansManager />
          ) : selectedChannel ? (
            <ChannelDashboard
              channel={selectedChannel}
              onBack={() => setSelectedChannel(null)}
              onChannelUpdated={(updated) => {
                setSelectedChannel(updated);
                setChannels(prev => prev.map(c => c.id === updated.id ? updated : c));
              }}
            />
          ) : (
            <div className="empty-state">
              <div style={{ fontSize: '4rem', marginBottom: '24px' }}>📺</div>
              <h2>Bienvenido a VideoBot</h2>
              <p>Selecciona un canal de la izquierda, crea uno nuevo, o configura tus Ajustes para empezar a trabajar.</p>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default App
