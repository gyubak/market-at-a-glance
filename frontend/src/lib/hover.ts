import { useSyncExternalStore } from "react";

export interface HoverOHLC {
  label: string;
  decimals: number;
  o: number;
  h: number;
  l: number;
  c: number;
}

let hover: HoverOHLC | null = null;
let owner: string | null = null;
const listeners = new Set<() => void>();

function emit() {
  listeners.forEach((l) => l());
}

/** 캔들 차트가 hover 중인 봉의 OHLC 를 공유(상단바 가격 표시기가 읽음). */
export function setHoverOHLC(id: string, v: HoverOHLC) {
  owner = id;
  hover = v;
  emit();
}

/** 해당 차트에서 벗어남 — 다른 차트가 이미 소유했다면 무시. */
export function clearHoverOHLC(id: string) {
  if (owner === id || owner === null) {
    owner = null;
    hover = null;
    emit();
  }
}

export function useHoverOHLC(): HoverOHLC | null {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    () => hover
  );
}
