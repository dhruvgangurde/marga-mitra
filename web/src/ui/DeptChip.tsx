import type * as React from 'react';
import { DEPTS } from './depts';
import type { Dept } from './depts';
import { Icon } from './Icon';
import { cx } from './util';

export interface DeptChipProps { dept: Dept; children?: React.ReactNode }

export function DeptChip({ dept, children }: DeptChipProps) {
  const d = DEPTS[dept] ?? DEPTS.roads;
  return (
    <span className={cx('mm-dept', 'mm-dept--' + dept)}>
      <span className="mm-dept__icon"><Icon name={d.icon} size={12} /></span>
      {children || d.name}
    </span>
  );
}
