/** 우측 패널 종목 리스트용 초소형 선차트. 상호작용 없음(스펙: 커서 올려도 반응 없음).
 * 10차: 데이터가 없거나(2점 미만) 전혀 움직이지 않으면 아무것도 그리지 않는다
 * (예전엔 값이 같아도 빨간 가로선이 그려져 보기 안 좋았음). */
export default function Sparkline({ values, className }: { values: number[]; className?: string }) {
  const lo = values.length ? Math.min(...values) : 0;
  const hi = values.length ? Math.max(...values) : 0;
  const span = hi - lo;
  const enough = values.length >= 3 && span > Math.max(1e-9, Math.abs(hi) * 1e-6);

  if (!enough) {
    return <svg className={className} viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden />;
  }

  const pts = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * 100;
      const y = 29 - ((v - lo) / span) * 28;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
  const up = values[values.length - 1] >= values[0];
  return (
    <svg className={className} viewBox="0 0 100 30" preserveAspectRatio="none">
      <polyline
        points={pts}
        fill="none"
        stroke={up ? "var(--up)" : "var(--down)"}
        strokeWidth={1.5}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}
