import { DeptChip } from './DeptChip';
import type { Dept } from './depts';
import { cx } from './util';

export interface DiffRowProps {
  dept: Dept;
  title: string;
  was?: string;
  /** @deprecated use was */
  from?: string;
  to: string;
  reason?: string;
  cost?: string;
  costDir?: 'up' | 'down';
}

// Renders an li: callers wrap DiffRows in a ul.
export function DiffRow({ dept, title, was: wasProp, from, to, reason, cost, costDir }: DiffRowProps) {
  const was = wasProp ?? from;
  return (
    <li className="mm-diff">
      <DeptChip dept={dept} />
      <div>
        <div className="mm-diff__title">{title}</div>
        <div className="mm-diff__dates">
          {was ? <s>{was}</s> : null}
          {was ? ' → ' : null}
          <b>{to}</b>
        </div>
        {reason ? <div className="mm-diff__reason">{reason}</div> : null}
      </div>
      {cost ? <span className={cx('mm-diff__cost', costDir === 'down' ? 'mm-diff__cost--down' : 'mm-diff__cost--up')}>{cost}</span> : <span />}
    </li>
  );
}
