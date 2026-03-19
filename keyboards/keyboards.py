from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from database.models import Service, Slot, Appointment
from keyboards.callback_data import ServiceCD, DateCD, TimeCD, ConfirmCD, AppointmentCD
from datetime import date

def get_contact_kb() -> ReplyKeyboardMarkup:
    kb = ReplyKeyboardBuilder()
    kb.row(KeyboardButton(text="Отправить контакт", request_contact=True))
    return kb.as_markup(resize_keyboard=True, one_time_keyboard=True)

def get_main_menu_inline(is_admin: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✂️ Записаться", callback_data="menu_book"))
    builder.row(InlineKeyboardButton(text="👤 Мой профиль", callback_data="menu_profile"))
    builder.row(InlineKeyboardButton(text="💰 Бонусы", callback_data="menu_bonuses"))
    if is_admin:
        builder.row(InlineKeyboardButton(text="🛠 Админ-панель", callback_data="admin_main"))
    return builder.as_markup()

def get_services_kb(services: list[Service]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for service in services:
        builder.row(InlineKeyboardButton(
            text=f"{service.name} - {service.price}₽",
            callback_data=ServiceCD(id=service.id).pack()
        ))
    return builder.as_markup()

def get_dates_kb(dates: list[date]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for d in dates:
        builder.row(InlineKeyboardButton(
            text=d.strftime("%d.%m (%a)"),
            callback_data=DateCD(d=d.isoformat()).pack()
        ))
    return builder.as_markup()

def get_slots_kb(slots: list[Slot]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for slot in slots:
        builder.add(InlineKeyboardButton(
            text=f"🕒 {slot.time.strftime('%H:%M')}",
            callback_data=TimeCD(slot_id=slot.id).pack()
        ))
    builder.adjust(2)
    return builder.as_markup()

def get_confirm_kb(can_use_bonuses: bool = False, bonus_amount: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if can_use_bonuses:
        builder.row(InlineKeyboardButton(
            text=f"Списать бонусы ({bonus_amount})",
            callback_data=ConfirmCD(use_bonuses=True).pack()
        ))
    builder.row(InlineKeyboardButton(
        text="Подтвердить без бонусов",
        callback_data=ConfirmCD(use_bonuses=False).pack()
    ))
    builder.row(InlineKeyboardButton(text="Отмена", callback_data="cancel_booking"))
    return builder.as_markup()

def get_admin_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="Услуги", callback_data="admin_services"))
    builder.row(InlineKeyboardButton(text="Расписание", callback_data="admin_slots"))
    builder.row(InlineKeyboardButton(text="Записи", callback_data="admin_appointments"))
    builder.row(InlineKeyboardButton(text="Клиенты", callback_data="admin_users"))
    return builder.as_markup()
