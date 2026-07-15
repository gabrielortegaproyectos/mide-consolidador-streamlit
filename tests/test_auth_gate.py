from __future__ import annotations

from streamlit.testing.v1 import AppTest

_PASSWORD_INPUT_KEY = "mide_login_password_input"
_SUBMIT_BUTTON_KEY = "FormSubmitter:mide_login_form-Ingresar"
_SESSION_STATE_KEY = "mide_authenticated"


def _new_app(password: str | None = "clave-mide") -> AppTest:
    at = AppTest.from_file("app/main.py")
    if password is not None:
        at.secrets["auth"] = {"password": password}
    return at


def _is_authenticated(at: AppTest) -> bool:
    if _SESSION_STATE_KEY not in at.session_state:
        return False
    return bool(at.session_state[_SESSION_STATE_KEY])


def test_unauthenticated_session_blocks_panel_manual_and_integrations() -> None:
    at = _new_app().run()

    assert at.exception == []
    assert len(at.tabs) == 0
    assert len(at.text_input) == 1
    assert _is_authenticated(at) is False


def test_correct_password_unlocks_main_content() -> None:
    at = _new_app().run()

    at.text_input(key=_PASSWORD_INPUT_KEY).set_value("clave-mide")
    at.button(key=_SUBMIT_BUTTON_KEY).click().run()

    assert at.exception == []
    assert at.session_state[_SESSION_STATE_KEY] is True
    assert len(at.tabs) == 2


def test_incorrect_password_stays_blocked_with_generic_message() -> None:
    at = _new_app().run()

    at.text_input(key=_PASSWORD_INPUT_KEY).set_value("clave-incorrecta")
    at.button(key=_SUBMIT_BUTTON_KEY).click().run()

    assert at.exception == []
    assert _is_authenticated(at) is False
    assert len(at.tabs) == 0
    assert any("incorrecta" in error.value for error in at.error)


def test_missing_secret_blocks_safely_without_login_form() -> None:
    at = _new_app(password=None).run()

    assert at.exception == []
    assert len(at.tabs) == 0
    assert len(at.text_input) == 0
    assert any("no tiene configurada" in error.value for error in at.error)


def test_access_persists_across_reruns_in_same_session() -> None:
    at = _new_app().run()
    at.text_input(key=_PASSWORD_INPUT_KEY).set_value("clave-mide")
    at.button(key=_SUBMIT_BUTTON_KEY).click().run()

    at.run()

    assert len(at.tabs) == 2
    assert at.session_state[_SESSION_STATE_KEY] is True


def test_new_session_requires_password_again() -> None:
    at = _new_app().run()
    at.text_input(key=_PASSWORD_INPUT_KEY).set_value("clave-mide")
    at.button(key=_SUBMIT_BUTTON_KEY).click().run()
    assert len(at.tabs) == 2

    fresh_session = _new_app().run()

    assert len(fresh_session.tabs) == 0
    assert _is_authenticated(fresh_session) is False


def test_logout_clears_authentication_and_blocks_again() -> None:
    at = _new_app().run()
    at.text_input(key=_PASSWORD_INPUT_KEY).set_value("clave-mide")
    at.button(key=_SUBMIT_BUTTON_KEY).click().run()
    assert len(at.tabs) == 2

    at.sidebar.button[0].click().run()

    assert at.exception == []
    assert at.session_state[_SESSION_STATE_KEY] is False
    assert len(at.tabs) == 0
    assert len(at.text_input) == 1


def test_submitted_password_is_not_retained_in_session_state() -> None:
    at = _new_app().run()
    at.text_input(key=_PASSWORD_INPUT_KEY).set_value("clave-mide")
    at.button(key=_SUBMIT_BUTTON_KEY).click().run()

    stored_state = at.session_state.filtered_state
    assert _PASSWORD_INPUT_KEY not in stored_state
    assert stored_state == {_SESSION_STATE_KEY: True}
