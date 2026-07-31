from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    choosing_timezone = State()
    choosing_currency = State()


class AddSubscriptionStates(StatesGroup):
    entering_name = State()
    entering_amount = State()
    choosing_currency = State()
    choosing_period = State()
    entering_next_charge_at = State()


class EditSubscriptionStates(StatesGroup):
    entering_name = State()
    entering_amount = State()
    choosing_currency = State()
    choosing_period = State()
    entering_date = State()
