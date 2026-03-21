# tests/test_config.py
import pytest
from config import Config

def test_default_port():
    assert Config.PORT == 65432

def test_default_rounds():
    assert 3 <= Config.ROUNDS_PER_SEGMENT <= 5

def test_model_name():
    assert Config.MODEL == "claude-haiku-4-5-20251001"
