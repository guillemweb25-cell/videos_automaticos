import React, { useState, useEffect } from 'react'
import { api, type UserResponse, type ChannelResponse } from './api'
import ChannelDashboard from './components/ChannelDashboard'

function App() {
  const [user, setUser] = useState<UserResponse | null>(null)
  const [channels, setChannels] = useState<ChannelResponse[]>([])
  const [isLogin, setIsLogin] = useState(true)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  // Selected Channel State
  const [selectedChannel, setSelectedChannel] = useState<ChannelResponse | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)

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

  const handleSelectChannel = (channel: ChannelResponse | null) => {
    setSelectedChannel(channel)
    if (channel) {
      localStorage.setItem('selectedChannelId', channel.id.toString())
    } else {
      localStorage.removeItem('selectedChannelId')
    }
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
              Entrar
            </button>
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
            {selectedChannel ? `Dashboard: ${selectedChannel.name}` : 'Selecciona un canal'}
          </div>
          {selectedChannel && (
            <button className="btn-delete" onClick={() => handleDeleteChannel(selectedChannel.id)}>
              Eliminar Canal
            </button>
          )}
        </header>
        
        <div className="content-area">
          {selectedChannel ? (
            <ChannelDashboard channel={selectedChannel} onBack={() => setSelectedChannel(null)} />
          ) : (
            <div className="empty-state">
              <div style={{ fontSize: '4rem', marginBottom: '24px' }}>📺</div>
              <h2>Bienvenido a VideoBot</h2>
              <p>Selecciona un canal de la izquierda o crea uno nuevo para empezar a trabajar.</p>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default App
