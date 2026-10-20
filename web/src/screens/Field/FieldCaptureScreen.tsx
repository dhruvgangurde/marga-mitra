import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ApiError, USE_MOCKS } from '../../api/client';
import { useEvidence, useSegments, useUploadEvidence, useVerification, useVerifyWork, useWork, useWorks } from '../../api/hooks';
import { useLiveEvent } from '../../api/live';
import { dateTimeLabel, dayRange, deptName, START_DATE } from '../../api/format';
import type { Assignment, Evidence, LedgerEntry } from '../../api/types';
import {
  Banner, Button, Card, DeptChip, EmptyState, LoadError, metresToLine, PhoneScreen, photoProblem, PhotoSlot, preparePhoto, Skeleton,
  StatusBadge, StepList,
} from '../../ui';
import type { Problem } from '../../ui';

type Kind = 'before' | 'after';
type Line = [number, number][];
type Place = { lat: number; lon: number };

const COLUMN = { display: 'flex', flexDirection: 'column', gap: 8 } as const;
const DAY_MS = 86400000;

const takenAt = (e: Evidence) => e.taken_at ?? e.uploaded_at;
const round6 = (v: number) => Math.round(v * 1e6) / 1e6;
const HINT = { margin: 0, color: 'var(--ink-3)' } as const;

// Day number of a photo: its calendar date in India minus the first plan day.
function photoDay(iso: string): number {
  const ymd = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Kolkata' }).format(new Date(iso));
  return Math.round((Date.parse(ymd + 'T00:00:00Z') - Date.parse(START_DATE + 'T00:00:00Z')) / DAY_MS);
}

function photoMeta(e: Evidence): string {
  const when = dateTimeLabel(takenAt(e));
  return e.lat != null && e.lon != null ? `${e.lat.toFixed(4)} N, ${e.lon.toFixed(4)} E · ${when}` : when;
}

function PhotoBadges({ evidence, lines, assignment, sent }: { evidence: Evidence; lines: Line[]; assignment?: Assignment | null; sent?: Place }) {
  const { lat, lon } = evidence;
  let place: ReactNode = null;
  let note: string | null = null;
  if (lat == null || lon == null) {
    place = <StatusBadge status="warn">Place: no location</StatusBadge>;
    note = 'Turn on location for this site and take the photo again.';
  } else if (lines.length > 0) {
    const m = Math.round(Math.min(...lines.map((line) => metresToLine(lat, lon, line))));
    place = m <= 50
      ? <StatusBadge status="ok">{`Place: on site, ${m} m`}</StatusBadge>
      : <StatusBadge status="warn">{`Place: ${m} m from the site`}</StatusBadge>;
  }
  if (lat != null && lon != null && sent && round6(lat) === sent.lat && round6(lon) === sent.lon) {
    note = "No location in the photo, so the phone's location was used.";
  }
  let time: ReactNode = null;
  if (assignment) {
    const day = photoDay(takenAt(evidence));
    time = day >= assignment.start_day - 2 && day <= assignment.end_day + 2
      ? <StatusBadge status="ok">Time: within the work dates</StatusBadge>
      : <StatusBadge status="warn">Time: outside the work dates</StatusBadge>;
  }
  return (
    <>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>{place}{time}</div>
      {note ? <p className="small" style={HINT}>{note}</p> : null}
    </>
  );
}

// The phone's position, or null when it is refused, unknown or too slow.
function phonePosition(): Promise<Place | null> {
  return new Promise((resolve) => {
    if (!navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lon: p.coords.longitude }),
      () => resolve(null),
      { timeout: 8000, maximumAge: 60000 },
    );
  });
}

export default function FieldCaptureScreen() {
  const { workId = '' } = useParams();
  const navigate = useNavigate();
  const workQuery = useWork(workId);
  const worksQuery = useWorks();
  const evidenceQuery = useEvidence(workId);
  const verificationQuery = useVerification(workId);
  const segmentsQuery = useSegments();
  const queries = [workQuery, worksQuery, evidenceQuery, verificationQuery, segmentsQuery];
  const view = workQuery.data;
  const works = worksQuery.data ?? [];
  const evidence = evidenceQuery.data ?? [];
  const verification = verificationQuery.data;
  const features = segmentsQuery.data?.features ?? [];
  const upload = useUploadEvidence();
  const verify = useVerifyWork();

  // A picked photo shows at once from this local address while it is sending.
  const [sending, setSending] = useState<Partial<Record<Kind, string>>>({});
  const [problem, setProblem] = useState<Problem | null>(null);
  // What this phone sent with each photo, to tell when the server used it instead of the photo's own place.
  const [sentPlaces, setSentPlaces] = useState<Record<string, Place>>({});
  // The upload has no note field (contracts.Evidence); add one only if the team changes the contract.
  const inputs = useRef<Partial<Record<Kind, HTMLInputElement | null>>>({});
  const previews = useRef<string[]>([]);

  useEffect(() => () => previews.current.forEach((url) => URL.revokeObjectURL(url)), []);

  // A photo added on another device shows here too.
  const refetchEvidence = evidenceQuery.refetch;
  useLiveEvent('ledger.appended', (data) => {
    const entry = data as unknown as LedgerEntry;
    if (entry.action === 'evidence.added' && entry.entity === `work:${workId}`) void refetchEvidence();
  });

  const badge = <StatusBadge status="live">On site</StatusBadge>;
  // The photos and the result load before the page shows, so nothing jumps when they arrive.
  const loading = workQuery.isLoading || evidenceQuery.isLoading || verificationQuery.isLoading;
  if (!view || loading) {
    const unknown = workQuery.error instanceof ApiError && workQuery.error.status === 404;
    return (
      <PhoneScreen title="Site photos" backTo="/field" badge={badge} busy={loading}>
        {loading ? (
          <>
            <Skeleton height={96} />
            <Skeleton height={240} />
          </>
        ) : unknown ? (
          <EmptyState icon="hardhat" text={`We could not find work ${workId}.`} action={<Button as="a" href="/field">Back to my works</Button>} />
        ) : (
          <LoadError queries={queries} />
        )}
      </PhoneScreen>
    );
  }

  const { work, assignment } = view;
  const lines: Line[] = work.segment_ids.flatMap((id) => {
    const f = features.find((feature) => feature.properties.segment_id === id);
    return f ? [f.geometry.coordinates] : [];
  });
  const latest = (kind: Kind) => evidence.filter((e) => e.kind === kind).at(-1);
  const before = sending.before ? undefined : latest('before');
  const after = sending.after ? undefined : latest('after');
  const partner = assignment?.shared_group
    ? works.find((v) => v.assignment?.shared_group === assignment.shared_group && v.work.work_id !== work.work_id)
    : undefined;
  const dates = assignment ? dayRange(assignment.start_day, assignment.end_day) : '';
  const method = (assignment?.mode ?? work.modes[0].mode) === 'trenchless' ? 'Trenchless' : 'Open cut';
  const ready = Boolean(before && after);

  async function onFile(kind: Kind, file: File | undefined) {
    if (!file) return;
    const url = URL.createObjectURL(file);
    previews.current.push(url);
    setProblem(null);
    setSending((s) => ({ ...s, [kind]: url }));
    try {
      const [{ photo }, found] = await Promise.all([preparePhoto(file), phonePosition()]);
      let place = found;
      if (!place && USE_MOCKS && lines[0]?.[0]) {
        // shortcut: demo location in mock mode; the real app sends the phone's location
        place = { lat: lines[0][0][1], lon: lines[0][0][0] };
      }
      const sent = place ? { lat: round6(place.lat), lon: round6(place.lon) } : undefined;
      // The time comes from the original file: a re-encoded photo is dated now.
      const added = await upload.mutateAsync({
        workId, kind, photo, lat: sent?.lat, lon: sent?.lon, takenAt: new Date(file.lastModified).toISOString(),
      });
      if (sent) setSentPlaces((m) => ({ ...m, [added.evidence_id]: sent }));
    } catch (error) {
      setProblem(photoProblem(error));
    } finally {
      setSending((s) => ({ ...s, [kind]: undefined }));
    }
  }

  async function sendForChecking() {
    setProblem(null);
    try {
      await verify.mutateAsync(workId);
      navigate(`/field/${workId}/result`, { state: { sentAt: Date.now() } });
    } catch (error) {
      setProblem(photoProblem(error));
    }
  }

  function slot(kind: Kind, label: string, emptyHint: string, shown: Evidence | undefined) {
    const preview = sending[kind];
    return (
      <>
        {preview ? (
          <PhotoSlot label={label} src={preview} alt={`${label}: ${work.title}, ${work.road_name}`} meta="Sending…" />
        ) : shown ? (
          <>
            <PhotoSlot label={label} src={shown.file_url} alt={`${label}: ${work.title}, ${work.road_name}`} meta={photoMeta(shown)} />
            <PhotoBadges evidence={shown} lines={lines} assignment={assignment} sent={sentPlaces[shown.evidence_id]} />
          </>
        ) : (
          <PhotoSlot label={label} hint={emptyHint} onPick={() => inputs.current[kind]?.click()} />
        )}
        <input
          ref={(el) => { inputs.current[kind] = el; }}
          type="file"
          accept="image/*"
          capture="environment"
          aria-label={kind === 'before' ? 'Take the before photo' : 'Take the after photo'}
          hidden
          onChange={(e) => { void onFile(kind, e.target.files?.[0]); e.target.value = ''; }}
        />
      </>
    );
  }

  const footer = (
    <>
      {ready ? null : (
        <p className="small" style={{ ...HINT, textAlign: 'center' }}>
          {before ? 'Add the after photo to send.' : 'Take the before photo first.'}
        </p>
      )}
      <Button variant="primary" block disabled={!ready || verify.isPending} onClick={() => void sendForChecking()}>
        {verify.isPending ? 'Checking the photos…' : 'Send for checking'}
      </Button>
    </>
  );

  return (
    <PhoneScreen title="Site photos" backTo="/field" badge={badge} footer={footer}>
      <LoadError queries={queries} />
      {problem ? <Banner tone="danger" title={problem.title}>{problem.text}</Banner> : null}
      {verification ? (
        <Banner
          tone="info"
          title="Already checked"
          action={<Button variant="ghost" as="a" href={`/field/${work.work_id}/result`}>See the result</Button>}
        >
          This work has a result.
        </Banner>
      ) : null}

      <Card style={COLUMN}>
        <div style={{ display: 'flex', gap: 8 }}>
          <DeptChip dept={work.dept} />
          <span className="mono" style={{ color: 'var(--ink-3)' }}>{work.work_id}</span>
        </div>
        <h2 className="title-l" style={{ margin: 0 }}>{`${work.title}, ${work.road_name}`}</h2>
        <p className="body-l" style={{ margin: 0, color: 'var(--ink-2)' }}>
          {partner ? `Shared trench with ${deptName(partner.work.dept)} ${partner.work.work_id} · ${dates}` : `${method} · ${dates}`}
        </p>
        <p className="small" style={{ margin: 0, color: 'var(--ink-3)' }}>
          Take both photos within 50 m of the site. The place and time are added to each photo for you.
        </p>
      </Card>

      <StepList
        steps={[
          before
            ? { text: 'Before photo', detail: `Taken ${dateTimeLabel(takenAt(before))}`, status: 'done' }
            : { text: 'Before photo', detail: 'At the site, before you dig', status: 'needs' },
          after
            ? { text: 'After photo', detail: `Taken ${dateTimeLabel(takenAt(after))}`, status: 'done' }
            : { text: 'After photo', detail: 'When the road is patched', status: before ? 'needs' : 'waiting' },
          { text: 'Checking and payment', detail: 'Place, time, photo reuse, repair, resident', status: 'waiting' },
        ]}
      />

      <section style={COLUMN}>
        <h2 className="title" style={{ margin: 0 }}>1 · Before the dig</h2>
        {slot('before', 'Before photo', 'Take it before the road is cut.', before)}
      </section>

      <section style={COLUMN}>
        <h2 className="title" style={{ margin: 0 }}>2 · After the repair</h2>
        {slot('after', 'After photo', 'Take it when the trench is closed and the road is patched.', after)}
      </section>
    </PhoneScreen>
  );
}
