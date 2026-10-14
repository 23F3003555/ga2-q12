
import time
import uuid
from collections import defaultdict, deque
from threading import Lock

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

EMAIL = "23f3003555@ds.study.iitm.ac.in"

RATE_LIMIT = 10
WINDOW_SECONDS = 10

rate_buckets = defaultdict(deque)
rate_lock = Lock()

ALLOWED_ORIGINS = [
    "https://app-xcpx85.example.com",
    "https://exam.sanand.workers.dev",
]


@app.middleware("http")
async def request_context_and_rate_limit(
    request: Request, call_next
):
    request_id = (
        request.headers.get("X-Request-ID") or str(uuid.uuid4())
    )
    request.state.request_id = request_id

    # Let CORS preflight requests through without rate limiting
    if request.method == "OPTIONS":
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    client_id = request.headers.get("X-Client-Id", "anonymous")
    now = time.monotonic()

    with rate_lock:
        bucket = rate_buckets[client_id]

        while bucket and now - bucket[0] >= WINDOW_SECONDS:
            bucket.popleft()

        if len(bucket) >= RATE_LIMIT:
            retry_after = max(
                1,
                int(WINDOW_SECONDS - (now - bucket[0]) + 0.999),
            )
            response = JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )
        else:
            bucket.append(now)
            response = None

    if response is None:
        response = await call_next(request)

    response.headers["X-Request-ID"] = request_id
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=[
        "X-Request-ID",
        "X-Client-Id",
        "Content-Type",
    ],
    expose_headers=["X-Request-ID"],
)


@app.get("/ping")
async def ping(request: Request):
    return {
        "email": EMAIL,
        "request_id": request.state.request_id,
    }
