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
  "PATH=$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH aiquota --json --ttl 240 2>/dev/null || echo '{}'";

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

  /* Widget material: translucent + blurred, like WidgetKit's system material */
  color: rgba(255, 255, 255, 0.92);
  background: rgba(28, 28, 30, 0.62);
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
    background: rgba(255, 255, 255, 0.66);
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
  }
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
    display: flex; align-items: baseline; gap: 6px; margin-bottom: 8px;
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

const shell = (cmd) => {
  const exec = typeof run === "function" ? run : window.run;
  if (typeof exec !== "function") return;
  exec(`PATH=$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH; ${cmd}`);
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

  const services = data.services || [];
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
      <div>
        {header}
        <div className="empty">No accounts yet</div>
        <div className="foot">
          <button className="primary" onClick={openPicker}>
            Add Account
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
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
              <span style={{ color: dotColor(s.tier), fontSize: "9px" }}>●</span>
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

            {s.tier === "unconfigured" ? (
              <button className="linkbtn" onClick={openPicker}>
                Connect →
              </button>
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
      </div>
    </div>
  );
};
