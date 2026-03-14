from fastapi import APIRouter, UploadFile, File
from app.service.ocr_transport_fuel import process_transport_fuel_bill

router = APIRouter(
    prefix="/ocr",
    tags=["OCR"]
)

@router.post("/upload-transport_fuel-bill")
async def upload_transport_fuel_bill(file: UploadFile = File(...)):
    result = await process_transport_fuel_bill(file)
    return result
