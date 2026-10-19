import type * as React from 'react';
import { DEPTS } from './depts';
import { Icon } from './Icon';

type LegendDept = 'water' | 'drainage' | 'gas' | 'power' | 'telecom' | 'roads';

export interface MapLegendProps { counts?: Partial<Record<LegendDept, number>>; title?: string }

const LEGEND_DEPTS: LegendDept[] = ['water', 'drainage', 'gas', 'power', 'telecom', 'roads'];

export function MapLegend({ counts = {}, title }: MapLegendProps) {
  return (
    <div className="mm-legend" role="group" aria-label="Map legend">
      <div className="mm-overline">{title ?? 'On the map'}</div>
      {LEGEND_DEPTS.map((k) => (
        <div key={k} className="mm-legend__row">
          <span className="mm-legend__swatch" style={{ '--dept': 'var(--dept-' + k + ')' } as React.CSSProperties} />
          <Icon name={DEPTS[k].icon} size={14} />
          {DEPTS[k].name}
          {counts[k] != null ? <span className="mm-legend__count">{counts[k]}</span> : null}
        </div>
      ))}
      <div className="mm-legend__row"><span className="mm-legend__swatch mm-legend__swatch--shared" />Shared trench</div>
      <div className="mm-legend__row"><span className="mm-legend__swatch mm-legend__swatch--nodig" /><Icon name="lock" size={14} />No new digs (protected)</div>
      <div className="mm-legend__row"><span className="mm-legend__swatch mm-legend__swatch--rain" />Heavy rain forecast</div>
      <div className="mm-legend__row"><span className="mm-legend__swatch mm-legend__swatch--air" />Poor air forecast</div>
      <div className="mm-legend__row"><span className="mm-legend__swatch mm-legend__swatch--event" />Event route</div>
    </div>
  );
}
