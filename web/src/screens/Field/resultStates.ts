// shortcut: screenshot states for the proposal, mock mode only; remove when the team takes no more mock screenshots
import type { CheckName, CheckStatus, Verification, VerificationCheck } from '../../api/types';

export type ResultState = Pick<Verification, 'result' | 'checks' | 'deposit_inr'>;
export type StateName = 'verified' | 'held' | 'inspect';

const check = (name: CheckName, status: CheckStatus, detail: string): VerificationCheck => ({ name, status, detail });

const VERIFIED: VerificationCheck[] = [
  check('place', 'ok', 'Both photos within 12 m of the site'),
  check('time', 'ok', 'Taken between 10 and 15 Nov'),
  check('reuse', 'ok', 'Not seen in any other work'),
  check('repair', 'ok', 'Trench closed, surface patched, no debris'),
  check('resident', 'ok', 'Confirmed the road is restored, 16 Nov'),
  check('inspection', 'pending', '1 in 10 works is visited'),
];

const changed = (...changes: VerificationCheck[]): VerificationCheck[] =>
  VERIFIED.map((c) => changes.find((x) => x.name === c.name) ?? c);

export const RESULT_STATES: Record<StateName, ResultState> = {
  verified: { result: 'verified', checks: VERIFIED, deposit_inr: 240000 },
  held: {
    result: 'held',
    checks: changed(check('reuse', 'fail', 'Same as the before photo of T-221 (96% alike)'), check('resident', 'pending', 'Asked on 15 Nov')),
    deposit_inr: 240000,
  },
  inspect: {
    result: 'inspect',
    checks: changed(check('repair', 'warn', 'The after photo is too dark to judge'), check('resident', 'pending', 'Asked on 15 Nov')),
    deposit_inr: 240000,
  },
};

export const isStateName = (s: string | null): s is StateName => s === 'verified' || s === 'held' || s === 'inspect';
