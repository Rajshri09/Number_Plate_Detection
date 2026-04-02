import cv2
import numpy as np
import urllib.request
import os

_yolo = None

def _load_yolo():
    global _yolo
    model_path = "license_plate_detector.pt"
    if not os.path.exists(model_path):
        print("[detector] Downloading license plate model...")
        try:
            url = "https://github.com/Muhammad-Zeerak-Khan/Automatic-License-Plate-Recognition-using-YOLOv8/raw/main/license_plate_detector.pt"
            urllib.request.urlretrieve(url, model_path)
            print("[detector] Model downloaded.")
        except Exception as e:
            print(f"[detector] Download failed: {e}")
            return
    try:
        from ultralytics import YOLO
        _yolo = YOLO(model_path)
        print("[detector] License plate YOLO model loaded")
    except Exception as e:
        print(f"[detector] YOLO load error: {e}")

_load_yolo()

cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_russian_plate_number.xml"
)

def _contour_detect(frame):
    gray    = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.bilateralFilter(gray, 11, 17, 17)
    edges   = cv2.Canny(blurred, 30, 200)
    contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    contours     = sorted(contours, key=cv2.contourArea, reverse=True)[:30]
    boxes = []
    for c in contours:
        peri   = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.018 * peri, True)
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(approx)
            ratio = w / float(h)
            area  = w * h
            if 1.5 < ratio < 6.0 and area > 1500:
                boxes.append((x, y, w, h))
    return boxes

def detect_plates(frame):
    annotated = frame.copy()
    crops     = []
    if _yolo:
        results = _yolo.predict(frame, verbose=False, conf=0.3)[0]
        boxes   = results.boxes
        if len(boxes) > 0:
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                pad = 4
                x1 = max(0, x1 - pad); y1 = max(0, y1 - pad)
                x2 = min(frame.shape[1], x2 + pad); y2 = min(frame.shape[0], y2 + pad)
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(annotated, f"{conf:.2f}", (x1, y1-6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
                crops.append(frame[y1:y2, x1:x2])
        else:
            for (x, y, w, h) in _contour_detect(frame):
                cv2.rectangle(annotated, (x, y), (x+w, y+h), (0,200,255), 2)
                crops.append(frame[y:y+h, x:x+w])
    else:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        haar_plates = cascade.detectMultiScale(gray, 1.1, 5, minSize=(60,20))
        haar_found  = list(haar_plates) if len(haar_plates) > 0 else []
        if haar_found:
            for (x, y, w, h) in haar_found:
                cv2.rectangle(annotated, (x, y), (x+w, y+h), (0,255,0), 2)
                crops.append(frame[y:y+h, x:x+w])
        else:
            for (x, y, w, h) in _contour_detect(frame):
                cv2.rectangle(annotated, (x, y), (x+w, y+h), (0,200,255), 2)
                crops.append(frame[y:y+h, x:x+w])
    return annotated, crops
