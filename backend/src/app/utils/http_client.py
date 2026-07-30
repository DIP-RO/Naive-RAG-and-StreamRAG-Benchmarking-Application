import httpx

SHARED_HTTP_CLIENT = httpx.AsyncClient(
    timeout=60.0, limits=httpx.Limits(max_keepalive_connections=10)
)
