from fastapi import FastAPI
from api_gateway.routes import router as api_router

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Welcome to the API Gateway"}

app.include_router(api_router)