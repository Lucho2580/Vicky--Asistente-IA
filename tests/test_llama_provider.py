import json
from unittest.mock import patch

import pytest

from ai.llama import DEFAULT_MODEL, LlamaProvider


def _tags_body(models=None):
    models = models or [DEFAULT_MODEL]
    return json.dumps({"models": [{"name": m} for m in models]})


class TestConnect:

    @patch("ai.base_provider.AIProvider._http_get")
    def test_connect_success_model_available(self, mock_get):
        mock_get.return_value = (200, _tags_body(), None)
        provider = LlamaProvider()

        connected, message = provider.connect(endpoint="http://nas:11434")

        assert connected is True
        assert provider.is_connected() is True
        assert "correctamente" in message

    @patch("ai.base_provider.AIProvider._http_get")
    def test_connect_success_but_model_missing(self, mock_get):
        mock_get.return_value = (200, _tags_body(models=["otro-modelo"]), None)
        provider = LlamaProvider()

        connected, message = provider.connect(endpoint="http://nas:11434")

        assert connected is True  # el servidor responde, aunque falte el modelo
        assert "ollama pull" in message

    @patch("ai.base_provider.AIProvider._http_get")
    def test_connect_server_unreachable(self, mock_get):
        mock_get.return_value = (None, None, "No se pudo conectar: timeout")
        provider = LlamaProvider()

        connected, message = provider.connect(endpoint="http://nas:11434")

        assert connected is False
        assert provider.is_connected() is False

    def test_connect_uses_default_endpoint_when_empty(self):
        with patch("ai.base_provider.AIProvider._http_get") as mock_get:
            mock_get.return_value = (200, _tags_body(), None)
            provider = LlamaProvider()
            provider.connect(endpoint="")
            called_url = mock_get.call_args[0][0]
            assert called_url.startswith("http://localhost:11434")

    def test_connect_strips_trailing_slash(self):
        with patch("ai.base_provider.AIProvider._http_get") as mock_get:
            mock_get.return_value = (200, _tags_body(), None)
            provider = LlamaProvider()
            provider.connect(endpoint="http://nas:11434/")
            assert provider._endpoint == "http://nas:11434"


class TestSendMessage:

    def _connected_provider(self):
        with patch("ai.base_provider.AIProvider._http_get") as mock_get:
            mock_get.return_value = (200, _tags_body(), None)
            provider = LlamaProvider()
            provider.connect(endpoint="http://nas:11434")
        return provider

    @patch("ai.base_provider.AIProvider._http_post")
    def test_send_message_success(self, mock_post):
        provider = self._connected_provider()
        mock_post.return_value = (
            200,
            json.dumps({"choices": [{"message": {"content": "Hola, soy Vicky"}}]}),
            None,
        )

        reply = provider.send_message("hola")

        assert reply == "Hola, soy Vicky"
        payload_sent = mock_post.call_args[0][2]
        assert payload_sent["model"] == DEFAULT_MODEL
        assert payload_sent["stream"] is False

    def test_send_message_raises_if_not_connected(self):
        provider = LlamaProvider()
        with pytest.raises(RuntimeError):
            provider.send_message("hola")

    @patch("ai.base_provider.AIProvider._http_post")
    def test_send_message_http_error_marks_disconnected(self, mock_post):
        provider = self._connected_provider()
        mock_post.return_value = (500, None, "Internal Server Error")

        with pytest.raises(RuntimeError):
            provider.send_message("hola")

        assert provider.is_connected() is False

    @patch("ai.base_provider.AIProvider._http_post")
    def test_send_message_malformed_response(self, mock_post):
        provider = self._connected_provider()
        mock_post.return_value = (200, json.dumps({"unexpected": "shape"}), None)

        with pytest.raises(RuntimeError):
            provider.send_message("hola")

    @patch("ai.base_provider.AIProvider._http_post")
    def test_send_message_includes_system_prompt_and_history(self, mock_post):
        provider = self._connected_provider()
        mock_post.return_value = (
            200,
            json.dumps({"choices": [{"message": {"content": "ok"}}]}),
            None,
        )

        provider.send_message(
            "pregunta actual",
            system_prompt="sos Vicky",
            history=[{"role": "user", "content": "hola"}, {"role": "assistant", "content": "hola!"}],
        )

        messages = mock_post.call_args[0][2]["messages"]
        assert messages[0] == {"role": "system", "content": "sos Vicky"}
        assert messages[-1] == {"role": "user", "content": "pregunta actual"}
        assert len(messages) == 4


class TestSendMessageStream:

    def _connected_provider(self):
        with patch("ai.base_provider.AIProvider._http_get") as mock_get:
            mock_get.return_value = (200, _tags_body(), None)
            provider = LlamaProvider()
            provider.connect(endpoint="http://nas:11434")
        return provider

    @patch("ai.base_provider.AIProvider._http_post_stream")
    def test_stream_accumulates_tokens(self, mock_stream):
        provider = self._connected_provider()
        tokens_received = []

        def fake_stream(url, headers, payload, on_line, should_stop=None, timeout=None):
            on_line('data: {"choices":[{"delta":{"content":"Hola"}}]}')
            on_line('data: {"choices":[{"delta":{"content":" mundo"}}]}')
            on_line("data: [DONE]")
            return 200, None

        mock_stream.side_effect = fake_stream

        final_text = provider.send_message_stream("hola", on_token=tokens_received.append)

        assert tokens_received == ["Hola", " mundo"]
        assert final_text == "Hola mundo"

    @patch("ai.base_provider.AIProvider._http_post_stream")
    def test_stream_http_error_raises(self, mock_stream):
        provider = self._connected_provider()
        mock_stream.return_value = (503, "Service Unavailable")

        with pytest.raises(RuntimeError):
            provider.send_message_stream("hola", on_token=lambda _delta: None)


class TestEmbed:

    def _connected_provider(self):
        with patch("ai.base_provider.AIProvider._http_get") as mock_get:
            mock_get.return_value = (200, _tags_body(), None)
            provider = LlamaProvider()
            provider.connect(endpoint="http://nas:11434")
        return provider

    @patch("ai.base_provider.AIProvider._http_post")
    def test_embed_success(self, mock_post):
        provider = self._connected_provider()
        mock_post.return_value = (200, json.dumps({"embedding": [0.1, 0.2, 0.3]}), None)

        vector = provider.embed("texto de ejemplo")

        assert vector == [0.1, 0.2, 0.3]

    def test_embed_returns_none_if_not_connected(self):
        provider = LlamaProvider()
        assert provider.embed("texto") is None

    @patch("ai.base_provider.AIProvider._http_post")
    def test_embed_returns_none_on_http_error(self, mock_post):
        provider = self._connected_provider()
        mock_post.return_value = (500, None, "error")

        assert provider.embed("texto") is None


class TestCapabilities:

    def test_does_not_support_vision(self):
        assert LlamaProvider().supports_vision() is False

    def test_does_not_support_dictation(self):
        assert LlamaProvider().supports_dictation() is False
