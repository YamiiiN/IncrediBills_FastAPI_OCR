from fastapi import APIRouter, UploadFile, File
from app.service.ocr_water import process_water_bill

router = APIRouter(
    prefix="/ocr",
    tags=["OCR"]
)

@router.post("/upload-water-bill")
async def upload_bill(file: UploadFile = File(...)): 
    """
    Receives an uploaded image and extracts text using PaddleOCR.
    """
    try:
        result = await process_water_bill(file)
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}