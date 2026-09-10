// AIQuotaBar — a native menu bar app, so installing aiquota does not also
// mean installing SwiftBar or Übersicht first.
//
// Deliberately thin. All provider logic, credential handling and honesty
// rules live in the Python CLI; this process only renders what
// `aiquota status --json` returns. That keeps one implementation of the rules
// that matter rather than two that drift.
//
// Build:  swift build -c release
// Run:    .build/release/AIQuotaBar

import AppKit
import Foundation
import SwiftUI

// MARK: - Model

struct Window: Decodable {
    let key: String
    let label: String
    let usedPct: Double
    let resetsAt: String

    enum CodingKeys: String, CodingKey {
        case key, label
        case usedPct = "used_pct"
        case resetsAt = "resets_at"
    }
}

struct Cost: Decodable {
    let human: String?
}

struct Service: Decodable, Identifiable {
    let name: String
    let service: String
    let plan: String
    let tier: String
    let windows: [Window]
    let note: String
    let error: String?
    let cost: Cost?
    let confidence: String?
    let failureHint: String?
    /// base64 data URI, present when the CLI is called with --logos.
    let logo: String?

    var id: String { name }

    enum CodingKeys: String, CodingKey {
        case name, service, plan, tier, windows, note, error, cost, confidence
        case logo
        case failureHint = "failure_hint"
    }

    /// The number shown on the row. Highest window wins, because the one
    /// closest to its limit is the one about to bite.
    var headline: Window? {
        windows.max(by: { $0.usedPct < $1.usedPct })
    }
}

struct Snapshot: Decodable {
    let services: [Service]
    let generatedAt: Double

    enum CodingKeys: String, CodingKey {
        case services
        case generatedAt = "generated_at"
    }
}

// MARK: - Reading from the CLI

@MainActor
final class Model: ObservableObject {
    @Published var services: [Service] = []
    @Published var lastError: String?
    @Published var loading = false

    private var timer: Timer?

    /// Find the CLI wherever the user installed it. Homebrew on Apple silicon
    /// and Intel differ, and `uv tool install` uses a third location.
    static func cliPath() -> String? {
        let candidates = [
            "/opt/homebrew/bin/aiquota",
            "/usr/local/bin/aiquota",
            NSHomeDirectory() + "/.local/bin/aiquota",
        ]
        for p in candidates where FileManager.default.isExecutableFile(atPath: p) {
            return p
        }
        // Fall back to asking the shell, in case of an unusual install.
        let which = Process()
        which.executableURL = URL(fileURLWithPath: "/bin/sh")
        which.arguments = ["-lc", "command -v aiquota"]
        let pipe = Pipe()
        which.standardOutput = pipe
        try? which.run()
        which.waitUntilExit()
        let out = String(data: pipe.fileHandleForReading.readDataToEndOfFile(),
                         encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        return out.isEmpty ? nil : out
    }

    func refresh(force: Bool = false) {
        guard !loading else { return }
        guard let cli = Self.cliPath() else {
            lastError = "aiquota not found — brew install anujpatel06/aiquota/aiquota"
            return
        }
        loading = true
        Task.detached(priority: .userInitiated) {
            // --logos so rows show the real platform icons the widget shows.
            var args = ["status", "--json", "--logos"]
            if force { args.append("-r") }

            // Compute the whole outcome before hopping to the main actor:
            // capturing mutable vars across that boundary is an error under
            // Swift 6 strict concurrency.
            let outcome: Result<Snapshot, Error> = {
                let proc = Process()
                proc.executableURL = URL(fileURLWithPath: cli)
                proc.arguments = args
                let out = Pipe()
                proc.standardOutput = out
                proc.standardError = Pipe()
                do {
                    try proc.run()
                    let data = out.fileHandleForReading.readDataToEndOfFile()
                    proc.waitUntilExit()
                    return .success(try JSONDecoder().decode(Snapshot.self,
                                                             from: data))
                } catch {
                    return .failure(error)
                }
            }()

            await MainActor.run {
                self.loading = false
                switch outcome {
                case .success(let s):
                    self.services = s.services
                    self.lastError = nil
                case .failure(let e):
                    self.lastError =
                        "could not read aiquota: \(e.localizedDescription)"
                }
            }
        }
    }

    /// Ask the CLI how often to poll rather than hard-coding an interval —
    /// the adaptive policy lives in one place, in Python.
    func scheduleNextRefresh() {
        timer?.invalidate()
        let delay = Self.refreshDelaySeconds()
        timer = Timer.scheduledTimer(withTimeInterval: delay, repeats: false) { _ in
            Task { @MainActor in
                self.refresh()
                self.scheduleNextRefresh()
            }
        }
    }

    static func refreshDelaySeconds() -> TimeInterval {
        guard let cli = cliPath() else { return 900 }
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: cli)
        proc.arguments = ["refresh", "--json"]
        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = Pipe()
        do {
            try proc.run()
            let d = pipe.fileHandleForReading.readDataToEndOfFile()
            proc.waitUntilExit()
            if let obj = try JSONSerialization.jsonObject(with: d) as? [String: Any],
               let secs = obj["delay_seconds"] as? Double {
                return secs
            }
        } catch { }
        return 900
    }

    func runCLI(_ args: [String]) {
        guard let cli = Self.cliPath() else { return }
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: cli)
        proc.arguments = args
        try? proc.run()
    }
}

// MARK: - Menu bar title

/// The worst reading across every linked account, because that is the number
/// that decides whether you can keep working.
func menuTitle(_ services: [Service]) -> String {
    let live = services.filter { $0.tier == "live" }
    guard let worst = live.compactMap({ $0.headline }).max(by: { $0.usedPct < $1.usedPct })
    else { return "—" }
    return "\(Int(worst.usedPct.rounded()))%"
}

// MARK: - Design
//
// These values are lifted from the Übersicht widget's stylesheet so the two
// surfaces are the same product rather than two apps that happen to share a
// name. Where the widget says `rgba(255,255,255,0.45)`, so does this.

enum D {
    // Apple system colors, dark-mode variants — same constants as the widget.
    static let red = Color(red: 1.0, green: 0.27, blue: 0.23)        // #FF453A
    static let gray = Color(red: 0.56, green: 0.56, blue: 0.58)      // #8E8E93
    static let blue = Color(red: 0.04, green: 0.52, blue: 1.0)       // #0A84FF

    // Primary text / meter fill. The widget deliberately keeps meters white:
    // "a wall of green reads as decoration and stops meaning anything."
    static let primary = Color.primary.opacity(0.92)
    static let secondary = Color.primary.opacity(0.45)
    static let tertiary = Color.primary.opacity(0.38)
    static let hairline = Color.primary.opacity(0.12)
    static let track = Color.primary.opacity(0.14)
    static let tile = Color.primary.opacity(0.10)

    static let cardWidth: CGFloat = 340       // widget is 340px
    static let radius: CGFloat = 24
    static let pad: CGFloat = 16

    /// Meter colour. Colour is reserved for the one case worth interrupting
    /// you: a window that is nearly spent. Matches the widget's `tone()`.
    static func tone(_ pct: Double) -> Color { pct >= 85 ? red : primary }

    /// Live/error dot, matching the widget's `dotColor()`.
    static func dot(_ tier: String) -> Color {
        switch tier {
        case "error": return red
        case "live": return primary
        default: return gray
        }
    }
}

// MARK: - UI

/// One quota window: label, percentage, reset time, capsule track.
struct MeterView: View {
    let w: Window

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text(w.label)
                    .font(.system(size: 11))
                    .foregroundStyle(D.secondary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                // Per-window percentage. The widget had a bug where the reset
                // time replaced this; don't reintroduce it here.
                Text("\(Int(w.usedPct.rounded()))%")
                    .font(.system(size: 11, weight: .semibold))
                    .monospacedDigit()
                    .foregroundStyle(D.tone(w.usedPct))
                if !w.resetsAt.isEmpty {
                    Text(w.resetsAt)
                        .font(.system(size: 11))
                        .monospacedDigit()
                        .foregroundStyle(D.tertiary)
                }
            }
            // Capsule track, like a macOS progress view.
            GeometryReader { geo in
                ZStack(alignment: .leading) {
                    Capsule().fill(D.track)
                    Capsule()
                        .fill(D.tone(w.usedPct))
                        .frame(width: max(0, min(w.usedPct, 100) / 100 * geo.size.width))
                }
            }
            .frame(height: 6)
        }
        .padding(.top, 7)
    }
}

/// A service card: logo tile, status dot, name, plan, meters, cost.
struct RowView: View {
    let s: Service

    /// The real platform logo, decoded from the base64 the CLI already
    /// attaches (`attach_logos`). The widget shows these; a monogram here
    /// would make the two surfaces look like different products.
    private var logo: NSImage? {
        guard var b64 = s.logo else { return nil }
        if let comma = b64.firstIndex(of: ",") {      // strip data: URL prefix
            b64 = String(b64[b64.index(after: comma)...])
        }
        guard let data = Data(base64Encoded: b64) else { return nil }
        return NSImage(data: data)
    }

    private var monogram: String { String(s.service.prefix(1)).uppercased() }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 8) {
                // Logo tile with the status dot pinned inside its lower-left
                // corner. Using an alignmentGuide rather than a raw offset so
                // the dot tracks the tile instead of a hard-coded number.
                RoundedRectangle(cornerRadius: 5, style: .continuous)
                    .fill(D.tile)
                    .frame(width: 18, height: 18)
                    .overlay {
                        if let img = logo {
                            Image(nsImage: img).resizable().scaledToFit().padding(2)
                        } else {
                            Text(monogram)
                                .font(.system(size: 10, weight: .bold))
                                .foregroundStyle(D.primary.opacity(0.6))
                        }
                    }
                    // Status dot at the tile's bottom-left, half on and half
                    // off the artwork — the widget's placement. Sitting fully
                    // inside covered the logo it is meant to annotate.
                    .overlay(alignment: .bottomLeading) {
                        Circle()
                            .fill(D.dot(s.tier))
                            .frame(width: 7, height: 7)
                            .overlay(Circle()
                                .stroke(Color(nsColor: .windowBackgroundColor),
                                        lineWidth: 1.5))
                            // Straddles the tile edge: enough overlap to read as
                            // attached to the icon, enough clearance to leave
                            // the artwork legible.
                            .offset(x: -1, y: 1)
                    }
                Text(s.service)
                    .font(.system(size: 13, weight: .semibold))
                if !s.plan.isEmpty {
                    Text(s.plan)
                        .font(.system(size: 11))
                        .foregroundStyle(D.secondary)
                }
                Spacer(minLength: 0)
            }

            ForEach(s.windows, id: \.key) { MeterView(w: $0) }

            if let c = s.cost?.human, !c.isEmpty {
                Text(c)
                    .font(.system(size: 11.5))
                    .monospacedDigit()
                    .foregroundStyle(D.primary.opacity(0.82))
                    .padding(.top, 3)
            }
            if let e = s.error {
                Text(e)
                    .font(.system(size: 11))
                    .foregroundStyle(D.red)
                    .padding(.top, 2)
                if let hint = s.failureHint, !hint.isEmpty {
                    Text(hint)
                        .font(.system(size: 10.5))
                        .foregroundStyle(D.tertiary)
                        .fixedSize(horizontal: false, vertical: true)
                }
            } else if s.windows.isEmpty && !s.note.isEmpty
                        && s.cost?.human != s.note {
                Text(s.note)
                    .font(.system(size: 11))
                    .foregroundStyle(D.secondary)
                    .padding(.top, 2)
            }
        }
        .padding(.vertical, 10)
    }
}

struct MenuView: View {
    @ObservedObject var model: Model

    private var stamp: String {
        let f = DateFormatter()
        f.dateFormat = "HH:mm"
        return f.string(from: Date())
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            // ---- header: blue glyph, title, timestamp ----
            HStack(spacing: 7) {
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .fill(LinearGradient(colors: [D.blue,
                                                  Color(red: 0, green: 0.38, blue: 0.87)],
                                         startPoint: .top, endPoint: .bottom))
                    .frame(width: 20, height: 20)
                    .overlay(Text("◐").font(.system(size: 11, weight: .bold))
                        .foregroundStyle(.white))
                Text("AI Quota").font(.system(size: 13, weight: .semibold))
                Spacer()
                Text(stamp)
                    .font(.system(size: 11)).monospacedDigit()
                    .foregroundStyle(D.secondary)
            }
            .padding(.bottom, 14)

            if let e = model.lastError {
                Text(e).font(.system(size: 12)).foregroundStyle(D.red)
                    .fixedSize(horizontal: false, vertical: true)
            } else if model.services.isEmpty {
                Text("No accounts linked yet")
                    .font(.system(size: 12))
                    .foregroundStyle(D.secondary)
                    .padding(.vertical, 6)
            } else {
                ForEach(Array(model.services.enumerated()), id: \.element.id) { i, s in
                    if i > 0 {
                        Rectangle().fill(D.hairline).frame(height: 0.5)
                    }
                    RowView(s: s)
                }
            }

            // ---- footer ----
            Rectangle().fill(D.hairline).frame(height: 0.5)
                .padding(.top, 12)
            HStack(spacing: 6) {
                Button("＋ Add an AI account") { model.runCLI(["link"]) }
                    .buttonStyle(PillButton(primary: true))
                Button(model.loading ? "Refreshing…" : "Refresh") {
                    model.refresh(force: true)
                }
                .buttonStyle(PillButton(primary: false))
                .disabled(model.loading)
                Spacer()
                Button("Quit") { NSApplication.shared.terminate(nil) }
                    .buttonStyle(PillButton(primary: false))
            }
            .padding(.top, 12)
        }
        .padding(D.pad)
        .frame(width: D.cardWidth)
    }
}

/// The widget's button: 8pt radius, translucent grey, blue when primary.
struct PillButton: ButtonStyle {
    let primary: Bool

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 12, weight: .medium))
            .foregroundStyle(primary ? Color.white : Color.primary.opacity(0.85))
            .padding(.horizontal, 12)
            .padding(.vertical, 5)
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(primary ? D.blue
                          : Color(red: 0.47, green: 0.47, blue: 0.5).opacity(0.36))
            )
            .scaleEffect(configuration.isPressed ? 0.97 : 1)
            .animation(.easeOut(duration: 0.06), value: configuration.isPressed)
    }
}

@main
struct AIQuotaBarApp: App {
    @StateObject private var model = Model()

    // Kick the first read off the app's own init rather than a view's
    // .onAppear: a MenuBarExtra label is not guaranteed to appear (or to run
    // onAppear) before the user clicks it, which left the title blank.
    init() {
        // `AIQuotaBar --render-preview <path>` exports the panel as a PNG so
        // the design can be reviewed without clicking a menu bar item.
        let args = CommandLine.arguments
        if let i = args.firstIndex(of: "--render-preview"), i + 1 < args.count {
            let out = args[i + 1]
            DispatchQueue.main.async {
                renderPanel(to: out)
                exit(0)
            }
        }
        let m = Model()
        _model = StateObject(wrappedValue: m)
        Task { @MainActor in
            m.refresh()
            m.scheduleNextRefresh()
        }
    }

    var body: some Scene {
        MenuBarExtra {
            MenuView(model: model)
        } label: {
            // An icon, not just a number. A bare "67%" sitting among a dozen
            // system icons is indistinguishable from a battery reading — the
            // first build shipped without one and was genuinely unfindable.
            // The gauge fills as quota is consumed, so the glyph itself
            // carries the reading even at a glance.
            HStack(spacing: 3) {
                Image(systemName: gaugeSymbol(model.services))
                Text(model.services.isEmpty && model.lastError == nil
                     ? "…" : menuTitle(model.services))
            }
        }
        .menuBarExtraStyle(.window)
    }
}

/// Pick a gauge glyph that reflects how full the worst window is, so the icon
/// is informative before you read the number.
func gaugeSymbol(_ services: [Service]) -> String {
    let live = services.filter { $0.tier == "live" }
    guard let worst = live.compactMap({ $0.headline })
        .max(by: { $0.usedPct < $1.usedPct })
    else { return "gauge.with.dots.needle.bottom.0percent" }
    switch worst.usedPct {
    case ..<34:  return "gauge.with.dots.needle.bottom.0percent"
    case ..<67:  return "gauge.with.dots.needle.bottom.50percent"
    default:     return "gauge.with.dots.needle.bottom.100percent"
    }
}
