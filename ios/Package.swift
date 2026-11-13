// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "NanoANEBridge",
    platforms: [
        .iOS(.v18),
        .macOS(.v15),
    ],
    products: [
        .library(name: "NanoANEBridge", targets: ["NanoANEBridge"]),
    ],
    dependencies: [
        .package(url: "https://github.com/john-rocky/CoreML-LLM", from: "1.9.0"),
        .package(url: "https://github.com/huggingface/swift-transformers", from: "1.0.0"),
    ],
    targets: [
        .target(
            name: "NanoANEBridge",
            dependencies: [
                .product(name: "CoreMLLLM", package: "CoreML-LLM"),
                .product(name: "Tokenizers", package: "swift-transformers"),
            ],
            swiftSettings: [.swiftLanguageMode(.v5)]
        ),
    ]
)
