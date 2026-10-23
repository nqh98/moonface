import json

from moonface.feed.notify import TelegramNotifier, notifier_from_env


def test_send_posts_to_bot_api():
    calls = []

    def fake_transport(url, data):
        calls.append((url, data))

    n = TelegramNotifier("TOK", "CHAT", transport=fake_transport)
    n.send("hello world")

    assert len(calls) == 1
    url, data = calls[0]
    assert url == "https://api.telegram.org/botTOK/sendMessage"
    body = json.loads(data)
    assert body == {"chat_id": "CHAT", "text": "hello world"}


def test_send_swallows_errors_and_logs(capsys):
    def boom(url, data):
        raise OSError("network down")

    n = TelegramNotifier("TOK", "CHAT", transport=boom)
    n.send("hello")  # must not raise

    assert "TELEGRAM SEND FAILED" in capsys.readouterr().err


def test_notifier_from_env_returns_notifier_when_both_set():
    env = {"TELEGRAM_BOT_TOKEN": "TOK", "TELEGRAM_CHAT_ID": "CHAT"}
    n = notifier_from_env(env)
    assert isinstance(n, TelegramNotifier)


def test_notifier_from_env_accepts_moonface_prefixed_names():
    env = {"MOONFACE_TELEGRAM_BOT_TOKEN": "TOK",
           "MOONFACE_TELEGRAM_CHAT_ID": "CHAT"}
    assert isinstance(notifier_from_env(env), TelegramNotifier)


def test_notifier_from_env_plain_names_take_precedence():
    env = {"TELEGRAM_BOT_TOKEN": "PLAIN", "TELEGRAM_CHAT_ID": "CHAT",
           "MOONFACE_TELEGRAM_BOT_TOKEN": "PREFIXED"}
    n = notifier_from_env(env)
    assert isinstance(n, TelegramNotifier)


def test_notifier_from_env_none_when_token_missing():
    assert notifier_from_env({"TELEGRAM_CHAT_ID": "CHAT"}) is None


def test_notifier_from_env_none_when_chat_missing():
    assert notifier_from_env({"TELEGRAM_BOT_TOKEN": "TOK"}) is None


def test_notifier_from_env_none_when_value_empty():
    env = {"TELEGRAM_BOT_TOKEN": "TOK", "TELEGRAM_CHAT_ID": ""}
    assert notifier_from_env(env) is None


def test_notifier_from_env_none_when_value_whitespace():
    env = {"TELEGRAM_BOT_TOKEN": "TOK", "TELEGRAM_CHAT_ID": "   "}
    assert notifier_from_env(env) is None
