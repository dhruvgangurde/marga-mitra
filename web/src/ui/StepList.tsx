import { Icon } from './Icon';
import type { IconName } from './icons';
import { cx } from './util';

type StepStatus = 'done' | 'running' | 'needs' | 'waiting';

export interface StepListProps { steps: { text: string; detail?: string; status?: StepStatus }[] }

const STEP_ICON: Record<StepStatus, IconName | null> = { done: 'check', running: null, needs: 'hand', waiting: null };

export function StepList({ steps }: StepListProps) {
  return (
    <ol className="mm-steps">
      {steps.map((s, i) => {
        const status = s.status ?? 'waiting';
        const icon = STEP_ICON[status];
        return (
          <li key={i} className={cx('mm-step', 'mm-step--' + status)}>
            <span className="mm-step__dot" aria-hidden="true">{icon ? <Icon name={icon} size={11} /> : null}</span>
            <span>
              {s.text}
              {s.detail ? <span className="mm-step__detail">{s.detail}</span> : null}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
