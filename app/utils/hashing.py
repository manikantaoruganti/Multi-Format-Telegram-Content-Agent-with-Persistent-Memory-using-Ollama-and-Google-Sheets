import hashlib

def generate_sha256(data: str) -> str:
    """
    Generates a SHA256 hash for the given string data.
    """
    return hashlib.sha256(data.encode('utf-8')).hexdigest()
