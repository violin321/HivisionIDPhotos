from __future__ import annotations


class AIEnhanceError(Exception):
    """Base error for ai_enhance plugin."""

    def __init__(self, message: str, error_code: str = "AI_ENHANCE_ERROR"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class AIEnhanceConfigError(AIEnhanceError):
    def __init__(self, message: str = "AI enhance provider is not configured"):
        super().__init__(message, error_code="PROVIDER_NOT_CONFIGURED")


class AIEnhanceConsentError(AIEnhanceError):
    def __init__(self, message: str = "User consent is required before uploading image to AI provider"):
        super().__init__(message, error_code="CONSENT_REQUIRED")


class AIEnhanceProviderError(AIEnhanceError):
    def __init__(self, message: str = "AI provider request failed", error_code: str = "PROVIDER_REQUEST_FAILED"):
        super().__init__(message, error_code=error_code)


class AIEnhanceValidationError(AIEnhanceError):
    def __init__(self, message: str = "Invalid AI enhance request"):
        super().__init__(message, error_code="INVALID_REQUEST")
