import { motion, useReducedMotion } from 'motion/react';
import { Link, useNavigate } from 'react-router-dom';
import { useRole } from '../../app/role';
import type { RoleId } from '../../app/role';
import { Button, Card, DeptChip, FolderCard, Icon, Seal, Tag } from '../../ui';
import type { IconName } from '../../ui';

const EASE: [number, number, number, number] = [0.2, 0.8, 0.2, 1];

type Word = { text: string; script?: boolean; breakAfter?: boolean };
const WORDS: Word[] = [
  { text: 'Dig' },
  { text: 'once.', script: true, breakAfter: true },
  { text: 'Fix' },
  { text: 'right.', breakAfter: true },
  { text: 'Keep' },
  { text: 'roads' },
  { text: 'moving.' },
];

function HeroWord({ word, index }: { word: Word; index: number }) {
  const reduce = useReducedMotion();
  const cls = 'mm-app-hero__word' + (word.script ? ' mm-app-hero__script' : '');
  return (
    <>
      <motion.span
        className={cls}
        initial={reduce ? false : { opacity: 0, y: 12 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ duration: 0.32, ease: EASE, delay: index * 0.04 }}
      >
        {word.text}
      </motion.span>
      {word.breakAfter ? <br /> : ' '}
    </>
  );
}

const STATS: { num: string; line: string; note: string }[] = [
  { num: '2,385', line: 'deaths in pothole crashes in India in 2024', note: '1' },
  { num: '₹3,000 cr', line: 'lost every year when digging damages underground cables', note: '2' },
  { num: '1,289 km', line: 'of new water pipes planned under Mangaluru roads', note: '3' },
  { num: '46%', line: 'less serious roadworks disruption in London after it charged for digging busy roads at peak times', note: '4' },
];

const ROLES: { icon: IconName; who: string; screen: string; line: string; href: string; role: RoleId }[] = [
  { icon: 'buildings', who: 'Ward engineer', screen: 'Command centre', line: 'See every dig in the ward, run the plan and approve changes.', href: '/command', role: 'ward_engineer' },
  { icon: 'handshake', who: 'Department officer', screen: 'Approvals', line: 'See what changed for your department and approve it from your phone.', href: '/approvals', role: 'department_officer' },
  { icon: 'hardhat', who: 'Field crew', screen: 'Field app', line: 'Take before and after photos at the site to get the repair paid.', href: '/field', role: 'field_crew' },
  { icon: 'users', who: 'Resident', screen: 'Report or confirm', line: 'Report a burst pipe or a gas smell, or tell the city your road is fixed.', href: '/report', role: 'resident' },
  { icon: 'eye', who: 'Anyone', screen: 'Public record', line: 'Every decision, its reason and who made it. Check that nothing was changed.', href: '/record', role: 'visitor' },
];

export default function LandingScreen() {
  const navigate = useNavigate();
  const { setRole } = useRole();
  return (
    <>
      <main className="mm-app-land">
        <section className="mm-app-hero" aria-labelledby="land-hero">
          <Tag>Surathkal pilot · Mangaluru</Tag>
          <h1 id="land-hero" className="display-hero" aria-label="Dig once. Fix right. Keep roads moving.">
            {WORDS.map((w, i) => <HeroWord key={w.text} word={w} index={i} />)}
          </h1>
          <div className="mm-app-hero__row">
            <div className="mm-app-hero__left">
              <p className="body-l">
                Water, drainage, gas, power, telecom and roads each dig on their own calendar, so the same road is cut again and again. MargaMitra gets their agents to agree on one plan, moves digging away from heavy rain and bad air, and releases repair money only after photo proof.
              </p>
              <div className="mm-app-hero__buttons">
                <Button variant="primary" size="lg" onClick={() => navigate('/command')}>Open command centre</Button>
                <Button variant="secondary" size="lg" icon="eye" onClick={() => navigate('/record')}>See the public record</Button>
              </div>
            </div>
            <Seal kind="brand" size={136} label="Dig once">Dig once</Seal>
          </div>
        </section>

        <section aria-labelledby="land-plan">
          <h2 id="land-plan" className="display-1 mm-app-h2">One plan for every dig</h2>
          <p className="body-l mm-app-lede">Three steps, run every day for the whole ward.</p>
          <div className="mm-app-folders">
            <FolderCard tab="01 Plan" icon="handshake" tone="paper">
              <h3 className="title-l mm-app-folder-title">Agents agree on one plan</h3>
              <p className="body mm-app-folder-text">Each department's agent books its works. When two works clash on a road, the agents negotiate for up to 3 rounds and the scheduler picks the dates, sharing one trench where it can.</p>
              <div className="mm-app-chips">
                <DeptChip dept="water" />
                <DeptChip dept="telecom" />
                <DeptChip dept="solver" />
              </div>
            </FolderCard>
            <FolderCard tab="02 Adapt" icon="rain" tone="maroon">
              <h3 className="title-l mm-app-folder-title">The plan moves before the rain</h3>
              <p className="body mm-app-folder-text mm-app-folder-text--dark">Rain, air-quality and event forecasts are checked every day. Works on low-lying roads move out of heavy rain; dusty open cuts move out of poor-air days.</p>
            </FolderCard>
            <FolderCard tab="03 Verify" icon="sealCheck" tone="ink">
              <h3 className="title-l mm-app-folder-title">Money only after proof</h3>
              <p className="body mm-app-folder-text mm-app-folder-text--dark">Crews take before and after photos at the site. MargaMitra checks the place, the time and photo reuse, a resident confirms, and only then is the deposit released.</p>
            </FolderCard>
          </div>
        </section>

        <section aria-labelledby="land-why">
          <h2 id="land-why" className="display-1 mm-app-h2">Why it matters</h2>
          <p className="body-l mm-app-lede">Uncoordinated digging costs lives, money and time.</p>
          <Card style={{ padding: 0 }}>
            <div className="mm-app-stats">
              {STATS.map((s) => (
                <div key={s.num} className="mm-app-stat">
                  <p className="display-2 mm-app-stat__num">{s.num}</p>
                  <p className="body mm-app-stat__line">{s.line} <sup>{s.note}</sup></p>
                </div>
              ))}
            </div>
          </Card>
          <p className="small mm-app-sources">
            Sources: 1 PTI via Siasat, 14 Feb 2026 (reply in Parliament) · 2 PIB, 22 Mar 2023 · 3 NewsKarnataka, 6 Jun 2026 · 4 Transport for London, Apr 2014
          </p>
        </section>

        <section className="mm-app-who" aria-labelledby="land-who">
          <Tag tone="lime">Pick your screen</Tag>
          <h2 id="land-who" className="display-1">Who are you?</h2>
          <div className="mm-app-roles">
            {ROLES.map((r) => (
              <Link key={r.href} to={r.href} className="mm-app-role" onClick={() => setRole(r.role)}>
                <span className="mm-app-role__icon"><Icon name={r.icon} size={22} /></span>
                <span className="title">{r.who}</span>
                <span className="mono-label" style={{ color: 'var(--ink-3)' }}>{r.screen}</span>
                <span className="body mm-app-role__line">{r.line}</span>
              </Link>
            ))}
          </div>
        </section>
      </main>

      <footer className="mm-app-foot">
        <div className="mm-app-foot__in">
          <span className="mm-app-foot__brand">MARGAMITRA</span>
          <p className="small mm-app-foot__text">
            Built for ChronoForge 2026, NITK Surathkal, by team ExploreeTinkerBell (SPIT, Mumbai). Road data © OpenStreetMap contributors. Forecasts by Open-Meteo.
          </p>
        </div>
      </footer>
    </>
  );
}