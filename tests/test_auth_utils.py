from auth.auth_utils import BCRYPT_ROUNDS, hash_password, verify_password


def test_hash_same_password_generates_different_hashes_and_verifies():
    password = "Vaish@1234"

    hash_one = hash_password(password)
    hash_two = hash_password(password)

    assert hash_one != hash_two
    assert verify_password(password, hash_one)
    assert verify_password(password, hash_two)


def test_verify_password_fails_for_wrong_password():
    password = "Vaish@1234"
    wrong_password = "Wrong@1234"
    hashed = hash_password(password)

    assert not verify_password(wrong_password, hashed)


def test_bcrypt_rounds_meets_minimum_security_baseline():
    assert BCRYPT_ROUNDS >= 12
