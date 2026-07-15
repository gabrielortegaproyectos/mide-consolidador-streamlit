from __future__ import annotations

import streamlit as st

from app.services import auth

_LOGIN_FORM_KEY = "mide_login_form"
_PASSWORD_INPUT_KEY = "mide_login_password_input"


def render_access_gate() -> bool:
    if auth.is_authenticated():
        _render_logout_control()
        return True

    _render_login_form(auth.get_auth_config_status())
    return False


def _render_login_form(status: auth.AuthConfigStatus) -> None:
    st.markdown("## Acceso restringido")
    st.caption(
        "Ingresa la contrasena compartida del equipo MIDE para habilitar la "
        "aplicacion."
    )

    if not status.configured:
        st.error(
            "La aplicacion no tiene configurada la contrasena de acceso. "
            "Contacta al equipo responsable de MIDE para configurar el "
            "secreto antes de continuar."
        )
        return

    with st.form(_LOGIN_FORM_KEY, clear_on_submit=True):
        password = st.text_input(
            "Contrasena", type="password", key=_PASSWORD_INPUT_KEY
        )
        submitted = st.form_submit_button("Ingresar")

    if not submitted:
        return

    if auth.verify_password(password, status.expected_password):
        auth.mark_authenticated()
        st.rerun()
    else:
        st.error("Contrasena incorrecta. Intenta nuevamente.")


def _render_logout_control() -> None:
    with st.sidebar:
        st.button("Cerrar sesion", on_click=_handle_logout)


def _handle_logout() -> None:
    auth.clear_authentication()
