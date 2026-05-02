"""Session management — one Claude Agent SDK client per active session.

For Phase 1 we use a simple per-request session pattern. Phase 2 will add
the long-running 1-hour session reuse + replay buffer pattern from
claude-code-sdk-1/src/session_management/.
"""

from .manager import SessionManager
from .types import QueryItem, SessionContext

__all__ = ["SessionManager", "SessionContext", "QueryItem"]
