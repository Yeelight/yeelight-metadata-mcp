def normalize_authorization_header(value: str) -> str:
    token = value.strip()
    if token.lower().startswith("bearer "):
        return token
    return f"Bearer {token}"
