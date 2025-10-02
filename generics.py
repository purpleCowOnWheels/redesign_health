import hashlib


def sha256_hash(text: str) -> str:
    """
    Takes a string and returns its SHA256 hash as a hexadecimal string.

    Args:
        text: The input string to hash

    Returns:
        The SHA256 hash as a hexadecimal string
    """
    return hashlib.sha256(text.encode('utf-8')).hexdigest()