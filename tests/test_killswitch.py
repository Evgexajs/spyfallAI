"""Tests for TASK-034: Kill-switch for inflight LLM requests."""

import asyncio
from src.models.game import GameOutcome


def test_game_outcome_cancelled():
    """Test that GameOutcome supports 'cancelled' winner."""
    outcome = GameOutcome(
        winner="cancelled",
        reason="Game stopped by user"
    )
    assert outcome.winner == "cancelled"
    assert outcome.reason == "Game stopped by user"
    assert outcome.accused_id is None


def test_game_outcome_with_accused_id():
    """Test that GameOutcome supports accused_id field."""
    outcome = GameOutcome(
        winner="civilians",
        reason="Spy caught",
        accused_id="boris_molot"
    )
    assert outcome.winner == "civilians"
    assert outcome.accused_id == "boris_molot"


def test_inflight_tasks_tracking():
    """Test that inflight tasks can be registered and unregistered."""

    async def run():
        from src.web.app import GameManager
        gm = GameManager()

        async def dummy_task():
            await asyncio.sleep(10)

        task = asyncio.create_task(dummy_task())
        gm.register_inflight_task(task)
        assert len(gm.inflight_tasks) == 1

        gm.unregister_inflight_task(task)
        assert len(gm.inflight_tasks) == 0

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(run())


def test_cancel_all_inflight_tasks():
    """Test that all inflight tasks are cancelled properly."""

    async def run():
        from src.web.app import GameManager
        gm = GameManager()

        async def long_task():
            try:
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                raise

        tasks = []
        for _ in range(3):
            task = asyncio.create_task(long_task())
            gm.register_inflight_task(task)
            tasks.append(task)

        assert len(gm.inflight_tasks) == 3

        await asyncio.sleep(0.1)

        gm.cancel_all_inflight_tasks()
        assert len(gm.inflight_tasks) == 0

        for task in tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
            assert task.cancelled()

    asyncio.run(run())


def test_reset_clears_inflight_tasks():
    """Test that reset() clears inflight_tasks set."""

    async def run():
        from src.web.app import GameManager
        gm = GameManager()

        async def dummy_task():
            await asyncio.sleep(10)

        task = asyncio.create_task(dummy_task())
        gm.register_inflight_task(task)
        assert len(gm.inflight_tasks) == 1

        gm.reset()
        assert len(gm.inflight_tasks) == 0

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(run())
