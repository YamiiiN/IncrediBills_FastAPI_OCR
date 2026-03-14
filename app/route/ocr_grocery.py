from fastapi import APIRouter, UploadFile, File
from app.service.ocr_grocery import process_grocery_bill

router = APIRouter(
    prefix="/ocr",
    tags=["OCR"]
)

@router.post("/upload-grocery-bill")
async def upload_grocery_bill(file: UploadFile = File(...)):
    result = await process_grocery_bill(file)
    return result
