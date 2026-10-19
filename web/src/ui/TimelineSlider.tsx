import type * as React from 'react';
import { IconButton } from './IconButton';
import { cx } from './util';

export interface TimelineSliderProps {
  days?: number;
  value: number;
  onChange?: (day: number) => void;
  valueLabel?: string;
  tickLabel?: (day: number) => string;
  range?: string;
  risks?: { start: number; end: number; kind: 'rain' | 'air' | 'event'; label?: string }[];
  playing?: boolean;
  onPlay?: () => void;
}

export function TimelineSlider({ days = 28, value = 0, onChange, valueLabel, tickLabel, range, risks, playing, onPlay }: TimelineSliderProps) {
  const pct = (d: number) => (d / Math.max(1, days - 1)) * 100 + '%';
  const ticks: number[] = [];
  for (let d = 0; d < days; d += 7) ticks.push(d);

  function onKey(e: React.KeyboardEvent<HTMLSpanElement>) {
    if (!onChange) return;
    const moves: Record<string, number> = { ArrowRight: Math.min(days - 1, value + 1), ArrowLeft: Math.max(0, value - 1), Home: 0, End: days - 1 };
    const next = moves[e.key];
    if (next === undefined) return;
    // Home and End would otherwise scroll the page.
    e.preventDefault();
    onChange(next);
  }

  function onClick(e: React.MouseEvent<HTMLDivElement>) {
    if (!onChange) return;
    const r = e.currentTarget.getBoundingClientRect();
    onChange(Math.round(((e.clientX - r.left) / r.width) * (days - 1)));
  }

  return (
    <div className="mm-timeline">
      <IconButton icon={playing ? 'pause' : 'play'} label={playing ? 'Pause' : 'Play the plan'} onClick={onPlay} tone="ink" />
      <div className="mm-timeline__track" onClick={onClick}>
        <span className="mm-timeline__fill" style={{ width: pct(value) }} />
        {(risks ?? []).map((r, i) => (
          <span
            key={i}
            className={cx('mm-timeline__risk', r.kind !== 'rain' && 'mm-timeline__risk--' + r.kind)}
            style={{ left: pct(r.start), width: 'calc(' + pct(r.end) + ' - ' + pct(r.start) + ')' }}
            title={r.label}
          />
        ))}
        <span className="mm-timeline__ticks" aria-hidden="true">
          {ticks.map((t) => <span key={t}>{tickLabel ? tickLabel(t) : 'D' + (t + 1)}</span>)}
        </span>
        <span
          className="mm-timeline__thumb"
          role="slider"
          tabIndex={0}
          aria-label="Plan day"
          aria-valuemin={0}
          aria-valuemax={days - 1}
          aria-valuenow={value}
          aria-valuetext={valueLabel}
          onKeyDown={onKey}
          style={{ left: pct(value) }}
        >
          <span className="mm-timeline__bubble">{valueLabel || 'Day ' + (value + 1)}</span>
        </span>
      </div>
      {range ? <span className="mm-timeline__range">{range}</span> : null}
    </div>
  );
}
