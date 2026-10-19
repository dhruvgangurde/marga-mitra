import { lazy, Suspense } from 'react';
import type { ComponentType, LazyExoticComponent } from 'react';
import type { RouteObject } from 'react-router-dom';
import { desktopRoutesB, phoneRoutesB } from '../screens/routesB';
import { DesktopLayout } from './DesktopLayout';
import { NotFound } from './NotFound';

const LandingScreen = lazy(() => import('../screens/Landing/LandingScreen'));
const CommandScreen = lazy(() => import('../screens/Command/CommandScreen'));

function page(Screen: LazyExoticComponent<ComponentType>) {
  return (
    <Suspense fallback={<p className="mono mm-app-loading">Loading…</p>}>
      <Screen />
    </Suspense>
  );
}

export const routes: RouteObject[] = [
  {
    element: <DesktopLayout />,
    children: [
      { path: '/', element: page(LandingScreen) },
      { path: '/command', element: page(CommandScreen) },
      ...desktopRoutesB,
      { path: '*', element: <NotFound /> },
    ],
  },
  ...phoneRoutesB,
];