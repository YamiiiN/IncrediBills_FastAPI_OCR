import tempfile
import re
from fastapi import UploadFile
from paddleocr import PaddleOCR

# Initialize PaddleOCR ONCE
ocr_model = PaddleOCR(use_angle_cls=True, lang="en")
# ocr_model = None

async def process_transport_fuel_bill(file: UploadFile):
    """
    Extract transport fuel receipt data:
    - date
    - cost
    - liters
    - provider
    """

    try:
        # Save image temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        # OCR
        ocr_result = ocr_model.ocr(tmp_path, cls=True)

        ocr_lines = []
        for page in ocr_result:
            for line in page:
                ocr_lines.append({
                    "text": line[1][0].strip(),
                    "clean": re.sub(r"\s+", " ", line[1][0].lower()).strip(),
                    "confidence": float(line[1][1])
                })

        all_text = " ".join([l["clean"] for l in ocr_lines])

        # -------------------------
        # DATE (date:09/29/2025)
        # -------------------------
        bill_date = None
        date_match = re.search(
            r'da?t[e]?:?\s*(\d{2}/\d{2}/\d{4})',
            all_text
        )

        if date_match:
            bill_date = date_match.group(1)

        # -------------------------
        # PROVIDER
        # -------------------------
        provider = "Unknown"

        if re.search(r'petron', all_text):
            provider = "Petron"
        elif re.search(r'shell', all_text):
            provider = "Shell"
        elif re.search(r'caltex', all_text):
            provider = "Caltex"
        elif re.search(r'seaoil', all_text):
            provider = "Seaoil"

        # -------------------------
        # LITERS (number before first PHP)
        # -------------------------
        liters = None
        liters_match = re.search(
            r'(\d+\.?\d*)\s*php',
            all_text
        )
        if liters_match:
            try:
                liters = float(liters_match.group(1))
            except ValueError:
                liters = None

        # -------------------------
        # COST (SECOND PHP VALUE)
        # -------------------------
        cost = None
        php_values = re.findall(
            r'php\s*([\d,]+\.\d{2})',
            all_text
        )

        if len(php_values) >= 2:
            try:
                cost = float(php_values[1].replace(",", ""))
            except ValueError:
                cost = None

        # -------------------------
        # RESPONSE
        # -------------------------
        return {
            "status": "success",
            "provider": provider,
            "date": bill_date,
            "cost": cost,
            "liters": liters,
            # "stationLocation": stationLocation,
            "ocr_validation": {
                "all_text_combined": all_text,
                "total_lines_detected": len(ocr_lines)
            }
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }
