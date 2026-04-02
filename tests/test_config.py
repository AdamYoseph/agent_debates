from config import Config


def test_default_port():
    assert Config.PORT == 65432


def test_default_rounds():
    assert Config.ROUNDS_PER_SEGMENT == 4


def test_model_name():
    assert Config.MODEL == "gemini-2.5-flash"


def test_max_tokens():
    assert Config.MAX_TOKENS == 4096


def test_host():
    assert Config.HOST == "localhost"
