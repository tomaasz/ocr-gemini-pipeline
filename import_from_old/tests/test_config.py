import os
import pytest
from unittest.mock import patch

def test_config_defaults():
    # Reload config to clear any previous env vars
    import gemini_config
    import importlib
    importlib.reload(gemini_config)

    assert gemini_config.UI_TIMEOUTS["PAGE_LOAD"] == 180_000
    assert gemini_config.UI_TIMEOUTS["ATTACH_CONFIRM"] == 8_000

def test_config_env_override():
    with patch.dict(os.environ, {"GEMINI_TIMEOUT_PAGE_LOAD": "99999"}):
        import gemini_config
        import importlib
        importlib.reload(gemini_config)

        assert gemini_config.UI_TIMEOUTS["PAGE_LOAD"] == 99999
        # Check that other values remain defaults
        assert gemini_config.UI_TIMEOUTS["ATTACH_CONFIRM"] == 8_000
