import asyncio
import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from auth import captcha


def _request(host: str = "127.0.0.1"):
    return SimpleNamespace(client=SimpleNamespace(host=host))


@pytest.fixture(autouse=True)
def _reset_recaptcha_settings(monkeypatch):
    monkeypatch.setattr(captcha.settings, "recaptcha_site_key", "")
    monkeypatch.setattr(captcha.settings, "recaptcha_secret_key", "")
    captcha._LOCAL_CAPTCHAS.clear()
    yield
    captcha._LOCAL_CAPTCHAS.clear()


def test_captcha_config_uses_google_when_keys_are_configured(monkeypatch):
    monkeypatch.setattr(captcha.settings, "recaptcha_site_key", "site-key")
    monkeypatch.setattr(captcha.settings, "recaptcha_secret_key", "secret-key")

    assert captcha.captcha_config() == {"provider": "google", "site_key": "site-key"}


def test_captcha_config_falls_back_to_local_without_keys():
    assert captcha.captcha_config() == {"provider": "local", "site_key": ""}


def test_local_captcha_verifies_expected_answer():
    challenge = captcha.create_local_captcha()
    expected_answer = captcha._LOCAL_CAPTCHAS[challenge["captcha_id"]][0]

    captcha.verify_local_captcha(challenge["captcha_id"], expected_answer)

    assert challenge["captcha_id"] not in captcha._LOCAL_CAPTCHAS


def test_google_recaptcha_requires_token(monkeypatch):
    monkeypatch.setattr(captcha.settings, "recaptcha_site_key", "site-key")
    monkeypatch.setattr(captcha.settings, "recaptcha_secret_key", "secret-key")

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(captcha.verify_login_captcha({"recaptcha_token": ""}, _request()))

    assert exc_info.value.detail == "Please complete the reCAPTCHA."


def test_google_recaptcha_accepts_success_response(monkeypatch):
    monkeypatch.setattr(captcha.settings, "recaptcha_site_key", "site-key")
    monkeypatch.setattr(captcha.settings, "recaptcha_secret_key", "secret-key")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"success": True}).encode("utf-8")

    def fake_urlopen(google_request, timeout):
        assert timeout == 5
        assert google_request.full_url == "https://www.google.com/recaptcha/api/siteverify"
        return FakeResponse()

    monkeypatch.setattr(captcha.request, "urlopen", fake_urlopen)

    asyncio.run(captcha.verify_login_captcha({"recaptcha_token": "token"}, _request()))


def test_google_recaptcha_rejects_failure_response(monkeypatch):
    monkeypatch.setattr(captcha.settings, "recaptcha_site_key", "site-key")
    monkeypatch.setattr(captcha.settings, "recaptcha_secret_key", "secret-key")

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return json.dumps({"success": False}).encode("utf-8")

    monkeypatch.setattr(captcha.request, "urlopen", lambda *_args, **_kwargs: FakeResponse())

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(captcha.verify_login_captcha({"recaptcha_token": "token"}, _request()))

    assert exc_info.value.detail == "reCAPTCHA verification failed. Please try again."
