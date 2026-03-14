import tempfile
import re
from fastapi import FastAPI, UploadFile, File
from paddleocr import PaddleOCR

app = FastAPI()

# Initialize PaddleOCR ONCE (important for performance)
ocr_model = PaddleOCR(use_angle_cls=True, lang="en")
# ocr_model = None

async def process_water_bill(file: UploadFile):
    """
    Extracts and returns FULL OCR data for validation
    """

    try:
        # Save uploaded image temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        # Perform OCR
        ocr_result = ocr_model.ocr(tmp_path, cls=True)

        ocr_lines = []

        # PaddleOCR result structure: [ [ line, line, ... ] ]
        for page in ocr_result:
            for line in page:
                bounding_box = line[0]
                text = line[1][0].strip()
                confidence = float(line[1][1])

                ocr_lines.append({
                    "text": text,
                    "confidence": confidence,
                    # "bounding_box": bounding_box
                })

        # normalized lines for easier pattern matching
        for l in ocr_lines:
            l["clean"] = re.sub(r"\s+", " ", l["text"].lower()).strip()

        all_text = " ".join([l["text"] for l in ocr_lines]).lower()


        # Provider detection (with common OCR fixes)
        provider = "Unknown"
        provider_candidates = all_text.replace(" ", "")
        # map common OCR misreads to canonical provider names
        if any(x in provider_candidates for x in ("manila water", "manila wate", "anilawater", "anila water", "Manila Water")):
            provider = "Manila Water"
        elif "maynilad" in provider_candidates:
            provider = "Maynilad Water"
        else:
            provider = "Manila Water"  # default/fallback


        # Date and Billing Period detection
        billing_period = None
        bill_date = None

        # relaxed date patterns (with or without spaces)
        date_patterns = [
            r'(\d{1,2}\s*[A-Za-z]{3,9}\s*\d{4})',  
            r'(\d{2}[A-Za-z]{3}\d{4})'               
        ]

        # try to find explicit "X to Y" ranges line-by-line first (more reliable)
        found_range = False
        for l in ocr_lines:       
            line_text = l["clean"]
            m = re.search(r'(\d{1,2}\s*[A-Za-z]{3,9}\s*\d{4}|\d{2}[A-Za-z]{3}\d{4})\s*(?:to|\-)\s*(\d{1,2}\s*[A-Za-z]{3,9}\s*\d{4}|\d{2}[A-Za-z]{3}\d{4})', line_text, re.IGNORECASE)
            if m:
                start = m.group(1).strip()
                end = m.group(2).strip()
                billing_period = f"{start} to {end}"
                bill_date = end
                found_range = True
                break

        # fallback: search full text if not found line-by-line
        if not found_range:
            m = re.search(r'(\d{1,2}\s*[A-Za-z]{3,9}\s*\d{4}|\d{2}[A-Za-z]{3}\d{4})\s*(?:to|\-)\s*(\d{1,2}\s*[A-Za-z]{3,9}\s*\d{4}|\d{2}[A-Za-z]{3}\d{4})', all_text, re.IGNORECASE)
            if m:
                start = m.group(1).strip()
                end = m.group(2).strip()
                billing_period = f"{start} to {end}"
                bill_date = end

        # if still no bill_date, try to capture 'bill date' label followed by a date in nearby lines
        if not bill_date:
            for i, l in enumerate(ocr_lines):
                if "bill date" in l["clean"]:
                    # check same line for a date
                    for patt in date_patterns:
                        m = re.search(patt, l["clean"], re.IGNORECASE)
                        if m:
                            bill_date = m.group(1).strip()
                            break
                    if bill_date:
                        break
                    # check next line
                    if i + 1 < len(ocr_lines):
                        for patt in date_patterns:
                            m = re.search(patt, ocr_lines[i + 1]["clean"], re.IGNORECASE)
                            if m:
                                bill_date = m.group(1).strip()
                                break
                        if bill_date:
                            break

        # normalize date spacing (e.g. "04Feb2025" -> "04 Feb 2025")
        def normalize_date_text(dt_text):
            if not dt_text:
                return None
            # add space between day-monthyear when concatenated like 04Feb2025
            m = re.match(r'^(\d{1,2})([A-Za-z]{3})(\d{4})$', dt_text.replace(" ", ""), re.IGNORECASE)
            if m:
                return f"{m.group(1)} {m.group(2)} {m.group(3)}".lower()
            return re.sub(r'\s+', ' ', dt_text).lower()

        bill_date = normalize_date_text(bill_date)
        if billing_period:
            # normalize both parts
            parts = re.split(r'\s*to\s*', billing_period, flags=re.IGNORECASE)
            if len(parts) == 2:
                billing_period = f"{normalize_date_text(parts[0])} to {normalize_date_text(parts[1])}"


        # Amount extraction (improved)
        total_amount_due = None

        # find all amounts in full text with positions
        amount_regex = re.compile(r'[₱P\$]?\s*([\d]{1,3}(?:,\d{3})*(?:\.\d+)?)')
        amounts = []
        for m in amount_regex.finditer(all_text):
            amt_text = m.group(1)
            try:
                amt_val = float(amt_text.replace(",", ""))
                amounts.append({"value": amt_val, "start": m.start(), "end": m.end(), "text": amt_text})
            except:
                continue

        keywords = [
            "total amount due", "total current charges", "total current charge",
            "total current", "fotal amount due", "total amount", "amount due", "total due"
        ]

        # find nearest amount to any keyword occurrence
        best = None
        for kw in keywords:
            for kpos in [m.start() for m in re.finditer(re.escape(kw), all_text)]:
                # find nearest amount by position distance
                if not amounts:
                    continue
                nearest = min(amounts, key=lambda a: abs(((a["start"] + a["end"]) // 2) - kpos))
                dist = abs(((nearest["start"] + nearest["end"]) // 2) - kpos)
                # prefer small distances; threshold tolerant (e.g., 200 chars)
                if best is None or dist < best["dist"]:
                    best = {"amount": nearest["value"], "dist": dist, "keyword": kw}
        # if not found via keywords, attempt to find amount on lines that contain 'total' or 'current'
        if best is None:
            for i, l in enumerate(ocr_lines):
                if "total" in l["clean"] or "current charges" in l["clean"] or "amount due" in l["clean"]:
                    # check same line for amount
                    m = amount_regex.search(l["clean"])
                    if m:
                        try:
                            total_amount_due = float(m.group(1).replace(",", ""))
                            break
                        except:
                            pass
                    # check previous or next lines
                    for j in (i-1, i+1):
                        if 0 <= j < len(ocr_lines):
                            m2 = amount_regex.search(ocr_lines[j]["clean"])
                            if m2:
                                try:
                                    total_amount_due = float(m2.group(1).replace(",", ""))
                                    break
                                except:
                                    pass
                    if total_amount_due is not None:
                        break
        else:
            total_amount_due = best["amount"]

        # last fallback: if only a single obvious large amount exists, choose a reasonable candidate
        if total_amount_due is None and amounts:
            # choose the largest amount (often the bill total)
            total_amount_due = max(a["value"] for a in amounts)

        # Consumption (Cubic Meters)
        consumption = None

        consumption_match = re.search(
            r'(\d+\.?\d*)\s*(cubic meters|cu\.?\s*m|consumption)',
            all_text,
            re.IGNORECASE
        )

        if consumption_match:
            try:
                consumption = float(consumption_match.group(1))
            except:
                consumption = None

        # Final Response
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
