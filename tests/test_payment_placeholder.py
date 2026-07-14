import unittest


class PaymentIntegrationTests(unittest.TestCase):
    @unittest.skip("Robokassa ещё не подключена: тесты платежа и возврата добавляются вместе с ResultURL и refund-flow")
    def test_payment_and_refund_flow(self) -> None:
        pass
