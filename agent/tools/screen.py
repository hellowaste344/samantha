"""
tools/screen.py — Real-time screen analysis pipeline for Samantha.

Stack
─────
  Capture   : MSS  — cross-platform, low-latency frame grab (< 5 ms per frame)
  Processing: OpenCV — preprocessing, contour-based UI element detection
  Detection : YOLOv8 (ultralytics)  — object-level detection on screen content
              → Falls back to OpenCV contours if ultralytics is not installed
  OCR       : PaddleOCR (primary)   — fast, accurate, GPU-optional
              → Falls back to pytesseract if PaddleOCR is not installed

Activation
──────────
  This module is only imported and its models only loaded when the user
  explicitly asks Samantha to inspect the screen (READ_SCREEN / FIND_ELEMENT /
  CLICK_ELEMENT actions). Everything else is lazy-loaded and thread-safe.

All public methods return plain strings suitable for LLM consumption.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import config

# ── Data types ────────────────────────────────────────────────────────────────

@dataclass
class UIElement:
    label: str
    confidence: float
    x: int
    y: int
    w: int
    h: int
    source: str = "unknown"     # "yolo" | "contour"
    center: Tuple[int, int] = field(init=False)

    def __post_init__(self):
        self.center = (self.x + self.w // 2, self.y + self.h // 2)


@dataclass
class ScreenResult:
    monitor_idx: int
    width: int
    height: int
    ocr_text: str
    elements: List[UIElement]
    ocr_engine: str             # "paddle" | "tesseract" | "none"
    det_engine: str             # "yolo" | "contour" | "none"
    t_capture_ms: float
    t_ocr_ms: float
    t_det_ms: float

    # ── Prompt-ready summary ───────────────────────────────────────────────────
    def to_prompt_str(self) -> str:
        lines = [
            f"[Screen analysis — Monitor {self.monitor_idx},"
            f" {self.width}×{self.height}]"
        ]

        # OCR text
        if self.ocr_text.strip():
            lines.append("\n--- Visible text on screen ---")
            text = self.ocr_text.strip()
            if len(text) > 2500:
                text = text[:2500] + "… [truncated]"
            lines.append(text)
        else:
            lines.append("\n[No text detected on screen]")

        # Detected UI elements
        if self.elements:
            lines.append(
                f"\n--- UI elements detected ({self.det_engine},"
                f" {len(self.elements)} total) ---"
            )
            # Group by source
            yolo_els = [e for e in self.elements if e.source == "yolo"]
            cnt_els  = [e for e in self.elements if e.source == "contour"]

            if yolo_els:
                lines.append("  [Object detection]")
                for el in yolo_els[:15]:
                    lines.append(
                        f"    • {el.label} (conf={el.confidence:.0%})"
                        f" at ({el.center[0]}, {el.center[1]})"
                        f" size {el.w}×{el.h}"
                    )

            if cnt_els:
                lines.append("  [UI elements / contours]")
                for el in cnt_els[:20]:
                    tag = f'"{el.label}"' if el.label and el.label != "ui_element" else ""
                    lines.append(
                        f"    • element{tag}"
                        f" at ({el.center[0]}, {el.center[1]})"
                        f" size {el.w}×{el.h}"
                    )
        else:
            lines.append("\n[No UI elements detected]")

        lines.append(
            f"\n[Timings: capture={self.t_capture_ms:.0f} ms"
            f"  ocr={self.t_ocr_ms:.0f} ms"
            f"  detection={self.t_det_ms:.0f} ms]"
        )
        return "\n".join(lines)


# ── ScreenCapture ─────────────────────────────────────────────────────────────

class ScreenCapture:
    """
    Thread-safe screen analysis tool.

    All models (YOLO, PaddleOCR) are loaded lazily on the first call
    to analyze() so startup time is not affected.
    """

    def __init__(self):
        self._lock         = threading.Lock()

        # YOLO
        self._yolo         = None
        self._yolo_tried   = False

        # OCR
        self._paddle       = None
        self._paddle_tried = False

    # ══════════════════════════════════════════════════════════════════════════
    # Model loading
    # ══════════════════════════════════════════════════════════════════════════

    def _load_yolo(self):
        if self._yolo_tried:
            return
        self._yolo_tried = True
        try:
            from ultralytics import YOLO  # type: ignore
            model_path = getattr(config, "YOLO_MODEL_PATH", "yolov8n.pt")
            self._yolo = YOLO(model_path)
            if config.DEBUG:
                print(f"[Screen] YOLOv8 loaded: {model_path}")
        except ImportError:
            if config.DEBUG:
                print("[Screen] ultralytics not installed — using contour detection only.")
        except Exception as exc:
            if config.DEBUG:
                print(f"[Screen] YOLOv8 load error: {exc}")

    def _load_paddle(self):
        if self._paddle_tried:
            return
        self._paddle_tried = True
        try:
            from paddleocr import PaddleOCR  # type: ignore
            self._paddle = PaddleOCR(
                use_angle_cls = True,
                lang          = getattr(config, "OCR_LANGUAGE", "en"),
                use_gpu       = getattr(config, "WHISPER_DEVICE", "cpu") == "cuda",
                show_log      = False,
            )
            if config.DEBUG:
                print("[Screen] PaddleOCR loaded ✓")
        except ImportError:
            if config.DEBUG:
                print("[Screen] PaddleOCR not installed — will try Tesseract.")
        except Exception as exc:
            if config.DEBUG:
                print(f"[Screen] PaddleOCR load error: {exc}")

    # ══════════════════════════════════════════════════════════════════════════
    # Frame capture
    # ══════════════════════════════════════════════════════════════════════════

    def capture_frame(
        self,
        monitor_idx: int = 1,
        region: Optional[dict] = None,
    ):
        """
        Grab a screen frame via MSS.

        Parameters
        ----------
        monitor_idx : 1-based monitor index (1 = primary).
        region      : optional {"left": x, "top": y, "width": w, "height": h}
                      to crop to a sub-region.

        Returns (np.ndarray BGR, width, height) or raises RuntimeError.
        """
        try:
            import mss          # type: ignore
            import numpy as np
            import cv2          # type: ignore
        except ImportError as e:
            raise RuntimeError(
                f"Missing dependency: {e}.  "
                "Install: pip install mss opencv-python numpy"
            ) from e

        with mss.mss() as sct:
            monitors = sct.monitors           # index 0 = all monitors combined
            if monitor_idx >= len(monitors):
                monitor_idx = 1               # fallback to primary
            mon = monitors[monitor_idx]

            grab_area = region if region else mon
            shot      = sct.grab(grab_area)
            # MSS returns BGRA
            img_bgra = __import__("numpy").frombuffer(shot.raw, dtype="uint8").reshape(
                (shot.height, shot.width, 4)
            )
            img_bgr  = cv2.cvtColor(img_bgra, cv2.COLOR_BGRA2BGR)
            return img_bgr, shot.width, shot.height

    # ══════════════════════════════════════════════════════════════════════════
    # YOLOv8 detection
    # ══════════════════════════════════════════════════════════════════════════

    def _detect_yolo(self, img) -> List[UIElement]:
        """Run YOLOv8 inference and return detected objects as UIElements."""
        self._load_yolo()
        if self._yolo is None:
            return []
        try:
            import numpy as np
            results = self._yolo(img, verbose=False, conf=0.35)
            elements: List[UIElement] = []
            for r in results:
                for box in r.boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    conf   = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    label  = self._yolo.names.get(cls_id, str(cls_id))
                    elements.append(UIElement(
                        label=label, confidence=conf,
                        x=x1, y=y1, w=x2 - x1, h=y2 - y1,
                        source="yolo",
                    ))
            return elements
        except Exception as exc:
            if config.DEBUG:
                print(f"[Screen] YOLO inference error: {exc}")
            return []

    # ══════════════════════════════════════════════════════════════════════════
    # OpenCV contour detection  (catches buttons, inputs, panels, etc.)
    # ══════════════════════════════════════════════════════════════════════════

    def _detect_contours(self, img) -> List[UIElement]:
        """
        Detect rectangular UI elements (buttons, input fields, panels) using
        OpenCV edge detection + contour analysis.

        Heuristics:
          • Area between 400 px² and 30 % of screen
          • Aspect ratio 0.25–20  (excludes slivers and square blobs)
          • Minimum 20 × 8 pixels
        """
        try:
            import cv2
            import numpy as np
        except ImportError:
            return []

        h, w = img.shape[:2]
        gray    = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Bilateral filter preserves edges while reducing noise
        denoised = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)

        # Adaptive threshold to find element borders on any background colour
        thresh = cv2.adaptiveThreshold(
            denoised, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV,
            blockSize=15, C=4,
        )

        # Close small gaps so button borders are solid
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(
            closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        elements: List[UIElement] = []
        seen_rects: List[Tuple[int,int,int,int]] = []

        for cnt in sorted(contours, key=cv2.contourArea, reverse=True)[:80]:
            x, y, cw, ch = cv2.boundingRect(cnt)
            area   = cw * ch
            aspect = cw / max(ch, 1)

            if area < 400 or area > w * h * 0.30:
                continue
            if aspect < 0.25 or aspect > 20:
                continue
            if cw < 20 or ch < 8:
                continue

            # Deduplicate heavily overlapping rects
            overlap = False
            for (rx, ry, rw, rh) in seen_rects:
                ix = max(0, min(x + cw, rx + rw) - max(x, rx))
                iy = max(0, min(y + ch, ry + rh) - max(y, ry))
                if ix * iy > 0.6 * min(cw * ch, rw * rh):
                    overlap = True
                    break
            if overlap:
                continue
            seen_rects.append((x, y, cw, ch))

            # Quick OCR on region to get a label
            roi   = img[y: y + ch, x: x + cw]
            label = self._quick_ocr_region(roi) or "ui_element"

            elements.append(UIElement(
                label=label, confidence=0.65,
                x=x, y=y, w=cw, h=ch,
                source="contour",
            ))

        return elements

    # ══════════════════════════════════════════════════════════════════════════
    # OCR helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _ocr_paddle(self, img) -> str:
        """Full-image OCR with PaddleOCR. Returns newline-joined text blocks."""
        self._load_paddle()
        if self._paddle is None:
            return ""
        try:
            import numpy as np
            result = self._paddle.ocr(img, cls=True)
            if not result or not result[0]:
                return ""
            lines = []
            for block in result[0]:
                # block = [bounding_box, (text, confidence)]
                if isinstance(block, (list, tuple)) and len(block) >= 2:
                    text_info = block[1]
                    if isinstance(text_info, (list, tuple)) and len(text_info) >= 1:
                        text = str(text_info[0]).strip()
                        conf = float(text_info[1]) if len(text_info) > 1 else 1.0
                        if text and conf > 0.5:
                            lines.append(text)
            return "\n".join(lines)
        except Exception as exc:
            if config.DEBUG:
                print(f"[Screen] PaddleOCR inference error: {exc}")
            return ""

    def _ocr_tesseract(self, img) -> str:
        """Full-image OCR with Tesseract as fallback."""
        try:
            import pytesseract  # type: ignore
            import cv2
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Page-segmentation mode 3: fully automatic, no OSD
            text = pytesseract.image_to_string(
                gray,
                lang   = getattr(config, "OCR_LANGUAGE", "eng"),
                config = "--psm 3 --oem 3",
            )
            return text.strip()
        except ImportError:
            return ""
        except Exception as exc:
            if config.DEBUG:
                print(f"[Screen] Tesseract error: {exc}")
            return ""

    def _quick_ocr_region(self, roi) -> str:
        """
        Lightweight single-region OCR to label a contour element.
        Uses Tesseract line mode (faster than full page analysis).
        Falls back to PaddleOCR if Tesseract is unavailable.
        """
        try:
            import pytesseract
            import cv2
            import numpy as np
            if roi.size == 0:
                return ""
            # Scale up small ROIs for better accuracy
            h, w = roi.shape[:2]
            if h < 30:
                scale = max(2, 30 // h)
                roi   = cv2.resize(roi, (w * scale, h * scale),
                                   interpolation=cv2.INTER_LINEAR)
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            return pytesseract.image_to_string(
                gray, config="--psm 7 --oem 3"
            ).strip()
        except Exception:
            pass

        # Paddle fallback for single region
        if self._paddle is not None:
            try:
                result = self._paddle.ocr(roi, cls=False)
                if result and result[0]:
                    texts = [b[1][0] for b in result[0] if b and len(b) >= 2]
                    return " ".join(texts).strip()
            except Exception:
                pass
        return ""

    # ══════════════════════════════════════════════════════════════════════════
    # Public API
    # ══════════════════════════════════════════════════════════════════════════

    def analyze(
        self,
        monitor_idx: int = None,
        region: Optional[dict] = None,
    ) -> ScreenResult:
        """
        Full pipeline: capture → YOLO + contour detection → OCR → ScreenResult.

        Thread-safe (one analysis at a time).
        """
        monitor_idx = monitor_idx or getattr(config, "SCREEN_MONITOR", 1)

        with self._lock:
            # 1. Capture
            t0 = time.perf_counter()
            img, width, height = self.capture_frame(monitor_idx, region)
            t_capture = (time.perf_counter() - t0) * 1000

            # 2. Element detection  (YOLO + contours run concurrently)
            t1 = time.perf_counter()
            yolo_els    = self._detect_yolo(img)
            contour_els = self._detect_contours(img)
            all_elements = yolo_els + contour_els
            t_det = (time.perf_counter() - t1) * 1000

            # 3. OCR (PaddleOCR primary, Tesseract fallback)
            t2    = time.perf_counter()
            otext = ""
            ocr_engine = "none"

            otext = self._ocr_paddle(img)
            if otext:
                ocr_engine = "paddle"
            else:
                otext = self._ocr_tesseract(img)
                if otext:
                    ocr_engine = "tesseract"

            t_ocr = (time.perf_counter() - t2) * 1000

            det_engine = (
                "yolo+contour" if (yolo_els and contour_els) else
                "yolo"         if yolo_els else
                "contour"      if contour_els else
                "none"
            )

            return ScreenResult(
                monitor_idx  = monitor_idx,
                width        = width,
                height       = height,
                ocr_text     = otext,
                elements     = all_elements,
                ocr_engine   = ocr_engine,
                det_engine   = det_engine,
                t_capture_ms = t_capture,
                t_ocr_ms     = t_ocr,
                t_det_ms     = t_det,
            )

    def analyze_to_str(self, region=None) -> str:
        """Convenience wrapper — returns a prompt-ready string."""
        try:
            result = self.analyze(region=region)
            return result.to_prompt_str()
        except RuntimeError as exc:
            return f"Screen capture failed: {exc}"
        except Exception as exc:
            if config.DEBUG:
                import traceback
                traceback.print_exc()
            return f"Screen analysis error: {exc}"

    # ── Element search ────────────────────────────────────────────────────────

    def find_element(self, label: str) -> str:
        """
        Locate a UI element by its text label or object class.

        Searches OCR text regions and detected element labels.
        Returns a description string with coordinates, or a not-found message.
        """
        if not label:
            return "No label provided to search for."

        try:
            result = self.analyze()
        except Exception as exc:
            return f"Screen capture failed: {exc}"

        needle = label.lower().strip()

        # 1. Search detected elements by label
        matches: List[UIElement] = []
        for el in result.elements:
            if needle in el.label.lower():
                matches.append(el)

        if matches:
            descriptions = []
            for el in matches[:5]:
                descriptions.append(
                    f'"{el.label}" at screen position ({el.center[0]}, {el.center[1]})'
                    f" — size {el.w}×{el.h} [detected by {el.source}]"
                )
            return (
                f'Found {len(matches)} match(es) for "{label}":\n'
                + "\n".join(descriptions)
            )

        # 2. Search OCR text for the label
        if needle in result.ocr_text.lower():
            return (
                f'The text "{label}" appears somewhere on screen '
                f"(OCR detected it, but exact position not pinpointed). "
                f"Use find_element with a more specific UI label, or use "
                f"read_screen for the full text layout."
            )

        return (
            f'Could not find "{label}" on the screen. '
            f"The screen shows {len(result.elements)} elements total. "
            f"Use read_screen to see the full screen content."
        )

    # ── Click ─────────────────────────────────────────────────────────────────

    def click_element(self, label: str) -> str:
        """
        Find a UI element by label and click its center with PyAutoGUI.

        Requires a display to be available.
        """
        import sys, os as _os
        # Display check
        if sys.platform not in ("win32", "darwin"):
            if not (_os.environ.get("DISPLAY") or _os.environ.get("WAYLAND_DISPLAY")):
                return (
                    "Cannot click — no display detected (running headless). "
                    "Set DISPLAY or WAYLAND_DISPLAY."
                )
        try:
            import pyautogui  # type: ignore
        except ImportError:
            return "pyautogui not installed. Run: pip install pyautogui"

        if not label:
            return "No element label provided."

        try:
            result = self.analyze()
        except Exception as exc:
            return f"Screen capture failed: {exc}"

        needle = label.lower().strip()
        best: Optional[UIElement] = None
        best_conf = -1.0

        for el in result.elements:
            if needle in el.label.lower() and el.confidence > best_conf:
                best      = el
                best_conf = el.confidence

        if best is None:
            return (
                f'Could not find "{label}" on screen. '
                "Use read_screen first to see what's visible."
            )

        cx, cy = best.center
        try:
            pyautogui.moveTo(cx, cy, duration=0.15)
            pyautogui.click()
            return (
                f'Clicked "{best.label}" at ({cx}, {cy}) '
                f"[confidence {best.confidence:.0%}, source: {best.source}]"
            )
        except Exception as exc:
            return f"Click failed at ({cx}, {cy}): {exc}"
