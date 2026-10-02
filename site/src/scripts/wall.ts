import { arrange, isDefault, matches, plural, readState, writeState, type Entry, type State } from "./wall-core";

const wall = document.querySelector<HTMLElement>("[data-wall]");
const form = document.querySelector<HTMLFormElement>("[data-controls]");
if (wall && form) void start(wall, form);

function stored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function store(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // private browsing: the size just isn't remembered
  }
}

async function start(wall: HTMLElement, form: HTMLFormElement): Promise<void> {
  const scope = wall.dataset.folio || null;
  const titles = JSON.parse(wall.dataset.titles ?? "{}") as Record<string, string>;
  const all = (await (await fetch(wall.dataset.index!)).json()) as Entry[];
  const entries = scope ? all.filter((e) => e.f === scope) : all;
  const tiles = new Map(Array.from(wall.querySelectorAll<HTMLElement>(".tile"), (t) => [t.dataset.id!, t]));
  const q = form.elements.namedItem("q") as HTMLInputElement;
  const how = form.elements.namedItem("arrange") as HTMLSelectElement;
  const size = form.elements.namedItem("size") as HTMLInputElement;
  const count = form.querySelector<HTMLElement>("[data-count]")!;
  const pills = Array.from(form.querySelectorAll<HTMLButtonElement>(".pill"));

  let state: State = readState(location.search);
  if (scope) state = { ...state, folios: [] };

  const pressed = (pill: HTMLButtonElement): boolean =>
    pill.dataset.folio ? state.folios.includes(pill.dataset.folio) : state.flags.includes(pill.dataset.flag!);
  const syncControls = (): void => {
    q.value = state.q;
    how.value = state.arrange;
    for (const pill of pills) pill.setAttribute("aria-pressed", String(pressed(pill)));
  };

  const section = (title: string, items: HTMLElement[]): HTMLElement => {
    const s = document.createElement("section");
    s.className = "group";
    const h = document.createElement("h2");
    h.className = "group-title";
    const n = document.createElement("span");
    n.className = "group-count";
    n.textContent = plural(items.length, "plate");
    h.append(`${title} `, n);
    const rows = document.createElement("div");
    rows.className = "rows";
    rows.append(...items);
    s.append(h, rows);
    return s;
  };

  const empty = (): HTMLElement => {
    const p = document.createElement("p");
    p.className = "empty";
    const clear = document.createElement("a");
    clear.href = location.pathname;
    clear.textContent = "Clear filters";
    clear.addEventListener("click", (e) => {
      e.preventDefault();
      state = { q: "", folios: [], flags: [], arrange: state.arrange };
      syncControls();
      render();
    });
    p.append("No plates match. ", clear);
    return p;
  };

  function render(): void {
    const visible = entries.filter((e) => matches(e, state));
    const out = document.createDocumentFragment();
    for (const g of arrange(visible, state.arrange, titles, scope)) out.append(section(g.title, g.ids.map((id) => tiles.get(id)!)));
    if (!visible.length) out.append(empty());
    wall.replaceChildren(out);
    count.textContent = plural(visible.length, "plate");
    history.replaceState(history.state, "", location.pathname + writeState(state) + location.hash);
  }

  const setRow = (): void => wall.style.setProperty("--row-h", `${size.value}px`);
  const saved = stored("row-h");
  if (saved) {
    size.value = saved;
    setRow();
  } else {
    size.value = String(parseInt(getComputedStyle(wall).getPropertyValue("--row-h"), 10) || 180);
  }

  let timer = 0;
  q.addEventListener("input", () => {
    clearTimeout(timer);
    timer = window.setTimeout(() => {
      state = { ...state, q: q.value };
      render();
    }, 120);
  });
  how.addEventListener("change", () => {
    state = { ...state, arrange: how.value as State["arrange"] };
    render();
  });
  for (const pill of pills) {
    pill.addEventListener("click", () => {
      const on = pill.getAttribute("aria-pressed") !== "true";
      pill.setAttribute("aria-pressed", String(on));
      if (pill.dataset.folio) {
        const v = pill.dataset.folio;
        state = { ...state, folios: on ? [...state.folios, v] : state.folios.filter((x) => x !== v) };
      } else {
        const v = pill.dataset.flag!;
        state = { ...state, flags: on ? [...state.flags, v] : state.flags.filter((x) => x !== v) };
      }
      render();
    });
  }
  size.addEventListener("input", () => {
    setRow();
    store("row-h", size.value);
  });
  form.addEventListener("submit", (e) => e.preventDefault());
  wall.addEventListener("click", (e) => {
    const tile = (e.target as HTMLElement).closest<HTMLElement>(".tile");
    if (!tile) return;
    for (const img of wall.querySelectorAll<HTMLImageElement>("img")) img.style.viewTransitionName = "";
    const img = tile.querySelector("img");
    if (img) img.style.viewTransitionName = "plate";
  });

  syncControls();
  if (!isDefault(state)) render();
}
