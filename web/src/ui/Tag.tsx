import type * as React from 'react';
import { Icon } from './Icon';
import type { IconName } from './icons';
import { cx } from './util';

export interface TagProps { tone?: 'ink' | 'lime' | 'maroon'; flat?: boolean; icon?: IconName; children?: React.ReactNode }

export function Tag({ tone, flat, icon, children }: TagProps) {
  return (
    <span className={cx('mm-tag', tone && tone !== 'ink' && 'mm-tag--' + tone, flat && 'mm-tag--flat')}>
      {icon ? <Icon name={icon} size={14} /> : null}
      {children}
    </span>
  );
}
