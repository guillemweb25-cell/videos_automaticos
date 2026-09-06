import React, { useState } from 'react';
import LtxVideoGenerator from './LtxVideoGenerator';
import CharacterGenerator from './CharacterGenerator';
import CharacterImages from './CharacterImages';
import CharacterFromRef from './CharacterFromRef';

type Tab = 'video' | 'chars' | 'images' | 'ref';

/** Apartado "Vídeo LTX" con pestañas: vídeo, personajes e imágenes. */
export default function LtxStudio() {
  const [tab, setTab] = useState<Tab>('video');

  const tabBtn = (key: Tab, label: string) => (
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
      <div style={{ display: 'flex', gap: 8, marginBottom: 18, flexWrap: 'wrap' }}>
        {tabBtn('video', '🎬 Vídeo')}
        {tabBtn('chars', '🧑‍🎨 Personajes')}
        {tabBtn('images', '🖼️ Imágenes')}
        {tabBtn('ref', '🎯 Desde referencia')}
      </div>
      {tab === 'video' ? <LtxVideoGenerator /> : tab === 'chars' ? <CharacterGenerator /> : tab === 'images' ? <CharacterImages /> : <CharacterFromRef />}
    </div>
  );
}
