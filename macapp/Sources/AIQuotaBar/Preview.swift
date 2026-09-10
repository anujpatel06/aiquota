// Render MenuView to a PNG without needing anyone to click a menu bar item.
// Verifying UI by driving the real menu bar proved unreliable (coordinates
// shift, other windows steal the click), and "it built" is not evidence that
// it looks right.
import AppKit
import SwiftUI

@MainActor
func renderPanel(to path: String) {
    let model = Model()
    model.services = [
        Service(name: "claude", service: "Claude", plan: "Max",
                tier: "live",
                windows: [
                    Window(key: "five_hour", label: "5-hour session",
                           usedPct: 83, resetsAt: "resets 01:50"),
                    Window(key: "seven_day", label: "Weekly (all)",
                           usedPct: 27, resetsAt: "resets Mon 00:30"),
                ],
                note: "", error: nil, cost: nil,
                confidence: "percent_only", failureHint: nil, logo: nil),
        Service(name: "chatgpt", service: "ChatGPT", plan: "Plus",
                tier: "live",
                windows: [
                    Window(key: "primary", label: "5-hour", usedPct: 12,
                           resetsAt: "resets 03:10"),
                    Window(key: "secondary", label: "7-day", usedPct: 91,
                           resetsAt: "resets Fri"),
                ],
                note: "", error: nil, cost: nil,
                confidence: "percent_only", failureHint: nil, logo: nil),
        Service(name: "deepseek", service: "DeepSeek", plan: "",
                tier: "live", windows: [],
                note: "$12.34 left", error: nil,
                cost: Cost(human: "$12.34 left"),
                confidence: "exact", failureHint: nil, logo: nil),
        Service(name: "cursor", service: "Cursor", plan: "",
                tier: "error", windows: [],
                note: "", error: "Cursor rejected the credential",
                cost: nil, confidence: "unknown",
                failureHint: "The key or session expired — sign in again.",
                logo: nil),
    ]

    let view = MenuView(model: model)
        // The real panel sits on macOS menu material; approximate it so the
        // exported image reads like what ships.
        .background(Color(nsColor: .windowBackgroundColor))

    let renderer = ImageRenderer(content: view)
    renderer.scale = 2
    guard let img = renderer.nsImage,
          let tiff = img.tiffRepresentation,
          let rep = NSBitmapImageRep(data: tiff),
          let png = rep.representation(using: .png, properties: [:])
    else {
        print("render failed")
        return
    }
    try? png.write(to: URL(fileURLWithPath: path))
    print("wrote \(path) — \(Int(img.size.width))x\(Int(img.size.height))pt")
}
