import '@fontsource/geist/400.css';
import '@fontsource/geist/500.css';
import '@fontsource/geist/600.css';
import '@fontsource/geist/700.css';
import '@fontsource/geist-mono/400.css';
import '@fontsource/geist-mono/500.css';
import '@fontsource/bowlby-one/400.css';
import '@fontsource/kaushan-script/400.css';
import './styles/tokens.css';
import './styles/bundle.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

// Placeholder until FE-A adds the app shell.
function Placeholder() {
  return (
    <main style={{ padding: 'var(--space-10)' }}>
      <h1 className="display-1" style={{ color: 'var(--maroon)', margin: 0 }}>MargaMitra</h1>
      <p className="body-l">Dig once. Fix right. Keep roads moving.</p>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Placeholder />
  </StrictMode>,
);