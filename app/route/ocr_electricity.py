from fastapi import APIRouter, UploadFile, File
from app.service.ocr_electricity import process_electricity_bill

router = APIRouter(
    prefix="/ocr",
    tags=["OCR"]
)

@router.post("/upload-electricity-bill")
async def upload_bill(file: UploadFile = File(...)):
    """
    Receives an uploaded image and extracts text using PaddleOCR.
    """
    try:
        result = await process_electricity_bill(file)
        print("OCR Result:", result)
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}