"""OpenCV reads a screenshot of the Studio's 2D canvas (the e2e tests call
it): what you see is what the core planned, so OpenCV must find the ids.

    python -I -B e2e/detect.py <png | pdf> <DICT_NAME> [x0 y0 x1 y1]

Prints JSON: {"ids": [...], "n": count}. The crop (screen px) is optional.
The canvas is dark around the tags, so the image is padded with white. A
PDF (the sticker sheet) is rasterised by pdfium at 300 dpi, every page read."""
import json
import sys

import cv2
import numpy as np


def pdf_pages(path):
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(path)
    for i in range(len(doc)):
        img = np.asarray(doc[i].render(scale=300 / 72.0, grayscale=True).to_numpy())
        if img.ndim == 3:
            img = img[:, :, 0] if img.shape[2] == 1 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        yield np.ascontiguousarray(img)


def main(argv):
    path, dictionary = argv[0], argv[1]
    if path.lower().endswith(".pdf"):
        d = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dictionary))
        det = cv2.aruco.ArucoDetector(d, cv2.aruco.DetectorParameters())
        out = []
        for img in pdf_pages(path):
            _c, ids, _r = det.detectMarkers(img)
            out += [int(i) for i in (ids.flatten() if ids is not None else [])]
        out = sorted(out)
        print(json.dumps({"ids": out, "n": len(out)}))
        return 0
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        print(json.dumps({"error": f"cannot read {path}"}))
        return 2
    if len(argv) >= 6:
        x0, y0, x1, y1 = (int(round(float(v))) for v in argv[2:6])
        img = img[max(0, y0):y1, max(0, x0):x1]
    img = cv2.copyMakeBorder(img, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
    d = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, dictionary))
    params = cv2.aruco.DetectorParameters()
    det = cv2.aruco.ArucoDetector(d, params)
    _corners, ids, _rej = det.detectMarkers(img)
    out = sorted(int(i) for i in (ids.flatten() if ids is not None else np.array([])))
    print(json.dumps({"ids": out, "n": len(out)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
