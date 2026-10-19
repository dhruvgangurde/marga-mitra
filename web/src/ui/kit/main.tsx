import '@fontsource/geist/400.css';
import '@fontsource/geist/500.css';
import '@fontsource/geist/600.css';
import '@fontsource/geist/700.css';
import '@fontsource/geist-mono/400.css';
import '@fontsource/geist-mono/500.css';
import '@fontsource/bowlby-one/400.css';
import '@fontsource/kaushan-script/400.css';
import '../../styles/tokens.css';
import '../../styles/bundle.css';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { KitPage } from './KitPage';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <MemoryRouter>
      <KitPage />
    </MemoryRouter>
  </StrictMode>,
);
