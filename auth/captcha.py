import json
import secrets
import time
from urllib import parse, request

from fastapi import HTTPException, Request, status

from backend.config.app_config import settings

_CAPTCHA_TTL_SECONDS = 180
_LOCAL_CAPTCHAS: dict[str, tuple[str, float]] = {}


def captcha_config() -> dict:
    if settings.recaptcha_site_key and settings.recaptcha_secret_key:
        return {"provider": "google", "site_key": settings.recaptcha_site_key}
    return {"provider": "local", "site_key": ""}


def create_local_captcha() -> dict:
    cleanup_expired_captchas()
    left = secrets.randbelow(8) + 2
    right = secrets.randbelow(8) + 2
    captcha_id = secrets.token_urlsafe(18)
    _LOCAL_CAPTCHAS[captcha_id] = (str(left + right), time.time() + _CAPTCHA_TTL_SECONDS)
    return {"captcha_id": captcha_id, "question": f"{left} + {right} = ?"}


async def verify_login_captcha(payload: dict, request_obj: Request) -> None:
    if settings.recaptcha_site_key and settings.recaptcha_secret_key:
        await verify_google_recaptcha(str(payload.get("recaptcha_token") or ""), request_obj)
        return
    verify_local_captcha(str(payload.get("captcha_id") or ""), str(payload.get("captcha_answer") or ""))


async def verify_google_recaptcha(token: str, request_obj: Request) -> None:
    if not token:
        raise captcha_error("Please complete the reCAPTCHA.")

    form = parse.urlencode(
        {
            "secret": settings.recaptcha_secret_key,
            "response": token,
            "remoteip": request_obj.client.host if request_obj.client else "",
        }
    ).encode()
    google_request = request.Request(
        "https://www.google.com/recaptcha/api/siteverify",
        data=form,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with request.urlopen(google_request, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise captcha_error("Could not verify reCAPTCHA. Please try again.") from exc

    if not result.get("success"):
        raise captcha_error("reCAPTCHA verification failed. Please try again.")


def verify_local_captcha(captcha_id: str, answer: str) -> None:
    cleanup_expired_captchas()
    expected = _LOCAL_CAPTCHAS.pop(captcha_id, None)
    if not captcha_id or not answer or not expected:
        raise captcha_error("Please complete the CAPTCHA.")

    expected_answer, expires_at = expected
    if time.time() > expires_at:
        raise captcha_error("CAPTCHA expired. Please try again.")
    if answer.strip() != expected_answer:
        raise captcha_error("CAPTCHA answer is incorrect.")


def cleanup_expired_captchas() -> None:
    now = time.time()
    expired = [captcha_id for captcha_id, (_, expires_at) in _LOCAL_CAPTCHAS.items() if expires_at < now]
    for captcha_id in expired:
        _LOCAL_CAPTCHAS.pop(captcha_id, None)


def captcha_error(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)
