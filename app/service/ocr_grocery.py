import tempfile
import re
from fastapi import UploadFile
from paddleocr import PaddleOCR
from datetime import datetime

# Initialize PaddleOCR ONCE
ocr_model = PaddleOCR(use_angle_cls=True, lang="en")
# ocr_model = None

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12
}

async def process_grocery_bill(file: UploadFile):
    """
    Extract grocery receipt data:
    - store
    - date
    - total cost
    - quantity of items
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
        # STORE NAME
        # -------------------------
        store = "Unknown"

        for l in ocr_lines[:10]:  # usually at the top
            clean = l["clean"]
            if "metro" in clean:
                store = "SM"
                break
            elif "market" in clean:
                store = "METRO MARKET"
                break

        # -------------------------
        # DATE (MM/DD/YY, MM/DD/YYYY, or textual)
        # -------------------------
        bill_date = None

        # Numeric dates
        date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})', all_text)
        if date_match:
            bill_date = date_match.group(1)
        else:
            # Textual months like dec72025, dec 7 2025, Dec072025, etc.
            text_date_match = re.search(r'\b([a-z]{3})\s?0?(\d{1,2})\s?(\d{4})\b', all_text, re.IGNORECASE)
            if not text_date_match:
                text_date_match = re.search(r'\b([a-z]{3})0?(\d{1,2})(\d{4})\b', all_text, re.IGNORECASE)
            if text_date_match:
                month_str, day_str, year_str = text_date_match.groups()
                month = MONTHS.get(month_str.lower(), 1)
                day = int(day_str)
                year = int(year_str)
                bill_date = f"{month:02}/{day:02}/{year}"

        # -------------------------
        # TOTAL COST
        # -------------------------
        total_amount = None
        total_match = re.search(
            r'total\s+([\d\.,]+)',  # allow digits, dots, commas
            all_text,
            flags=re.IGNORECASE
        )

        if total_match:
            raw_total = total_match.group(1)  # e.g. "2.548.73" or "2,988.21" or "8391.86"

            # Normalize number: remove thousand separators (dot or comma), keep last dot as decimal
            temp = raw_total.replace(",", ".")
            parts = temp.split(".")
            if len(parts) >= 2:
                normalized = "".join(parts[:-1]) + "." + parts[-1]
            else:
                normalized = temp  # just a simple number like "8391.86"
            try:
                total_amount = float(normalized)
            except ValueError:
                total_amount = None

        # -------------------------
        # QUANTITY (ITEM COUNT)
        # Count lines between "Business Style" and "TOTAL"
        # -------------------------
        start_idx = None
        end_idx = None

        for i, l in enumerate(ocr_lines):
            clean = l["clean"]

            if "business style" in clean or "business" in clean:
                start_idx = i + 1

            if start_idx is not None and "total" in clean:
                end_idx = i
                break

        quantity = 0
        if start_idx is not None and end_idx is not None:
            item_block = ocr_lines[start_idx:end_idx]

            for line in item_block:
                # product lines usually start with text, not numbers
                if re.match(r'^[a-z]', line["clean"]):
                    quantity += 1

        # -------------------------
        # RESPONSE
        # -------------------------
        return {
            "status": "success",
            "store": store,
            "date": bill_date,
            "cost": total_amount,
            "quantity": quantity,
            "ocr_validation": {
                "total_lines_detected": len(ocr_lines),
                "all_text_combined": all_text,
            }
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": str(e)
        }
