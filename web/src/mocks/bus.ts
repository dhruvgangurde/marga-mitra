import type { WsEvent } from '../api/types';

type Listener = (event: WsEvent) => void;

const listeners = new Set<Listener>();

export const mockBus = {
  on(fn: Listener): () => void {
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  },
  emit(event: WsEvent): void {
    listeners.forEach((fn) => fn(event));
  },
};