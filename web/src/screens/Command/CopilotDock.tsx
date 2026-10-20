import { useEffect, useRef, useState } from 'react';
import { useCopilot } from '../../api/hooks';
import { useLiveEvent } from '../../api/live';
import type { CopilotStep } from '../../api/types';
import { Card, CopilotBar, IconButton, StepList } from '../../ui';

export interface CopilotContext {
  day: number;
  tab: string;
  selected_work: string | null;
  plan_id?: string;
}

const CLOSE_AFTER_MS = 8000;

export function CopilotDock({ context }: { context: CopilotContext }) {
  const [value, setValue] = useState('');
  const [steps, setSteps] = useState<CopilotStep[]>([]);
  const [text, setText] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout>>();
  const copilot = useCopilot();

  const close = () => {
    clearTimeout(timer.current);
    setOpen(false);
  };

  useEffect(() => () => clearTimeout(timer.current), []);
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  useLiveEvent('copilot.step', (data) => {
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
    setSteps([]);
    setText(null);
    setOpen(true);
    copilot.mutate({ message: asked, context: { ...context } }, {
      onSuccess: (reply) => {
        setSteps(reply.steps);
        setText(reply.text);
        setValue('');
        timer.current = setTimeout(() => setOpen(false), CLOSE_AFTER_MS);
      },
      onError: () => {
        setText('I could not do that. Try again.');
        timer.current = setTimeout(() => setOpen(false), CLOSE_AFTER_MS);
      },
    });
  };

  return (
    <>
      {open && (steps.length > 0 || text) ? (
        <div className="mm-app-copilot__steps">
          <Card soft style={{ border: 'var(--stroke-ui) solid var(--ink)' }}>
            <div className="mm-app-copilot__head">
              <span className="mono-label" style={{ color: 'var(--ink-3)' }}>Copilot</span>
              <IconButton icon="x" label="Close" size="sm" onClick={close} />
            </div>
            {steps.length > 0 ? (
              <StepList steps={steps.map((s) => ({ text: s.text, detail: s.detail ?? undefined, status: s.status }))} />
            ) : null}
            {text ? <p className="body" style={{ margin: steps.length ? '12px 0 0' : 0 }}>{text}</p> : null}
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