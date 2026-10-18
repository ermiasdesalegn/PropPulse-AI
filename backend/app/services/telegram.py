"""Minimal Telegram Bot API client (HTTP via httpx)."""

from __future__ import annotations

import logging
from functools import cached_property
from typing import Any

import httpx

log = logging.getLogger(__name__)

CAPTION_LIMIT = 1024
MESSAGE_LIMIT = 4096


class TelegramError(RuntimeError):
    pass


class Telegram:
    def __init__(self, token: str, channel_id: str = ""):
        self.token = token
        self.channel_id = channel_id
        self.http = httpx.Client(base_url=f"https://api.telegram.org/bot{token}/", timeout=40)

    def call(self, method: str, **params: Any) -> Any:
        payload = {k: v for k, v in params.items() if v is not None}
        response = self.http.post(method, json=payload, timeout=params.get("timeout", 0) + 15)
        data = response.json()
        if not data.get("ok"):
            raise TelegramError(f"{method}: {data.get('description', response.text)}")
        return data["result"]

    @cached_property
    def bot_username(self) -> str:
        return self.call("getMe")["username"]

    def deep_link(self, payload: str) -> str:
        return f"https://t.me/{self.bot_username}?start={payload}"

    # -- sending -----------------------------------------------------------
    def send_message(self, chat_id: int | str, text: str, buttons: list[list[dict]] | None = None) -> dict:
        markup = {"inline_keyboard": buttons} if buttons else None
        return self.call(
            "sendMessage",
            chat_id=chat_id,
            text=text[:MESSAGE_LIMIT],
            reply_markup=markup,
            link_preview_options={"is_disabled": True},
        )

    def send_photo(self, chat_id: int | str, photo_url: str, caption: str, buttons: list[list[dict]] | None = None) -> dict:
        markup = {"inline_keyboard": buttons} if buttons else None
        return self.call("sendPhoto", chat_id=chat_id, photo=photo_url, caption=caption[:CAPTION_LIMIT], reply_markup=markup)

    def send_location(self, chat_id: int | str, latitude: float, longitude: float) -> dict:
        return self.call("sendLocation", chat_id=chat_id, latitude=latitude, longitude=longitude)

    def send_typing(self, chat_id: int | str) -> None:
        try:
            self.call("sendChatAction", chat_id=chat_id, action="typing")
        except Exception:  # cosmetic only
            pass

    def answer_callback(self, callback_query_id: str, text: str | None = None) -> None:
        try:
            self.call("answerCallbackQuery", callback_query_id=callback_query_id, text=text)
        except Exception:
            pass

    def post_to_channel(self, text: str, buttons: list[list[dict]] | None = None, photo_url: str | None = None) -> dict:
        if not self.channel_id:
            raise TelegramError("TELEGRAM_CHANNEL_ID is not configured")
        if photo_url:
            try:
                caption = text[:CAPTION_LIMIT] if len(text) > CAPTION_LIMIT else text
                return self.send_photo(self.channel_id, photo_url, caption, buttons)
            except Exception as exc:
                log.warning("send_photo to channel failed (%s), falling back to send_message", exc)
        return self.send_message(self.channel_id, text, buttons)

    # -- updates -----------------------------------------------------------
    def get_updates(self, offset: int | None, timeout: int = 30) -> list[dict]:
        return self.call(
            "getUpdates", offset=offset, timeout=timeout, allowed_updates=["message", "callback_query"]
        )

    def set_webhook(self, url: str, secret_token: str | None = None) -> Any:
        return self.call(
            "setWebhook", url=url, secret_token=secret_token or None, allowed_updates=["message", "callback_query"]
        )

    def delete_webhook(self) -> Any:
        return self.call("deleteWebhook")
