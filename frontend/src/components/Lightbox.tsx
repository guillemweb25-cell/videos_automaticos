import React, { useEffect, useRef, useState } from 'react';

/** Visor a pantalla completa con navegación ‹ › (flechas, teclado y swipe). */
export default function Lightbox({ urls, index, onClose }: { urls: string[]; index: number; onClose: () => void }) {
  const [i, setI] = useState(index);
  const touchX = useRef<number | null>(null);
  useEffect(() => setI(index), [index]);
  const go = (d: number) => setI((p) => (p + d + urls.length) % urls.length);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') go(-1);
      else if (e.key === 'ArrowRight') go(1);
      else if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
    // eslint-disable-next-line
  }, [urls.length]);

  if (!urls.length) return null;
  const arrow: React.CSSProperties = {
    position: 'absolute', top: '50%', transform: 'translateY(-50%)', background: 'rgba(0,0,0,0.45)',
    color: '#fff', border: 'none', fontSize: '2.2rem', lineHeight: 1, width: 56, height: 56,
    borderRadius: '50%', cursor: 'pointer', zIndex: 2100, display: 'flex', alignItems: 'center', justifyContent: 'center',
  };
  return (
    <div
      onClick={onClose}
      onTouchStart={(e) => { touchX.current = e.touches[0].clientX; }}
      onTouchEnd={(e) => {
        if (touchX.current == null) return;
        const dx = e.changedTouches[0].clientX - touchX.current;
        if (Math.abs(dx) > 40) go(dx < 0 ? 1 : -1);
        touchX.current = null;
      }}
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.92)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000, padding: 12 }}
    >
      {urls.length > 1 && <button onClick={(e) => { e.stopPropagation(); go(-1); }} style={{ ...arrow, left: 10 }}>‹</button>}
      <img src={urls[i]} onClick={(e) => e.stopPropagation()} style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', borderRadius: 8 }} />
      {urls.length > 1 && <button onClick={(e) => { e.stopPropagation(); go(1); }} style={{ ...arrow, right: 10 }}>›</button>}
      <button onClick={(e) => { e.stopPropagation(); onClose(); }} style={{ position: 'absolute', top: 12, right: 16, background: 'none', border: 'none', color: '#fff', fontSize: '1.8rem', cursor: 'pointer', zIndex: 2100 }}>✕</button>
      <div style={{ position: 'absolute', bottom: 16, left: 0, right: 0, textAlign: 'center', color: '#cbd5e1', fontSize: '0.85rem' }}>{i + 1} / {urls.length}</div>
    </div>
  );
}
