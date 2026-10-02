/** Zoom and pan on the plate. Pinch, ctrl- or ⌘-scroll, double-click and the buttons zoom; drag pans. */
for (const root of document.querySelectorAll<HTMLElement>("[data-viewer]")) viewer(root);

function viewer(root: HTMLElement): void {
  const stage = root.querySelector<HTMLElement>("[data-stage]")!;
  const reset = root.querySelector<HTMLButtonElement>("[data-zoom=reset]")!;
  const pointers = new Map<number, { x: number; y: number }>();
  let scale = 1;
  let x = 0;
  let y = 0;

  const image = (): HTMLImageElement => stage.querySelector<HTMLImageElement>("img:not([hidden])")!;
  const clamp = (v: number, lo: number, hi: number): number => Math.min(hi, Math.max(lo, v));

  function apply(): void {
    const img = image();
    const mx = ((scale - 1) * img.offsetWidth) / 2;
    const my = ((scale - 1) * img.offsetHeight) / 2;
    x = clamp(x, -mx, mx);
    y = clamp(y, -my, my);
    img.style.transform = scale === 1 ? "" : `translate(${x}px, ${y}px) scale(${scale})`;
    stage.classList.toggle("zoomed", scale > 1);
    reset.hidden = scale === 1;
  }

  /** Zoom by factor, keeping the point under (cx, cy) where it is. */
  function zoomAt(factor: number, cx: number, cy: number): void {
    const img = image();
    const r = stage.getBoundingClientRect();
    const px = cx - (r.left + img.offsetLeft + img.offsetWidth / 2);
    const py = cy - (r.top + img.offsetTop + img.offsetHeight / 2);
    const next = clamp(scale * factor, 1, 8);
    x = px - ((px - x) * next) / scale;
    y = py - ((py - y) * next) / scale;
    scale = next;
    if (scale === 1) x = y = 0;
    apply();
  }

  const centre = (): [number, number] => {
    const r = stage.getBoundingClientRect();
    return [r.left + r.width / 2, r.top + r.height / 2];
  };

  stage.addEventListener("wheel", (e) => {
    if (!e.ctrlKey && !e.metaKey) return; // plain scrolling scrolls the page; a trackpad pinch arrives with ctrlKey
    e.preventDefault();
    zoomAt(Math.exp(-clamp(e.deltaY, -50, 50) * 0.01), e.clientX, e.clientY);
  }, { passive: false });
  stage.addEventListener("dblclick", (e) => zoomAt(scale > 1 ? 1 / scale : 2.5, e.clientX, e.clientY));
  stage.addEventListener("pointerdown", (e) => {
    if (scale === 1 && e.pointerType !== "mouse") return; // let a finger scroll the page
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    stage.setPointerCapture(e.pointerId);
  });
  stage.addEventListener("pointermove", (e) => {
    const last = pointers.get(e.pointerId);
    if (!last) return;
    if (pointers.size === 1 && scale > 1) {
      x += e.clientX - last.x;
      y += e.clientY - last.y;
      apply();
    } else if (pointers.size === 2) {
      const other = [...pointers.entries()].find(([id]) => id !== e.pointerId)![1];
      const before = Math.hypot(last.x - other.x, last.y - other.y);
      const after = Math.hypot(e.clientX - other.x, e.clientY - other.y);
      if (before > 0) zoomAt(after / before, (e.clientX + other.x) / 2, (e.clientY + other.y) / 2);
    }
    pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  });
  for (const type of ["pointerup", "pointercancel"] as const) stage.addEventListener(type, (e) => pointers.delete(e.pointerId));

  root.querySelector("[data-zoom=in]")!.addEventListener("click", () => zoomAt(1.6, ...centre()));
  root.querySelector("[data-zoom=out]")!.addEventListener("click", () => zoomAt(1 / 1.6, ...centre()));
  reset.addEventListener("click", () => zoomAt(1 / scale, ...centre()));

  for (const button of root.querySelectorAll<HTMLButtonElement>("[data-show]")) {
    button.addEventListener("click", () => {
      image().style.transform = "";
      scale = 1;
      x = y = 0;
      for (const img of stage.querySelectorAll<HTMLImageElement>("img")) img.hidden = img.dataset.cut !== button.dataset.show;
      for (const b of root.querySelectorAll<HTMLButtonElement>("[data-show]")) b.setAttribute("aria-pressed", String(b === button));
      apply();
    });
  }
  window.addEventListener("resize", apply);
}
