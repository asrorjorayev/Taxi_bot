import json
import logging


class StructuredLogger:
    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _log(self, level: int, event: str, **kwargs) -> None:
        if kwargs:
            message = json.dumps({"event": event, **kwargs}, ensure_ascii=False, default=str)
        else:
            message = event
        self._logger.log(level, message)

    def info(self, event: str, **kwargs) -> None:
        self._log(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs) -> None:
        self._log(logging.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs) -> None:
        self._log(logging.ERROR, event, **kwargs)


def get_logger(name: str) -> StructuredLogger:
    return StructuredLogger(name)
