"""Tests for typing indicator functionality (TASK-037)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock


def test_on_typing_broadcasts_event():
    """Test that on_typing broadcasts a typing event."""

    async def run():
        from src.web.app import GameManager, GameStatus

        gm = GameManager()
        mock_ws = AsyncMock()
        gm.websocket_connections.append(mock_ws)
        gm.status = GameStatus.RUNNING

        await gm.on_typing("boris_molot")

        mock_ws.send_json.assert_called_once_with({
            "type": "typing",
            "speaker_id": "boris_molot",
        })

    asyncio.run(run())


def test_on_typing_raises_on_stop():
    """Test that on_typing raises CancelledError when stopped."""

    async def run():
        from src.web.app import GameManager, GameStatus

        gm = GameManager()
        gm.status = GameStatus.STOPPED

        try:
            await gm.on_typing("zoya")
            assert False, "Should have raised CancelledError"
        except asyncio.CancelledError:
            pass

    asyncio.run(run())


def test_on_typing_handles_disconnected_clients():
    """Test that on_typing handles disconnected WebSocket clients."""

    async def run():
        from src.web.app import GameManager, GameStatus

        gm = GameManager()
        mock_ws1 = AsyncMock()
        mock_ws1.send_json.side_effect = Exception("Connection closed")
        mock_ws2 = AsyncMock()

        gm.websocket_connections = [mock_ws1, mock_ws2]
        gm.status = GameStatus.RUNNING

        await gm.on_typing("margo")

        assert mock_ws1 not in gm.websocket_connections
        assert mock_ws2 in gm.websocket_connections
        mock_ws2.send_json.assert_called_once()

    asyncio.run(run())


def test_on_typing_with_multiple_clients():
    """Test that on_typing broadcasts to all connected clients."""

    async def run():
        from src.web.app import GameManager, GameStatus

        gm = GameManager()
        mock_ws1 = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws3 = AsyncMock()

        gm.websocket_connections = [mock_ws1, mock_ws2, mock_ws3]
        gm.status = GameStatus.RUNNING

        await gm.on_typing("kim")

        expected_message = {"type": "typing", "speaker_id": "kim"}
        mock_ws1.send_json.assert_called_once_with(expected_message)
        mock_ws2.send_json.assert_called_once_with(expected_message)
        mock_ws3.send_json.assert_called_once_with(expected_message)

    asyncio.run(run())
