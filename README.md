# SpyfallAI

AI-powered Spyfall game generator with character-driven agents.

## Quick Start

```bash
# Install dependencies
pip install -e .

# For web UI
pip install -e '.[web]'

# Run CLI game
python -m src.cli -c boris_molot,zoya,kim -l hospital

# Run web UI
python -m src.web
```

## Configuration

Copy `.env.example` to `.env` and set your API keys:

```bash
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY
```

## Security

### API Keys

- Store API keys only in `.env` file (never commit to git)
- `.env` is in `.gitignore` by default
- Keys are never logged in game files

### Web UI Security

**IMPORTANT: The web UI is designed for local use only.**

Default configuration binds to `127.0.0.1` (localhost), which is accessible only from your machine.

#### Risks of Public Binding

If you set `WEB_UI_HOST=0.0.0.0`, the server will be accessible from other machines. This is dangerous because:

1. **No Authentication**: MVP has no login or access control
2. **API Key Exposure**: Your OpenAI/Anthropic keys are in server memory
3. **Network Exposure**: Anyone on your network can start games and consume API credits
4. **No Encryption**: HTTP traffic is not encrypted

#### Safe Configuration

```bash
# .env - RECOMMENDED (localhost only)
WEB_UI_HOST=127.0.0.1
WEB_UI_PORT=8000
```

#### If You Need Remote Access

Do NOT set `WEB_UI_HOST=0.0.0.0`. Instead:

1. Keep `WEB_UI_HOST=127.0.0.1`
2. Set up a reverse proxy (nginx, Caddy) with:
   - HTTPS/TLS encryption
   - Basic authentication or OAuth
   - Rate limiting
3. Access through the authenticated proxy

Example nginx configuration:

```nginx
server {
    listen 443 ssl;
    server_name spyfall.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    auth_basic "SpyfallAI";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Project Structure

```
spyfallai/
├── src/
│   ├── orchestrator/    # Game engine, phases, turns
│   ├── agents/          # Prompt building, LLM calls
│   ├── triggers/        # Trigger conditions and reactions
│   ├── llm/             # Provider adapter layer
│   ├── storage/         # Game log repository
│   ├── web/             # FastAPI + WebSocket
│   └── cli.py           # CLI entry point
├── characters/          # Character JSON profiles
├── games/               # Game logs (JSON)
├── locations.json
├── trigger_rules.json
└── llm_config.json
```

## License

Private project - not for redistribution.
