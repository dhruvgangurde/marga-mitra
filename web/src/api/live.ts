// Live events: a WebSocket in real mode, the mock bus in mock mode. Unknown event types are ignored.
import {
  createContext, createElement, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode,
} from 'react';
import { useQueryClient, type QueryClient } from '@tanstack/react-query';
import { mockBus } from '../mocks/bus';
import { USE_MOCKS, WS_URL } from './client';
import { invalidate, keys } from './hooks';
import type { EventType, NegotiationMessage, WsEvent } from './types';

type Handler = (data: Record<string, unknown>, event: WsEvent) => void;

interface LiveValue {
  subscribe: (type: EventType, handler: Handler) => () => void;
  fresh: ReadonlySet<string>;
}

const KNOWN: ReadonlySet<string> = new Set<EventType>([
  'negotiation.message', 'plan.updated', 'risk.windows_changed', 'approval.requested', 'approval.decided',
  'verification.result', 'ledger.appended', 'copilot.step', 'ui.action', 'auditor.flag',
]);

const FRESH_MS = 1200;
const RETRY_MS = [1000, 2000, 5000];
const NO_IDS: ReadonlySet<string> = new Set();

const LiveContext = createContext<LiveValue | null>(null);

function appendMessage(qc: QueryClient, message: NegotiationMessage): void {
  const add = (old: NegotiationMessage[] | undefined): NegotiationMessage[] | undefined => {
    if (!old) return old;
    if (old.some((m) => m.msg_id === message.msg_id)) return old;
    // A list left over from an earlier run is replaced by the new run's first message.
    if (old.length > 0 && old[0].run_id !== message.run_id) return [message];
    return [...old, message];
  };
  qc.setQueryData<NegotiationMessage[] | undefined>(keys.negotiation(message.run_id), add);
  qc.setQueryData<NegotiationMessage[] | undefined>(keys.negotiation(), add);
}

function applyEvent(qc: QueryClient, event: WsEvent, markFresh: (id: string) => void): void {
  switch (event.type) {
    case 'negotiation.message': {
      const message = event.data as unknown as NegotiationMessage;
      appendMessage(qc, message);
      markFresh(message.msg_id);
      break;
    }
    case 'plan.updated':
      void invalidate(qc, 'works', 'plans', 'metrics', 'approvals');
      break;
    case 'risk.windows_changed':
      void invalidate(qc, 'risk');
      break;
    case 'approval.requested':
    case 'approval.decided':
      void invalidate(qc, 'approvals', 'plans');
      break;
    case 'verification.result':
      void invalidate(qc, 'verification', 'works');
      break;
    case 'ledger.appended':
      void invalidate(qc, 'ledger');
      break;
    case 'auditor.flag':
      void invalidate(qc, 'flags');
      break;
    default:
      // copilot.step and ui.action go only to the screens that subscribed.
      break;
  }
}

// Reconnects after 1 s, 2 s and 5 s, then every 5 s.
function connect(onEvent: (event: WsEvent) => void): () => void {
  let socket: WebSocket | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let attempt = 0;
  let closed = false;

  const open = (): void => {
    socket = new WebSocket(WS_URL);
    socket.onopen = () => {
      attempt = 0;
    };
    socket.onmessage = (message) => {
      try {
        onEvent(JSON.parse(String(message.data)) as WsEvent);
      } catch {
        // A frame that is not JSON is not ours; skip it.
      }
    };
    socket.onclose = () => {
      if (closed) return;
      const delay = RETRY_MS[Math.min(attempt, RETRY_MS.length - 1)];
      attempt += 1;
      timer = setTimeout(open, delay);
    };
  };

  open();
  return () => {
    closed = true;
    clearTimeout(timer);
    socket?.close();
  };
}

export function LiveEventsProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const handlers = useRef(new Map<EventType, Set<Handler>>());
  const timers = useRef(new Set<ReturnType<typeof setTimeout>>());
  const [fresh, setFresh] = useState<ReadonlySet<string>>(NO_IDS);

  const subscribe = useCallback((type: EventType, handler: Handler) => {
    const set = handlers.current.get(type) ?? new Set<Handler>();
    set.add(handler);
    handlers.current.set(type, set);
    return () => {
      set.delete(handler);
    };
  }, []);

  const markFresh = useCallback((id: string) => {
    setFresh((prev) => new Set(prev).add(id));
    const timer = setTimeout(() => {
      timers.current.delete(timer);
      setFresh((prev) => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }, FRESH_MS);
    timers.current.add(timer);
  }, []);

  useEffect(() => {
    const onEvent = (event: WsEvent): void => {
      if (!KNOWN.has(event.type)) return;
      applyEvent(qc, event, markFresh);
      handlers.current.get(event.type)?.forEach((handler) => handler(event.data, event));
    };
    const stop = USE_MOCKS ? mockBus.on(onEvent) : connect(onEvent);
    const pending = timers.current;
    return () => {
      stop();
      pending.forEach((t) => clearTimeout(t));
      pending.clear();
    };
  }, [qc, markFresh]);

  const value = useMemo<LiveValue>(() => ({ subscribe, fresh }), [subscribe, fresh]);
  return createElement(LiveContext.Provider, { value }, children);
}

export function useLiveEvent(type: EventType, handler: Handler): void {
  const live = useContext(LiveContext);
  const latest = useRef(handler);
  useEffect(() => {
    latest.current = handler;
  }, [handler]);
  const subscribe = live?.subscribe;
  useEffect(() => subscribe?.(type, (data, event) => latest.current(data, event)), [subscribe, type]);
}

// Ids of messages that arrived in the last 1.2 seconds, for the "new" highlight.
export function useFreshIds(): ReadonlySet<string> {
  return useContext(LiveContext)?.fresh ?? NO_IDS;
}