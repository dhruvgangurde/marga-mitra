import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { deptName, dayRange, metres, methodLabel, workStatusBadge } from '../../api/format';
import { useShownPlan, useWorks } from '../../api/hooks';
import type { WorkView } from '../../api/types';
import { DeptChip, Icon, StatusBadge, Tabs, TextField } from '../../ui';

type Filter = 'all' | 'moved' | 'digging' | 'done';

const MATCHES: Record<Filter, (v: WorkView) => boolean> = {
  all: () => true,
  moved: (v) => v.status === 'moved' || v.status === 'shared',
  digging: (v) => v.status === 'digging',
  done: (v) => v.status === 'done' || v.status === 'verified',
};

const startOf = (v: WorkView): number => v.assignment?.start_day ?? v.work.requested_start;

export function WorksTab({ onPick }: { onPick?: (workId: string) => void }) {
  const [params] = useSearchParams();
  const [text, setText] = useState('');
  const [filter, setFilter] = useState<Filter>('all');
  const plan = useShownPlan().data;
  const views = useWorks(plan?.plan_id).data ?? [];
  const selected = params.get('work');

  const needle = text.trim().toLowerCase();
  const found = views.filter((v) => !needle || [v.work.work_id, v.work.title, v.work.road_name, deptName(v.work.dept)]
    .some((field) => field.toLowerCase().includes(needle)));
  const shown = found.filter(MATCHES[filter]).sort((a, b) => startOf(a) - startOf(b) || a.work.work_id.localeCompare(b.work.work_id));

  useEffect(() => {
    if (selected) document.getElementById('work-card-' + selected)?.scrollIntoView({ block: 'nearest' });
  }, [selected, shown.length]);

  const linkTo = (id: string): string => {
    const next = new URLSearchParams(params);
    next.set('tab', 'works');
    next.set('work', id);
    return '?' + next.toString();
  };

  const items = [
    { id: 'all', label: 'All', count: found.length },
    { id: 'moved', label: 'Moved', count: found.filter(MATCHES.moved).length },
    { id: 'digging', label: 'Digging', count: found.filter(MATCHES.digging).length },
    { id: 'done', label: 'Done', count: found.filter(MATCHES.done).length },
  ];

  return (
    <div className="mm-app-works">
      <TextField label="Find a work" placeholder="Road, department or ID" value={text} onChange={(e) => setText(e.target.value)} />
      <Tabs items={items} value={filter} onChange={(id) => setFilter(id as Filter)} label="Filter works" />
      {shown.length === 0 ? (
        <div className="mm-app-works__empty">
          <Icon name="question" size={24} />
          <p className="body" style={{ margin: 0, color: 'var(--ink-2)' }}>
            {text.trim() ? `No work matches \u201c${text.trim()}\u201d.` : 'No works in this view.'}
          </p>
        </div>
      ) : (
        <ul className="mm-app-works__list">
          {shown.map((v) => {
            const badge = workStatusBadge(v.status);
            const mode = v.assignment?.mode ?? v.work.modes[0]?.mode ?? 'open_cut';
            const how = v.work.dept === 'roads' ? 'after every dig' : methodLabel(mode);
            return (
              <li key={v.work.work_id}>
                <Link
                  id={'work-card-' + v.work.work_id}
                  to={linkTo(v.work.work_id)}
                  replace
                  onClick={() => onPick?.(v.work.work_id)}
                  className="mm-card mm-card--interactive mm-app-works__card"
                  aria-current={selected === v.work.work_id ? 'true' : undefined}
                >
                  <span className="mm-app-works__row">
                    <DeptChip dept={v.work.dept} />
                    <span className="mono" style={{ color: 'var(--ink-3)' }}>{v.work.work_id}</span>
                    <span style={{ marginLeft: 'auto' }}><StatusBadge status={badge.status}>{badge.label}</StatusBadge></span>
                  </span>
                  <span className="body-strong">{v.work.title}, {v.work.road_name}</span>
                  <span className="mm-app-works__row mm-app-works__row--split">
                    <span className="small" style={{ color: 'var(--ink-3)' }}>{`${metres(v.work.length_m)} \u00b7 ${how}`}</span>
                    <span className="mono">{v.assignment ? dayRange(v.assignment.start_day, v.assignment.end_day) : ''}</span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}