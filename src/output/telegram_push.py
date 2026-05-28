"""Push rendered digest text to Telegram via Bot API with message splitting."""

import logging

import aiohttp

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"
MAX_MESSAGE_LENGTH = 4096


def _split_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split a long message into parts that fit Telegram limits.

    Tries to split at paragraph boundaries first, then at line breaks,
    then hard-cuts at the character limit.

    Args:
        text: The full message text.
        max_length: Maximum characters per part.

    Returns:
        A list of message parts, each within the character limit.
    """
    if len(text) <= max_length:
        return [text]

    parts: list[str] = []
    remaining = text

    while len(remaining) > max_length:
        # Try splitting at a paragraph break within the limit
        cut = remaining.rfind("\n\n", 0, max_length)
        if cut < max_length // 2:
            # Paragraph split too early; try a newline
            cut = remaining.rfind("\n", 0, max_length)
        if cut < max_length // 3:
            # Still too early; hard cut
            cut = max_length
        else:
            # Include the separator in the first part
            cut += 1

        parts.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()

    if remaining:
        parts.append(remaining)

    return parts


async def push_to_telegram(bot_token: str, chat_id: str, text: str) -> bool:
    """Send a message to a Telegram chat, splitting if necessary.

    Args:
        bot_token: The Telegram bot token.
        chat_id: The target chat ID.
        text: The message text to send.

    Returns:
        True if all parts were sent successfully, False otherwise.
    """
    parts = _split_message(text)
    success = True

    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=30)
    ) as session:
        for idx, part in enumerate(parts, 1):
            payload = {
                "chat_id": chat_id,
                "text": part,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            }

            try:
                url = f"{TELEGRAM_API}/bot{bot_token}/sendMessage"
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        logger.info(
                            "Telegram message part %d/%d sent successfully",
                            idx,
                            len(parts),
                        )
                    else:
                        body = await resp.text()
                        logger.error(
                            "Telegram API error (part %d/%d): %d - %s",
                            idx,
                            len(parts),
                            resp.status,
                            body,
                        )
                        success = False
            except aiohttp.ClientError as exc:
                logger.error(
                    "Telegram network error (part %d/%d): %s",
                    idx,
                    len(parts),
                    exc,
                )
                success = False

    return success
