import type * as React from 'react';
import { cx, scallopPath } from './util';

export interface SealProps { kind?: 'verified' | 'held' | 'inspect' | 'brand'; size?: number; stamp?: boolean; label?: string; children?: React.ReactNode }

const PATH = scallopPath(100, 18, 6);

export function Seal({ kind = 'verified', size = 96, stamp, label, children }: SealProps) {
  return (
    <span
      className={cx('mm-seal', 'mm-seal--' + kind, stamp && 'mm-seal--stamp')}
      style={{ '--seal-size': size + 'px' } as React.CSSProperties}
      role="img"
      aria-label={label || (typeof children === 'string' ? children : kind)}
    >
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <path className="mm-seal__shadow" d={PATH} transform="translate(3 3)" />
        <path className="mm-seal__body" d={PATH} />
      </svg>
      <span className="mm-seal__text" aria-hidden="true">{children}</span>
    </span>
  );
}
