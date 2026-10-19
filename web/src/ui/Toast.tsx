import type * as React from 'react';
import { Icon } from './Icon';
import type { IconName } from './icons';
import { cx } from './util';

export interface ToastProps { icon?: IconName; actionLabel?: string; onAction?: () => void; fixed?: boolean; children?: React.ReactNode }

export function Toast({ icon, actionLabel, onAction, fixed, children }: ToastProps) {
  return (
    <div className={cx('mm-toast', fixed && 'mm-toast--fixed')} role="status">
      {icon ? <Icon name={icon} /> : null}
      <span>{children}</span>
      {actionLabel ? <button type="button" className="mm-toast__action" onClick={onAction}>{actionLabel}</button> : null}
    </div>
  );
}
