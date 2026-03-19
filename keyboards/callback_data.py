from aiogram.filters.callback_data import CallbackData
from typing import Optional

class ServiceCD(CallbackData, prefix="srv"):
    id: int
    action: str = "select" # select, edit, delete

class DateCD(CallbackData, prefix="dt"):
    d: str # Format YYYY-MM-DD

class TimeCD(CallbackData, prefix="tm"):
    slot_id: int

class ConfirmCD(CallbackData, prefix="cnf"):
    use_bonuses: bool

class AppointmentCD(CallbackData, prefix="app"):
    id: int
    action: str # cancel, complete, no_show

class PaginationCD(CallbackData, prefix="page"):
    page: int
    action: str # services, appointments
