import { useEffect, useState } from 'react';
import type * as React from 'react';
import {
  Banner, Button, Card, CopilotBar, DataTable, DEPTS, DeptChip, DiffRow, FolderCard, Icon, IconButton, MapLegend, MetricTile,
  NegotiationMessage, PhotoSlot, Seal, StatusBadge, StepList, Tabs, Tag, TextField, Toast, Toggle, TimelineSlider, TopBar,
} from '..';
import type { Dept, IconName } from '..';
import { ICONS } from '../icons';

const ICON_NAMES = Object.keys(ICONS) as IconName[];
const DEPT_IDS = Object.keys(DEPTS) as Dept[];
const PLAN_DAYS = 28;
const ROW: React.CSSProperties = { display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'flex-start' };

// An img cannot read CSS variables, so the sand token is resolved once for the sample photo.
function sandPhoto(): string {
  const sand = getComputedStyle(document.documentElement).getPropertyValue('--sand').trim();
  return 'data:image/svg+xml,' + encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 4 3"><rect width="4" height="3" fill="${sand}"/></svg>`);
}

function Section({ name, shows, children }: { name: string; shows: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="display-3" style={{ margin: '0 0 8px' }}>{name}</h2>
      <p className="mono-label" style={{ margin: '0 0 16px', color: 'var(--ink-3)' }}>{shows}</p>
      <div style={ROW}>{children}</div>
    </section>
  );
}

const RECORD_COLUMNS = [
  { key: 'n', label: '#', num: true, mono: true },
  { key: 'time', label: 'Time', mono: true },
  { key: 'who', label: 'Who' },
  { key: 'what', label: 'What happened' },
  { key: 'work', label: 'Work', mono: true },
  { key: 'link', label: 'Link' },
];

const RECORD_ROWS = [
  { id: 'r4', n: 4, time: '10 Nov, 08:12', who: 'Field crew', what: 'Before photo added', work: 'W-104', link: 'Photo' },
  { id: 'r3', n: 3, time: '2 Nov, 09:20', who: 'Ward engineer', what: 'Plan approved', work: '16 works', link: 'Plan' },
  { id: 'r2', n: 2, time: '2 Nov, 09:12', who: 'Scheduler', what: 'Plan made: 4 digs → 2 on Munchur Road', work: '16 works', link: 'Plan' },
  { id: 'r1', n: 1, time: '2 Nov, 09:00', who: 'Coordinator', what: 'Planning started for 2–29 Nov', work: '—', link: 'Notice' },
];

export function KitPage() {
  const [photo] = useState(sandPhoto);
  const [stampKey, setStampKey] = useState(0);
  const [countKey, setCountKey] = useState(0);
  const [clicks, setClicks] = useState(0);
  const [tab, setTab] = useState('negotiation');
  const [newWay, setNewWay] = useState(true);
  const [day, setDay] = useState(8);
  const [playing, setPlaying] = useState(false);
  const [command, setCommand] = useState('');

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setDay((d) => (d >= PLAN_DAYS - 1 ? 0 : d + 1)), 400);
    return () => clearInterval(id);
  }, [playing]);

  return (
    <div className="mm-dotgrid" style={{ minHeight: '100vh' }}>
      <main style={{ maxWidth: 1200, margin: '0 auto', padding: '48px 24px 96px', display: 'flex', flexDirection: 'column', gap: 64 }}>
        <Section name="Icon" shows="name · size · label">
          {ICON_NAMES.map((n) => (
            <div key={n} style={{ width: 80, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
              <Icon name={n} />
              <span className="small" style={{ color: 'var(--ink-3)' }}>{n}</span>
            </div>
          ))}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
            <Icon name="sealCheck" size={16} />
            <Icon name="sealCheck" size={24} />
            <Icon name="sealCheck" size={28} label="Verified" />
          </div>
        </Section>

        <Section name="Button" shows="variant · size · icon · arrow · block · disabled · as · href">
          <Button variant="primary">Approve plan</Button>
          <Button variant="primary" size="lg">Plan next month</Button>
          <Button variant="primary" arrow={false}>Send</Button>
          <Button icon="refresh">Re-plan</Button>
          <Button variant="danger" icon="x">Reject</Button>
          <Button variant="ghost">Nothing is saved</Button>
          <Button disabled>Waiting</Button>
          <div style={{ width: 360 }}><Button variant="primary" block>Approve plan</Button></div>
          <Button as="a" href="/command">Open command centre</Button>
        </Section>

        <Section name="IconButton" shows="icon · label · tone · size · disabled">
          <IconButton icon="caretLeft" label="Back" />
          <IconButton icon="play" label="Play the plan" tone="ink" />
          <IconButton icon="x" label="Close" size="sm" />
          <IconButton icon="refresh" label="Re-plan" disabled />
        </Section>

        <Section name="Tag" shows="tone · flat · icon">
          <Tag>Live negotiation</Tag>
          <Tag tone="lime">Pick your screen</Tag>
          <Tag tone="maroon">Simulated forecast</Tag>
          <Tag tone="lime" flat>4 digs → 2 on Munchur Road</Tag>
          <Tag icon="rain">Heavy rain on 14–15 Nov</Tag>
        </Section>

        <Section name="StatusBadge" shows="status">
          <StatusBadge status="ok">Passed</StatusBadge>
          <StatusBadge status="fail">Photo reused</StatusBadge>
          <StatusBadge status="warn">Moved</StatusBadge>
          <StatusBadge status="pending">Waiting</StatusBadge>
          <StatusBadge status="approved">Shared trench</StatusBadge>
          <StatusBadge status="live">Digging</StatusBadge>
          <StatusBadge status="emergency">Emergency</StatusBadge>
        </Section>

        <Section name="DeptChip" shows="dept">
          {DEPT_IDS.map((d) => <DeptChip key={d} dept={d} />)}
        </Section>

        <Section name="Seal" shows="kind · size · stamp · label">
          <Seal kind="verified">Repair verified</Seal>
          <Seal kind="held">Money held</Seal>
          <Seal kind="inspect">Needs inspector</Seal>
          <Seal kind="brand" size={112}>Dig once</Seal>
          <Seal kind="verified" size={72}>Repair verified</Seal>
          <Seal kind="verified" size={120}>Repair verified</Seal>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
            <Seal key={stampKey} kind="verified" stamp>Repair verified</Seal>
            <Button variant="ghost" onClick={() => setStampKey((k) => k + 1)}>Stamp again</Button>
          </div>
        </Section>

        <Section name="Card" shows="title · meta · tone · soft · flat · interactive · onClick">
          <div style={{ width: 260 }}><Card title="W-104 water main" meta="Munchur Road · 12–15 Nov"><p className="body" style={{ margin: 0 }}>Shares the trench with T-221.</p></Card></div>
          <div style={{ width: 260 }}><Card interactive onClick={() => setClicks((c) => c + 1)} title="Open the plan"><p className="body" style={{ margin: 0 }}>Clicked {clicks} times</p></Card></div>
          <div style={{ width: 260 }}><Card soft title="Soft"><p className="body" style={{ margin: 0 }}>No outline, soft shadow.</p></Card></div>
          <div style={{ width: 260 }}><Card flat title="Flat"><p className="body" style={{ margin: 0 }}>Outline, no shadow.</p></Card></div>
          <div style={{ width: 260 }}><Card tone="maroon" title="Maroon"><p className="body" style={{ margin: 0 }}>For the big promise.</p></Card></div>
          <div style={{ width: 260 }}><Card tone="ink" title="Ink"><p className="body" style={{ margin: 0 }}>For the public record.</p></Card></div>
        </Section>

        <Section name="FolderCard" shows="tab · icon · tone">
          <FolderCard tab="01 Plan" icon="handshake" tone="paper" style={{ width: 320 }}>
            <p className="title-l" style={{ margin: 0 }}>Dig once</p>
            <p className="body" style={{ margin: 0 }}>Departments agree one trench for the month.</p>
          </FolderCard>
          <FolderCard tab="02 Adapt" icon="rain" tone="maroon" style={{ width: 320 }}>
            <p className="title-l" style={{ margin: 0 }}>Move with the weather</p>
            <p className="body" style={{ margin: 0 }}>Works leave the rain window before it opens.</p>
          </FolderCard>
          <FolderCard tab="03 Verify" icon="sealCheck" tone="ink" style={{ width: 320 }}>
            <p className="title-l" style={{ margin: 0 }}>Pay for real repairs</p>
            <p className="body" style={{ margin: 0 }}>Money is released only when the photos pass.</p>
          </FolderCard>
        </Section>

        <Section name="Banner" shows="tone · title · icon · action">
          <div style={{ width: 560 }}><Banner title="How a plan is made">Each department sends its works; the scheduler finds one plan.</Banner></div>
          <div style={{ width: 560 }}><Banner tone="warn" title="Simulated forecast">The rain in this demo is a practice forecast.</Banner></div>
          <div style={{ width: 560 }}><Banner tone="danger" title="In danger right now?">Call 112. This app is not for emergencies.</Banner></div>
          <div style={{ width: 560 }}><Banner tone="ok" title="Plan ready for your approval" action={<Button variant="ghost">Open</Button>}>It changes 7 works.</Banner></div>
          <div style={{ width: 560 }}><Banner tone="ink" title="Public record">Every decision is written here and never changed.</Banner></div>
        </Section>

        <Section name="Toast" shows="icon · actionLabel · onAction · fixed">
          <Toast icon="rain" actionLabel="View changes">Plan updated. 3 works moved out of the rain window.</Toast>
        </Section>

        <Section name="Tabs" shows="items · value · onChange · label">
          <Tabs
            label="Command centre panels"
            value={tab}
            onChange={setTab}
            items={[
              { id: 'negotiation', label: 'Negotiation', count: 6 },
              { id: 'works', label: 'Works', count: 16 },
              { id: 'risk', label: 'Risk', count: 2 },
              { id: 'approvals', label: 'Approvals', count: 1 },
            ]}
          />
        </Section>

        <Section name="Toggle" shows="checked · onChange · off · on · label">
          <Toggle checked={newWay} onChange={setNewWay} off="Old way" on="MargaMitra" label="Compare with the old way" />
        </Section>

        <Section name="TextField" shows="label · placeholder · hint · error · multiline">
          <div style={{ width: 360 }}><TextField label="Work" placeholder="W-104" /></div>
          <div style={{ width: 360 }}><TextField label="Road" placeholder="Munchur Road" hint="As written on the work board" /></div>
          <div style={{ width: 360 }}><TextField label="After photo" defaultValue="IMG_2041.jpg" error="This photo was taken 840 m from the work site. Take it again at the site." /></div>
          <div style={{ width: 360 }}><TextField label="Note for the inspector" placeholder="Anything the inspector should know" multiline /></div>
        </Section>

        <Section name="PhotoSlot" shows="label · hint · src · alt · meta · badge · onPick">
          <div style={{ width: 280 }}><PhotoSlot label="After photo" hint="Take it when the trench is closed and the road is patched." /></div>
          <div style={{ width: 280 }}>
            <PhotoSlot
              label="Before photo"
              src={photo}
              meta="13.0101 N, 74.7943 E · 10 Nov, 08:12"
              badge={<StatusBadge status="ok">Place: on site, 12 m</StatusBadge>}
            />
          </div>
        </Section>

        <Section name="MetricTile" shows="label · value · unit · compare · delta · better · countUp">
          <div key={countKey} style={ROW}>
            <div style={{ width: 220 }}><MetricTile label="Digs per road" value={1.6} unit="avg" compare="Old way 3.4" delta="−53%" /></div>
            <div style={{ width: 220 }}><MetricTile label="Trench hours saved" value={530} unit="h" /></div>
            <div style={{ width: 220 }}><MetricTile label="Days late" value={0.4} unit="days" compare="Old way 0" delta="+0.4" better={false} /></div>
            <div style={{ width: 220 }}><MetricTile label="Repeat repairs" value="—" /></div>
          </div>
          <Button variant="ghost" onClick={() => setCountKey((k) => k + 1)}>Count again</Button>
        </Section>

        <Section name="DataTable" shows="columns · rows · caption">
          <div style={{ width: '100%' }}><DataTable caption="Newest first" columns={RECORD_COLUMNS} rows={RECORD_ROWS} /></div>
        </Section>

        <Section name="NegotiationMessage" shows="sender · to · type · round · time · body · options · fresh">
          <div style={{ width: 520, display: 'flex', flexDirection: 'column', gap: 12 }}>
            <NegotiationMessage sender="coordinator" to="All departments" type="NOTICE" round={1} time="09:00" body="Planning 2–29 Nov. Send your works by 10:00." />
            <NegotiationMessage
              sender="water"
              to="Telecom"
              type="COUNTER"
              round={2}
              time="09:04"
              body="W-104 can share the trench with T-221 if it moves two days."
              options={[{ label: 'Share the trench, 12–15 Nov', cost: '−₹1,64,000' }, { label: 'Own dig, 10–13 Nov', cost: '₹0' }]}
            />
            <NegotiationMessage sender="telecom" to="Water" type="ACCEPT" round={2} time="09:06" body="Agreed: T-221 moves to 12–15 Nov." />
            <NegotiationMessage sender="gas" to="Coordinator" type="ESCALATE" round={3} time="09:10" body="G-310 cannot move: the safety inspection is booked." />
            <NegotiationMessage sender="solver" to="All departments" type="DECISION" round={4} time="09:12" body="Plan made: 16 works, 4 digs → 2 on Munchur Road." fresh />
          </div>
        </Section>

        <Section name="DiffRow" shows="dept · title · was · to · reason · cost · costDir">
          <ul style={{ width: 560, listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <DiffRow dept="power" title="P-140 cable repair" was="12–14 Nov" to="16–18 Nov" reason="Out of the rain window" cost="+₹38,000" costDir="up" />
            <DiffRow dept="water" title="W-104 water main" was="10–13 Nov" to="12–15 Nov" reason="Shares the trench with T-221" cost="−₹1,64,000" costDir="down" />
          </ul>
        </Section>

        <Section name="TimelineSlider" shows="days · value · onChange · valueLabel · tickLabel · range · risks · playing · onPlay">
          <div style={{ width: '100%', paddingTop: 32 }}>
            <TimelineSlider
              days={PLAN_DAYS}
              value={day}
              onChange={setDay}
              valueLabel={2 + day + ' Nov'}
              tickLabel={(t) => 2 + t + ' Nov'}
              range="2–29 Nov"
              risks={[
                { start: 12, end: 13, kind: 'rain', label: 'Heavy rain forecast' },
                // A one-day risk is drawn from start to end, so end is the next day.
                { start: 18, end: 19, kind: 'event', label: 'Event route' },
              ]}
              playing={playing}
              onPlay={() => setPlaying((p) => !p)}
            />
          </div>
        </Section>

        <Section name="MapLegend" shows="counts · title">
          <MapLegend title="On the map · 10 Nov" counts={{ water: 2, drainage: 2, gas: 1, power: 1, telecom: 1, roads: 1 }} />
        </Section>

        <Section name="StepList" shows="steps · status">
          <StepList
            steps={[
              { text: 'Rules check passed', detail: 'No protected road is dug', status: 'done' },
              { text: 'Checking place, time and photo reuse', status: 'running' },
              { text: 'Ward engineer: you', detail: 'Plans that change 5 or more works', status: 'needs' },
              { text: 'Department heads are told', detail: 'After you approve', status: 'waiting' },
            ]}
          />
        </Section>

        <Section name="CopilotBar" shows="value · onChange · onSubmit · placeholder · busy · fixed">
          <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>
            <CopilotBar value={command} onChange={setCommand} onSubmit={() => setCommand('')} />
            <CopilotBar value="plan next month and keep the procession route clear" busy />
          </div>
        </Section>

        <Section name="TopBar" shows="active · links · place · role · onRole · homeHref">
          <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>
            <TopBar active="command" homeHref="/" />
            <TopBar active="record" role="Visitor" homeHref="/" />
          </div>
        </Section>
      </main>
    </div>
  );
}
