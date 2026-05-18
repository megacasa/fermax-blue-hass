"""Tests for shared Fermax notification manager."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.fermax_blue.notification_manager import FermaxSharedNotificationManager


@pytest.fixture
def mock_hass():
    hass = MagicMock()
    hass.async_create_task = MagicMock()
    return hass


@pytest.mark.asyncio
async def test_registers_shared_token_once(mock_hass):
    manager = FermaxSharedNotificationManager(
        hass=mock_hass,
        firebase_api_key="key",
        firebase_sender_id=1,
        firebase_app_id="app",
        firebase_project_id="proj",
        firebase_package_name="com.fermax.blue.app",
    )
    manager._listener = MagicMock()
    manager._listener.fcm_token = None
    manager._listener.register = AsyncMock(return_value="tok")

    token = await manager.async_get_or_register_token()
    assert token == "tok"

    manager._listener.fcm_token = "tok"
    token2 = await manager.async_get_or_register_token()
    assert token2 == "tok"
    manager._listener.register.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_is_idempotent(mock_hass):
    manager = FermaxSharedNotificationManager(
        hass=mock_hass,
        firebase_api_key="key",
        firebase_sender_id=1,
        firebase_app_id="app",
        firebase_project_id="proj",
        firebase_package_name="com.fermax.blue.app",
    )
    manager._listener = MagicMock()
    manager._listener.fcm_token = "tok"
    manager._listener.is_started = False
    manager._listener.start = AsyncMock()
    manager._listener.register = AsyncMock()

    await manager.async_start()
    manager._listener.start.assert_awaited_once()

    manager._listener.is_started = True
    await manager.async_start()
    manager._listener.start.assert_awaited_once()


def test_subscribe_unsubscribe_triggers_cleanup_task(mock_hass):
    mock_hass.async_create_task = MagicMock(side_effect=lambda coro: coro.close())
    manager = FermaxSharedNotificationManager(
        hass=mock_hass,
        firebase_api_key="key",
        firebase_sender_id=1,
        firebase_app_id="app",
        firebase_project_id="proj",
        firebase_package_name="com.fermax.blue.app",
    )
    callback = MagicMock()
    unsubscribe = manager.subscribe(callback)
    assert len(manager._subscribers) == 1

    unsubscribe()
    assert len(manager._subscribers) == 0
    mock_hass.async_create_task.assert_called_once()
