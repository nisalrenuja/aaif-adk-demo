# ADK discovers the agent by importing this package, so this import is the
# entry point rather than dead code. __all__ declares that intent.
from . import agent

__all__ = ["agent"]
