"""
AES-256-GCM End-to-End Encryption Module
Provides high-speed authenticated encryption and decryption for file chunks, streams, and text payloads.
"""

import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

NONCE_SIZE = 12  # 96-bit standard nonce for AES-GCM
KEY_SIZE = 32    # 256-bit AES key

def generate_key() -> str:
    """Generate a random 256-bit AES key encoded as URL-safe Base64."""
    raw_key = AESGCM.generate_key(bit_length=256)
    return base64.urlsafe_b64encode(raw_key).decode("utf-8")

def derive_key_from_passphrase(passphrase: str, salt: bytes = b"localshare_aes_gcm_salt") -> bytes:
    """Derive a 256-bit key from a human passphrase using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=KEY_SIZE,
        salt=salt,
        iterations=100_000,
    )
    return kdf.derive(passphrase.encode("utf-8"))

def normalize_key(key_input: str | bytes) -> bytes:
    """Convert string or base64 key input into 32 raw bytes."""
    if isinstance(key_input, bytes):
        if len(key_input) == KEY_SIZE:
            return key_input
        key_input = key_input.decode("utf-8", errors="ignore")
    
    clean_str = str(key_input).strip()
    if not clean_str:
        raise ValueError("Encryption key is empty.")

    # Try base64 decode
    try:
        decoded = base64.urlsafe_b64decode(clean_str.encode("utf-8"))
        if len(decoded) == KEY_SIZE:
            return decoded
    except Exception:
        pass

    # If raw passphrase given, derive 32-byte key
    return derive_key_from_passphrase(clean_str)

def encrypt_chunk(data: bytes, key: str | bytes) -> bytes:
    """
    Encrypt a data chunk using AES-256-GCM.
    Output format: [12-byte Nonce][Ciphertext + 16-byte Auth Tag]
    """
    key_bytes = normalize_key(key)
    aesgcm = AESGCM(key_bytes)
    nonce = os.urandom(NONCE_SIZE)
    ciphertext = aesgcm.encrypt(nonce, data, None)
    return nonce + ciphertext

def decrypt_chunk(encrypted_data: bytes, key: str | bytes) -> bytes:
    """
    Decrypt and authenticate an AES-256-GCM data chunk.
    Input format: [12-byte Nonce][Ciphertext + 16-byte Auth Tag]
    """
    if len(encrypted_data) < NONCE_SIZE + 16:
        raise ValueError("Ciphertext too short or corrupted.")
    
    key_bytes = normalize_key(key)
    aesgcm = AESGCM(key_bytes)
    nonce = encrypted_data[:NONCE_SIZE]
    ciphertext = encrypted_data[NONCE_SIZE:]
    return aesgcm.decrypt(nonce, ciphertext, None)

def encrypt_text(text: str, key: str | bytes) -> str:
    """Encrypt plain text string and return URL-safe base64 string."""
    encrypted_bytes = encrypt_chunk(text.encode("utf-8"), key)
    return base64.urlsafe_b64encode(encrypted_bytes).decode("utf-8")

def decrypt_text(encrypted_b64: str, key: str | bytes) -> str:
    """Decrypt URL-safe base64 string and return plain text."""
    encrypted_bytes = base64.urlsafe_b64decode(encrypted_b64.encode("utf-8"))
    plaintext_bytes = decrypt_chunk(encrypted_bytes, key)
    return plaintext_bytes.decode("utf-8")
