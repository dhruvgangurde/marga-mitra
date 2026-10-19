import { useNavigate } from 'react-router-dom';
import { Button } from '../ui';

export function NotFound() {
  const navigate = useNavigate();
  return (
    <main className="mm-app-notfound">
      <h1 className="display-2" style={{ margin: 0 }}>Page not found</h1>
      <p className="body-l" style={{ margin: 0, color: 'var(--ink-2)' }}>This page does not exist.</p>
      <Button variant="primary" onClick={() => navigate('/command')}>Open command centre</Button>
    </main>
  );
}