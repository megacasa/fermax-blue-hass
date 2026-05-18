"""Shared FCM notification manager for Fermax Blue."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from homeassistant.core import CALLBACK_TYPE, HomeAssistant

from .notification import FermaxNotificationListener

_LOGGER = logging.getLogger(__name__)


class FermaxSharedNotificationManager:
    """Own a single FCM listener and fan out events to subscribers."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        firebase_api_key: str,
        firebase_sender_id: int | str,
        firebase_app_id: str,
        firebase_project_id: str,
        firebase_package_name: str,
    ) -> None:
        self._hass = hass
        self._listener = FermaxNotificationListener(
            hass=hass,
            notification_callback=self._on_notification,
            firebase_api_key=firebase_api_key,
            firebase_sender_id=firebase_sender_id,
            firebase_app_id=firebase_app_id,
            firebase_project_id=firebase_project_id,
            firebase_package_name=firebase_package_name,
        )
        self._subscribers: set[Callable[[dict[str, Any], str], None]] = set()
        self._lifecycle_lock = asyncio.Lock()

    @property
    def fcm_token(self) -> str | None:
        """Return the shared FCM token if available."""
        return self._listener.fcm_token

    async def async_get_or_register_token(self) -> str | None:
        """Register once and return the shared token."""
        async with self._lifecycle_lock:
            if self._listener.fcm_token:
                return self._listener.fcm_token
            return await self._listener.register()

    async def async_start(self) -> None:
        """Start shared FCM listener if needed."""
        async with self._lifecycle_lock:
            if self._listener.is_started:
                return
            if not self._listener.fcm_token:
                await self._listener.register()
            if self._listener.fcm_token:
                await self._listener.start()

    async def async_ensure_running(self) -> None:
        """Revive shared listener when there are active subscribers."""
        if not self._subscribers:
            return
        await self._listener.ensure_running()

    async def async_stop(self) -> None:
        """Stop shared FCM listener."""
        async with self._lifecycle_lock:
            await self._listener.stop()

    async def async_maybe_stop(self) -> None:
        """Stop listener when there are no subscribers left."""
        if self._subscribers:
            return
        await self.async_stop()

    def subscribe(self, callback: Callable[[dict[str, Any], str], None]) -> CALLBACK_TYPE:
        """Subscribe callback and return an unsubscribe callable."""
        self._subscribers.add(callback)

        def _unsubscribe() -> None:
            self._subscribers.discard(callback)
            self._hass.async_create_task(self.async_maybe_stop())

        return _unsubscribe

    def _on_notification(self, notification: dict[str, Any], persistent_id: str) -> None:
        """Fan-out incoming push notification to current subscribers."""
        for callback in list(self._subscribers):
            try:
                callback(notification, persistent_id)
            except Exception:  # pragma: no cover - defensive
                _LOGGER.exception("Unhandled error in Fermax notification subscriber")
