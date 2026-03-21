import pytest
from config import Config

def test_default_port():
    assert Config.PORT == 65432

def test_default_rounds():
    assert Config.ROUNDS_PER_SEGMENT == 4

def test_model_name():
    assert Config.MODEL == "claude-haiku-4-5-20251001"

def test_max_tokens():
    assert Config.MAX_TOKENS == 1024

def test_host():
    assert Config.HOST == "localhost"
