"""OpenCV reads a screenshot of the Studio's 2D canvas (the e2e tests call
it): what you see is what the core planned, so OpenCV must find the ids.

    python -I -B e2e/detect.py <png> <DICT_NAME> [x0 y0 x1 y1]

Prints JSON: {"ids": [...], "n": count}. The crop (screen px) is optional.
The canvas is dark around the tags, so the image is padded with white."""
import json
import sys

import cv2
import numpy as np


def main(argv):
    path, dictionary = argv[0], argv[1]
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
