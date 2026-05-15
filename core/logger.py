import json
import logging
from contextvars import ContextVar
from logging.config import dictConfig

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
path_var: ContextVar[str] = ContextVar("path", default="-")


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.path = path_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
            "path": getattr(record, "path", "-"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def configure_logging() -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "request_context": {
                    "()": "core.logger.RequestContextFilter",
                }
            },
            "formatters": {
                "json": {
                    "()": "core.logger.JsonFormatter",
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "filters": ["request_context"],
                }
            },
            "root": {
                "level": "INFO",
                "handlers": ["default"],
            },
        }
    )


def set_request_context(request_id: str, path: str) -> None:
    request_id_var.set(request_id)
    path_var.set(path)


def clear_request_context() -> None:
    request_id_var.set("-")
    path_var.set("-")
