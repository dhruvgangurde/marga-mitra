import type * as React from 'react';
import { Icon } from './Icon';
import type { IconName } from './icons';
import { cx } from './util';

export interface StatusBadgeProps { status: 'ok' | 'fail' | 'warn' | 'pending' | 'approved' | 'live' | 'emergency'; children?: React.ReactNode }

const STATUS_ICON: Record<StatusBadgeProps['status'], IconName | null> = {
  ok: 'check', fail: 'x', warn: 'question', pending: 'clock', approved: 'sealCheck', live: null, emergency: 'siren',
};

export function StatusBadge({ status, children }: StatusBadgeProps) {
  const icon = STATUS_ICON[status];
  return (
    <span className={cx('mm-badge', 'mm-badge--' + status)}>
      {icon ? <Icon name={icon} size={14} /> : null}
      {children}
    </span>
  );
}
