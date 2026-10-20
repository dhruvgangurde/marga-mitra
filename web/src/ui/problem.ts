// Every send error on screen, in plain words. Server text is shown only when it is a short sentence for people.
import { ApiError } from '../api/client';

export interface Problem { title: string; text: string }

const NEVER_SHOW = /\b(api|llm|model|prompt|token|json|hash|ledger|exif|seed|cp-sat|langgraph|agentic)\b/i;

const NOT_SENT: Problem = { title: 'Could not send', text: 'Check your connection and try again.' };

const isSentence = (s: string) => s.endsWith('.') && s.length <= 120 && !NEVER_SHOW.test(s);

// A read that answers 404 is not there yet: show the empty state, not an error.
export const isMissing = (error: unknown): boolean => error instanceof ApiError && error.status === 404;

export function problemText(error: unknown): Problem {
  if (!(error instanceof ApiError)) return NOT_SENT;
  const { status, detail } = error;
  if (status === 409) return { title: 'Already decided', text: 'Someone decided this on another screen. This page now shows the latest.' };
  if (status === 404) return { title: 'Not found', text: 'This is no longer here. Go back and pick it again.' };
  if (status === 422 && typeof detail === 'string' && isSentence(detail)) return { title: 'Could not send', text: detail };
  if (status === 422) return { title: 'Could not send', text: 'Something in the form is not right. Check it and try again.' };
  if (status >= 500) return { title: 'Something went wrong', text: 'Try again in a moment.' };
  return NOT_SENT;
}

export const PROBLEM_CASES: Array<[name: string, error: unknown, expected: Problem]> = [
  ['never reached the server', new TypeError('Failed to fetch'), NOT_SENT],
  ['already decided', new ApiError(409, 'This approval is already decided'), {
    title: 'Already decided', text: 'Someone decided this on another screen. This page now shows the latest.',
  }],
  ['not found', new ApiError(404, 'Unknown work W-999'), { title: 'Not found', text: 'This is no longer here. Go back and pick it again.' }],
  ['sentence shown', new ApiError(422, 'The photo is larger than 8 MB.'), { title: 'Could not send', text: 'The photo is larger than 8 MB.' }],
  ['never-show word hidden', new ApiError(422, 'The LLM could not read the photo.'), {
    title: 'Could not send', text: 'Something in the form is not right. Check it and try again.',
  }],
  ['field list hidden', new ApiError(422, [{ loc: ['body', 'work_id'], msg: 'Field required', type: 'missing' }]), {
    title: 'Could not send', text: 'Something in the form is not right. Check it and try again.',
  }],
  ['server failed', new ApiError(500, 'Internal Server Error'), { title: 'Something went wrong', text: 'Try again in a moment.' }],
  ['anything else', new ApiError(0, 'network'), NOT_SENT],
];
