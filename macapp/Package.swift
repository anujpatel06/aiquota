// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "AIQuotaBar",
    platforms: [.macOS(.v13)],   // MenuBarExtra needs 13+
    targets: [
        .executableTarget(
            name: "AIQuotaBar",
            path: "Sources/AIQuotaBar"
        )
    ]
)
