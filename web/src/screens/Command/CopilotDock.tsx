import { useEffect, useRef, useState } from 'react';
import { errorText } from '../../api/format';
import { useCopilot } from '../../api/hooks';
import { useLiveEvent } from '../../api/live';
import type { CopilotStep, UiAction } from '../../api/types';
import { Card, CopilotBar, IconButton, StepList } from '../../ui';

export interface CopilotContext {
  day: number;
  tab: string;
  selected_work: string | null;
  plan_id?: string;
}

const CLOSE_AFTER_MS = 8000;
const STILL_WORKING_MS = 90000;

export function CopilotDock({ context, onAction }: { context: CopilotContext; onAction: (action: string, args: Record<string, unknown>) => void }) {
  const [value, setValue] = useState('');
  const [steps, setSteps] = useState<CopilotStep[]>([]);
  const [text, setText] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [still, setStill] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const slow = useRef<ReturnType<typeof setTimeout>>();
  const copilot = useCopilot();
  // One turn at a time: the reply id of the turn being waited for, and how many of its actions already ran.
  const busy = useRef(false);
  const replyId = useRef<string | null>(null);
  const applied = useRef(0);
  const act = useRef(onAction);
  act.current = onAction;

  const close = () => {
    clearTimeout(timer.current);
    setOpen(false);
  };

  useEffect(() => () => {
    clearTimeout(timer.current);
    clearTimeout(slow.current);
  }, []);
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e: KeyboardEvent) => {
      // The drawer closes first.
      if (e.key === 'Escape' && !document.querySelector('.mm-app-drawer')) close();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  // shortcut: one copilot turn at a time on this screen; another viewer's turn at the same moment could be taken for ours
  const ours = (data: Record<string, unknown>): boolean => {
    if (!busy.current) return false;
    const id = typeof data.reply_id === 'string' ? data.reply_id : null;
    if (!id) return false;
    if (replyId.current === null) replyId.current = id;
    return replyId.current === id;
  };

  useLiveEvent('ui.action', (data) => {
    if (!ours(data)) return;
    applied.current += 1;
    act.current(String(data.action ?? ''), (data.args ?? {}) as Record<string, unknown>);
  });

  useLiveEvent('copilot.step', (data) => {
    if (!ours(data)) return;
    const step = data as unknown as CopilotStep;
    setSteps((prev) => {
      const at = prev.findIndex((s) => s.step_id === step.step_id);
      if (at < 0) return [...prev, step];
      const next = [...prev];
      next[at] = step;
      return next;
    });
  });

  const submit = (message: string) => {
    const asked = message.trim();
    if (!asked || copilot.isPending) return;
    clearTimeout(timer.current);
    clearTimeout(slow.current);
    busy.current = true;
    replyId.current = null;
    applied.current = 0;
    setSteps([]);
    setText(null);
    setStill(false);
    setOpen(true);
    slow.current = setTimeout(() => setStill(true), STILL_WORKING_MS);
    copilot.mutate({ message: asked, context: { ...context } }, {
      onSuccess: (reply) => {
        busy.current = false;
        clearTimeout(slow.current);
        setStill(false);
        setSteps(reply.steps);
        setText(reply.text);
        setValue('');
        // The live stream may have been down; then the reply carries the actions.
        if (applied.current === 0) reply.actions.forEach((a: UiAction) => act.current(a.action, a.args));
        timer.current = setTimeout(() => setOpen(false), CLOSE_AFTER_MS);
      },
      onError: (e) => {
        busy.current = false;
        clearTimeout(slow.current);
        setStill(false);
        setText(errorText(e));
        timer.current = setTimeout(() => setOpen(false), CLOSE_AFTER_MS);
      },
    });
  };

  return (
    <>
      {open && (steps.length > 0 || text || still) ? (
        <div className="mm-app-copilot__steps" aria-live="polite">
          <Card soft style={{ border: 'var(--stroke-ui) solid var(--ink)' }}>
            <div className="mm-app-copilot__head">
              <span className="mono-label" style={{ color: 'var(--ink-3)' }}>Copilot</span>
              <IconButton icon="x" label="Close" size="sm" onClick={close} />
            </div>
            {steps.length > 0 ? (
              <StepList steps={steps.map((s) => ({ text: s.text, detail: s.detail ?? undefined, status: s.status }))} />
            ) : null}
            {text ? <p className="body" style={{ margin: steps.length ? '12px 0 0' : 0 }}>{text}</p> : null}
            {still ? (
              <p className="small" style={{ margin: '8px 0 0', color: 'var(--ink-3)' }}>
                Still working. The scheduler may be re-planning.
              </p>
            ) : null}
          </Card>
        </div>
      ) : null}
      <CopilotBar
        value={value}
        onChange={setValue}
        onSubmit={submit}
        busy={copilot.isPending}
        placeholder="Ask the copilot: show every dig on Munchur Road next week"
      />
    </>
  );
}
