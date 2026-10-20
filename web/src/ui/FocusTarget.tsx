import { useEffect, useRef } from 'react';
import type * as React from 'react';

export interface FocusTargetProps { focus?: boolean; children?: React.ReactNode }

// Takes focus once when it appears, so keyboard and screen-reader users land on the new result.
export function FocusTarget({ focus = true, children }: FocusTargetProps) {
  const ref = useRef<HTMLDivElement>(null);
  const focusOnMount = useRef(focus);
  useEffect(() => {
    if (focusOnMount.current) ref.current?.focus();
  }, []);
  return <div ref={ref} tabIndex={-1}>{children}</div>;
}
