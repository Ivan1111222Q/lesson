from prometheus_client import Counter, Gauge, Histogram
import time

# Business metrics
products_created_total = Counter(
    'products_created_total',
    'Total number of products created',
    ['category']
)

products_deleted_total = Counter(
    'products_deleted_total',
    'Total number of products deleted',
    ['category']
)

products_stock_gauge = Gauge(
    'products_stock_total',
    'Current total stock across all products'
)

product_price_histogram = Histogram(
    'product_price_distribution',
    'Distribution of product prices',
    ['category'],
    buckets=[10, 50, 100, 500, 1000, 5000, 10000]
)

stock_updates_total = Counter(
    'stock_updates_total',
    'Total number of stock updates',
    ['product_id', 'operation']  # operation: increase/decrease
)

# Inter-service call metrics
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
    """Context manager for measuring HTTP client requests"""

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
        """Set the HTTP status code"""
        if 200 <= status_code < 300:
            self.status = "success"
        elif 400 <= status_code < 500:
            self.status = "client_error"
        elif 500 <= status_code < 600:
            self.status = "server_error"
        else:
            self.status = str(status_code)
