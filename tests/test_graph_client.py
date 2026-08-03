import json
from unittest.mock import MagicMock, patch

from core.graph_client import GraphClient


def _make_client(token="fake-token"):
    auth = MagicMock()
    auth.get_cached_access_token.return_value = token
    return GraphClient(auth_service=auth), auth


class _FakeHTTPResponse:
    def __init__(self, status, body):
        self.status = status
        self._body = body.encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class TestAuthGuard:

    def test_no_token_returns_error_without_network_call(self):
        client, auth = _make_client(token=None)
        with patch("urllib.request.urlopen") as mock_open:
            ok, result = client.list_recent_messages()
            mock_open.assert_not_called()
        assert ok is False
        assert "sesión" in result.lower()


class TestListRecentMessages:

    @patch("urllib.request.urlopen")
    def test_success(self, mock_open):
        client, _ = _make_client()
        mock_open.return_value = _FakeHTTPResponse(200, json.dumps({"value": [{"id": "1"}, {"id": "2"}]}))

        ok, messages = client.list_recent_messages(top=5)

        assert ok is True
        assert len(messages) == 2

    @patch("urllib.request.urlopen")
    def test_applies_filter_query(self, mock_open):
        client, _ = _make_client()
        mock_open.return_value = _FakeHTTPResponse(200, json.dumps({"value": []}))

        client.list_recent_messages(filter_query="from/emailAddress/address eq 'a@b.com'")

        called_request = mock_open.call_args[0][0]
        assert "%24filter" in called_request.full_url or "$filter" in called_request.full_url


class TestCreateListItem:

    @patch("urllib.request.urlopen")
    def test_success(self, mock_open):
        client, _ = _make_client()
        mock_open.return_value = _FakeHTTPResponse(
            201, json.dumps({"id": "42", "webUrl": "https://sp/item/42"})
        )

        ok, result = client.create_list_item("site1", "list1", {"Title": "Falla impresora"})

        assert ok is True
        assert result["id"] == "42"

    def test_http_error_returns_message(self):
        import urllib.error

        client, _ = _make_client()

        class _FakeError(urllib.error.HTTPError):
            def read(self):
                return json.dumps({"error": {"message": "columna inválida"}}).encode("utf-8")

        with patch("urllib.request.urlopen", side_effect=_FakeError("url", 400, "Bad Request", {}, None)):
            ok, result = client.create_list_item("site1", "list1", {"Bad": "x"})

        assert ok is False
        assert "columna inválida" in result


class TestResolveSiteId:

    @patch("urllib.request.urlopen")
    def test_success(self, mock_open):
        client, _ = _make_client()
        mock_open.return_value = _FakeHTTPResponse(200, json.dumps({"id": "abc-site-id"}))

        ok, site_id = client.resolve_site_id("lavianda.sharepoint.com", "/sites/IT")

        assert ok is True
        assert site_id == "abc-site-id"
