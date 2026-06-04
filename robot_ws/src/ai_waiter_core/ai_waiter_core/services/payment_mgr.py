from ai_waiter_core.utils import logger

class PaymentManager:
    """
    Generates simulated payment links/QR payloads.
    """
    def __init__(self, bank_id="ICB", account_no="123456789"):
        self.bank_id = bank_id
        self.account_no = account_no
        
    def generate_qr_payload(self, table_id: str, amount: float) -> str:
        """
        Generates a VietQR-style link.
        """
        info = f"Payment_Table_{table_id}"
        payment_url = f"https://img.vietqr.io/image/{self.bank_id}-{self.account_no}-qr_only.png?amount={int(amount)}&addInfo={info}"
        
        logger.info(f"Generated payment link for Table {table_id}: {amount} VND")
        return payment_url
