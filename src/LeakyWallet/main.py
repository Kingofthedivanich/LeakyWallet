from fastapi import FastAPI

from LeakyWallet.logging import configure_logging, get_logger

configure_logging()
logger = get_logger(__name__)

app = FastAPI(title="LeakyWallet")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
