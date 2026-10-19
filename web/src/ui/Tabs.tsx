import { useRef } from 'react';
import type * as React from 'react';
import { Icon } from './Icon';
import type { IconName } from './icons';

export interface TabsProps { items: { id: string; label: string; count?: number; icon?: IconName }[]; value: string; onChange?: (id: string) => void; label?: string }

export function Tabs({ items, value, onChange, label }: TabsProps) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  // Roving tab stop: if no tab matches the value, the first one stays reachable.
  const selected = Math.max(0, items.findIndex((it) => it.id === value));

  // The reference has no keyboard support; arrows, Home and End follow the ARIA tabs pattern.
  function onKeyDown(e: React.KeyboardEvent<HTMLButtonElement>, i: number) {
    const n = items.length;
    const moves: Record<string, number> = { ArrowRight: (i + 1) % n, ArrowLeft: (i - 1 + n) % n, Home: 0, End: n - 1 };
    const next = moves[e.key];
    if (next === undefined) return;
    e.preventDefault();
    onChange?.(items[next].id);
    refs.current[next]?.focus();
  }

  return (
    <div className="mm-tabs" role="tablist" aria-label={label}>
      {items.map((it, i) => (
        <button
          key={it.id}
          ref={(el) => { refs.current[i] = el; }}
          type="button"
          role="tab"
          aria-selected={it.id === value ? 'true' : 'false'}
          tabIndex={i === selected ? 0 : -1}
          className="mm-tab"
          onClick={() => onChange?.(it.id)}
          onKeyDown={(e) => onKeyDown(e, i)}
        >
          {it.icon ? <Icon name={it.icon} size={16} /> : null}
          {it.label}
          {it.count != null ? <span className="mm-tab__count">{it.count}</span> : null}
        </button>
      ))}
    </div>
  );
}
