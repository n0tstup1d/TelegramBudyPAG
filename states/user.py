from aiogram.fsm.state import State, StatesGroup


class WithdrawStates(StatesGroup):
    waiting_for_requisites = State()


class SupportStates(StatesGroup):
    waiting_message = State()
