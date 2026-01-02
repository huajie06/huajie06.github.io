---
title: Python logging guide
pubDate: "2026-01-01"
description: "python logging note for myself"
tags: ["python", "logging"]
---

## The Quick Start (Scripts)

For single-file scripts or quick debugging, use `basicConfig`.

**Key Rule:** `basicConfig` must be called **once** and **before** any other logging calls.

```python
import logging

# Configure immediately
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='app.log' # Optional: Remove this line to print to console
)

logging.debug("This won't show (Level < INFO)")
logging.info("Script processing started")
logging.warning("Disk space low")
logging.error("Database connection failed")
```

## The Advanced Version

Assume the entry file `main.py`, it has some connection and get user function. Each of these function have things to log.

```python
import logging
from .logging_config import setup_logging_dict
from .make_connection import make_connection
from .get_users import get_user

logger = logging.getLogger(__name__)


if __name__ == "__main__":
    setup_logging_dict()
    print(make_connection())
    print(get_user(1))
```

I can set up the logging using a dictionary

```python
import logging
import logging.config # separate import for `logging.config.dictConfig`
from pathlib import Path
import sys


class ColorizedFormatter(logging.Formatter):
    """a simple color fomatter for terminal"""
    grey = "\x1b[38;20m"
    purple = "\x1b[35;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    FORMATS = {
        logging.DEBUG: purple + fmt + reset,
        logging.INFO: grey + fmt + reset,
        logging.WARNING: yellow + fmt + reset,
        logging.ERROR: red + fmt + reset,
        logging.CRITICAL: bold_red + fmt + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def setup_logging_dict():
    """the actual setup for the logger"""
    log_path = Path("learn_logging") / "app.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)


    # 1. version is required and cannot be a float
    # 2. disable_existing_loggers is also required and othewise it would slient
    # 3. it basically has 3 component: the formatter, handler, and logger itself (for different module/package)
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {"format": "%(asctime)s - %(module)s - %(levelname)s - %(message)s"},
            "console_format": {"()": ColorizedFormatter},
        },
        "handlers": {
            "file": {
                "class": "logging.FileHandler",
                "level": "DEBUG",
                "formatter": "standard",
                "filename": str(log_path),
                "mode": "w",
            },
            "console": {
                "class": "logging.StreamHandler",
                "level": "DEBUG",
                "formatter": "console_format",
                "stream": sys.stdout,
            },
        },
        "root": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
        },
        "loggers": {
            "my_cool_module": {
                "level": "DEBUG",
                "propagate": True,
            },
            "urllib3": {
                "level": "WARNING",
                "propagate": True,
            },
        },
    }

    logging.config.dictConfig(config=config)
```

This way, the config is in a center place, and for each script I would only need to do `logger = logging.getLogger(__name__)`, which would be a lot easier to manage.
