import { lazy, Suspense } from 'react';
import type { ComponentType, LazyExoticComponent } from 'react';
import type { RouteObject } from 'react-router-dom';

const ApprovalsScreen = lazy(() => import('./Approvals/ApprovalsScreen'));
const FieldListScreen = lazy(() => import('./Field/FieldListScreen'));
const FieldCaptureScreen = lazy(() => import('./Field/FieldCaptureScreen'));
const FieldResultScreen = lazy(() => import('./Field/FieldResultScreen'));
const ReportScreen = lazy(() => import('./Resident/ReportScreen'));
const ConfirmScreen = lazy(() => import('./Resident/ConfirmScreen'));
const RecordScreen = lazy(() => import('./Record/RecordScreen'));
const ImpactScreen = lazy(() => import('./Impact/ImpactScreen'));

function page(Screen: LazyExoticComponent<ComponentType>) {
  return (
    <Suspense fallback={<p className="mono" style={{ padding: 'var(--space-6)', color: 'var(--ink-3)' }}>Loading…</p>}>
      <Screen />
    </Suspense>
  );
}

// FE-A mounts these inside its pathless desktop layout route, under the TopBar.
export const desktopRoutesB: RouteObject[] = [
  { path: '/record', element: page(RecordScreen) },
  { path: '/impact', element: page(ImpactScreen) },
];

// FE-A mounts these at the top level: phone screens have no TopBar.
export const phoneRoutesB: RouteObject[] = [
  { path: '/approvals', element: page(ApprovalsScreen) },
  { path: '/field', element: page(FieldListScreen) },
  { path: '/field/:workId', element: page(FieldCaptureScreen) },
  { path: '/field/:workId/result', element: page(FieldResultScreen) },
  { path: '/report', element: page(ReportScreen) },
  { path: '/confirm/:workId', element: page(ConfirmScreen) },
];
