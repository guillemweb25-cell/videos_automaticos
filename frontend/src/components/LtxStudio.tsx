import React, { useState } from 'react';
import LtxVideoGenerator from './LtxVideoGenerator';
import CharacterGenerator from './CharacterGenerator';

/** Apartado "Vídeo LTX" con pestañas: generación de vídeo y de personajes. */
export default function LtxStudio() {
  const [tab, setTab] = useState<'video' | 'chars'>('video');

  const tabBtn = (key: 'video' | 'chars', label: string) => (
    <button
      onClick={() => setTab(key)}
      style={{
        padding: '8px 18px', borderRadius: 8, border: 'none', cursor: 'pointer',
        fontWeight: 600, fontSize: '0.9rem',
        background: tab === key ? '#0e7490' : '#1e293b',
        color: tab === key ? '#fff' : '#94a3b8',
      }}
    >{label}</button>
  );

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <div style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
        {tabBtn('video', '🎬 Vídeo')}
        {tabBtn('chars', '🧑‍🎨 Personajes')}
      </div>
      {tab === 'video' ? <LtxVideoGenerator /> : <CharacterGenerator />}
    </div>
  );
}
