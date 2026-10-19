import type * as React from 'react';
import { Icon } from './Icon';
import { cx } from './util';

export interface PhotoSlotProps { label?: string; hint?: string; src?: string; alt?: string; meta?: string; badge?: React.ReactNode; onPick?: () => void }

export function PhotoSlot({ label, hint, src, alt, meta, badge, onPick }: PhotoSlotProps) {
  if (src) {
    return (
      <figure className={cx('mm-photo', 'mm-photo--filled')} style={{ margin: 0 }}>
        <img src={src} alt={alt ?? label ?? 'Site photo'} />
        <figcaption className="mm-photo__meta"><span>{meta}</span>{badge || null}</figcaption>
      </figure>
    );
  }
  return (
    <button type="button" className={cx('mm-photo', 'mm-photo--empty')} onClick={onPick} style={{ font: 'inherit', color: 'inherit' }}>
      <Icon name="camera" size={28} />
      <span className="mm-photo__title">{label ?? 'Take photo'}</span>
      {hint ? <span className="mm-photo__hint">{hint}</span> : null}
    </button>
  );
}
