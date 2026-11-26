# Application logging

The API uses Python's built-in `logging` module, configured in
`app/core/logging.py`. No additional package is required. Application logs are
written to stdout as one JSON object per line, suitable for local terminals and
Docker's log collection. Uvicorn and third-party logs retain their own settings
and formats.

Set `LOG_LEVEL` in `.env` or the environment to `DEBUG`, `INFO`, `WARNING`, `ERROR`,
or `CRITICAL`. The default is `INFO`. Docker Compose also passes this setting to
the API container. View container logs with `docker compose logs -f api`.

Every HTTP request receives a generated `X-Request-ID` response header. The same
ID appears in logs emitted during that request. HTTP logs include a route
template, such as `/users/me`, the method, status code, and duration in
milliseconds. Responses with 4xx statuses use `WARNING`, 5xx statuses use `ERROR`,
and other responses use `INFO`. Unmatched routes are recorded as `<unmatched>`.

```json
{"timestamp":"2026-11-18T10:00:00+00:00","level":"INFO","logger":"app.api.middleware","event":"request_completed","request_id":"1f80c1c32e4e4b4a89109f09c43e88d3","method":"PATCH","route":"/users/me","status_code":200,"duration_ms":182.5}
```

The API also records `application_started`, `application_stopped`, and
`database_unavailable`. Unexpected request exceptions produce `request_failed`,
including the exception type and traceback file/function/line locations. Their
HTTP response contains a generic error and the request ID.

To add application events:

```python
import logging

logger = logging.getLogger(__name__)
logger.info("operation_started")
```

Use static event names. Do not put passwords, hashes, tokens, cookies, request
bodies, database connection strings, or personal data in log messages. The HTTP
middleware does not collect headers, bodies, query strings, or raw URL paths.
The JSON formatter only includes explicitly allowed extra fields and omits
exception messages and traceback source lines. Custom message text is emitted as
provided, so callers must keep it free of secrets. Request context is reset after
each request and remains separate across concurrent requests.
