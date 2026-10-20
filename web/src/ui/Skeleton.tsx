export interface SkeletonProps { height: number }

export function Skeleton({ height }: SkeletonProps) {
  return <div aria-hidden="true" style={{ height, background: 'var(--sand)', borderRadius: 'var(--radius-xl)' }} />;
}
