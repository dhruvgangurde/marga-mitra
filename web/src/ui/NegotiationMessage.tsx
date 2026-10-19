import { DeptChip } from './DeptChip';
import type { Dept } from './depts';
import { cx } from './util';

export interface NegotiationMessageProps {
  sender: Dept;
  /** @deprecated use sender */
  from?: Dept;
  to?: string;
  type: 'NOTICE' | 'ACCEPT' | 'COUNTER' | 'ESCALATE' | 'DECISION';
  round?: number;
  time?: string;
  body?: string;
  options?: { label: string; cost: string }[];
  fresh?: boolean;
}

export function NegotiationMessage({ sender, from, to, type, round, time, body, options, fresh }: NegotiationMessageProps) {
  const kind = (type ?? 'NOTICE').toUpperCase();
  return (
    <article className={cx('mm-msg', 'mm-msg--' + kind.toLowerCase(), fresh && 'mm-msg--fresh')}>
      <header className="mm-msg__head">
        <DeptChip dept={sender ?? from} />
        {to ? <span className="mm-msg__to">{'→ ' + to}</span> : null}
        <span className="mm-msg__type">{kind}</span>
        <time className="mm-msg__time">{(round ? 'R' + round + ' · ' : '') + (time ?? '')}</time>
      </header>
      {body ? <p className="mm-msg__body">{body}</p> : null}
      {options && options.length ? (
        <ul className="mm-msg__opts">
          {options.map((o, i) => <li key={i} className="mm-msg__opt"><span>{o.label}</span><span>{o.cost}</span></li>)}
        </ul>
      ) : null}
    </article>
  );
}
