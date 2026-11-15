"""Ephemeral, local medical-report text extraction and conservative parsing.

This module reports observations only. It never predicts, assigns a diagnosis,
or silently converts a laboratory result into a Pima model input.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

from PIL import Image, ImageOps, UnidentifiedImageError
from pypdf import PdfReader

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 5
SUPPORTED = {"application/pdf", "image/png", "image/jpeg"}


class ReportError(ValueError):
    """Safe-to-display report parsing error."""


@dataclass(frozen=True)
class ExtractedText:
    text: str
    method: str
    confidence: float | None
    pages: int


def _ocr(image: Image.Image) -> tuple[str, float | None]:
    try:
        import pytesseract
        from pytesseract import TesseractNotFoundError
        data = pytesseract.image_to_data(ImageOps.exif_transpose(image), output_type=pytesseract.Output.DICT, timeout=7)
    except (ImportError, OSError) as exc:
        raise ReportError("This report needs local OCR. Install Tesseract OCR and the Python OCR dependencies, or enter the values manually.") from exc
    except Exception as exc:
        if exc.__class__.__name__ == "TesseractNotFoundError":
            raise ReportError("Local OCR is not installed. Install Tesseract OCR or enter the values manually.") from exc
        raise ReportError("The report image could not be read. Try a clearer image or enter the values manually.") from exc
    words, confidences = [], []
    for word, confidence in zip(data.get("text", []), data.get("conf", [])):
        word = word.strip()
        if word:
            words.append(word)
            try:
                if float(confidence) >= 0:
                    confidences.append(float(confidence))
            except (ValueError, TypeError):
                pass
    return " ".join(words), (sum(confidences) / len(confidences) / 100 if confidences else None)


def extract_text(payload: bytes, content_type: str) -> ExtractedText:
    if len(payload) > MAX_BYTES:
        raise ReportError("The report is larger than the 10 MB limit.")
    if not payload:
        raise ReportError("The uploaded file is empty.")
    if content_type not in SUPPORTED:
        raise ReportError("Upload a PDF, PNG, JPG, or JPEG file.")

    if content_type == "application/pdf":
        if not payload.startswith(b"%PDF-"):
            raise ReportError("The file does not contain a valid PDF document.")
        try:
            reader = PdfReader(io.BytesIO(payload), strict=True)
            if reader.is_encrypted:
                raise ReportError("Password-protected PDFs are not supported. Export an unlocked copy or enter values manually.")
            pages = len(reader.pages)
            if pages < 1:
                raise ReportError("The PDF has no readable pages.")
            if pages > MAX_PAGES:
                raise ReportError(f"The PDF exceeds the {MAX_PAGES}-page limit.")
            texts = [(page.extract_text() or "").strip() for page in reader.pages]
            text = "\n".join(part for part in texts if part)
            if text.strip():
                return ExtractedText(text[:100_000], "embedded_pdf_text", None, pages)
            try:
                import fitz
                doc = fitz.open(stream=payload, filetype="pdf")
                pages_text, confs = [], []
                for page in doc:
                    rect = page.rect
                    scale = min(2.0, (40_000_000 / max(1.0, rect.width * rect.height)) ** 0.5)
                    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                    image = Image.open(io.BytesIO(pix.tobytes("png")))
                    part, confidence = _ocr(image)
                    pages_text.append(part)
                    if confidence is not None:
                        confs.append(confidence)
                text = "\n".join(pages_text)
                return ExtractedText(text[:100_000], "local_ocr", sum(confs) / len(confs) if confs else None, pages)
            except ImportError as exc:
                raise ReportError("This scanned PDF needs local OCR. Install the PDF rendering and Tesseract OCR dependencies, or enter the values manually.") from exc
        except ReportError:
            raise
        except Exception as exc:
            raise ReportError("The PDF is corrupt or could not be safely read.") from exc

    try:
        image = Image.open(io.BytesIO(payload))
        image.verify()
        image = Image.open(io.BytesIO(payload))
        if image.format not in {"PNG", "JPEG"}:
            raise ReportError("The image content does not match PNG or JPEG format.")
        if image.width * image.height > 40_000_000:
            raise ReportError("The image dimensions exceed the 40-megapixel limit.")
        text, confidence = _ocr(image)
        return ExtractedText(text[:100_000], "local_ocr", confidence, 1)
    except ReportError:
        raise
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ReportError("The image is corrupt, too large, or unreadable.") from exc


def parse_observations(text: str, confidence: float | None = None) -> list[dict]:
    """Extract a short allowlist of labeled values with units/context intact."""
    normalized = re.sub(r"\s+", " ", text)
    patterns = [
        ("HbA1c", r"\b(?:Hb\s*A1c|A1c|glycated\s+hemoglobin)\b[^\d]{0,35}(\d{1,2}(?:\.\d+)?)\s*(%|mmol/mol)?", "%", None),
        ("Glucose", r"\b(fasting\s+glucose|fasting\s+blood\s+glucose|random\s+glucose|2\s*(?:-|hour\s*)?h(?:our)?\s*(?:OGTT|oral\s+glucose\s+tolerance)?|glucose)\b[^\d]{0,40}(\d{1,3}(?:\.\d+)?)\s*(mg\s*/\s*dL|mmol\s*/\s*L)?", "mg/dL", "Glucose"),
        ("Blood pressure", r"\b(?:blood\s+pressure|BP)\b[^\d]{0,15}(\d{2,3})\s*/\s*(\d{2,3})\s*(mm\s*Hg)?", "mm Hg", None),
        ("BMI", r"\b(?:BMI|body\s+mass\s+index)\b[^\d]{0,25}(\d{1,2}(?:\.\d+)?)\s*(kg\s*/\s*m(?:2|²))?", "kg/m²", "BMI"),
        ("Age", r"\bage\b[^\d]{0,12}(\d{1,3})\s*(years?|yrs?)?\b", "years", "Age"),
    ]
    findings: list[dict] = []
    for name, pattern, default_unit, feature in patterns:
        hits = list(re.finditer(pattern, normalized, flags=re.I))
        if len(hits) != 1:
            continue
        match = hits[0]
        groups = match.groups()
        context = match.group(0)
        if name == "Blood pressure":
            value = f"{groups[0]}/{groups[1]}"
            unit = groups[2] or default_unit
        elif name == "Glucose":
            label, value, unit = groups
            label = label.lower()
            unit = re.sub(r"\s+", "", unit) if unit else default_unit
            if unit.lower() == "mmol/l":
                # Preserve the original unit and do not auto-convert into the model.
                feature = None
            # A Pima-compatible glucose is specifically a two-hour post-load value.
            if not re.search(r"2\s*(?:-|hour\s*)?h|2\s*hour|ogtt|oral glucose tolerance", label):
                feature = None
        else:
            value, unit = groups[0], groups[1] or default_unit
        findings.append({
            "name": name, "value": str(value), "unit": unit,
            "context": context[:140], "source": "uploaded report",
            "suggested_model_feature": feature,
            "confidence": confidence,
            "review_required": True,
        })
    return findings
