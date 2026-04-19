import React, { useState, useEffect } from 'react';
import { api, type UserResponse } from '../api';

interface PaymentsProps {
  user: UserResponse;
  onUpdateUser: (user: UserResponse) => void;
}

export const Payments: React.FC<PaymentsProps> = ({ user, onUpdateUser }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    // Check if redirected from Stripe with success/cancel
    const params = new URLSearchParams(window.location.search);
    if (params.get('payment') === 'success') {
      setSuccess('¡Pago realizado con éxito! Tus créditos han sido añadidos.');
      // Refresh user data to get new balance
      api.getMe().then(onUpdateUser).catch(console.error);
      // Clean URL
      window.history.replaceState({}, '', window.location.pathname);
    } else if (params.get('payment') === 'cancel') {
      setError('El pago fue cancelado. No se han realizado cargos.');
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, []);

  const handleBuy = async (amount: number) => {
    setLoading(true);
    setError('');
    setSuccess('');
    try {
      const { checkout_url } = await api.createCheckoutSession(amount);
      window.location.href = checkout_url;
    } catch (err: any) {
      setError(err.message || 'Error al conectar con la pasarela de pago');
    } finally {
      setLoading(false);
    }
  };

  const packs = [
    { amount: 10, credits: 1000, label: 'Básico', popular: false },
    { amount: 30, credits: 3000, label: 'Recomendado', popular: true },
    { amount: 50, credits: 5000, label: 'Pro', popular: false },
  ];

  return (
    <div className="payments-container">
      <div className="payments-header">
        <h2>Saldo de Créditos</h2>
        <div className="current-balance-card">
          <div className="balance-label">Tu saldo actual</div>
          <div className="balance-value">{(user.credits / 100).toFixed(2)}€</div>
          <div className="balance-credits">{user.credits} créditos</div>
        </div>
      </div>

      {error && <div className="error-banner">{error}</div>}
      {success && <div className="success-banner">{success}</div>}

      <div className="pricing-grid">
        {packs.map((pack) => (
          <div key={pack.amount} className={`pricing-card ${pack.popular ? 'popular' : ''}`}>
            {pack.popular && <div className="popular-badge">Más popular</div>}
            <h3>{pack.label}</h3>
            <div className="pack-price">{pack.amount}€</div>
            <div className="pack-credits">{pack.credits} créditos</div>
            <p className="pack-desc">Aproximadamente {Math.floor(pack.credits / 300)} vídeos</p>
            <button 
              className={`btn ${pack.popular ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => handleBuy(pack.amount)}
              disabled={loading}
            >
              {loading ? 'Procesando...' : 'Comprar ahora'}
            </button>
          </div>
        ))}
      </div>

      <div className="payments-info">
        <h3>¿Cómo funcionan los créditos?</h3>
        <ul>
          <li>Cada vídeo generado tiene un coste de <strong>300 créditos (3€)</strong>.</li>
          <li>Los créditos no caducan nunca.</li>
          <li>Los pagos son procesados de forma segura a través de <strong>Stripe</strong>.</li>
          <li>Recibirás tus créditos instantáneamente tras completar el pago.</li>
        </ul>
      </div>
    </div>
  );
};
