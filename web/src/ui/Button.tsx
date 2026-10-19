import type * as React from 'react';
import { AppLink } from './AppLink';
import { Icon } from './Icon';
import type { IconName } from './icons';
import { cx, scallopPath } from './util';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'md' | 'lg';
  icon?: IconName;
  arrow?: boolean;
  block?: boolean;
  as?: 'a' | 'button';
  href?: string;
}

function ArrowSeal() {
  return (
    <span className="mm-btn__seal" aria-hidden="true">
      <svg viewBox="0 0 24 24">
        <path d={scallopPath(24, 12, 2.2)} fill="var(--signal)" stroke="var(--ink)" strokeWidth={1.2} />
        <path d="M7.5 12h8.5m-3.4-3.6L16.2 12l-3.6 3.6" fill="none" stroke="var(--paper)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}

export function Button({ variant = 'secondary', size = 'md', icon, arrow, block, as, href, className, children, ...rest }: ButtonProps) {
  const primary = variant === 'primary';
  const face = (
    <span className="mm-btn__face">
      {icon && !primary ? <Icon name={icon} /> : null}
      {primary ? (
        <span className="mm-btn__label">
          <span className="mm-btn__roll" data-text={typeof children === 'string' ? children : ''}>{children}</span>
        </span>
      ) : (
        <span>{children}</span>
      )}
      {primary && arrow !== false ? <ArrowSeal /> : null}
    </span>
  );
  const cls = cx('mm-btn', 'mm-btn--' + variant, size === 'lg' && 'mm-btn--lg', block && 'mm-btn--block', className);
  if (as === 'a') {
    const anchor = rest as React.AnchorHTMLAttributes<HTMLAnchorElement>;
    return <AppLink {...anchor} href={href} className={cls}>{face}</AppLink>;
  }
  return <button type="button" {...rest} className={cls}>{face}</button>;
}
