import tempfile
import re
from fastapi import UploadFile
from paddleocr import PaddleOCR

# Initialize PaddleOCR ONCE
ocr_model = PaddleOCR(use_angle_cls=True, lang="en")
# ocr_model = None


async def process_miscellaneous_bill(file: UploadFile):
    """
    Extract ONLY:
    - date
    - cost
    """

    try:
        # Save uploaded image temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        # OCR
        ocr_result = ocr_model.ocr(tmp_path, cls=True)

        ocr_lines = []
        for page in ocr_result:
            for line in page:
                ocr_lines.append(
                    re.sub(r"\s+", " ", line[1][0].lower()).strip()
                )

        all_text = " ".join(ocr_lines)

        # -------------------------
        # DATE EXTRACTION
        # -------------------------
        bill_date = None

        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{2,4}',              # 10/04/25, 10/04/2025
            r'\d{1,2}\s*[a-z]{3,9}\s*\d{4}',        # 04 oct 2025
            r'\d{2}[a-z]{3}\d{4}'                   # 04oct2025
        ]

        for pattern in date_patterns:
            match = re.search(pattern, all_text)
            if match:
                bill_date = match.group(0)
                break

        # -------------------------
        # COST EXTRACTION
        # -------------------------
        total_cost = None

        # 1️⃣ Try keyword-based TOTAL
        total_match = re.search(
            r'total\s*([\d\.]+)',
            all_text
        )

        def normalize_amount(raw):
            parts = raw.split(".")
            if len(parts) >= 2:
                return float("".join(parts[:-1]) + "." + parts[-1])
            return float(raw)

        if total_match:
            try:
                total_cost = normalize_amount(total_match.group(1))
            except:
                total_cost = None

        # 2️⃣ Fallback → largest detected amount
        if total_cost is None:
            amounts = re.findall(r'[\d]{1,3}(?:[.,]\d{3})*(?:\.\d{2})', all_text)
            parsed = []

            for amt in amounts:
                try:
                    parsed.append(normalize_amount(amt.replace(",", "")))
                except:
                    pass

            if parsed:
                total_cost = max(parsed)

        # -------------------------
        # RESPONSE
        # -------------------------
        return {
            "status": "success",
            "date": bill_date,
            "cost": total_cost
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }
