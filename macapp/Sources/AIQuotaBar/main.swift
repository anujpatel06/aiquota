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

    var id: String { name }

    enum CodingKeys: String, CodingKey {
        case name, service, plan, tier, windows, note, error, cost, confidence
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
            var args = ["status", "--json"]
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

// MARK: - UI

struct RowView: View {
    let s: Service

    private var tint: Color {
        guard let pct = s.headline?.usedPct else { return .secondary }
        if pct >= 85 { return .red }
        if pct >= 60 { return .orange }
        return .primary
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack {
                Text(s.service).font(.system(size: 13, weight: .medium))
                Spacer()
                if let h = s.headline {
                    Text("\(Int(h.usedPct.rounded()))%")
                        .font(.system(size: 13, weight: .semibold,
                                      design: .rounded))
                        .foregroundStyle(tint)
                }
            }
            ForEach(s.windows, id: \.key) { w in
                HStack(spacing: 6) {
                    Text(w.label)
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                        .frame(width: 78, alignment: .leading)
                    ProgressView(value: min(w.usedPct, 100) / 100)
                        .progressViewStyle(.linear)
                        .frame(height: 3)
                    if !w.resetsAt.isEmpty {
                        Text(w.resetsAt)
                            .font(.system(size: 10))
                            .foregroundStyle(.tertiary)
                    }
                }
            }
            if let c = s.cost?.human, !c.isEmpty {
                Text(c).font(.system(size: 11)).foregroundStyle(.secondary)
            }
            if let e = s.error {
                Text(e).font(.system(size: 11)).foregroundStyle(.red)
                if let hint = s.failureHint, !hint.isEmpty {
                    Text(hint).font(.system(size: 10))
                        .foregroundStyle(.tertiary)
                }
            }
        }
        .padding(.vertical, 4)
    }
}

struct MenuView: View {
    @ObservedObject var model: Model

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            if let e = model.lastError {
                Text(e).font(.system(size: 12)).foregroundStyle(.red)
                    .padding(8)
            } else if model.services.isEmpty {
                Text("No accounts linked yet")
                    .font(.system(size: 12)).foregroundStyle(.secondary)
                    .padding(8)
            } else {
                ForEach(model.services) { s in
                    RowView(s: s).padding(.horizontal, 10)
                    Divider().opacity(0.4)
                }
            }

            Divider()
            Button("Add an account…") { model.runCLI(["link"]) }
                .keyboardShortcut("n")
            Button(model.loading ? "Refreshing…" : "Refresh now") {
                model.refresh(force: true)
            }
            .keyboardShortcut("r")
            .disabled(model.loading)
            Divider()
            Button("Quit") { NSApplication.shared.terminate(nil) }
                .keyboardShortcut("q")
        }
        .frame(width: 320)
    }
}

@main
struct AIQuotaBarApp: App {
    @StateObject private var model = Model()

    // Kick the first read off the app's own init rather than a view's
    // .onAppear: a MenuBarExtra label is not guaranteed to appear (or to run
    // onAppear) before the user clicks it, which left the title blank.
    init() {
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
