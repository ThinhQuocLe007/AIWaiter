import threading
from ai_waiter_core.services.restaurant_db import RestaurantDB
from ai_waiter_core.utils import logger

MOCK_VERIFY_DELAY = 5  # seconds


class PaymentManager:
    """
    Generates VietQR payment links and schedules mock auto-verification.
    """
    def __init__(self, bank_id="ICB", account_no="123456789"):
        self.bank_id = bank_id
        self.account_no = account_no

    def generate_qr_payload(self, session_id: int, amount: float) -> str:
        """
        Generates a VietQR-style link.
        """
        info = f"Payment_Session_{session_id}"
        payment_url = (
            f"https://img.vietqr.io/image/{self.bank_id}-{self.account_no}"
            f"-qr_only.png?amount={int(amount)}&addInfo={info}"
        )

        logger.info(f"Generated payment link for Session #{session_id}: {amount} VND")
        return payment_url

    def schedule_mock_verify(self, session_id: int):
        """
        Auto-completes payment after MOCK_VERIFY_DELAY seconds (simulates customer paying).
        """
        def _auto_complete():
            db = RestaurantDB()
            db.update_payment_status(session_id, "COMPLETED")
            logger.info(
                f"Mock verification: Session #{session_id} auto-completed after {MOCK_VERIFY_DELAY}s"
            )

        timer = threading.Timer(MOCK_VERIFY_DELAY, _auto_complete)
        timer.daemon = True
        timer.start()
