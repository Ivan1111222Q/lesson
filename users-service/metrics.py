from prometheus_client import Counter, Gauge, Histogram
import time
import os
import psutil
import threading


# -------------------
# 📊 РЕСУРСНЫЕ МЕТРИКИ
# -------------------

cpu_usage_gauge = Gauge("app_cpu_usage_percent", "CPU usage percent")
mem_usage_gauge = Gauge("app_memory_usage_mib", "Memory usage in MiB")
cpu_limit_gauge = Gauge("app_cpu_limit", "CPU limit (cores)")
mem_limit_gauge = Gauge("app_memory_limit_mib", "Memory limit (MiB)")


def get_resource_metrics():
    """Получает текущие показатели CPU/RAM и лимиты из окружения"""
    cpu_limit = os.getenv("CPU_LIMIT")
    mem_limit = os.getenv("MEMORY_LIMIT")

    process = psutil.Process()
    cpu_usage = process.cpu_percent(interval=1)
    mem_usage = process.memory_info().rss / (1024 * 1024)  # в MiB

    return {
        "cpu_limit": cpu_limit,
        "memory_limit": mem_limit,
        "cpu_usage_percent": cpu_usage,
        "memory_usage_mib": mem_usage
    }


def update_metrics():
    """Обновляет значения Gauge-метрик по ресурсам"""
    data = get_resource_metrics()

    cpu_usage_gauge.set(data["cpu_usage_percent"])
    mem_usage_gauge.set(data["memory_usage_mib"])

    # CPU лимит может быть в формате '1000m', конвертируем в число
    if data["cpu_limit"]:
        cpu_limit = (
            float(data["cpu_limit"].replace("m", "")) / 1000
            if "m" in data["cpu_limit"]
            else float(data["cpu_limit"])
        )
        cpu_limit_gauge.set(cpu_limit)

    if data["memory_limit"]:
        mem_value = data["memory_limit"].replace("Mi", "").replace("Gi", "")
        mem_limit_gauge.set(float(mem_value))


def start_metrics_updater(interval: int = 10):
    """Запускает фоновый поток для регулярного обновления метрик"""
    def loop():
        while True:
            try:
                update_metrics()
            except Exception as e:
                print(f"[metrics] Failed to update: {e}")
            time.sleep(interval)

    threading.Thread(target=loop, daemon=True).start()


# Business metrics
users_registered_total = Counter(
    'users_registered_total',
    'Total number of users registered'
)

user_logins_total = Counter(
    'user_logins_total',
    'Total number of user login attempts',
    ['result']  # result: success/failed
)

user_logouts_total = Counter(
    'user_logouts_total',
    'Total number of user logouts'
)

active_users_gauge = Gauge(
    'active_users_total',
    'Current total number of registered users'
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
