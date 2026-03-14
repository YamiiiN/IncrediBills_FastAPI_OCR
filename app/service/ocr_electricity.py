import re
import tempfile
from paddleocr import PaddleOCR

ocr_model = PaddleOCR(use_angle_cls=True, lang='en')
# cr_model = None

async def process_electricity_bill(file):
    """
    Extracts electricity bill info with OCR validation
    """
    try:
        # Save uploaded image temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        # Perform OCR
        ocr_result = ocr_model.ocr(tmp_path, cls=True)
        #ocr_result = ocr_model.ocr(tmp_path)

        ocr_lines = []
        all_text = ""

        # Process OCR lines
        for page in ocr_result:
            for line in page:
                bounding_box = line[0]
                text = line[1][0].strip()
                confidence = float(line[1][1])
                all_text += " " + text

                ocr_lines.append({
                    "text": text,
                    "confidence": confidence,
                    "bounding_box": bounding_box,
                    "clean": re.sub(r"\s+", " ", text.lower()).strip()
                })

        all_text_lower = all_text.lower()

        # --- Provider ---
        provider = "Meralco"
        # --- Billing period & bill date ---
        billing_period = None
        bill_date = None

        # Normalize month OCR misreads
        def fix_month_ocr(text):
            text = text.replace("0ct", "Oct").replace("0CT", "Oct").replace("OCT", "Oct")
            text = text.replace("0ct", "Oct").replace("oCt", "Oct")
            return text

        # Normalize date strings like "25Oct2025" -> "25 Oct 2025"
        def normalize_date_text(dt_text):
            if not dt_text:
                return None
            dt_text = fix_month_ocr(dt_text)
            # handle concatenated day+month+year
            m = re.match(r'^(\d{1,2})\s*([A-Za-z]{3,9})\s*(\d{4})$', dt_text.replace(" ", ""), re.IGNORECASE)
            if m:
                return f"{m.group(1)} {m.group(2)} {m.group(3)}".lower()
            # add space if day and month are stuck together
            m2 = re.match(r'^(\d{1,2})([A-Za-z]{3,9})(\d{4})$', dt_text.replace(" ", ""), re.IGNORECASE)
            if m2:
                return f"{m2.group(1)} {m2.group(2)} {m2.group(3)}".lower()
            return re.sub(r'\s+', ' ', dt_text).lower()

        # --- Step 1: Try to find explicit "X to Y" ranges in all text ---
        range_pattern = r'(\d{1,2}\s*[A-Za-z]{3,9}\s*\d{4})\s*(?:to|\-)\s*(\d{1,2}\s*[A-Za-z]{3,9}\s*\d{4})'
        all_text_fixed = fix_month_ocr(all_text)
        range_match = re.search(range_pattern, all_text_fixed, re.IGNORECASE)

        if range_match:
            start_raw = range_match.group(1).strip()
            end_raw = range_match.group(2).strip()
            billing_period = f"{normalize_date_text(start_raw)} to {normalize_date_text(end_raw)}"
            bill_date = normalize_date_text(end_raw)

        # --- Step 2: Fallback, look for "bill date" keyword in lines ---
        if not bill_date:
            for i, l in enumerate(ocr_lines):
                if "bill date" in l["clean"]:
                    # same line
                    date_match = re.search(r'(\d{1,2}\s*[A-Za-z]{3,9}\s*\d{4})', fix_month_ocr(l["clean"]))
                    if date_match:
                        bill_date = normalize_date_text(date_match.group(1).strip())
                        break
                    # next line
                    if i + 1 < len(ocr_lines):
                        date_match = re.search(r'(\d{1,2}\s*[A-Za-z]{3,9}\s*\d{4})', fix_month_ocr(ocr_lines[i+1]["clean"]))
                        if date_match:
                            bill_date = normalize_date_text(date_match.group(1).strip())
                            break

        # --- Step 3: Extra safeguard, if OCR captured something like "25Oct2025" stuck together ---
        if not bill_date and all_text:
            date_match = re.search(r'(\d{1,2}[A-Za-z]{3,9}\d{4})', fix_month_ocr(all_text))
            if date_match:
                bill_date = normalize_date_text(date_match.group(1))

        # --- Total Amount Due (keep existing logic!) ---
        total_amount_due = None
        for i, item in enumerate(ocr_lines):
            if "total amount due" in item["clean"]:
                # Look next few lines for the amount
                for j in range(i+1, min(i+6, len(ocr_lines))):
                    candidate = ocr_lines[j]["text"]
                    match = re.search(r'[\$P]?([\d,]+\.\d+)', candidate)
                    if match:
                        try:
                            total_amount_due = float(match.group(1).replace(',', ''))
                            break
                        except:
                            continue
                if total_amount_due is not None:
                    break

        # --- Consumption in kWh ---
        consumption = None
        cons_match = re.search(r'(\d+(?:\.\d+)?)\s*[kK][wW][hH]?', all_text)
        if cons_match:
            try:
                consumption = float(cons_match.group(1))
            except:
                consumption = None

        # Final structured response
        return {
            "status": "success",
            "provider": provider,
            "bill_date": bill_date,
            "billing_period": billing_period,
            "total_amount_due": total_amount_due,
            "consumption": consumption,
            "ocr_validation": {
                "total_lines_detected": len(ocr_lines),
                "all_text_combined": all_text,
                "lines": ocr_lines
            }
        }

    except Exception as e:
        print("❌ OCR Error:", str(e))
        return {
            "status": "failed",
            "error": str(e)
        }