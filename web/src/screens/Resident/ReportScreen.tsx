import { useEffect, useRef, useState } from 'react';
import { ApiError, USE_MOCKS } from '../../api/client';
import { useReportEmergency, useSegments, useWork } from '../../api/hooks';
import type { CitizenReport, EmergencyInput } from '../../api/types';
import {
  Banner, Button, Card, FocusTarget, Icon, LoadError, metresBetween, metresToLine, PhoneScreen, photoProblem, PhotoSlot, preparePhoto,
  StatusBadge, TextField,
} from '../../ui';
import type { IconName, Problem } from '../../ui';

type Kind = EmergencyInput['category'];
type Place = { lat: number; lon: number };

const KINDS: { id: Kind; icon: IconName; label: string }[] = [
  { id: 'water', icon: 'drop', label: 'Burst water pipe' },
  { id: 'gas', icon: 'flame', label: 'Gas smell' },
  { id: 'power', icon: 'lightning', label: 'Cable cut or sparking' },
  { id: 'cavein', icon: 'road', label: 'Road has caved in' },
  { id: 'trench', icon: 'shovel', label: 'Open trench left unsafe' },
];

const SURATHKAL: Place = { lat: 13.01, lon: 74.794 };
const DEMO_SPOT: Place = { lat: 13.0089, lon: 74.7988 };
const HINT = { margin: 0, color: 'var(--ink-3)' } as const;

// A 404 here means the server has no reporting yet; anything else reads as any other send error.
function reportProblem(error: unknown): Problem {
  if (error instanceof ApiError && error.status === 404) {
    return { title: 'Could not send', text: 'Reporting is not switched on yet. Call 112 if anyone is in danger.' };
  }
  return photoProblem(error);
}

export default function ReportScreen() {
  const segments = useSegments();
  const features = segments.data?.features ?? [];
  const demoWork = useWork(USE_MOCKS ? 'W-118' : undefined);
  const report = useReportEmergency();
  const [kind, setKind] = useState<Kind | null>(null);
  const [reading, setReading] = useState<Place | null>(null);
  const [locating, setLocating] = useState(true);
  const [locFailed, setLocFailed] = useState(false);
  const [photo, setPhoto] = useState<{ file: File; url: string } | null>(null);
  const [note, setNote] = useState('');
  const [sent, setSent] = useState<CitizenReport | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [preparing, setPreparing] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const urls = useRef<string[]>([]);

  // shortcut: demo location in mock mode; the real app needs the phone's location
  const start = features.find((f) => f.properties.segment_id === demoWork.data?.work.segment_ids[0])?.geometry.coordinates[0];
  const demoSpot: Place = start ? { lat: start[1] + 5 / 111320, lon: start[0] } : DEMO_SPOT;
  const place = USE_MOCKS && (!reading || metresBetween(reading.lat, reading.lon, SURATHKAL.lat, SURATHKAL.lon) > 20000)
    ? demoSpot
    : reading;

  function locate() {
    setLocating(true);
    setLocFailed(false);
    const done = (p: Place | null) => {
      if (p) setReading(p);
      setLocFailed(!p && !USE_MOCKS);
      setLocating(false);
    };
    if (!navigator.geolocation) return done(null);
    navigator.geolocation.getCurrentPosition(
      (p) => done({ lat: p.coords.latitude, lon: p.coords.longitude }),
      () => done(null),
      { timeout: 8000 },
    );
  }

  useEffect(locate, []);
  useEffect(() => () => urls.current.forEach((url) => URL.revokeObjectURL(url)), []);

  function onFile(file: File | undefined) {
    if (!file) return;
    const url = URL.createObjectURL(file);
    urls.current.push(url);
    setPhoto({ file, url });
  }

  async function send() {
    if (!kind || !place) return;
    setProblem(null);
    setPreparing(true);
    try {
      const written = note.trim();
      const prepared = photo ? (await preparePhoto(photo.file)).photo : undefined;
      setSent(await report.mutateAsync({
        category: kind, lat: place.lat, lon: place.lon, note: written || undefined, photo: prepared,
      }));
    } catch (error) {
      // The danger banner shows the failure; every field keeps what the person entered.
      setProblem(reportProblem(error));
    } finally {
      setPreparing(false);
    }
  }

  const badge = <StatusBadge status="emergency">Emergency</StatusBadge>;

  if (sent) {
    return (
      <PhoneScreen title="Report" backTo="/" badge={badge} footer={<Button as="a" href="/" block>Back to the start</Button>}>
        <FocusTarget>
          <Banner tone="ok" title="Report sent">
            {sent.work_id ? `A crew is on the way. Emergency work ${sent.work_id} is open.` : 'A crew is on the way.'}
          </Banner>
        </FocusTarget>
        <p className="small" style={HINT}>{`Report ${sent.report_id} is in the public record without your name.`}</p>
      </PhoneScreen>
    );
  }

  const named = place
    ? features
      .filter((f) => f.properties.name)
      .map((f) => ({ name: f.properties.name, m: metresToLine(place.lat, place.lon, f.geometry.coordinates) }))
      .filter((r) => r.m <= 300)
      .sort((a, b) => a.m - b.m)[0]?.name
    : null;
  const why = !kind ? 'Pick what is happening first.' : !place ? 'We need your location to send a crew.' : null;

  const footer = (
    <>
      {why ? <p className="small" style={{ ...HINT, textAlign: 'center' }}>{why}</p> : null}
      <Button variant="primary" block disabled={Boolean(why) || preparing} onClick={() => void send()}>Send report</Button>
    </>
  );

  return (
    <PhoneScreen title="Report" backTo="/" badge={badge} footer={footer}>
      <LoadError queries={[segments]} />
      {problem ? <Banner tone="danger" title={problem.title}>{`${problem.text} Your report is still here.`}</Banner> : null}
      <Banner tone="danger" title="In danger right now?">Move away and call 112 first.</Banner>

      <fieldset style={{ margin: 0, padding: 0, border: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <legend className="title" style={{ padding: 0, margin: '0 0 8px' }}>What is happening?</legend>
        {KINDS.map((k) => {
          const picked = kind === k.id;
          return (
            <label
              key={k.id}
              className="mm-card"
              style={{
                display: 'flex', alignItems: 'center', gap: 12, padding: 12, cursor: 'pointer',
                ...(picked ? { background: 'var(--lime-soft)', borderWidth: 2 } : null),
              }}
            >
              <input
                type="radio"
                name="kind"
                value={k.id}
                checked={picked}
                onChange={() => setKind(k.id)}
                style={{ width: 20, height: 20, margin: 0, accentColor: 'var(--ink)' }}
              />
              <span
                style={{
                  width: 36, height: 36, flex: 'none', boxSizing: 'border-box', borderRadius: 'var(--radius-pill)',
                  border: 'var(--stroke-ui) solid var(--ink)', background: 'var(--paper)', display: 'grid', placeItems: 'center',
                }}
              >
                <Icon name={k.icon} />
              </span>
              <span className="body-l" style={{ fontWeight: 600 }}>{k.label}</span>
            </label>
          );
        })}
      </fieldset>

      <section>
        <Card style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <h2 className="title" style={{ margin: 0 }}>Where?</h2>
          {place ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Icon name="pin" />
                <span className="body-l">{named ? `Near ${named}, Surathkal` : 'Surathkal'}</span>
              </div>
              <span className="mono" style={{ color: 'var(--ink-3)' }}>
                {`${place.lat.toFixed(4)} N, ${place.lon.toFixed(4)} E · from your phone`}
              </span>
            </>
          ) : null}
          {locating && !place ? <span className="small" style={{ color: 'var(--ink-3)' }}>Finding where you are…</span> : null}
          {locFailed ? (
            <p className="small" style={{ margin: 0, color: 'var(--signal-2)' }}>
              We could not get your location. Turn on location for this site, then tap Use my location again.
            </p>
          ) : null}
          <div><Button icon="pin" onClick={locate}>Use my location again</Button></div>
        </Card>
      </section>

      {photo ? (
        <>
          <PhotoSlot src={photo.url} meta="Photo added" />
          <div><Button variant="ghost" onClick={() => fileInput.current?.click()}>Take it again</Button></div>
        </>
      ) : (
        <PhotoSlot label="Add a photo" hint="Optional. It helps the crew find the place." onPick={() => fileInput.current?.click()} />
      )}
      <input
        ref={fileInput}
        type="file"
        accept="image/*"
        capture="environment"
        aria-label="Add a photo"
        hidden
        onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ''; }}
      />

      <TextField
        label="Anything else the crew should know?"
        hint="Optional"
        multiline
        placeholder="Water is flowing onto the road near the bus stop"
        maxLength={280}
        value={note}
        onChange={(e) => setNote(e.target.value)}
      />
      <p className="small" style={HINT}>Your report goes into the public record without your name or phone number.</p>
    </PhoneScreen>
  );
}
