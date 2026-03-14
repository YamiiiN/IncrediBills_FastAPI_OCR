from fastapi import APIRouter, UploadFile, File
# from app.services.ocr.ocr_water import process_water_bill
from app.service.ocr_miscellaneous import process_miscellaneous_bill

router = APIRouter(
    prefix="/ocr",
    tags=["OCR"]
)

@router.post("/upload-miscellaneous-bill")
async def upload_bill(file: UploadFile = File(...)): 
    """
    Receives an uploaded image and extracts text using PaddleOCR.
    """
    try:
        result = await process_miscellaneous_bill(file)
        return {"status": "success", "data": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}