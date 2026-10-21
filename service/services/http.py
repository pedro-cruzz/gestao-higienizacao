import ssl
from functools import lru_cache

import certifi


@lru_cache(maxsize=1)
def get_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return context
