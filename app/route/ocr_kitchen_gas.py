from fastapi import APIRouter, UploadFile, File
from app.service.ocr_kitchen_gas import process_kitchen_gas_bill

router = APIRouter(
    prefix="/ocr",
    tags=["OCR"]
)

@router.post("/upload-kitchen_gas-bill")
async def upload_kitchen_gas_bill(file: UploadFile = File(...)):
    result = await process_kitchen_gas_bill(file)
    return result