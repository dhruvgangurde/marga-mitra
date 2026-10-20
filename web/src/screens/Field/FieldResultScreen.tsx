import { useEffect } from 'react';
import type { ReactNode } from 'react';
import { useParams, useSearchParams } from 'react-router-dom';
import { ApiError, USE_MOCKS } from '../../api/client';
import { useEvidence, useVerification, useWork } from '../../api/hooks';
import { dateTimeLabel, inr } from '../../api/format';
import type { CheckName, CheckStatus, Evidence, VerificationCheck } from '../../api/types';
import {
  Button, Card, EmptyState, LoadError, PhoneScreen, PhotoSlot, Seal, Skeleton, StatusBadge, StepList,
} from '../../ui';
import { isStateName, RESULT_STATES } from './resultStates';
import type { ResultState } from './resultStates';

const NAMES: Record<CheckName, string> = {
  place: 'Place', time: 'Time', reuse: 'Photo reuse', repair: 'Repair check', resident: 'Resident', inspection: 'Random inspection',
};

const WORDS: Record<CheckName, Partial<Record<CheckStatus, string>>> = {
  place: { ok: 'Passed', fail: 'Wrong place', warn: 'Not sure' },
  time: { ok: 'Passed', fail: 'Wrong time', warn: 'Not sure' },
  reuse: { ok: 'New photo', fail: 'Photo reused' },
  repair: { ok: 'Passed', warn: 'Not sure', fail: 'Failed' },
  resident: { ok: 'Confirmed', pending: 'Waiting', fail: 'Not restored' },
  inspection: { pending: 'Not picked', ok: 'Passed', warn: 'Visit due' },
};

// A status without its own word shows as waiting.
function badgeFor(c: VerificationCheck): { status: CheckStatus; word: string } {
  const word = WORDS[c.name][c.status];
  return word ? { status: c.status, word } : { status: 'pending', word: 'Waiting' };
}

function reusedFrom(checks: VerificationCheck[]): string {
  const detail = checks.find((c) => c.name === 'reuse')?.detail ?? '';
  return detail.match(/\b[A-Z]-\d+\b/)?.[0] ?? 'another work';
}

function Outcome({ shown }: { shown: ResultState | null }) {
  switch (shown?.result) {
    case 'verified':
      return (
        <>
          <Seal kind="verified" size={112} stamp>Repair verified</Seal>
          <p className="title-l" style={{ margin: 0 }}>{`Repair verified. ${inr(shown.deposit_inr)} released to the contractor.`}</p>
        </>
      );
    case 'held':
      return (
        <>
          <Seal kind="held" size={112} stamp>Money held</Seal>
          <p className="title-l" style={{ margin: 0 }}>{`Photo reused from work ${reusedFrom(shown.checks)}. Money held. Inspector called.`}</p>
        </>
      );
    case 'inspect':
      return (
        <>
          <Seal kind="inspect" size={112} stamp>Needs inspector</Seal>
          <p className="title-l" style={{ margin: 0 }}>The repair check is not sure. An inspector visits within 2 days.</p>
        </>
      );
    default:
      return <StepList steps={[{ text: 'Checking place, time and photo reuse', status: 'running' }]} />;
  }
}

function photo(label: string, alt: string, e: Evidence | undefined) {
  return e
    ? <PhotoSlot label={label} src={e.file_url} alt={alt} meta={dateTimeLabel(e.taken_at ?? e.uploaded_at)} />
    : <Card soft><p className="small" style={{ margin: 0, color: 'var(--ink-3)' }}>No photo yet</p></Card>;
}

export default function FieldResultScreen() {
  const { workId = '' } = useParams();
  const [search] = useSearchParams();
  const work = useWork(workId);
  const verification = useVerification(workId);
  const evidenceQuery = useEvidence(workId);
  const queries = [work, verification, evidenceQuery];
  const evidence = evidenceQuery.data ?? [];

  const asked = search.get('result');
  const shown: ResultState | null = USE_MOCKS && isStateName(asked) ? RESULT_STATES[asked] : verification.data ?? null;
  const result = shown?.result ?? 'pending';
  const { refetch } = verification;

  useEffect(() => {
    if (!shown || result !== 'pending') return;
    const id = setInterval(() => void refetch(), 2000);
    return () => clearInterval(id);
  }, [shown, result, refetch]);

  const latest = (kind: Evidence['kind']) => evidence.filter((e) => e.kind === kind).at(-1);
  const badge = <span className="mono" style={{ color: 'var(--ink-3)' }}>{workId}</span>;
  const loading = work.isLoading || verification.isLoading;

  if (loading || !shown) {
    const unknown = work.error instanceof ApiError && work.error.status === 404;
    let body: ReactNode;
    if (loading) {
      body = (
        <>
          <Skeleton height={96} />
          <Skeleton height={240} />
        </>
      );
    } else if (unknown) {
      body = <EmptyState icon="hardhat" text={`We could not find work ${workId}.`} action={<Button as="a" href="/field">Back to my works</Button>} />;
    } else if (queries.some((q) => q.isError)) {
      body = <LoadError queries={queries} />;
    } else {
      body = <EmptyState icon="camera" text="No result yet. Send the photos first." action={<Button as="a" href={`/field/${workId}`}>Take the photos</Button>} />;
    }
    return <PhoneScreen title="Result" backTo="/field" badge={badge} busy={loading}>{body}</PhoneScreen>;
  }

  return (
    <PhoneScreen title="Result" backTo="/field" badge={badge} footer={<Button as="a" href="/field" block>Back to my works</Button>}>
      <LoadError queries={queries} />
      <div
        className="mm-dotgrid"
        aria-live="polite"
        style={{
          borderRadius: 'var(--radius-xl)', border: 'var(--stroke-ui) solid var(--ink)', padding: '20px 16px',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, textAlign: 'center',
        }}
      >
        {/* Keyed by the result so the seal stamps once, and again only when the result changes. */}
        <Outcome key={result} shown={shown} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {photo('Before', 'Before photo: open trench', latest('before'))}
        {photo('After', 'After photo: trench closed and patched', latest('after'))}
      </div>

      <section>
        <Card style={{ display: 'flex', flexDirection: 'column', gap: 0, padding: '4px 16px' }}>
          <h2 className="mono-label" style={{ margin: '12px 0 4px', color: 'var(--ink-3)' }}>Checks</h2>
          {shown.checks.map((c) => {
            const check = badgeFor(c);
            return (
              <div
                key={c.name}
                style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, padding: '10px 0', borderTop: '1px solid var(--line)' }}
              >
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <span className="body-strong">{NAMES[c.name]}</span>
                  <span className="small" style={{ color: 'var(--ink-3)' }}>{c.detail}</span>
                </div>
                <StatusBadge status={check.status}>{check.word}</StatusBadge>
              </div>
            );
          })}
        </Card>
      </section>
    </PhoneScreen>
  );
}
