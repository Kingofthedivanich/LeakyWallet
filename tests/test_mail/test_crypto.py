from LeakyWallet.mail.crypto import decrypt_token, encrypt_token


def test_encrypt_decrypt_roundtrip() -> None:
    plaintext = "super-secret-token-value"
    ciphertext = encrypt_token(plaintext)

    assert ciphertext != plaintext
    assert decrypt_token(ciphertext) == plaintext


def test_encrypt_is_not_deterministic() -> None:
    plaintext = "same-input"
    assert encrypt_token(plaintext) != encrypt_token(plaintext)
