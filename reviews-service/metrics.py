from prometheus_client import Counter, Gauge, Histogram
import time

# Reviews metrics
reviews_created_total = Counter(
    'reviews_created_total',
    'Total number of reviews created',
    ['rating', 'verified_purchase']
)

reviews_deleted_total = Counter(
    'reviews_deleted_total',
    'Total number of reviews deleted'
)

reviews_with_photos_total = Counter(
    'reviews_with_photos_total',
    'Total number of reviews with photos'
)

# Photos metrics
photos_uploaded_total = Counter(
    'photos_uploaded_total',
    'Total number of photos uploaded'
)

photos_deleted_total = Counter(
    'photos_deleted_total',
    'Total number of photos deleted'
)

photos_storage_size_bytes = Gauge(
    'photos_storage_size_bytes',
    'Total size of stored photos in bytes'
)

# Product rating metrics
average_product_rating = Gauge(
    'average_product_rating',
    'Average rating for products',
    ['product_id']
)

# HTTP client metrics for inter-service calls
http_client_request_duration = Histogram(
    'http_client_request_duration_seconds',
    'HTTP client request duration in seconds',
    ['target_service', 'method', 'status'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

http_client_requests_total = Counter(
    'http_client_requests_total',
    'Total HTTP client requests',
    ['target_service', 'method', 'status']
)


class HTTPClientMetrics:
    """Context manager for tracking HTTP client metrics"""

    def __init__(self, target_service: str, method: str):
        self.target_service = target_service
        self.method = method
        self.start_time = None
        self.status = "unknown"

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        http_client_request_duration.labels(
            target_service=self.target_service,
            method=self.method,
            status=self.status
        ).observe(duration)
        http_client_requests_total.labels(
            target_service=self.target_service,
            method=self.method,
            status=self.status
        ).inc()
        return False

    def set_status(self, status_code: int):
        if 200 <= status_code < 300:
            self.status = "success"
        elif 400 <= status_code < 500:
            self.status = "client_error"
        elif 500 <= status_code < 600:
            self.status = "server_error"
