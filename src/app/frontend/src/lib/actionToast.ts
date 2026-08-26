export type ActionToastKind = 'promo' | 'precio' | 'ok' | 'error';

export interface ActionToastItem {
  id: string;
  kind: ActionToastKind;
  title: string;
  summary?: string;
  arrivedAt: number;
}

type Listener = (item: ActionToastItem) => void;
const listeners = new Set<Listener>();

export function subscribeActionToast(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function pushActionToast(
  kind: ActionToastKind,
  title: string,
  summary?: string,
): void {
  const item: ActionToastItem = {
    id: crypto.randomUUID(),
    kind,
    title,
    summary,
    arrivedAt: Date.now(),
  };
  listeners.forEach((l) => l(item));
}
