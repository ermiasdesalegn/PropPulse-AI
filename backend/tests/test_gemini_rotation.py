"""Tests for Gemini multi-key loader, thread-safe rotation, and 429 quota failover."""

from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest
from google.genai import errors, types

from app.config import Settings
from app.services.gemini import Gemini, load_keys_from_file, mask_key


def test_mask_key():
    assert mask_key("") == "<empty>"
    assert mask_key("123456") == "12...56"
    assert mask_key("AIzaSyB123456789X") == "AIza...789X"


def test_load_keys_from_file_with_csv_header(tmp_path):
    csv_file = tmp_path / "keys.csv"
    csv_file.write_text(
        "api_key\n"
        "AIzaKey1\n"
        "\n"
        "# comment\n"
        "AIzaKey2\n"
        "AIzaKey1\n",  # duplicate
        encoding="utf-8",
    )
    keys = load_keys_from_file(csv_file)
    assert keys == ["AIzaKey1", "AIzaKey2"]


def test_load_keys_from_file_plain_list(tmp_path):
    txt_file = tmp_path / "keys.txt"
    txt_file.write_text("KeyAlpha\nKeyBeta\n", encoding="utf-8")
    keys = load_keys_from_file(txt_file)
    assert keys == ["KeyAlpha", "KeyBeta"]


def test_load_keys_missing_file():
    assert load_keys_from_file("non_existent_keys.csv") == []


def test_gemini_init_sources(tmp_path):
    # From single string
    g1 = Gemini(api_key="KeySingle")
    assert g1.keys == ["KeySingle"]

    # From comma-separated string
    g2 = Gemini(api_key="KeyA, KeyB ,KeyC")
    assert g2.keys == ["KeyA", "KeyB", "KeyC"]

    # From list
    g3 = Gemini(api_keys=["Key1", "Key2"])
    assert g3.keys == ["Key1", "Key2"]

    # From file
    keys_file = tmp_path / "keys.csv"
    keys_file.write_text("api_key\nFromFile1\nFromFile2\n", encoding="utf-8")
    g4 = Gemini(keys_file=keys_file)
    assert g4.keys == ["FromFile1", "FromFile2"]

    # No keys raises ValueError
    with pytest.raises(ValueError, match="No valid Gemini API keys provided"):
        Gemini(api_key="")


def test_gemini_rotates_on_429():
    g = Gemini(api_keys=["Key1", "Key2", "Key3"])

    # Mock clients
    mock_client1 = MagicMock()
    mock_client2 = MagicMock()
    mock_client3 = MagicMock()

    # Key1 throws 429
    quota_error = errors.APIError(429, {"error": {"message": "RESOURCE_EXHAUSTED: Quota exceeded"}})
    mock_client1.models.generate_content.side_effect = quota_error

    # Key2 succeeds
    expected_resp = types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=[types.Part.from_text(text="Success from Key2")]))]
    )
    mock_client2.models.generate_content.return_value = expected_resp

    clients_map = {"Key1": mock_client1, "Key2": mock_client2, "Key3": mock_client3}
    g._get_client_for_key = lambda k: clients_map[k]

    config = types.GenerateContentConfig()
    result = g.generate("Hello", config)

    assert result.text == "Success from Key2"
    assert g.current_index == 1  # rotated to Key2
    mock_client1.models.generate_content.assert_called_once()
    mock_client2.models.generate_content.assert_called_once()


def test_gemini_exhausts_all_keys_and_raises():
    g = Gemini(api_keys=["Key1", "Key2"], max_retries=1)

    mock_client = MagicMock()
    quota_error = errors.APIError(429, {"error": {"message": "RESOURCE_EXHAUSTED"}})
    mock_client.models.generate_content.side_effect = quota_error

    g._get_client_for_key = lambda k: mock_client

    config = types.GenerateContentConfig()
    with pytest.raises(errors.APIError) as exc_info:
        g.generate("Hello", config)

    assert exc_info.value.code == 429


def test_gemini_thread_safety_during_rotation():
    g = Gemini(api_keys=[f"Key{i}" for i in range(10)])

    # Simulate 20 concurrent threads calling rotate_key
    def worker():
        for _ in range(5):
            g.rotate_key()

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Should remain a valid index within bounds
    assert 0 <= g.current_index < len(g.keys)


def test_settings_gemini_keys_resolution(tmp_path):
    csv_file = tmp_path / "custom_keys.csv"
    csv_file.write_text("api_key\nKeyFromCsv\n", encoding="utf-8")

    settings = Settings(
        _env_file=None,
        gemini_api_key="KeyPrimary",
        gemini_api_keys="KeyMulti1,KeyMulti2",
        gemini_keys_file=str(csv_file),
    )

    keys = settings.get_gemini_api_keys()
    assert "KeyMulti1" in keys
    assert "KeyMulti2" in keys
    assert "KeyPrimary" in keys
    assert "KeyFromCsv" in keys
