/** Squarified treemap (Bruls, Huizing & van Wijk 1999).
 * 값이 클수록 정사각형에 가까운 칸을 배정해 한쪽으로 길쭉해지는 것을 막는다.
 * 입력 순서(내림차순으로 정렬해서 넣으면 됨)를 유지해 결과를 그대로 반환한다
 * — 첫 항목이 항상 좌상단(가로가 세로보다 넓은 사각형이면 좌측 상단 셀)에 먼저 배치된다. */

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

function worst(row: number[], side: number): number {
  if (!row.length) return Infinity;
  let sum = 0;
  let max = -Infinity;
  let min = Infinity;
  for (const v of row) {
    sum += v;
    if (v > max) max = v;
    if (v < min) min = v;
  }
  if (sum <= 0 || min <= 0) return Infinity;
  const s2 = side * side;
  const sum2 = sum * sum;
  return Math.max((s2 * max) / sum2, sum2 / (s2 * min));
}

function layoutRow(row: number[], rect: Rect): { rects: Rect[]; rest: Rect } {
  const sum = row.reduce((a, b) => a + b, 0);
  const rects: Rect[] = [];
  if (rect.w >= rect.h) {
    // 짧은 변(h)을 기준으로 왼쪽에 세로 스트립을 채운다.
    const stripW = rect.h > 0 ? sum / rect.h : 0;
    let cy = rect.y;
    for (const v of row) {
      const h = sum > 0 ? (v / sum) * rect.h : 0;
      rects.push({ x: rect.x, y: cy, w: stripW, h });
      cy += h;
    }
    return { rects, rest: { x: rect.x + stripW, y: rect.y, w: Math.max(0, rect.w - stripW), h: rect.h } };
  }
  // 짧은 변(w)을 기준으로 위쪽에 가로 스트립을 채운다.
  const stripH = rect.w > 0 ? sum / rect.w : 0;
  let cx = rect.x;
  for (const v of row) {
    const w = sum > 0 ? (v / sum) * rect.w : 0;
    rects.push({ x: cx, y: rect.y, w, h: stripH });
    cx += w;
  }
  return { rects, rest: { x: rect.x, y: rect.y + stripH, w: rect.w, h: Math.max(0, rect.h - stripH) } };
}

/** values 는 양수여야 하며, 순서를 그대로 유지한 Rect[] 를 돌려준다.
 * (내림차순 정렬은 호출하는 쪽에서 미리 해서 넣어야 "가장 큰 것부터" 배치된다.) */
export function squarify(values: number[], rect: Rect): Rect[] {
  const n = values.length;
  const empty = () => values.map(() => ({ x: rect.x, y: rect.y, w: 0, h: 0 }));
  if (n === 0 || rect.w <= 0 || rect.h <= 0) return empty();
  const total = values.reduce((a, b) => a + b, 0);
  if (total <= 0) return empty();

  const area = rect.w * rect.h;
  const order = values.map((_, i) => i).sort((a, b) => values[b] - values[a]);
  const scaled = order.map((i) => (Math.max(values[i], 0) / total) * area);

  const outByOrder: Rect[] = [];
  let cur: Rect = { ...rect };
  let row: number[] = [];
  let i = 0;
  while (i < scaled.length) {
    const side = Math.min(cur.w, cur.h);
    const candidate = scaled[i];
    if (row.length === 0 || worst(row, side) >= worst([...row, candidate], side)) {
      row.push(candidate);
      i++;
    } else {
      const { rects, rest } = layoutRow(row, cur);
      outByOrder.push(...rects);
      cur = rest;
      row = [];
    }
  }
  if (row.length) {
    outByOrder.push(...layoutRow(row, cur).rects);
  }

  const out: Rect[] = new Array(n);
  order.forEach((origIdx, pos) => {
    out[origIdx] = outByOrder[pos];
  });
  return out;
}
