/** ← and → go to the previous and next plate. */
document.addEventListener("keydown", (e) => {
  if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || e.defaultPrevented) return;
  if ((e.target as HTMLElement).closest("input, select, textarea, [contenteditable]")) return;
  const rel = e.key === "ArrowLeft" ? "prev" : e.key === "ArrowRight" ? "next" : "";
  const link = rel ? document.querySelector<HTMLAnchorElement>(`a[rel="${rel}"]`) : null;
  if (link) location.href = link.href;
});
