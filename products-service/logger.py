import logging
import sys
import os
from pythonjsonlogger import jsonlogger
from contextvars import ContextVar

# Context variable for trace_id
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")

# Configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT = os.getenv("LOG_FORMAT", "json").lower()
SERVICE_NAME = "products-service"


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with service name and trace_id"""

    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        log_record['service'] = SERVICE_NAME
        log_record['timestamp'] = self.formatTime(record, self.datefmt)
        log_record['level'] = record.levelname

        # Add trace_id if available
        trace_id = trace_id_var.get()
        if trace_id:
            log_record['trace_id'] = trace_id


def setup_logger(name: str = SERVICE_NAME) -> logging.Logger:
    """Setup and configure logger with JSON format"""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL))

    # Remove existing handlers
    logger.handlers = []

    # Console handler
    handler = logging.StreamHandler(sys.stdout)

    if LOG_FORMAT == "json":
        formatter = CustomJsonFormatter(
            '%(timestamp)s %(level)s %(service)s %(name)s %(message)s'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


# Create default logger
logger = setup_logger()


def get_logger(name: str = None) -> logging.Logger:
    """Get logger instance"""
    if name:
        return logging.getLogger(f"{SERVICE_NAME}.{name}")
    return logger


def set_trace_id(trace_id: str):
    """Set trace_id for current context"""
    trace_id_var.set(trace_id)


def get_trace_id() -> str:
    """Get current trace_id"""
    return trace_id_var.get()
