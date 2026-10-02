// What macOS Vision reads in each image: one JSON object per image per line of output,
// {"path": "...", "lines": [{"text": "...", "box": [x0, y0, x1, y1]}]}, boxes in pixels from the top left.
//
//     swiftc -O tools/ocr.swift -o .cache/ocr && .cache/ocr IMAGE...
//
// tools/imprints.py compiles and runs it.
import Foundation
import ImageIO
import Vision

for path in CommandLine.arguments.dropFirst() {
    var lines: [[String: Any]] = []
    if let source = CGImageSourceCreateWithURL(URL(fileURLWithPath: path) as CFURL, nil),
       let image = CGImageSourceCreateImageAtIndex(source, 0, nil) {
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false
        try? VNImageRequestHandler(cgImage: image).perform([request])
        let w = Double(image.width), h = Double(image.height)
        for observation in request.results ?? [] {
            guard let text = observation.topCandidates(1).first?.string else { continue }
            let b = observation.boundingBox  // normalised, origin bottom left
            lines.append(["text": text,
                          "box": [Int(b.minX * w), Int((1 - b.maxY) * h), Int(b.maxX * w), Int((1 - b.minY) * h)]])
        }
    }
    let data = try! JSONSerialization.data(withJSONObject: ["path": path, "lines": lines])
    print(String(data: data, encoding: .utf8)!)
}
