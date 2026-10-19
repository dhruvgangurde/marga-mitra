import type * as React from 'react';
import { Icon } from './Icon';
import type { IconName } from './icons';
import { cx } from './util';

type BannerTone = 'info' | 'warn' | 'danger' | 'ok' | 'ink';

export interface BannerProps { tone?: BannerTone; title?: React.ReactNode; icon?: IconName; action?: React.ReactNode; children?: React.ReactNode }

const BANNER_ICON: Record<BannerTone, IconName> = { info: 'info', warn: 'warning', danger: 'warning', ok: 'sealCheck', ink: 'info' };

export function Banner({ tone = 'info', title, icon, action, children }: BannerProps) {
  return (
    <div className={cx('mm-banner', tone !== 'info' && 'mm-banner--' + tone)} role={tone === 'danger' ? 'alert' : 'status'}>
      <Icon name={icon || BANNER_ICON[tone]} />
      <div className="mm-banner__body">
        {title ? <div className="mm-banner__title">{title}</div> : null}
        {children ? <div className="mm-banner__text">{children}</div> : null}
      </div>
      {action || null}
    </div>
  );
}
