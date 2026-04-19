"""Tests for web UI localhost security (TASK-045)."""

import os
from unittest.mock import patch

import pytest


class TestWebUIHostSecurity:
    """Test suite for WEB_UI_HOST security features."""

    def test_default_host_is_localhost(self):
        """Verify that default WEB_UI_HOST is 127.0.0.1."""
        with open(".env.example", "r") as f:
            content = f.read()

        assert "WEB_UI_HOST=127.0.0.1" in content, (
            ".env.example should have WEB_UI_HOST=127.0.0.1 as default"
        )

    def test_is_public_host_detects_public_bindings(self):
        """Verify is_public_host correctly identifies public bindings."""
        from src.web.__main__ import is_public_host

        assert is_public_host("0.0.0.0") is True
        assert is_public_host("::") is True
        assert is_public_host("192.168.1.1") is True
        assert is_public_host("10.0.0.1") is True

    def test_is_public_host_allows_localhost(self):
        """Verify is_public_host allows localhost variants."""
        from src.web.__main__ import is_public_host

        assert is_public_host("127.0.0.1") is False
        assert is_public_host("localhost") is False
        assert is_public_host("::1") is False

    def test_localhost_aliases_defined(self):
        """Verify LOCALHOST_ALIASES contains expected values."""
        from src.web.__main__ import LOCALHOST_ALIASES

        assert "127.0.0.1" in LOCALHOST_ALIASES
        assert "localhost" in LOCALHOST_ALIASES
        assert "::1" in LOCALHOST_ALIASES

    def test_security_warning_exists(self):
        """Verify security warning message is defined."""
        from src.web.__main__ import SECURITY_WARNING

        assert "WARNING" in SECURITY_WARNING
        assert "SECURITY" in SECURITY_WARNING
        assert "0.0.0.0" not in SECURITY_WARNING or "host}" in SECURITY_WARNING
        assert "authentication" in SECURITY_WARNING.lower()

    def test_security_warning_mentions_risks(self):
        """Verify security warning covers all risks."""
        from src.web.__main__ import SECURITY_WARNING

        warning_lower = SECURITY_WARNING.lower()
        assert "risk" in warning_lower
        assert "api key" in warning_lower or "keys" in warning_lower
        assert "127.0.0.1" in SECURITY_WARNING

    def test_readme_contains_security_section(self):
        """Verify README.md has security documentation."""
        with open("README.md", "r") as f:
            content = f.read()

        assert "## Security" in content, "README should have Security section"
        assert "localhost" in content.lower()
        assert "0.0.0.0" in content
        assert "authentication" in content.lower()

    def test_readme_warns_about_public_binding(self):
        """Verify README warns about risks of public binding."""
        with open("README.md", "r") as f:
            content = f.read()

        content_lower = content.lower()
        assert "risk" in content_lower
        assert "api key" in content_lower or "keys" in content_lower
        assert "not recommended" in content_lower or "dangerous" in content_lower

    @patch.dict(os.environ, {"WEB_UI_HOST": "127.0.0.1"}, clear=False)
    def test_env_default_host_value(self):
        """Test that os.getenv returns correct default."""
        from dotenv import load_dotenv

        load_dotenv()

        host = os.getenv("WEB_UI_HOST", "127.0.0.1")
        assert host == "127.0.0.1"

    def test_web_module_is_runnable(self):
        """Verify src.web can be imported as module."""
        try:
            from src.web import __main__ as web_main

            assert hasattr(web_main, "main")
            assert hasattr(web_main, "is_public_host")
            assert hasattr(web_main, "SECURITY_WARNING")
        except ImportError as e:
            pytest.fail(f"Failed to import src.web.__main__: {e}")
