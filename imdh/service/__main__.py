"""python -m imdh.service: serve the API (and the built dashboard) on $PORT."""
import os

import uvicorn

from imdh.service.api import app_from_env

if __name__ == "__main__":
    uvicorn.run(app_from_env(), host="0.0.0.0", port=int(os.environ.get("PORT", "8080")), log_level="info")
