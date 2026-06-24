from hashlib import sha256


def generate_text_hash(text: str) -> str:
    hash_text = str(text) + 'None'
    return sha256(hash_text.encode()).hexdigest()