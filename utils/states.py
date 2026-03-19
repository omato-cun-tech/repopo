from aiogram.fsm.state import StatesGroup, State

class Registration(StatesGroup):
    waiting_for_contact = State()

class Booking(StatesGroup):
    choosing_service = State()
    choosing_date = State()
    choosing_time = State()
    confirming = State()

class AdminService(StatesGroup):
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_duration = State()

class AdminSlot(StatesGroup):
    waiting_for_date = State()
    waiting_for_times = State()

class AdminAppointment(StatesGroup):
    waiting_for_cancel_reason = State()
