"""Serial/IMEI/Nonce OCR Extraction and Cross-Check Engine (F-01: FR-03)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.domain.serial_registry import normalize_serial


@dataclass(frozen=True)
class OcrSerialMatchResult:
    """Result of OCR extraction and normalized serial cross-check."""

    sku: str
    extracted_serial: str
    normalized_extracted: str
    normalized_expected: str
    matched: bool
    confidence: float


SERIAL_REGEX = re.compile(r"\b([A-Z0-9]{2,6}-[A-Z0-9]{2,6}-[A-Z0-9]{3,8})\b", re.IGNORECASE)


def extract_and_match_serial(
    *,
    sku: str,
    ocr_text: str,
    expected_serial: str,
) -> OcrSerialMatchResult:
    """Extract serial number from OCR text and cross-check against expected serial (FR-03)."""
    match = SERIAL_REGEX.search(ocr_text)
    extracted = match.group(1).upper() if match else ocr_text.strip().upper()
    norm_ext = normalize_serial(extracted)
    norm_exp = normalize_serial(expected_serial)
    is_match = norm_ext == norm_exp and len(norm_exp) > 0
    return OcrSerialMatchResult(
        sku=sku,
        extracted_serial=extracted,
        normalized_extracted=norm_ext,
        normalized_expected=norm_exp,
        matched=is_match,
        confidence=0.98 if is_match else 0.40,
    )
