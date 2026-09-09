// aiquota.jsx — Übersicht desktop widget
// Styled to match native macOS (Sonoma/Sequoia) widgets.
// https://github.com/anujpatel06/aiquota
//
// Design notes — these mirror Apple's WidgetKit conventions:
//   • 24px corner radius (macOS medium widget)
//   • vibrancy: heavy backdrop blur + saturation, not a flat dark panel
//   • 16px padding, 8pt spacing rhythm
//   • SF Pro text stack, tight sizes (13 / 11 / 22)
//   • Apple system colors (systemGreen/Orange/Red), light+dark adaptive
//   • hairline 0.5px separators, capsule progress tracks

export const refreshFrequency = 300000; // 5 min — each refresh costs ~1 Haiku token

export const command =
  "PATH=$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH aiquota --json --logos --ttl 240 2>/dev/null || echo '{}'";

// Übersicht widgets are click-through by default: the container ignores the
// mouse so the desktop stays usable. Interactive elements opt back in with
// `pointer-events: auto`.
export const className = `
  top: 40px;
  right: 40px;
  width: 340px;

  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text",
               "Helvetica Neue", sans-serif;
  -webkit-font-smoothing: antialiased;
  font-size: 13px;
  line-height: 1.3;
  letter-spacing: -0.01em;

  /* Widget material: translucent + blurred, like WidgetKit's system material.
     Opacity 0.81 = half the transparency of the original 0.62 (0.38 -> 0.19),
     so the wallpaper still tints it but text stays legible over busy images. */
  color: rgba(255, 255, 255, 0.92);
  background: rgba(28, 28, 30, 0.81);
  -webkit-backdrop-filter: blur(50px) saturate(180%);
  backdrop-filter: blur(50px) saturate(180%);

  border-radius: 24px;
  padding: 16px;

  /* Hairline edge + layered shadow, as macOS draws widget cards */
  box-shadow:
    inset 0 0 0 0.5px rgba(255, 255, 255, 0.14),
    0 1px 1px rgba(0, 0, 0, 0.14),
    0 8px 28px rgba(0, 0, 0, 0.28);

  z-index: 1;

  @media (prefers-color-scheme: light) {
    color: rgba(0, 0, 0, 0.88);
    background: rgba(255, 255, 255, 0.83);
    box-shadow:
      inset 0 0 0 0.5px rgba(0, 0, 0, 0.08),
      0 1px 1px rgba(0, 0, 0, 0.06),
      0 8px 28px rgba(0, 0, 0, 0.14);
  }

  * { box-sizing: border-box; }

  /* ---- header ------------------------------------------------------ */
  .hdr {
    display: flex; align-items: center; gap: 7px;
    margin-bottom: 14px;
    pointer-events: auto;      /* drag handle — container is click-through */
    cursor: grab;
    user-select: none; -webkit-user-select: none;
  }
  .hdr:active { cursor: grabbing; }
  .glyph {
    width: 20px; height: 20px; border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
    background: linear-gradient(180deg, #0A84FF 0%, #0060DF 100%);
    color: #fff; font-size: 11px; font-weight: 700;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.28);
    flex: none;
  }
  .htitle {
    font-size: 13px; font-weight: 600; letter-spacing: -0.02em;
  }
  .hstamp {
    margin-left: auto;
    font-size: 11px;
    color: rgba(255, 255, 255, 0.45);
    font-variant-numeric: tabular-nums;
  }
  @media (prefers-color-scheme: light) {
    .hstamp { color: rgba(0, 0, 0, 0.42); }
  }

  /* ---- service rows ------------------------------------------------ */
  .svc { padding: 10px 0; }
  .svc + .svc { border-top: 0.5px solid rgba(255, 255, 255, 0.12); }
  @media (prefers-color-scheme: light) {
    .svc + .svc { border-top-color: rgba(0, 0, 0, 0.09); }
  }

  .srow {
    display: flex; align-items: center; gap: 8px; margin-bottom: 8px;
  }
  /* Platform logo: small rounded tile, like an app icon in a macOS list */
  .logo {
    width: 18px; height: 18px; border-radius: 5px; flex: none;
    object-fit: contain; padding: 2px;
    background: rgba(255, 255, 255, 0.10);
  }
  @media (prefers-color-scheme: light) {
    .logo { background: rgba(0, 0, 0, 0.06); }
  }
  .logo-ph {
    width: 18px; height: 18px; border-radius: 5px; flex: none;
    display: flex; align-items: center; justify-content: center;
    font-size: 10px; font-weight: 700;
    background: rgba(255, 255, 255, 0.10); color: rgba(255,255,255,0.55);
  }
  @media (prefers-color-scheme: light) {
    .logo-ph { background: rgba(0,0,0,0.06); color: rgba(0,0,0,0.45); }
  }
  /* Tiny live/error dot, now overlaid at the logo's corner */
  .status {
    width: 7px; height: 7px; border-radius: 50%; flex: none;
    margin-left: -13px; margin-top: 12px;
    box-shadow: 0 0 0 1.5px rgba(28,28,30,0.9);
  }
  @media (prefers-color-scheme: light) {
    .status { box-shadow: 0 0 0 1.5px rgba(255,255,255,0.9); }
  }
  .sname { font-size: 13px; font-weight: 590; letter-spacing: -0.01em; }
  .splan {
    font-size: 11px; color: rgba(255, 255, 255, 0.45);
  }
  .sbig {
    margin-left: auto;
    font-size: 22px; font-weight: 600; letter-spacing: -0.03em;
    font-variant-numeric: tabular-nums; line-height: 1;
  }
  @media (prefers-color-scheme: light) {
    .splan { color: rgba(0, 0, 0, 0.42); }
  }

  .meter { margin-top: 7px; }
  .mlabel {
    display: flex; justify-content: space-between; gap: 8px;
    font-size: 11px; margin-bottom: 4px;
    color: rgba(255, 255, 255, 0.5);
  }
  .mlabel b {
    font-weight: 590; font-variant-numeric: tabular-nums;
    color: rgba(255, 255, 255, 0.78);
  }
  @media (prefers-color-scheme: light) {
    .mlabel { color: rgba(0, 0, 0, 0.45); }
    .mlabel b { color: rgba(0, 0, 0, 0.72); }
  }

  /* Capsule track, like a macOS progress view */
  .track {
    height: 6px; border-radius: 3px; overflow: hidden;
    background: rgba(255, 255, 255, 0.14);
  }
  @media (prefers-color-scheme: light) {
    .track { background: rgba(0, 0, 0, 0.1); }
  }
  .fill {
    height: 100%; border-radius: 3px;
    transition: width 0.45s cubic-bezier(0.4, 0, 0.2, 1);
  }

  .note {
    font-size: 11px; color: rgba(255, 255, 255, 0.45); margin-top: 2px;
  }
  .warn { color: #FF9F0A; }
  @media (prefers-color-scheme: light) {
    .note { color: rgba(0, 0, 0, 0.42); }
    .warn { color: #C93400; }
  }

  /* ---- footer / controls ------------------------------------------- */
  .foot {
    display: flex; gap: 6px; align-items: center;
    margin-top: 12px; padding-top: 12px;
    border-top: 0.5px solid rgba(255, 255, 255, 0.12);
  }
  @media (prefers-color-scheme: light) {
    .foot { border-top-color: rgba(0, 0, 0, 0.09); }
  }

  button {
    pointer-events: auto;  /* container is click-through; buttons opt back in */
    cursor: default;
    font: inherit; font-size: 12px; font-weight: 500;
    letter-spacing: -0.01em;
    color: #fff;
    background: rgba(120, 120, 128, 0.36);
    border: none; border-radius: 8px;
    padding: 5px 12px;
    transition: background 0.12s ease, transform 0.06s ease;
  }
  button:hover { background: rgba(120, 120, 128, 0.5); }
  button:active { transform: scale(0.97); }
  button.primary { background: #0A84FF; }
  button.primary:hover { background: #3395FF; }
  @media (prefers-color-scheme: light) {
    button { color: rgba(0, 0, 0, 0.85); background: rgba(120, 120, 128, 0.2); }
    button:hover { background: rgba(120, 120, 128, 0.3); }
    button.primary { color: #fff; background: #007AFF; }
  }

  .linkbtn {
    pointer-events: auto; cursor: default;
    font: inherit; font-size: 11px; font-weight: 500;
    color: #0A84FF; background: none; border: none;
    padding: 3px 0; margin-top: 5px;
  }
  .linkbtn:hover { opacity: 0.7; }
  @media (prefers-color-scheme: light) { .linkbtn { color: #007AFF; } }

  .empty {
    font-size: 12px; color: rgba(255, 255, 255, 0.45);
    padding: 6px 0 2px;
  }
  @media (prefers-color-scheme: light) {
    .empty { color: rgba(0, 0, 0, 0.42); }
  }
`;

// Apple system colors (dark-mode variants).
const SYS_GREEN = "#30D158";
const SYS_ORANGE = "#FF9F0A";
const SYS_RED = "#FF453A";
const SYS_GRAY = "#8E8E93";

const tone = (p) => (p >= 85 ? SYS_RED : p >= 60 ? SYS_ORANGE : SYS_GREEN);

const dotColor = (t) =>
  t === "live" ? SYS_GREEN : t === "error" ? SYS_RED : SYS_GRAY;

// Run a shell command. Übersicht injects `run` into the render scope, but a
// bare `typeof run` throws a ReferenceError in some scopes and kills the click
// silently — so try every shape, then fall back to POSTing Übersicht's own
// /run/ endpoint, which is what run() does internally.
const shell = (cmd) => {
  const full =
    `PATH=$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH; ` +
    `echo "$(date) ${cmd}" >> "$HOME/.cache/aiquota/clicks.log" 2>/dev/null; ` +
    cmd;

  let exec = null;
  try { if (typeof run === "function") exec = run; } catch (e) {}
  if (!exec && typeof window !== "undefined" && typeof window.run === "function") {
    exec = window.run;
  }
  if (exec) {
    try { exec(full); return; } catch (e) {}
  }

  // Last resort: Übersicht's HTTP API, same origin as the widget page.
  try {
    fetch("/run/", { method: "POST", body: full }).catch(() => {});
  } catch (e) {}
};

// ---- dragging -------------------------------------------------------
// Übersicht owns the outer element and re-runs render() on every refresh,
// so the position lives in localStorage and is re-applied on each mount.
const POS_KEY = "aiquota.pos";

const loadPos = () => {
  try {
    const v = JSON.parse(localStorage.getItem(POS_KEY) || "null");
    if (v && typeof v.x === "number" && typeof v.y === "number") return v;
  } catch (e) {}
  return null;
};

const applyPos = (el, pos) => {
  if (!el || !pos) return;
  // Switch to left/top so dragging works regardless of the CSS anchor.
  el.style.left = `${pos.x}px`;
  el.style.top = `${pos.y}px`;
  el.style.right = "auto";
  el.style.bottom = "auto";
};

// Attach drag once per mounted element (guarded by a data flag).
const makeDraggable = (node) => {
  if (!node) return;
  const el = node.closest("#aiquota") || node.parentElement || node;
  if (!el) return;

  applyPos(el, loadPos());

  if (el.dataset.aiqDrag === "1") return; // already wired
  el.dataset.aiqDrag = "1";

  const handle = node.querySelector(".hdr");
  if (!handle) return;
  handle.style.pointerEvents = "auto";
  handle.style.cursor = "grab";

  let startX = 0, startY = 0, originX = 0, originY = 0, dragging = false;

  const onMove = (e) => {
    if (!dragging) return;
    const x = Math.max(0, originX + (e.clientX - startX));
    const y = Math.max(0, originY + (e.clientY - startY));
    el.style.left = `${x}px`;
    el.style.top = `${y}px`;
    el.style.right = "auto";
    el.style.bottom = "auto";
    e.preventDefault();
  };

  const onUp = () => {
    if (!dragging) return;
    dragging = false;
    handle.style.cursor = "grab";
    el.style.transition = "";
    document.removeEventListener("mousemove", onMove, true);
    document.removeEventListener("mouseup", onUp, true);
    try {
      localStorage.setItem(
        POS_KEY,
        JSON.stringify({
          x: parseInt(el.style.left, 10) || 0,
          y: parseInt(el.style.top, 10) || 0,
        })
      );
    } catch (e) {}
  };

  handle.addEventListener("mousedown", (e) => {
    if (e.button !== 0) return;
    const r = el.getBoundingClientRect();
    startX = e.clientX;
    startY = e.clientY;
    originX = r.left;
    originY = r.top;
    dragging = true;
    handle.style.cursor = "grabbing";
    el.style.transition = "none"; // no easing while tracking the cursor
    document.addEventListener("mousemove", onMove, true);
    document.addEventListener("mouseup", onUp, true);
    e.preventDefault();
  });

  // Double-click the header to snap back to the default corner.
  handle.addEventListener("dblclick", () => {
    try {
      localStorage.removeItem(POS_KEY);
    } catch (e) {}
    el.style.left = "";
    el.style.top = "";
    el.style.right = "";
    el.style.bottom = "";
  });
};

// Native platform picker; falls back to the terminal flow if absent.
const openPicker = () =>
  shell(
    "command -v aiquota-picker >/dev/null && aiquota-picker || " +
      "osascript -e 'tell application \"Terminal\" to do script \"aiquota link\"' " +
      "-e 'tell application \"Terminal\" to activate'"
  );

export const render = ({ output }) => {
  let data = {};
  try {
    data = JSON.parse(output || "{}");
  } catch (e) {
    return <div className="empty">Couldn’t read usage data</div>;
  }

  // Only show LINKED services. Unlinked platforms live in the Add Account
  // picker — a dead card taking up desktop space helps nobody.
  const all = data.services || [];
  const services = all.filter((s) => s.tier !== "unconfigured");
  const hidden = all.length - services.length;
  const stamp = data.generated_at
    ? new Date(data.generated_at * 1000).toLocaleTimeString([], {
        hour: "numeric",
        minute: "2-digit",
      })
    : "";

  const header = (
    <div className="hdr">
      <div className="glyph">◐</div>
      <div className="htitle">AI Quota</div>
      <div className="hstamp">{stamp}</div>
    </div>
  );

  if (!services.length) {
    return (
      <div ref={makeDraggable}>
        {header}
        <div className="empty">No accounts linked yet</div>
        <div className="foot">
          <button className="primary" onClick={openPicker}>
            Add Account
          </button>
        </div>
      </div>
    );
  }

  return (
    <div ref={makeDraggable}>
      {header}

      {services.map((s, i) => {
        const ex = s.extra || {};
        const wins = s.windows || [];
        // Headline number = the window under most pressure.
        const peak = wins.length
          ? wins.reduce((a, b) => (Number(b.used_pct) > Number(a.used_pct) ? b : a))
          : null;

        return (
          <div className="svc" key={i}>
            <div className="srow">
              {s.logo ? (
                <img className="logo" src={s.logo} alt="" />
              ) : (
                <div className="logo-ph">
                  {(s.service || "?").charAt(0).toUpperCase()}
                </div>
              )}
              <span
                className="status"
                style={{ background: dotColor(s.tier) }}
              />
              <span className="sname">{s.service}</span>
              {s.plan && s.plan !== s.service ? (
                <span className="splan">{s.plan}</span>
              ) : null}
              {peak ? (
                <span className="sbig" style={{ color: tone(Number(peak.used_pct)) }}>
                  {Math.round(Number(peak.used_pct))}%
                </span>
              ) : null}
            </div>

            {wins.map((w, j) => {
              const p = Math.max(0, Math.min(100, Number(w.used_pct)));
              return (
                <div className="meter" key={j}>
                  <div className="mlabel">
                    <span>{w.label}</span>
                    <b>{w.resets_at || `${p.toFixed(0)}%`}</b>
                  </div>
                  <div className="track">
                    <div
                      className="fill"
                      style={{ width: `${p}%`, background: tone(p) }}
                    />
                  </div>
                </div>
              );
            })}

            {!wins.length && (s.error || s.note) ? (
              <div className={`note ${s.error ? "warn" : ""}`}>
                {s.error || s.note}
              </div>
            ) : null}

            {ex.credits !== undefined || ex.renews_in_days !== undefined ? (
              <div className="note">
                {ex.credits !== undefined ? `${ex.credits} credits` : ""}
                {ex.credits !== undefined && ex.renews_in_days !== undefined
                  ? " · "
                  : ""}
                {ex.renews_in_days !== undefined
                  ? `renews in ${ex.renews_in_days}d`
                  : ""}
              </div>
            ) : null}
          </div>
        );
      })}

      <div className="foot">
        <button className="primary" onClick={openPicker}>
          Add Account
        </button>
        <button onClick={() => shell("aiquota -r >/dev/null 2>&1")}>
          Refresh
        </button>
        {hidden > 0 ? (
          <span className="note" style={{ marginLeft: "auto", marginTop: 0 }}>
            {hidden} not linked
          </span>
        ) : null}
      </div>
    </div>
  );
};
