import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { USE_MOCKS } from '../api/client';
import { LiveEventsProvider } from '../api/live';
import { applyDemoState } from '../mocks/server';
import { RoleProvider } from './role';
import { routes } from './routes';

// Mock mode: pick the demo state from ?demo= once, before anything renders.
if (USE_MOCKS) {
  applyDemoState(new URLSearchParams(window.location.search).get('demo') ?? 'ready');
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30000, retry: 1 } },
});

const router = createBrowserRouter(routes);

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RoleProvider>
        <LiveEventsProvider>
          <RouterProvider router={router} />
        </LiveEventsProvider>
      </RoleProvider>
    </QueryClientProvider>
  );
}