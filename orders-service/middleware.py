import uuid
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from logger import set_trace_id, logger


class TraceIDMiddleware(BaseHTTPMiddleware):
    """Middleware to generate and track trace_id for each request"""

    async def dispatch(self, request: Request, call_next):
        # Generate or extract trace_id
        trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
        set_trace_id(trace_id)

        # Log incoming request
        start_time = time.time()
        logger.info(
            "Incoming request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query_params": dict(request.query_params),
                "client_host": request.client.host if request.client else None,
            }
        )

        # Process request
        try:
            response = await call_next(request)

            # Calculate processing time
            process_time = time.time() - start_time

            # Add trace_id to response headers
            response.headers["X-Trace-ID"] = trace_id

            # Log response
            logger.info(
                "Request completed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "process_time": round(process_time, 3),
                }
            )

            return response
        except Exception as e:
            # Log error
            logger.error(
                "Request failed",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True
            )
            raise
