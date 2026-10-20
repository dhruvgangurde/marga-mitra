import { Banner } from './Banner';
import { Button } from './Button';

export interface LoadErrorProps { queries: { isError: boolean; refetch: () => unknown }[] }

// Shows once any of a screen's queries failed; Try again reloads only the failed ones.
export function LoadError({ queries }: LoadErrorProps) {
  const failed = queries.filter((q) => q.isError);
  if (failed.length === 0) return null;
  return (
    <Banner
      tone="warn"
      title="Could not load"
      action={<Button variant="ghost" onClick={() => failed.forEach((q) => void q.refetch())}>Try again</Button>}
    >
      Check your connection.
    </Banner>
  );
}
