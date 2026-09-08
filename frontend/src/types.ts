export type Light = "green" | "red" | "gray";

export interface Bar {
  t: number; // epoch seconds, 5-min bucket start (KST)
  o: number;
  h: number;
  l: number;
  c: number;
  flat?: boolean; // 종가 유지용으로 채운 봉
}

export interface CandleSeries {
  kind: "candles";
  id: string;
  label: string;
  unit: "price" | "yield";
  decimals: number;
  bars: Bar[];
  price: number | null;
  change_pct?: number | null;
  light: Light;
  unavailable?: boolean;
}

export interface FlowBar {
  t: number;
  individual: number;
  foreign: number;
  institution: number;
}

export interface FlowSeries {
  kind: "flow";
  id: string;
  label: string;
  bars: FlowBar[];
  current: { individual: number; foreign: number; institution: number };
  foreign_detail: Record<string, number> | null;
  institution_detail: Record<string, number>;
  light: Light;
  unavailable?: boolean;
}

export interface HeatmapRow {
  rank: number;
  code: string;
  name: string;
  price: number;
  change_pct: number | null;
  market_cap_eok: number; // 억원
  sector: string;
}

export interface HeatmapSeries {
  kind: "heatmap";
  id: string;
  label: string;
  rows: HeatmapRow[];
  light: Light;
}

export interface RankRow {
  rank: number;
  code: string;
  name: string;
  price: number;
  change_pct: number | null;
  trade_value_eok: number; // 억원
  market_cap_eok: number; // 억원(근사)
  spark: number[];
}

export interface RankingSeries {
  kind: "ranking";
  id: string;
  label: string;
  rows: RankRow[];
  light: Light;
}

export type Series = CandleSeries | FlowSeries | HeatmapSeries | RankingSeries;
