from unittest.mock import MagicMock, patch

from core.microsoft_auth import SCOPES, TICKET_SCOPES, MicrosoftAuthService


class TestScopeSeparation:
    """
    Regresión: en algún momento SCOPES incluyó Mail.Read y Sites.ReadWrite.All
    junto con User.Read, lo que rompió el login básico para cuentas sin
    consentimiento de administrador otorgado (ver captura de "Se necesita la
    aprobación del administrador"). El login básico debe pedir SIEMPRE solo
    lo mínimo (User.Read); los scopes de tickets se piden aparte, solo cuando
    hace falta.
    """

    def test_base_scopes_is_only_user_read(self):
        assert SCOPES == ["User.Read"]

    def test_ticket_scopes_does_not_include_user_read(self):
        assert "User.Read" not in TICKET_SCOPES

    def test_base_and_ticket_scopes_are_disjoint(self):
        assert set(SCOPES).isdisjoint(set(TICKET_SCOPES))


class TestLoginUsesBaseScopesByDefault:

    @patch("core.microsoft_auth.is_configured", return_value=True)
    def test_login_with_device_code_defaults_to_base_scopes(self, _mock_configured):
        service = MicrosoftAuthService()
        fake_app = MagicMock()
        fake_app.initiate_device_flow.return_value = {"user_code": "ABC123", "verification_uri": "https://x"}
        fake_app.acquire_token_by_device_flow.return_value = {"access_token": "tok"}

        with patch.object(service, "_build_app", return_value=fake_app):
            service.login_with_device_code(on_code_ready=lambda *_: None)

        fake_app.initiate_device_flow.assert_called_once_with(scopes=SCOPES)

    @patch("core.microsoft_auth.is_configured", return_value=True)
    def test_login_with_device_code_can_request_ticket_scopes_explicitly(self, _mock_configured):
        service = MicrosoftAuthService()
        fake_app = MagicMock()
        fake_app.initiate_device_flow.return_value = {"user_code": "ABC123", "verification_uri": "https://x"}
        fake_app.acquire_token_by_device_flow.return_value = {"access_token": "tok"}

        with patch.object(service, "_build_app", return_value=fake_app):
            service.request_ticket_scopes(on_code_ready=lambda *_: None)

        called_scopes = fake_app.initiate_device_flow.call_args.kwargs["scopes"]
        assert set(called_scopes) == set(SCOPES + TICKET_SCOPES)

    @patch("core.microsoft_auth.is_configured", return_value=True)
    def test_try_silent_login_defaults_to_base_scopes(self, _mock_configured):
        service = MicrosoftAuthService()
        fake_app = MagicMock()
        fake_app.get_accounts.return_value = [{"username": "a@b.com"}]
        fake_app.acquire_token_silent.return_value = {"access_token": "tok"}

        with patch.object(service, "_build_app", return_value=fake_app):
            service.try_silent_login()

        fake_app.acquire_token_silent.assert_called_once_with(SCOPES, account={"username": "a@b.com"})

    @patch("core.microsoft_auth.is_configured", return_value=True)
    def test_get_cached_access_token_can_request_ticket_scopes(self, _mock_configured):
        service = MicrosoftAuthService()
        fake_app = MagicMock()
        fake_app.get_accounts.return_value = [{"username": "a@b.com"}]
        fake_app.acquire_token_silent.return_value = {"access_token": "tok"}

        with patch.object(service, "_build_app", return_value=fake_app):
            token = service.get_cached_access_token(scopes=SCOPES + TICKET_SCOPES)

        assert token == "tok"
        called_scopes = fake_app.acquire_token_silent.call_args[0][0]
        assert set(called_scopes) == set(SCOPES + TICKET_SCOPES)

    @patch("core.microsoft_auth.is_configured", return_value=True)
    def test_admin_consent_error_gets_friendly_message(self, _mock_configured):
        service = MicrosoftAuthService()
        fake_app = MagicMock()
        fake_app.initiate_device_flow.return_value = {"user_code": "ABC123", "verification_uri": "https://x"}
        fake_app.acquire_token_by_device_flow.return_value = {
            "error": "access_denied",
            "error_description": "AADSTS65001: admin approval required",
        }

        with patch.object(service, "_build_app", return_value=fake_app):
            success, result, message = service.login_with_device_code(on_code_ready=lambda *_: None)

        assert success is False
        assert "administrador" in message.lower()
