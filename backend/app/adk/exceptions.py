"""
ADK Exceptions Module

Custom exceptions for the ADK module to provide clear error handling.
"""


class ADKError(Exception):
    """Base exception for ADK errors."""
    pass


class ADKNotEnabledError(ADKError):
    """Raised when ADK is not enabled but a feature is requested."""
    def __init__(self, message: str = "ADK is not enabled"):
        self.message = message
        super().__init__(self.message)


class ADKTimeoutError(ADKError):
    """Raised when agent execution times out."""
    def __init__(self, timeout_seconds: int, message: str = None):
        self.timeout_seconds = timeout_seconds
        self.message = message or f"Agent execution timed out after {timeout_seconds} seconds"
        super().__init__(self.message)


class ADKAgentError(ADKError):
    """Raised when agent execution fails."""
    def __init__(self, agent_name: str, error: Exception):
        self.agent_name = agent_name
        self.original_error = error
        self.message = f"Agent '{agent_name}' failed: {str(error)}"
        super().__init__(self.message)


class ADKModelError(ADKError):
    """Raised when there's an issue with the AI model."""
    def __init__(self, model_id: str, message: str):
        self.model_id = model_id
        self.message = f"Model '{model_id}' error: {message}"
        super().__init__(self.message)


class ADKRateLimitError(ADKError):
    """Raised when API rate limit is exceeded."""
    def __init__(self, provider: str = "AI Provider"):
        self.provider = provider
        self.message = f"{provider} rate limit exceeded (429). Please wait and try again."
        super().__init__(self.message)
