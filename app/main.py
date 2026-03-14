from fastapi import FastAPI
from app.route import ocr_water, ocr_transport_fuel, ocr_kitchen_gas, ocr_grocery, ocr_electricity, ocr_miscellaneous

app = FastAPI(title="IncrediBills OCR API")

app.include_router(ocr_electricity.router)
app.include_router(ocr_water.router)
app.include_router(ocr_grocery.router)
app.include_router(ocr_transport_fuel.router)
app.include_router(ocr_miscellaneous.router)
app.include_router(ocr_kitchen_gas.router)

@app.get("/")
def root():
    return {"message": "Welcome to IncrediBills FastAPI Server for OCR processing!"}