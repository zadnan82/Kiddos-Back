class ContentGenerationException(Exception):
    """Raised when there is an error during content generation."""

    pass


class ContentNotFoundException(Exception):
    """Raised when the requested content is not found."""

    pass


class InsufficientCreditsException(Exception):
    """Raised when the user does not have enough credits to perform an action."""

    pass


class InvalidContentRequestException(Exception):
    """Raised when the content request is invalid or malformed."""

    pass
