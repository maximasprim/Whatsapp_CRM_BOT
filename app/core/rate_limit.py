from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

# Shared limiter instance. main.py attaches this to app.state.limiter and
# registers the RateLimitExceeded handler; individual route modules import
# this same instance so their @limiter.limit(...) decorators share state
# with it instead of creating disconnected limiters.
limiter = Limiter(key_func=get_remote_address)
