// Live events: a WebSocket in real mode, the mock bus in mock mode. Unknown event types are ignored.
import {
  createContext, createElement, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode,
} from 'react';
import { useQueryClient, type QueryClient } from '@tanstack/react-query';
import { mockBus } from '../mocks/bus';
import { USE_MOCKS, WS_URL } from './client';
import { keys, noteRun } from './hooks';
import type { EventType, LedgerEntry, NegotiationMessage, WsEvent } from './types';

type Handler = (data: Record<string, unknown>, event: WsEvent) => void;

export type LiveStatus = 'open' | 'connecting' | 'closed';

interface LiveValue {
  subscribe: (type: EventType, handler: Handler) => () => void;
  fresh: ReadonlySet<string>;
  status: LiveStatus;
}

const KNOWN: ReadonlySet<string> = new Set<EventType>([
  'negotiation.message', 'plan.updated', 'risk.windows_changed', 'approval.requested', 'approval.decided',
  'verification.result', 'ledger.appended', 'copilot.step', 'ui.action', 'auditor.flag',
]);

const FRESH_MS = 1200;
const BATCH_MS = 150;
const LOST_MS = 3000;
// Lists that do not change when the connection comes back.
const STAYS: ReadonlySet<string> = new Set(['segments', 'departments']);
const RETRY_MS = [1000, 2000, 5000];
const NO_IDS: ReadonlySet<string> = new Set();

const LiveContext = createContext<LiveValue | null>(null);

// A new message goes into the cached list of its own run, once. If that list is not cached, it is fetched.
function mergeMessage(qc: QueryClient, message: NegotiationMessage): boolean {
  const key = keys.negotiation(message.run_id);
  const old = qc.getQueryData<NegotiationMessage[]>(key);
  if (!old) return false;
  if (old.some((m) => m.msg_id === message.msg_id)) return true;
  const next = [...old, message].sort((a, b) => a.ts.localeCompare(b.ts) || a.msg_id.localeCompare(b.msg_id));
  qc.setQueryData<NegotiationMessage[]>(key, next);
  return true;
}

// A new ledger entry goes into every cached list by its number, newest first, without a refetch.
function mergeLedger(qc: QueryClient, entry: LedgerEntry): boolean {
  if (!entry || typeof entry.seq !== 'number') return false;
  for (const [key, old] of qc.getQueriesData<LedgerEntry[]>({ queryKey: ['ledger'] })) {
    if (!old || old.some((e) => e.seq === entry.seq)) continue;
    const limit = Number(key[1]);
    const next = [entry, ...old].sort((a, b) => b.seq - a.seq);
    qc.setQueryData<LedgerEntry[]>(key, Number.isFinite(limit) && next.length > limit ? next.slice(0, limit) : next);
  }
  return true;
}

function applyEvent(
  qc: QueryClient, event: WsEvent, markFresh: (id: string) => void, later: (...roots: string[]) => void,
): void {
  switch (event.type) {
    case 'negotiation.message': {
      const message = event.data as unknown as NegotiationMessage;
      if (!message || typeof message.run_id !== 'string') break;
      noteRun(qc, message.run_id);
      if (!mergeMessage(qc, message)) later('negotiation');
      markFresh(`${message.run_id}/${message.msg_id}`);
      break;
    }
    case 'plan.updated':
      later('works', 'plans', 'metrics', 'approvals');
      break;
    case 'risk.windows_changed':
      later('risk');
      break;
    case 'approval.requested':
    case 'approval.decided':
      later('approvals', 'plans');
      break;
    case 'verification.result':
      later('verification', 'works');
      break;
    case 'ledger.appended':
      if (!mergeLedger(qc, event.data as unknown as LedgerEntry)) later('ledger');
      break;
    case 'auditor.flag':
      later('flags');
      break;
    default:
      // copilot.step and ui.action go only to the screens that subscribed.
      break;
  }
}

// Reconnects after 1 s, 2 s and 5 s, then every 5 s.
function connect(
  onEvent: (event: WsEvent) => void, onStatus: (status: LiveStatus) => void, onReturn: () => void,
): () => void {
  let socket: WebSocket | null = null;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let attempt = 0;
  let closed = false;
  let opened = false;

  const open = (): void => {
    onStatus('connecting');
    socket = new WebSocket(WS_URL);
    socket.onopen = () => {
      attempt = 0;
      onStatus('open');
      if (opened) onReturn();
      opened = true;
    };
    socket.onmessage = (message) => {
      try {
        const event = JSON.parse(String(message.data)) as WsEvent | null;
        if (event && typeof event === 'object' && typeof event.type === 'string') {
          onEvent({ ...event, data: event.data ?? {} });
        }
      } catch {
        // A frame that is not JSON is not ours; skip it.
      }
    };
    socket.onclose = () => {
      if (closed) return;
      onStatus('closed');
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
  const [status, setStatus] = useState<LiveStatus>(USE_MOCKS ? 'open' : 'connecting');
  const queued = useRef(new Set<string>());
  const flushTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  // Events that arrive together refetch each list once.
  const later = useCallback((...roots: string[]) => {
    roots.forEach((root) => queued.current.add(root));
    if (flushTimer.current) return;
    flushTimer.current = setTimeout(() => {
      flushTimer.current = undefined;
      const roots = [...queued.current];
      queued.current.clear();
      roots.forEach((root) => void qc.invalidateQueries({ queryKey: [root], refetchType: 'active' }));
    }, BATCH_MS);
  }, [qc]);

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
      applyEvent(qc, event, markFresh, later);
      handlers.current.get(event.type)?.forEach((handler) => handler(event.data, event));
    };
    // After a lost connection, whatever is on screen is fetched once more.
    const onReturn = (): void => {
      void qc.invalidateQueries({ refetchType: 'active', predicate: (q) => !STAYS.has(String(q.queryKey[0])) });
    };
    const stop = USE_MOCKS ? mockBus.on(onEvent) : connect(onEvent, setStatus, onReturn);
    const pending = timers.current;
    return () => {
      stop();
      clearTimeout(flushTimer.current);
      flushTimer.current = undefined;
      queued.current.clear();
      pending.forEach((t) => clearTimeout(t));
      pending.clear();
    };
  }, [qc, markFresh, later]);

  const value = useMemo<LiveValue>(() => ({ subscribe, fresh, status }), [subscribe, fresh, status]);
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
export function useLiveStatus(): LiveStatus {
  return useContext(LiveContext)?.status ?? 'open';
}

// True once the connection has been down for 3 seconds. A short break does not change the screen.
export function useConnectionLost(): boolean {
  const status = useLiveStatus();
  const [lost, setLost] = useState(false);
  useEffect(() => {
    if (status === 'open') {
      setLost(false);
      return undefined;
    }
    const timer = setTimeout(() => setLost(true), LOST_MS);
    return () => clearTimeout(timer);
  }, [status]);
  return lost;
}
