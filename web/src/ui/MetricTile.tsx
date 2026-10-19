import { cx, decimals, useCountUp } from './util';

export interface MetricTileProps { label: string; value: number | string; unit?: string; compare?: string; delta?: string; better?: boolean; countUp?: boolean }

export function MetricTile({ label, value, unit, compare, delta, better, countUp }: MetricTileProps) {
  const v = useCountUp(value, countUp !== false);
  const dp = decimals(value);
  return (
    <div className="mm-metric">
      <div className="mm-metric__label">{label}</div>
      <div className="mm-metric__value">
        {typeof v === 'number' ? v.toLocaleString('en-IN', { minimumFractionDigits: dp, maximumFractionDigits: dp }) : v}
        {unit ? <span className="mm-metric__unit">{unit}</span> : null}
      </div>
      {delta || compare ? (
        <div className="mm-metric__foot">
          {compare ? <span>{compare}</span> : <span />}
          {delta ? <span className={cx('mm-delta', better === false ? 'mm-delta--worse' : 'mm-delta--better')}>{delta}</span> : null}
        </div>
      ) : null}
    </div>
  );
}
