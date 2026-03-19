from aiogram import Bot
from database.models import User, Service, Slot, Appointment
from keyboards.callback_data import AppointmentCD
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
import logging

async def notify_admin_new_appointment(
    bot: Bot, 
    admin_ids: list[int], 
    user: User, 
    service: Service, 
    slot: Slot, 
    appointment: Appointment
):
    text = (
        "🆕 *Новая запись!*\n\n"
        f"👤 *Клиент:* {user.name}\n"
        f"📞 *Контакт:* {user.phone}\n\n"
        f"✂️ *Услуга:* {service.name}\n"
        f"📅 *Дата:* {slot.date}\n"
        f"⏰ *Время:* {slot.time.strftime('%H:%M')}\n"
        f"💰 *К оплате:* {appointment.total_price} RUB "
        f"(Списано бонусов: {appointment.bonuses_used})\n"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="❌ Отменить запись", 
        callback_data=AppointmentCD(id=appointment.id, action="cancel").pack()
    ))
    builder.row(InlineKeyboardButton(
        text="👤 Профиль клиента", 
        callback_data=f"user_info_{user.id}"
    ))
    
    for admin_id in admin_ids:
        try:
            await bot.send_message(
                admin_id, 
                text, 
                parse_mode="Markdown", 
                reply_markup=builder.as_markup()
            )
        except Exception as e:
            logging.error(f"Failed to notify admin {admin_id}: {e}")
