import secrets


def generate_request_id() -> str:
    """Generate a unique identifier for an API request."""
    return secrets.token_hex(16)


def mask_secret(value: str | None) -> str:
    """
    Safely mask a secret before logging or displaying it.
    Never expose the complete credential.
    """
    if not value:
        return ""

    if len(value) <= 8:
        return "********"

    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"