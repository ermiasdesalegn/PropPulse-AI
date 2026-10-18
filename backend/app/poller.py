"""Local development: receive Telegram updates by long-polling instead of a public webhook.

    python -m app.poller
"""

import logging
import time

from app.deps import get_services
from app.workflows.conversation import handle_telegram_update

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("poller")


def main() -> None:
    services = get_services()
    tg = services.telegram
    tg.delete_webhook()  # getUpdates doesn't work while a webhook is set
    log.info("Polling as @%s — press Ctrl+C to stop", tg.bot_username)
    offset = None
    while True:
        try:
            updates = tg.get_updates(offset)
        except Exception:
            log.exception("getUpdates failed; retrying in 5s")
            time.sleep(5)
            continue
        for update in updates:
            offset = update["update_id"] + 1
            try:
                handle_telegram_update(services, update)
            except Exception:
                log.exception("failed to handle update %s", update["update_id"])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
