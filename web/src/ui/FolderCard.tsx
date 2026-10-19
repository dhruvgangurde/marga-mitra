import type * as React from 'react';
import { Icon } from './Icon';
import type { IconName } from './icons';
import { cx } from './util';

export interface FolderCardProps { tab: React.ReactNode; icon?: IconName; tone?: 'paper' | 'maroon' | 'ink'; style?: React.CSSProperties; children?: React.ReactNode }

export function FolderCard({ tab, icon, tone, style, children }: FolderCardProps) {
  return (
    <section className={cx('mm-folder', tone && 'mm-folder--' + tone)} style={style}>
      <div className="mm-folder__tab">
        {icon ? <Icon name={icon} size={16} /> : null}
        {tab}
      </div>
      <div className="mm-folder__body">{children}</div>
    </section>
  );
}
