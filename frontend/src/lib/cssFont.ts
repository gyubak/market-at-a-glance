/** CSS 커스텀 프로퍼티(예: clamp() 로 정의된 --fs-*)의 실제 계산된 px 값을 읽는다.
 * getComputedStyle(...).getPropertyValue("--x") 는 커스텀 프로퍼티 자체를 작성된 원문
 * 그대로(예: "clamp(12px, 0.83vw, 17px)") 돌려줄 뿐 계산은 안 해준다 — 실제 font-size
 * 프로퍼티에 적용해 브라우저가 계산하게 한 다음 그 결과를 읽어야 한다. */
let probe: HTMLDivElement | null = null;

export function cssFontPx(varName: string, fallback: number): number {
  if (!probe) {
    probe = document.createElement("div");
    probe.style.position = "fixed";
    probe.style.left = "-9999px";
    probe.style.visibility = "hidden";
    probe.style.pointerEvents = "none";
    document.body.appendChild(probe);
  }
  probe.style.fontSize = `var(${varName})`;
  const px = parseFloat(getComputedStyle(probe).fontSize);
  return Number.isFinite(px) ? px : fallback;
}
