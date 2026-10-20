import { Link } from 'react-router-dom';
import { useWorks } from '../../api/hooks';
import { dayLabel, dayRange, methodLabel, metres, TODAY_DAY, workStatusBadge } from '../../api/format';
import type { WorkView } from '../../api/types';
import { Button, Card, DeptChip, Icon, PhoneScreen, StatusBadge } from '../../ui';

const onSiteToday = (v: WorkView) =>
  v.status === 'held' || (v.assignment != null && v.assignment.start_day <= TODAY_DAY && TODAY_DAY <= v.assignment.end_day);

export default function FieldListScreen() {
  const works = useWorks();
  const list = (works.data ?? []).filter(onSiteToday).sort((a, b) => a.work.work_id.localeCompare(b.work.work_id));

  return (
    <PhoneScreen title="My works" backTo="/" badge={<StatusBadge status="live">{dayLabel(TODAY_DAY)}</StatusBadge>}>
      <p className="small" style={{ margin: 0, color: 'var(--ink-3)' }}>
        Works on site today. Take a before photo when you start and an after photo when the road is patched.
      </p>
      {works.isLoading ? null : list.length === 0 ? (
        <Card soft style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 12 }}>
          <Icon name="hardhat" size={24} />
          <p className="body-l" style={{ margin: 0 }}>No work on site today.</p>
          <Button as="a" href="/record">See the public record</Button>
        </Card>
      ) : (
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {list.map(({ work, assignment, status }) => {
            const badge = workStatusBadge(status);
            return (
              <li key={work.work_id}>
                <Link
                  to={`/field/${work.work_id}`}
                  className="mm-card mm-card--interactive"
                  style={{ display: 'flex', flexDirection: 'column', gap: 6, padding: 12, textDecoration: 'none', color: 'var(--ink)' }}
                >
                  <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <DeptChip dept={work.dept} />
                    <span className="mono" style={{ color: 'var(--ink-3)' }}>{work.work_id}</span>
                    <span style={{ marginLeft: 'auto' }}><StatusBadge status={badge.status}>{badge.label}</StatusBadge></span>
                  </span>
                  <span className="body-strong">{`${work.title}, ${work.road_name}`}</span>
                  <span style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <span className="small" style={{ color: 'var(--ink-3)' }}>
                      {`${metres(work.length_m)} · ${methodLabel(assignment?.mode ?? work.modes[0].mode)}`}
                    </span>
                    {assignment ? <span className="mono">{dayRange(assignment.start_day, assignment.end_day)}</span> : null}
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </PhoneScreen>
  );
}
