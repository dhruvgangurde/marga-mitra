import { cx } from './util';

export interface ToggleProps { checked: boolean; onChange?: (next: boolean) => void; off?: string; on?: string; label?: string }

export function Toggle({ checked, onChange, off, on, label }: ToggleProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked ? 'true' : 'false'}
      aria-label={label}
      className="mm-toggle"
      onClick={() => onChange?.(!checked)}
      style={{ background: 'none', border: 0, padding: 0, font: 'inherit' }}
    >
      {off ? <span className={cx('mm-toggle__side', !checked && 'mm-toggle__side--on')}>{off}</span> : null}
      <span className="mm-toggle__track"><span className="mm-toggle__knob" /></span>
      {on ? <span className={cx('mm-toggle__side', checked && 'mm-toggle__side--on')}>{on}</span> : null}
    </button>
  );
}
