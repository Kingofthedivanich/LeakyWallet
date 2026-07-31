from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    choosing_timezone = State()
    choosing_currency = State()
