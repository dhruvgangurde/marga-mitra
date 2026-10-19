import { Icon } from './Icon';
import type { IconName } from './icons';
import { cx } from './util';

export interface IconButtonProps { icon: IconName; label: string; tone?: 'ink'; size?: 'sm'; onClick?: () => void; disabled?: boolean }

export function IconButton({ icon, label, tone, size, onClick, disabled }: IconButtonProps) {
  return (
    <button
      type="button"
      className={cx('mm-iconbtn', tone === 'ink' && 'mm-iconbtn--ink', size === 'sm' && 'mm-iconbtn--sm')}
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
    >
      <Icon name={icon} size={size === 'sm' ? 16 : 20} />
    </button>
  );
}
