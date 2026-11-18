// Detects face rectangles in derived previews. Does NOT identify people.
import Foundation
import Vision
import ImageIO

struct Face: Codable {
    let x: Double
    let y: Double
    let width: Double
    let height: Double
    let confidence: Float
}
struct Result: Codable {
    let faces: [Face]
    let error: String?
}

let paths = Array(CommandLine.arguments.dropFirst())
var results: [Result] = []
for path in paths {
    do {
        let request = VNDetectFaceRectanglesRequest()
        let handler = VNImageRequestHandler(url: URL(fileURLWithPath: path), options: [:])
        try handler.perform([request])
        let faces = (request.results ?? []).map { observation in
            let box = observation.boundingBox
            return Face(x: box.origin.x, y: box.origin.y, width: box.width, height: box.height,
                        confidence: observation.confidence)
        }
        results.append(Result(faces: faces, error: nil))
    } catch {
        results.append(Result(faces: [], error: "Rilevamento non disponibile"))
    }
}
let data = try JSONEncoder().encode(results)
FileHandle.standardOutput.write(data)
