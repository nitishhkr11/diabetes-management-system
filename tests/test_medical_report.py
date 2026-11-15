import io
import pytest
import fitz
from PIL import Image
from starlette.datastructures import UploadFile

from src.medical_report import ReportError, extract_text, parse_observations
from backend import main


def test_extract_rejects_empty_oversized_and_unsupported_files():
    with pytest.raises(ReportError, match="empty"):
        extract_text(b"", "application/pdf")
    with pytest.raises(ReportError, match="10 MB"):
        extract_text(b"x" * (10 * 1024 * 1024 + 1), "image/png")
    with pytest.raises(ReportError, match="Upload a PDF"):
        extract_text(b"data", "text/plain")


def test_extract_rejects_malformed_pdf_and_image_signatures():
    with pytest.raises(ReportError, match="valid PDF"):
        extract_text(b"not a pdf", "application/pdf")
    with pytest.raises(ReportError, match="corrupt"):
        extract_text(b"not an image", "image/png")


def test_text_pdf_is_extracted_and_limited_page_count_is_enforced():
    document = fitz.open()
    document.new_page().insert_text((72, 72), "HbA1c 6.2 %")
    result = extract_text(document.tobytes(), "application/pdf")
    assert "HbA1c 6.2" in result.text
    assert result.method == "embedded_pdf_text"
    assert result.pages == 1

    too_many = fitz.open()
    for _ in range(6):
        too_many.new_page()
    with pytest.raises(ReportError, match="5-page"):
        extract_text(too_many.tobytes(), "application/pdf")


def test_upload_resource_is_closed_after_successful_processing():
    document = fitz.open()
    document.new_page().insert_text((72, 72), "HbA1c 6.2 %")
    stream = io.BytesIO(document.tobytes())
    upload = UploadFile(filename="report.pdf", file=stream, headers={"content-type": "application/pdf"})
    result = __import__("asyncio").run(main.extract_medical_report({"id": "test-user"}, upload))
    assert result["retained"] is False
    assert stream.closed


def test_image_report_uses_local_ocr_and_reports_confidence(monkeypatch):
    import src.medical_report as report_module
    image = Image.new("RGB", (80, 40), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    monkeypatch.setattr(report_module, "_ocr", lambda _: ("HbA1c 6.2 %", 0.91))
    result = extract_text(buffer.getvalue(), "image/png")
    assert result.method == "local_ocr"
    assert result.confidence == 0.91
    assert "HbA1c" in result.text


def test_scanned_pdf_uses_local_ocr_fallback(monkeypatch):
    import src.medical_report as report_module
    document = fitz.open()
    document.new_page()
    monkeypatch.setattr(report_module, "_ocr", lambda _: ("BMI 28.4 kg/m2", 0.84))
    result = extract_text(document.tobytes(), "application/pdf")
    assert result.method == "local_ocr"
    assert result.confidence == 0.84
    assert "BMI" in result.text


def test_parser_keeps_labs_separate_and_only_suggests_semantically_matching_features():
    values = parse_observations("HbA1c 6.4 %; fasting glucose 112 mg/dL; 2-hour OGTT glucose 178 mg/dL; BMI 29.3 kg/m2; Age 42 years")
    by_name = {row["name"]: row for row in values}
    assert by_name["HbA1c"]["value"] == "6.4"
    assert by_name["HbA1c"]["suggested_model_feature"] is None
    # More than one glucose entry is deliberately ambiguous and not extracted.
    assert "Glucose" not in by_name
    assert by_name["BMI"]["suggested_model_feature"] == "BMI"
    assert by_name["Age"]["suggested_model_feature"] == "Age"


def test_parser_maps_only_unambiguous_two_hour_glucose_measurement():
    rows = parse_observations("2-hour OGTT glucose 178 mg/dL")
    assert len(rows) == 1
    assert rows[0]["suggested_model_feature"] == "Glucose"
    assert rows[0]["unit"] == "mg/dL"


def test_parser_leaves_fast_or_random_glucose_unmapped():
    for label in ("fasting glucose 112 mg/dL", "random glucose 160 mg/dL"):
        rows = parse_observations(label)
        assert rows[0]["suggested_model_feature"] is None


def test_parser_does_not_guess_conflicting_duplicate_measurements():
    assert parse_observations("BMI 29.3 kg/m2; BMI 31.0 kg/m2") == []
