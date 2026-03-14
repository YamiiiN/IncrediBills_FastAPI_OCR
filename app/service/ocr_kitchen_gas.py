import tempfile
import re
from fastapi import UploadFile
from paddleocr import PaddleOCR

# Initialize PaddleOCR ONCE
ocr_model = PaddleOCR(use_angle_cls=True, lang="en")


async def process_kitchen_gas_bill(file: UploadFile):
    """
    Extract kitchen gas receipt data:
    - date
    - total cost
    - provider
    """

    try:
        # Save image temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        # OCR
        ocr_result = ocr_model.ocr(tmp_path, cls=True)
        #ocr_result = ocr_model.ocr(tmp_path)

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
        # DATE (same logic as fuel)
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
        provider = "Others"

        if re.search(r'island\s*gas', all_text):
            provider = "Island Gas"
        elif re.search(r'ultragaz', all_text):
            provider = "Ultragaz"
        elif re.search(r'puregaz', all_text):
            provider = "Puregaz"
        elif re.search(r'solane', all_text):
            provider = "Solane"

        # -------------------------
        # TOTAL (value beside word "total")
        # -------------------------
        total = None

        total_match = re.search(
            r'total[^0-9]*([\d,]+\.\d{2})',
            all_text
        )

        if total_match:
            try:
                total = float(total_match.group(1).replace(",", ""))
            except ValueError:
                total = None

        # -------------------------
        # RESPONSE
        # -------------------------
        return {
            "status": "success",
            "provider": provider,
            "date": bill_date,
            "cost": total,
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