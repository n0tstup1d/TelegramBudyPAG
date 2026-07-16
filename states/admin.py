from aiogram.fsm.state import State, StatesGroup


class BroadcastStates(StatesGroup):
    waiting_audience = State()
    waiting_message = State()
    waiting_button_decision = State()
    waiting_button = State()
    confirm = State()


class ReferralSettings(StatesGroup):
    waiting_reward = State()
    waiting_minw = State()


class PromoStates(StatesGroup):
    waiting_code = State()
    waiting_discount = State()
    waiting_limit = State()


class AdminUserStates(StatesGroup):
    waiting_user_id = State()
    waiting_new_role = State()


class ShopStates(StatesGroup):
    waiting_name = State()
    waiting_country = State()
    waiting_url = State()

class ReceiptStates(StatesGroup):
    waiting_link = State()
    waiting_file = State()
    confirming = State()
    waiting_search = State()

