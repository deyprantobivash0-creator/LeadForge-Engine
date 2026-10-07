"""Minimal secret redaction for existing application and migration logging."""
import logging
import re
from urllib.parse import quote, quote_plus
from sqlalchemy.engine import make_url
from backend.core.config import settings, secret_value


def redact(value: str) -> str:
    secrets = [secret_value(getattr(settings, key)) for key in
               ("DATABASE_URL", "GEMINI_API_KEY", "DEEPSEEK_API_KEY", "HUBSPOT_ACCESS_TOKEN")]
    try:
        password = make_url(secrets[0]).password
        if password:
            secrets.extend((password, quote(password, safe=""), quote_plus(password)))
    except Exception:
        pass
    for secret in sorted(set(filter(None, secrets)), key=len, reverse=True):
        value = value.replace(secret, "[REDACTED]")
    return re.sub(r"\b(?:postgres(?:ql)?(?:\+\w+)?|https?)://[^\s/@]+:[^\s/@]+@[^\s]+", "[REDACTED URL]", value)


class SecretFilter(logging.Filter):
    def filter(self, record):
        record.msg = redact(record.getMessage())
        record.args = ()
        if record.exc_info:
            # Keep the exception category without driver messages or SQL parameters.
            record.msg += f" | exception={record.exc_info[0].__name__}"
            record.exc_info = None
            record.exc_text = None
        return True


def install_secret_filters():
    loggers = [logging.getLogger(), *[item for item in logging.Logger.manager.loggerDict.values() if isinstance(item, logging.Logger)]]
    handlers = {handler for logger in loggers for handler in logger.handlers}
    for handler in handlers:
        if not any(isinstance(item, SecretFilter) for item in handler.filters):
            handler.addFilter(SecretFilter())
