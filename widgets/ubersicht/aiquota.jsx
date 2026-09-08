// aiquota.jsx — Übersicht desktop widget
// Shows AI subscription quota directly on the desktop wallpaper.
// https://github.com/anujpatel06/aiquota

export const refreshFrequency = 300000; // 5 min — each refresh costs ~1 Haiku token

export const command =
  "PATH=$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH aiquota --json --ttl 240 2>/dev/null || echo '{}'";

// Übersicht widgets are click-through by default: the container ignores the
// mouse so you can still use your desktop. Interactive elements must opt back
// in with `pointer-events: auto` — that's what makes the buttons below
// clickable while the rest of the panel stays out of the way.
export const className = `
  top: 40px;
  right: 40px;
  width: 300px;
  font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
  color: #e6e6e6;
  background: rgba(22, 27, 34, 0.82);
  -webkit-backdrop-filter: blur(24px);
  backdrop-filter: blur(24px);
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 14px;
  padding: 15px 17px;
  box-shadow: 0 10px 34px rgba(0, 0, 0, 0.42);
  z-index: 1;

  h1 {
    margin: 0 0 3px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    color: #8b949e;
  }
  .stamp { font-size: 10px; color: #6e7681; margin-bottom: 12px; }
  .svc { margin-bottom: 13px; }
  .svc:last-child { margin-bottom: 0; }
  .sh {
    display: flex; justify-content: space-between;
    align-items: baseline; margin-bottom: 6px;
  }
  .sn { font-size: 12.5px; font-weight: 600; }
  .plan { font-size: 10px; color: #6e7681; font-weight: 400; }
  .dot { font-size: 9px; margin-right: 4px; }
  .row { margin-bottom: 6px; }
  .row:last-child { margin-bottom: 0; }
  .lbl {
    display: flex; justify-content: space-between;
    font-size: 10.5px; color: #8b949e; margin-bottom: 3px;
  }
  .pct { font-weight: 600; font-variant-numeric: tabular-nums; color: #c9d1d9; }
  .reset { color: #6e7681; margin-left: 5px; font-weight: 400; }
  .track {
    height: 4px; border-radius: 2px;
    background: rgba(255, 255, 255, 0.08); overflow: hidden;
  }
  .fill { height: 100%; border-radius: 2px; transition: width .4s ease; }
  .meta { font-size: 10px; color: #6e7681; margin-top: 4px; }
  .err { font-size: 10px; color: #f85149; margin-top: 3px; }
  .empty { font-size: 11px; color: #6e7681; }
  .cta {
    margin-top: 12px; padding-top: 10px;
    border-top: 1px solid rgba(255, 255, 255, 0.07);
    display: flex; gap: 8px; align-items: center;
  }
  button {
    pointer-events: auto;          /* opt back in — container is click-through */
    cursor: pointer;
    font-family: inherit; font-size: 11px; font-weight: 500;
    color: #58a6ff;
    background: rgba(88, 166, 255, 0.1);
    border: 1px solid rgba(88, 166, 255, 0.28);
    border-radius: 7px;
    padding: 5px 11px;
    transition: background .15s ease, border-color .15s ease;
  }
  button:hover {
    background: rgba(88, 166, 255, 0.2);
    border-color: rgba(88, 166, 255, 0.55);
  }
  button:active { transform: translateY(1px); }
  button.ghost {
    color: #8b949e;
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.12);
  }
  button.ghost:hover {
    background: rgba(255, 255, 255, 0.1);
    border-color: rgba(255, 255, 255, 0.25);
  }
  .link-btn {
    pointer-events: auto; cursor: pointer;
    font-family: inherit; font-size: 10px; font-weight: 500;
    color: #58a6ff; background: none; border: none;
    padding: 2px 0; margin-top: 3px; text-align: left;
  }
  .link-btn:hover { text-decoration: underline; }
`;

const tone = (p) => (p >= 85 ? "#f85149" : p >= 60 ? "#d29922" : "#3fb950");
const dotColor = (t) =>
  t === "live" ? "#3fb950" : t === "error" ? "#f85149" : "#6e7681";

// Open the native platform picker (a real macOS list dialog).
// Falls back to Terminal only if the picker binary isn't installed.
const openPicker = () => {
  const exec = typeof run === "function" ? run : window.run;
  if (typeof exec !== "function") return;
  exec(
    "PATH=$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH; " +
      "command -v aiquota-picker >/dev/null && aiquota-picker || " +
      "osascript -e 'tell application \"Terminal\" to do script \"aiquota link\"' " +
      "-e 'tell application \"Terminal\" to activate'"
  );
};

const runCmd = (cmd) => {
  const exec = typeof run === "function" ? run : window.run;
  if (typeof exec !== "function") return;
  exec(`PATH=$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH; ${cmd}`);
};

export const render = ({ output }) => {
  let data = {};
  try {
    data = JSON.parse(output || "{}");
  } catch (e) {
    return <div className="empty">aiquota: bad output</div>;
  }

  const services = data.services || [];
  if (!services.length) {
    return (
      <div>
        <h1>AI Quota</h1>
        <div className="empty">No accounts added yet</div>
        <div className="cta">
          <button onClick={openPicker}>
            ＋ Add an AI account
          </button>
        </div>
      </div>
    );
  }

  const stamp = data.generated_at
    ? new Date(data.generated_at * 1000).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "";

  return (
    <div>
      <h1>AI Quota</h1>
      <div className="stamp">updated {stamp}</div>

      {services.map((s, i) => {
        const ex = s.extra || {};
        const wins = s.windows || [];
        return (
          <div className="svc" key={i}>
            <div className="sh">
              <div className="sn">
                <span className="dot" style={{ color: dotColor(s.tier) }}>
                  ●
                </span>
                {s.service}
              </div>
              {s.plan && s.plan !== s.service ? (
                <span className="plan">{s.plan}</span>
              ) : null}
            </div>

            {wins.map((w, j) => {
              const p = Math.max(0, Math.min(100, Number(w.used_pct)));
              return (
                <div className="row" key={j}>
                  <div className="lbl">
                    <span>{w.label}</span>
                    <span className="pct">
                      {p.toFixed(0)}%
                      {w.resets_at ? (
                        <span className="reset">{w.resets_at}</span>
                      ) : null}
                    </span>
                  </div>
                  <div className="track">
                    <div
                      className="fill"
                      style={{ width: p + "%", background: tone(p) }}
                    />
                  </div>
                </div>
              );
            })}

            {!wins.length && (s.note || s.error) ? (
              <div className={s.error ? "err" : "meta"}>
                {s.error || s.note}
              </div>
            ) : null}

            {s.tier === "unconfigured" ? (
              <button
                className="link-btn"
                onClick={openPicker}
              >
                Link this account →
              </button>
            ) : null}

            {ex.credits !== undefined || ex.renews_in_days !== undefined ? (
              <div className="meta">
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

      <div className="cta">
        <button onClick={openPicker}>
          ＋ Add account
        </button>
        <button
          className="ghost"
          onClick={() => runCmd("aiquota -r >/dev/null 2>&1")}
        >
          Refresh
        </button>
      </div>
    </div>
  );
};
