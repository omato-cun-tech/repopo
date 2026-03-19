from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from database import crud
from database.models import User, Appointment, Slot, Service, AppointmentStatus
from keyboards import keyboards as kb
from keyboards.callback_data import AppointmentCD
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from core.config import settings
from utils.states import AdminService, AdminSlot, AdminAppointment
from utils.filters import IsAdminFilter
from datetime import datetime, date, time, timedelta
from aiogram.exceptions import TelegramBadRequest
import logging

router = Router()
# Apply IsAdminFilter to all handlers in this router
router.message.filter(IsAdminFilter())
router.callback_query.filter(IsAdminFilter())

@router.callback_query(AppointmentCD.filter(F.action == "cancel"))
async def admin_cancel_appointment_start(callback: types.CallbackQuery, callback_data: AppointmentCD, state: FSMContext):
    await state.update_data(appointment_id=callback_data.id)
    await callback.message.answer("Введите причину отмены для клиента:")
    await state.set_state(AdminAppointment.waiting_for_cancel_reason)
    await callback.answer()

@router.message(AdminAppointment.waiting_for_cancel_reason)
async def admin_cancel_appointment_reason(message: types.Message, state: FSMContext, session: AsyncSession):
    data = await state.get_data()
    appointment_id = data['appointment_id']
    reason = message.text
    
    # Load appointment with user info
    result = await session.execute(
        select(Appointment)
        .where(Appointment.id == appointment_id)
        .options(selectinload(Appointment.user), selectinload(Appointment.slot))
    )
    appointment = result.scalar_one_or_none()
    
    if appointment:
        await crud.cancel_appointment(session, appointment_id)
        try:
            await message.bot.send_message(
                appointment.user.tg_id,
                f"⚠️ Ваша запись на {appointment.slot.date} в {appointment.slot.time.strftime('%H:%M')} была отменена мастером.\nПричина: {reason}"
            )
            await message.answer("Запись отменена, клиент уведомлен.")
        except Exception as e:
            logging.error(f"Failed to notify user about cancellation: {e}")
            await message.answer("Запись отменена в БД, но не удалось уведомить клиента.")
    else:
        await message.answer("Запись не найдена.")
    
    await state.clear()

@router.message(Command("help"))
async def cmd_help_admin(message: types.Message):
    text = (
        "🛠 *Панель управления администратора*\n\n"
        "• /admin — Открыть главное меню управления\n"
        "• /help — Список команд админа (это сообщение)\n\n"
        "*Логика работы с календарем:*\n"
        "1. Перейдите в 'Расписание' в меню /admin.\n"
        "2. Введите дату (ГГГГ-ММ-ДД).\n"
        "3. Введите время работы и шаг (например: 10:00 18:00 60).\n\n"
        "*Управление услугами:* Добавляйте и удаляйте услуги через меню 'Услуги'."
    )
    await message.answer(text, parse_mode="Markdown")

@router.callback_query(F.data == "admin_main")
async def admin_main_callback(callback: types.CallbackQuery):
    try:
        await callback.message.edit_text("Панель управления:", reply_markup=kb.get_admin_main_kb())
    except TelegramBadRequest:
        await callback.answer()

@router.message(F.text == "Админ-панель")
@router.message(Command("admin"))
async def admin_panel(message: types.Message):
    await message.answer("Панель управления:", reply_markup=kb.get_admin_main_kb())

@router.callback_query(F.data == "admin_services")
async def admin_services(callback: types.CallbackQuery, session: AsyncSession):
    services = await crud.get_active_services(session)
    builder = InlineKeyboardBuilder()
    for s in services:
        builder.row(InlineKeyboardButton(text=f"❌ {s.name}", callback_data=f"del_srv_{s.id}"))
    builder.row(InlineKeyboardButton(text="➕ Добавить услугу", callback_data="add_service"))
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_main"))
    
    try:
        await callback.message.edit_text("Управление услугами:", reply_markup=builder.as_markup())
    except TelegramBadRequest:
        await callback.answer()

@router.callback_query(F.data == "add_service")
async def add_service_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите название услуги:")
    await state.set_state(AdminService.waiting_for_name)

@router.message(AdminService.waiting_for_name)
async def add_service_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите цену услуги (число):")
    await state.set_state(AdminService.waiting_for_price)

@router.message(AdminService.waiting_for_price)
async def add_service_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Пожалуйста, введите число.")
    await state.update_data(price=float(message.text))
    await message.answer("Введите длительность в минутах:")
    await state.set_state(AdminService.waiting_for_duration)

@router.message(AdminService.waiting_for_duration)
async def add_service_duration(message: types.Message, state: FSMContext, session: AsyncSession):
    if not message.text.isdigit():
        return await message.answer("Пожалуйста, введите число.")
    data = await state.get_data()
    await crud.add_service(session, data['name'], data['price'], int(message.text))
    await message.answer("Услуга добавлена!", reply_markup=kb.get_admin_main_kb())
    await state.clear()

@router.callback_query(F.data == "admin_slots")
async def admin_slots(callback: types.CallbackQuery, state: FSMContext):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_main_cancel"))
    
    await callback.message.edit_text(
        "📅 *Управление расписанием*\n\nВведите дату в формате `ГГГГ-ММ-ДД` для создания рабочих слотов:",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown"
    )
    await state.set_state(AdminSlot.waiting_for_date)

@router.message(AdminSlot.waiting_for_date)
async def admin_slot_date(message: types.Message, state: FSMContext):
    try:
        date.fromisoformat(message.text)
        await state.update_data(date=message.text)
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="⬅️ Отмена", callback_data="admin_main_cancel"))
        
        await message.answer(
            "⏰ *Параметры времени*\n\nВведите время начала, окончания и шаг в минутах\n"
            "Пример: `10:00 18:00 60`",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        await state.set_state(AdminSlot.waiting_for_times)
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте ГГГГ-ММ-ДД (например, 2024-05-20).")

@router.callback_query(F.data == "admin_main_cancel")
async def admin_main_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await admin_main_callback(callback)

@router.message(AdminSlot.waiting_for_times)
async def admin_slot_times(message: types.Message, state: FSMContext, session: AsyncSession):
    try:
        parts = message.text.split()
        if len(parts) != 3:
            raise ValueError("Нужно 3 параметра")
        start_str, end_str, step_str = parts
        start_h, start_m = map(int, start_str.split(':'))
        end_h, end_m = map(int, end_str.split(':'))
        step = int(step_str)
        
        data = await state.get_data()
        d = date.fromisoformat(data['date'])
        
        from database.models import Slot
        current_time = datetime.combine(d, time(start_h, start_m))
        end_time = datetime.combine(d, time(end_h, end_m))
        
        slots_to_add = []
        while current_time < end_time:
            slots_to_add.append(Slot(date=d, time=current_time.time()))
            current_time += timedelta(minutes=step)
            
        await crud.create_slots(session, slots_to_add)
        await message.answer(f"Создано {len(slots_to_add)} слотов на {data['date']}.", reply_markup=kb.get_admin_main_kb())
        await state.clear()
    except Exception as e:
        await message.answer(f"Ошибка: {e}. Попробуйте еще раз в формате: 10:00 18:00 60")

@router.callback_query(F.data.startswith("user_info_"))
async def admin_user_info(callback: types.CallbackQuery, session: AsyncSession):
    user_id = int(callback.data.split("_")[2])
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return await callback.answer("Пользователь не найден.")
        
    text = (
        f"👤 *Клиент:* {user.name}\n"
        f"📞 *Тел:* {user.phone}\n"
        f"💰 *Бонусы:* {user.bonus_balance}\n"
        f"🚫 *Забанен:* {'Да' if user.is_banned else 'Нет'}"
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "admin_users")
async def admin_users(callback: types.CallbackQuery, session: AsyncSession):
    users = await crud.get_all_users(session)
    if not users:
        try:
            return await callback.message.edit_text("Список клиентов пуст.", reply_markup=kb.get_admin_main_kb())
        except TelegramBadRequest:
            return await callback.answer()
    
    text = "👥 Список клиентов:\n\n"
    for user in users:
        text += f"ID: {user.tg_id}\nИмя: {user.name}\nТел: {user.phone}\nБонусы: {user.bonus_balance}\n"
        text += f"{'🚫 ЗАБАНЕН' if user.is_banned else '✅ Активен'}\n"
        text += "-------------------\n"
    
    try:
        await callback.message.edit_text(text, reply_markup=kb.get_admin_main_kb())
    except TelegramBadRequest:
        await callback.answer()

@router.callback_query(F.data == "admin_appointments")
async def admin_appointments(callback: types.CallbackQuery, session: AsyncSession):
    today = date.today()
    result = await session.execute(
        select(Appointment)
        .join(Slot, Appointment.slot_id == Slot.id)
        .where(Slot.date >= today, Appointment.status == AppointmentStatus.PENDING)
        .options(selectinload(Appointment.user), selectinload(Appointment.service), selectinload(Appointment.slot))
        .order_by(Slot.date, Slot.time)
    )
    appointments = result.scalars().all()
    
    if not appointments:
        try:
            return await callback.message.edit_text("Активных записей не найдено.", reply_markup=kb.get_admin_main_kb())
        except TelegramBadRequest:
            return await callback.answer()
    
    text = "📅 Предстоящие записи:\n\n"
    builder = InlineKeyboardBuilder()
    for app in appointments:
        text += f"📍 ID: {app.id} | {app.slot.date} {app.slot.time.strftime('%H:%M')}\n"
        text += f"👤 {app.user.name} ({app.user.phone})\n"
        text += f"✂️ {app.service.name}\n"
        text += f"Статус: {app.status}\n"
        text += "-------------------\n"
        builder.row(InlineKeyboardButton(
            text=f"✅ Выполнено ID {app.id}", 
            callback_data=AppointmentCD(id=app.id, action="complete_list").pack()
        ))
        builder.row(InlineKeyboardButton(
            text=f"❌ Отменить ID {app.id}", 
            callback_data=AppointmentCD(id=app.id, action="cancel_list").pack()
        ))
    
    builder.row(InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_main"))
    
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())
    except TelegramBadRequest:
        await callback.answer()

@router.callback_query(AppointmentCD.filter(F.action == "cancel_list"))
async def admin_cancel_from_list(callback: types.CallbackQuery, callback_data: AppointmentCD, session: AsyncSession):
    # Load appointment with all needed info for notification
    result = await session.execute(
        select(Appointment)
        .where(Appointment.id == callback_data.id)
        .options(selectinload(Appointment.user), selectinload(Appointment.slot), selectinload(Appointment.service))
    )
    appointment = result.scalar_one_or_none()
    
    if appointment:
        # 1. Update status in DB and free slot
        await crud.cancel_appointment(session, callback_data.id)
        
        # 2. Notify client
        try:
            notification_text = (
                f"⚠️ Ваша запись на {appointment.slot.date} в {appointment.slot.time.strftime('%H:%M')} "
                f"на услугу '{appointment.service.name}' была отменена мастером.\n\n"
                "Для выбора другого времени нажмите /book"
            )
            await callback.bot.send_message(appointment.user.tg_id, notification_text)
        except Exception as e:
            logging.error(f"Failed to notify client {appointment.user.tg_id}: {e}")
            
        await callback.answer("Запись отменена, клиент уведомлен.")
        # 3. Refresh the appointments list
        await admin_appointments(callback, session)
    else:
        await callback.answer("Запись не найдена.")

@router.callback_query(AppointmentCD.filter(F.action == "complete_list"))
async def admin_complete_appointment(callback: types.CallbackQuery, callback_data: AppointmentCD, session: AsyncSession):
    # 1. Logic to update status and award bonuses
    bonus_earned, referrer_tg_id = await crud.complete_appointment(
        session, 
        callback_data.id, 
        settings.cashback_percent, 
        settings.referral_reward
    )
    
    if bonus_earned >= 0:
        # Load appointment for info
        result = await session.execute(
            select(Appointment)
            .where(Appointment.id == callback_data.id)
            .options(selectinload(Appointment.user), selectinload(Appointment.slot))
        )
        app = result.scalar_one_or_none()
        
        # 2. Notify client about cashback
        try:
            await callback.bot.send_message(
                app.user.tg_id,
                f"✅ Визит завершен! Вам начислено {bonus_earned} бонусов.\n"
                f"Ваш текущий баланс: {app.user.bonus_balance} баллов."
            )
        except:
            pass
            
        # 3. Notify referrer if applicable
        if referrer_tg_id:
            try:
                await callback.bot.send_message(
                    referrer_tg_id,
                    f"🎁 Ваш друг завершил первый визит! Вам начислено {settings.referral_reward} бонусов."
                )
            except:
                pass
        
        await callback.answer(f"Запись завершена. Начислено {bonus_earned} баллов.")
        await admin_appointments(callback, session)
    else:
        await callback.answer("Ошибка или запись уже завершена.")
