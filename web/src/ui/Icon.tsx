import { ICONS } from './icons';
import type { IconName } from './icons';
import { cx } from './util';

export interface IconProps { name: IconName; size?: number; label?: string; className?: string }

export function Icon({ name, size, label, className }: IconProps) {
  const Glyph = ICONS[name];
  if (!Glyph) return null;
  return (
    <Glyph
      weight="bold"
      size={size ?? 20}
      className={cx('mm-icon', className)}
      aria-hidden={label ? undefined : 'true'}
      role={label ? 'img' : undefined}
      aria-label={label}
    />
  );
}
