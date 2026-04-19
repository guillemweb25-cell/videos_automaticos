import React, { useState, useEffect } from 'react';
import { api, type UserResponse } from '../api';

interface AdminDashboardProps {
  onUserUpdate?: (user: UserResponse) => void;
}

export const AdminDashboard: React.FC<AdminDashboardProps> = ({ onUserUpdate }) => {
  const [users, setUsers] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [addingCreditsTo, setAddingCreditsTo] = useState<number | null>(null);
  const [creditsAmount, setCreditsAmount] = useState(100);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [usersData, statsData] = await Promise.all([
        api.adminGetUsers(),
        api.adminGetStats()
      ]);
      setUsers(usersData);
      setStats(statsData);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleAddCredits = async (userId: number) => {
    try {
      const updatedUser = await api.adminAddCredits(userId, creditsAmount);
      setAddingCreditsTo(null);
      loadData(); // Refresh table
      if (onUserUpdate) onUserUpdate(updatedUser);
      alert('Créditos añadidos con éxito');
    } catch (err: any) {
      alert('Error: ' + err.message);
    }
  };

  if (loading) return <div>Cargando panel de administración...</div>;
  if (error) return <div className="error-text">Error: {error}</div>;

  return (
    <div className="admin-dashboard">
      <div className="stats-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px', marginBottom: '32px' }}>
        <div className="stat-card" style={{ background: '#1e293b', padding: '20px', borderRadius: '12px', border: '1px solid #334155' }}>
          <div style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: '4px' }}>Usuarios Totales</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>{stats?.total_users}</div>
        </div>
        <div className="stat-card" style={{ background: '#1e293b', padding: '20px', borderRadius: '12px', border: '1px solid #334155' }}>
          <div style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: '4px' }}>Vídeos Generados</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>{stats?.total_videos}</div>
        </div>
        <div className="stat-card" style={{ background: '#1e293b', padding: '20px', borderRadius: '12px', border: '1px solid #334155' }}>
          <div style={{ color: '#94a3b8', fontSize: '0.875rem', marginBottom: '4px' }}>Créditos en Circulación</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 600 }}>{stats?.total_credits}</div>
        </div>
      </div>

      <div className="users-table-container" style={{ background: '#1e293b', borderRadius: '12px', border: '1px solid #334155', overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ background: '#0f172a', borderBottom: '1px solid #334155' }}>
              <th style={{ padding: '16px' }}>Email</th>
              <th style={{ padding: '16px' }}>Créditos</th>
              <th style={{ padding: '16px' }}>Vídeos</th>
              <th style={{ padding: '16px' }}>Registro</th>
              <th style={{ padding: '16px' }}>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {users.map(user => (
              <tr key={user.id} style={{ borderBottom: '1px solid #334155' }}>
                <td style={{ padding: '16px' }}>
                  {user.email}
                  {user.is_admin && <span style={{ marginLeft: '8px', background: '#3b82f6', fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px' }}>ADMIN</span>}
                </td>
                <td style={{ padding: '16px' }}>{user.credits} ({(user.credits / 100).toFixed(2)}€)</td>
                <td style={{ padding: '16px' }}>{user.video_count}</td>
                <td style={{ padding: '16px', color: '#94a3b8', fontSize: '0.875rem' }}>
                  {new Date(user.created_at).toLocaleDateString()}
                </td>
                <td style={{ padding: '16px' }}>
                  {addingCreditsTo === user.id ? (
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <input 
                        type="number" 
                        value={creditsAmount} 
                        onChange={(e) => setCreditsAmount(parseInt(e.target.value))}
                        style={{ width: '80px', padding: '4px' }}
                      />
                      <button className="btn btn-primary" style={{ padding: '4px 8px', fontSize: '0.75rem' }} onClick={() => handleAddCredits(user.id)}>OK</button>
                      <button className="btn btn-secondary" style={{ padding: '4px 8px', fontSize: '0.75rem' }} onClick={() => setAddingCreditsTo(null)}>X</button>
                    </div>
                  ) : (
                    <button 
                      className="btn btn-secondary" 
                      style={{ padding: '4px 12px', fontSize: '0.75rem' }}
                      onClick={() => setAddingCreditsTo(user.id)}
                    >
                      + Créditos
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
