"""Web server entry point with security checks.

Run with: python -m src.web
"""

import os
import sys
import warnings

from dotenv import load_dotenv

SECURITY_WARNING = """
================================================================================
WARNING: SECURITY RISK - PUBLIC NETWORK BINDING
================================================================================

You are starting the web server on {host}:{port}.
This binds to ALL network interfaces and makes the server accessible from
other machines on your network (and potentially the internet).

RISKS:
- Anyone on your network can access the SpyfallAI interface
- API keys in memory could potentially be exposed
- No authentication is implemented in MVP

RECOMMENDATIONS:
- Use 127.0.0.1 (localhost) for local-only access
- If you need remote access, set up a reverse proxy with authentication
- Never expose this server directly to the internet

To use localhost (recommended):
  Set WEB_UI_HOST=127.0.0.1 in your .env file

================================================================================
Press Enter to continue or Ctrl+C to cancel...
"""

LOCALHOST_ALIASES = {"127.0.0.1", "localhost", "::1"}


def is_public_host(host: str) -> bool:
    """Check if host binding will expose server publicly."""
    if host in LOCALHOST_ALIASES:
        return False
    if host == "0.0.0.0":
        return True
    if host == "::":
        return True
    return True


def main() -> None:
    """Start the web server with security checks."""
    load_dotenv()

    host = os.getenv("WEB_UI_HOST", "127.0.0.1")
    port = int(os.getenv("WEB_UI_PORT", "8000"))

    if is_public_host(host):
        print(SECURITY_WARNING.format(host=host, port=port), file=sys.stderr)
        try:
            input()
        except KeyboardInterrupt:
            print("\nServer startup cancelled.")
            sys.exit(0)
        warnings.warn(
            f"Starting server on public interface {host}:{port}. "
            "This is not recommended for production use.",
            RuntimeWarning,
            stacklevel=2,
        )

    try:
        import uvicorn
    except ImportError:
        print(
            "Error: uvicorn is not installed.\n"
            "Install web dependencies with: pip install -e '.[web]'",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Starting SpyfallAI web server on http://{host}:{port}")
    if host in LOCALHOST_ALIASES:
        print("Server is bound to localhost only (recommended for security).")

    uvicorn.run(
        "src.web.app:app",
        host=host,
        port=port,
        reload=False,
    )


if __name__ == "__main__":
    main()
