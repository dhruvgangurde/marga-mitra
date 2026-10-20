import { useEffect, useRef, useState } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { USE_MOCKS } from '../../api/client';
import { useConfirmRoad, useEvidence, useUploadEvidence, useWork, useWorks } from '../../api/hooks';
import { dayLabel } from '../../api/format';
import type { Evidence } from '../../api/types';
import { Banner, Button, Card, DeptChip, PhoneScreen, PhotoSlot, StatusBadge } from '../../ui';

type Stage = 'asking' | 'notyet' | 'sent-yes' | 'sent-notyet';
type Place = { lat: number; lon: number };

const PROBLEMS = ['Still dug up', 'Uneven patch', 'Water collects there', 'Debris left behind'];
const HINT = { margin: 0, color: 'var(--ink-3)' } as const;
const BOX = { width: 20, height: 20, margin: 0, accentColor: 'var(--ink)' } as const;
const photoDate = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', timeZone: 'Asia/Kolkata' });

// The phone's position if it comes within 3 s; the answer never waits longer.
function quickPosition(): Promise<Place | null> {
  const asked = new Promise<Place | null>((resolve) => {
    if (!navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ lat: p.coords.latitude, lon: p.coords.longitude }),
      () => resolve(null),
      { timeout: 3000 },
    );
  });
  return Promise.race([asked, new Promise<null>((resolve) => setTimeout(() => resolve(null), 3000))]);
}

function crewPhoto(label: string, alt: string, e: Evidence | undefined) {
  return e ? (
    <PhotoSlot label={label} src={e.file_url} alt={alt} meta={photoDate.format(new Date(e.taken_at ?? e.uploaded_at))} />
  ) : (
    <Card soft><p className="small" style={HINT}>No photo yet</p></Card>
  );
}

function startStage(answer: string | null): Stage {
  if (!USE_MOCKS) return 'asking';
  if (answer === 'yes') return 'sent-yes';
  if (answer === 'notyet') return 'notyet';
  return 'asking';
}

export default function ConfirmScreen() {
  const { workId = '' } = useParams();
  const [search] = useSearchParams();
  const view = useWork(workId).data;
  const works = useWorks().data ?? [];
  const evidence = useEvidence(workId).data ?? [];
  const confirm = useConfirmRoad();
  const upload = useUploadEvidence();

  const [stage, setStage] = useState<Stage>(() => startStage(search.get('answer')));
  const [problems, setProblems] = useState<string[]>([PROBLEMS[0]]);
  const [photo, setPhoto] = useState<{ file: File; url: string } | null>(null);
  const [failed, setFailed] = useState(false);
  const [sending, setSending] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const urls = useRef<string[]>([]);

  useEffect(() => () => urls.current.forEach((url) => URL.revokeObjectURL(url)), []);

  const answered = stage === 'sent-yes' || stage === 'sent-notyet';
  const badge = answered
    ? <StatusBadge status="ok">Answered</StatusBadge>
    : <StatusBadge status="pending">1 question</StatusBadge>;

  if (!view) return <PhoneScreen title="Your road" backTo="/" badge={badge} />;

  const { work, assignment } = view;
  const partners = assignment?.shared_group
    ? works.filter((v) => v.assignment?.shared_group === assignment.shared_group && v.work.work_id !== work.work_id)
    : [];
  const titles = [work.title, ...partners.map((p) => p.work.title.toLowerCase())].join(' and ');
  const finished = assignment ? dayLabel(assignment.end_day) : '';
  const lead = partners.length
    ? `${titles} in one trench. The crew says the work finished on ${finished}.`
    : `${work.title}. The crew says the work finished on ${finished}.`;
  const latest = (kind: Evidence['kind']) => evidence.filter((e) => e.kind === kind).at(-1);

  async function send(answer: 'yes' | 'notyet') {
    setFailed(false);
    setSending(true);
    try {
      const place = await quickPosition();
      if (answer === 'notyet' && photo) {
        await upload.mutateAsync({
          workId, kind: 'citizen', photo: photo.file, lat: place?.lat, lon: place?.lon,
          takenAt: new Date(photo.file.lastModified).toISOString(),
        });
      }
      await confirm.mutateAsync({
        work_id: workId, answer, problems: answer === 'notyet' ? PROBLEMS.filter((p) => problems.includes(p)) : [], lat: place?.lat, lon: place?.lon,
      });
      setStage(answer === 'yes' ? 'sent-yes' : 'sent-notyet');
    } catch {
      setFailed(true);
    } finally {
      setSending(false);
    }
  }

  function onFile(file: File | undefined) {
    if (!file) return;
    const url = URL.createObjectURL(file);
    urls.current.push(url);
    setPhoto({ file, url });
  }

  const toggle = (p: string) => setProblems((list) => (list.includes(p) ? list.filter((x) => x !== p) : [...list, p]));

  return (
    <PhoneScreen title="Your road" backTo="/" badge={badge}>
      <Card style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <DeptChip dept={work.dept} />
          {partners.map((p) => <DeptChip key={p.work.work_id} dept={p.work.dept} />)}
        </div>
        <h2 className="title-l" style={{ margin: 0 }}>{work.road_name}</h2>
        <p className="body-l" style={{ margin: 0, color: 'var(--ink-2)' }}>{lead}</p>
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {crewPhoto('Before', 'Crew photo before: open trench', latest('before'))}
        {crewPhoto('After', 'Crew photo after: road patched', latest('after'))}
      </div>

      <h2 className="display-3" style={{ margin: '8px 0 0', color: 'var(--maroon)' }}>Is the road outside your house restored?</h2>

      {failed ? <Banner tone="danger" title="Could not send">Check your connection and try again.</Banner> : null}

      {stage === 'asking' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <Button variant="primary" block arrow={false} disabled={sending} onClick={() => void send('yes')}>Yes</Button>
          <Button block disabled={sending} onClick={() => setStage('notyet')}>Not yet</Button>
        </div>
      ) : null}

      {stage === 'notyet' ? (
        <>
          <fieldset className="mm-card" style={{ margin: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <legend className="title" style={{ padding: '0 4px' }}>What is still wrong?</legend>
            {PROBLEMS.map((p) => (
              <label key={p} className="body-l" style={{ display: 'flex', gap: 10, alignItems: 'center', minHeight: 44 }}>
                <input type="checkbox" checked={problems.includes(p)} onChange={() => toggle(p)} style={BOX} />
                {p}
              </label>
            ))}
          </fieldset>
          {photo ? (
            <PhotoSlot src={photo.url} meta="Photo added" />
          ) : (
            <PhotoSlot label="Add a photo" hint="Optional. Take it from where you stand." onPick={() => fileInput.current?.click()} />
          )}
          <input
            ref={fileInput}
            type="file"
            accept="image/*"
            capture="environment"
            hidden
            onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ''; }}
          />
          {problems.length === 0 ? <p className="small" style={{ ...HINT, textAlign: 'center' }}>Tick what is still wrong.</p> : null}
          <Button variant="primary" block disabled={problems.length === 0 || sending} onClick={() => void send('notyet')}>Send</Button>
        </>
      ) : null}

      {stage === 'sent-yes' ? (
        <Banner tone="ok" title="Thank you">Your answer is in the public record. The contractor&apos;s deposit can now be released.</Banner>
      ) : null}
      {stage === 'sent-notyet' ? (
        <Banner tone="info" title="Thank you">The crew is asked to come back. The deposit stays held until the road is restored.</Banner>
      ) : null}

      <p className="small" style={HINT}>We do not ask for your name. Until a resident says yes, the contractor&apos;s deposit stays held.</p>
    </PhoneScreen>
  );
}
