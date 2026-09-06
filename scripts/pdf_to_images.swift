// pdf_to_images.swift — macOS 零依赖 PDF 逐页转 PNG（CoreGraphics + ImageIO）。
// 用法: swift pdf_to_images.swift <input.pdf> <outdir> [targetWidth=1600]
// 输出: <outdir>/page-001.png, page-002.png ...
// 适合把含公式/图表/扫描件的论文交给视觉模型（read_image）逐页阅读。
import Foundation
import CoreGraphics
import ImageIO
import UniformTypeIdentifiers

guard CommandLine.arguments.count >= 3 else {
    FileHandle.standardError.write("usage: swift pdf_to_images.swift <input.pdf> <outdir> [targetWidth]\n".data(using: .utf8)!)
    exit(2)
}
let pdfPath = CommandLine.arguments[1]
let outDir  = CommandLine.arguments[2]
let targetWidth = CommandLine.arguments.count >= 4 ? Double(CommandLine.arguments[3]) ?? 1600 : 1600

let url = URL(fileURLWithPath: pdfPath)
guard let doc = CGPDFDocument(url as CFURL) else {
    FileHandle.standardError.write("cannot open pdf\n".data(using: .utf8)!)
    exit(1)
}
try? FileManager.default.createDirectory(atPath: outDir, withIntermediateDirectories: true)

let pageCount = doc.numberOfPages
let colorSpace = CGColorSpaceCreateDeviceRGB()

for i in 1...pageCount {
    guard let page = doc.page(at: i) else { continue }
    let box = page.getBoxRect(.mediaBox)
    let scale = targetWidth / box.width
    let w = Int(box.width * scale)
    let h = Int(box.height * scale)
    guard let ctx = CGContext(
        data: nil, width: w, height: h,
        bitsPerComponent: 8, bytesPerRow: 0, space: colorSpace,
        bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
    ) else { continue }
    ctx.setFillColor(CGColor(gray: 1, alpha: 1))
    ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.scaleBy(x: scale, y: scale)
    ctx.drawPDFPage(page)
    guard let image = ctx.makeImage() else { continue }
    let file = String(format: "%@/page-%03d.png", outDir, i)
    guard let dest = CGImageDestinationCreateWithURL(URL(fileURLWithPath: file) as CFURL, UTType.png.identifier as CFString, 1, nil) else { continue }
    CGImageDestinationAddImage(dest, image, nil)
    CGImageDestinationFinalize(dest)
    print("wrote \(file) (\(w)x\(h))")
}
print("pages: \(pageCount)")
