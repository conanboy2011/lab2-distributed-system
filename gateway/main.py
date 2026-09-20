import os
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import httpx

app = FastAPI(title="API Gateway - Microservices System")

# 1. Cấu hình CORS để Swagger UI gọi không bị chặn
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. URL nội bộ của các microservice trong Docker network
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://user-service:8050")
LIBRARY_SERVICE_URL = os.getenv("LIBRARY_SERVICE_URL", "http://library-service:8060")
RESERVATION_SERVICE_URL = os.getenv("RESERVATION_SERVICE_URL", "http://reservation-service:8070")

@app.get("/manage/health")
def health_check():
    return {"status": "OK"}

# 3. Hàm Proxy tổng quát chuyển tiếp request
async def forward_request(service_url: str, path: str, request: Request):
    clean_path = path.lstrip('/')
    if clean_path in ["users", "books", "reservations"]:
        clean_path = f"{clean_path}/"
        
    url = f"{service_url.rstrip('/')}/{clean_path}"
    body = await request.body()
    params = request.query_params
    headers = dict(request.headers)
    headers.pop("host", None)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(
            method=request.method,
            url=url,
            content=body,
            params=params,
            headers=headers
        )
    return Response(
        content=response.content, 
        status_code=response.status_code, 
        headers=dict(response.headers)
    )

# ==========================================
# 4. CÁC ROUTE CHÍNH (GỌN GÀNG, ĐỦ DÙNG)
# ==========================================

# --- USER SERVICE ---
@app.api_route("/users", methods=["GET"])
async def gw_users_get(request: Request):
    return await forward_request(USER_SERVICE_URL, "users", request)

@app.api_route("/users", methods=["POST"])
async def gw_users_post(request: Request, username: str = None, email: str = None):
    return await forward_request(USER_SERVICE_URL, "users", request)


# --- LIBRARY SERVICE (BOOKS) ---
@app.api_route("/books", methods=["GET"])
async def gw_books_get(request: Request):
    return await forward_request(LIBRARY_SERVICE_URL, "books", request)

@app.api_route("/books", methods=["POST"])
async def gw_books_post(request: Request, title: str, author: str, isbn: str):
    return await forward_request(LIBRARY_SERVICE_URL, "books", request)


# --- RESERVATION SERVICE ---
@app.api_route("/reservations", methods=["GET"])
async def gw_reservations_get(request: Request):
    return await forward_request(RESERVATION_SERVICE_URL, "reservations", request)

@app.api_route("/reservations", methods=["POST"])
async def gw_reservations_post(request: Request, user_id: int, book_id: int):
    return await forward_request(RESERVATION_SERVICE_URL, "reservations", request)