import type * as React from 'react';
import { cx } from './util';

export interface CardProps {
  title?: React.ReactNode;
  meta?: React.ReactNode;
  tone?: 'maroon' | 'ink';
  soft?: boolean;
  flat?: boolean;
  interactive?: boolean;
  onClick?: () => void;
  style?: React.CSSProperties;
  children?: React.ReactNode;
}

export function Card({ title, meta, tone, soft, flat, interactive, onClick, style, children }: CardProps) {
  // The reference has no keyboard handling; this keeps a clickable card usable without a mouse.
  const onKeyDown = interactive && onClick
    ? (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); }
    }
    : undefined;
  return (
    <div
      className={cx('mm-card', tone && 'mm-card--' + tone, soft && 'mm-card--soft', flat && 'mm-card--flat', interactive && 'mm-card--interactive')}
      onClick={onClick}
      onKeyDown={onKeyDown}
      tabIndex={interactive ? 0 : undefined}
      role={interactive && onClick ? 'button' : undefined}
      style={style}
    >
      {title ? <h3 className="mm-card__title">{title}</h3> : null}
      {meta ? <div className="mm-card__meta">{meta}</div> : null}
      {children}
    </div>
  );
}
