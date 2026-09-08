import { useSyncExternalStore } from "react";
import type { Series } from "../types";

type State = Record<string, Series>;

let state: State = {};
const listeners = new Set<() => void>();

function emit() {
  state = { ...state };
  listeners.forEach((l) => l());
}

function applySnapshot(series: Record<string, any>) {
  const next: State = {};
  for (const [id, data] of Object.entries(series)) {
    next[id] = { id, ...(data as any) } as Series;
  }
  state = next;
  listeners.forEach((l) => l());
}

function applyUpdate(msg: any) {
  const { id, kind, ...rest } = msg;
  const prev = state[id];
  state[id] = { ...(prev as any), id, kind, ...rest } as Series;
  emit();
}

function applyLight(id: string, light: string) {
  if (state[id]) {
    state[id] = { ...(state[id] as any), light };
    emit();
  }
}

let ws: WebSocket | null = null;
let reconnectTimer: number | undefined;

export function connect() {
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === "snapshot") applySnapshot(msg.series);
    else if (msg.type === "update") applyUpdate(msg);
    else if (msg.type === "light") applyLight(msg.id, msg.light);
  };
  ws.onclose = () => {
    window.clearTimeout(reconnectTimer);
    reconnectTimer = window.setTimeout(connect, 1500);
  };
  ws.onerror = () => ws?.close();
}

function subscribe(cb: () => void) {
  listeners.add(cb);
  connect();
  return () => listeners.delete(cb);
}

export function useSeries(id: string): Series | undefined {
  return useSyncExternalStore(subscribe, () => state[id]);
}

export function useAllSeries(): State {
  return useSyncExternalStore(subscribe, () => state);
}
