"""API Gateway HTTP API v2 / REST proxy adapter (no provider startup calls)."""

from mangum import Mangum

from .app import app

handler = Mangum(app, lifespan="off")
