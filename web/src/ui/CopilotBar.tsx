import { Button } from './Button';
import { Icon } from './Icon';
import { cx } from './util';

export interface CopilotBarProps { value: string; onChange?: (v: string) => void; onSubmit?: (v: string) => void; placeholder?: string; busy?: boolean; fixed?: boolean }

export function CopilotBar({ value, onChange, onSubmit, placeholder, busy, fixed }: CopilotBarProps) {
  return (
    <form
      className={cx('mm-copilot', fixed && 'mm-copilot--fixed')}
      onSubmit={(e) => { e.preventDefault(); onSubmit?.(value); }}
      role="search"
      aria-label="Copilot"
    >
      <span className="mm-copilot__badge"><Icon name="command" size={16} />Copilot</span>
      <input
        className="mm-copilot__input"
        value={value}
        onChange={(e) => onChange?.(e.target.value)}
        placeholder={placeholder ?? 'Tell MargaMitra what to do, for example: plan next month and keep the procession route clear'}
        aria-label="Copilot command"
      />
      <Button variant="primary" type="submit" disabled={busy}>{busy ? 'Working' : 'Run'}</Button>
    </form>
  );
}
