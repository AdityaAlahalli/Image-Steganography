from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import os, base64

# 128‑bit salt + 12‑byte nonce lengths are standard
PBKDF2_SALT_SIZE = 16
AES_NONCE_SIZE = 12
KDF_ITERATIONS = 100_000
AES_KEY_SIZE = 32  # 256 bits

def derive_key(password: str, salt: bytes) -> bytes:
    # Derive an AES key using PBKDF2
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=AES_KEY_SIZE,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )
    return kdf.derive(password.encode())

def encrypt_data(data: bytes, password: str) -> bytes:
    # Format: salt + nonce + ciphertext + tag
    salt = os.urandom(PBKDF2_SALT_SIZE)
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    nonce = os.urandom(AES_NONCE_SIZE)
    encrypted = aesgcm.encrypt(nonce, data, None)
    return salt + nonce + encrypted

def decrypt_data(token: bytes, password: str) -> bytes:
    # Parse salt, nonce, encrypted payload, verify integrity
    salt = token[:PBKDF2_SALT_SIZE]
    nonce = token[PBKDF2_SALT_SIZE:PBKDF2_SALT_SIZE + AES_NONCE_SIZE]
    ciphertext = token[PBKDF2_SALT_SIZE + AES_NONCE_SIZE:]
    key = derive_key(password, salt)
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)
