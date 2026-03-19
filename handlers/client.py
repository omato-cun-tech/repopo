from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession
from database import crud
from keyboards import keyboards as kb
from utils.states import Registration, Booking
from keyboards.callback_data import ServiceCD, DateCD, TimeCD, ConfirmCD, AppointmentCD
from core.config import settings
from database.models import Appointment, AppointmentStatus, Service, Slot
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from datetime import date, datetime, timedelta

router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, session: AsyncSession, state: FSMContext, is_admin: bool, command: CommandObject):
    user = await crud.get_user_by_tg_id(session, message.from_user.id)
    if not user:
        referred_by_id = None
        if command.args and command.args.isdigit():
            referrer_tg_id = int(command.args)
            referrer = await crud.get_user_by_tg_id(session, referrer_tg_id)
            if referrer:
                referred_by_id = referrer.id
        
        await state.update_data(referred_by_id=referred_by_id)
        await message.answer(
            "Добро пожаловать! Для регистрации, пожалуйста, поделитесь своим контактом через кнопку ниже.",
            reply_markup=kb.get_contact_kb()
        )
        await state.set_state(Registration.waiting_for_contact)
    else:
        if user.is_banned:
            return await message.answer("Вы заблокированы.")
        await message.answer(
            f"Привет, {user.name}! Выберите действие:", 
            reply_markup=kb.get_main_menu_inline(is_admin)
        )

@router.message(Registration.waiting_for_contact, F.contact)
async def process_contact(message: types.Message, session: AsyncSession, state: FSMContext, is_admin: bool):
    data = await state.get_data()
    await crud.create_user(
        session, 
        tg_id=message.from_user.id, 
        name=message.from_user.full_name, 
        phone=message.contact.phone_number,
        referred_by_id=data.get("referred_by_id")
    )
    await message.answer(
        "Регистрация успешна! Нижняя панель команд убрана. Используйте меню ниже:", 
        reply_markup=ReplyKeyboardRemove()
    )
    await message.answer(
        "Главное меню:", 
        reply_markup=kb.get_main_menu_inline(is_admin)
    )
    await state.clear()

# --- Callback handlers for Inline Main Menu ---

@router.callback_query(F.data == "menu_book")
async def callback_book(callback: types.CallbackQuery, session: AsyncSession, state: FSMContext):
    await start_booking(callback, session, state)
    await callback.answer()

@router.callback_query(F.data == "menu_profile")
async def callback_profile(callback: types.CallbackQuery, session: AsyncSession):
    await show_profile(callback, session)
    await callback.answer()

@router.callback_query(F.data == "menu_bonuses")
async def callback_bonuses(callback: types.CallbackQuery, session: AsyncSession):
    await cmd_bonuses(callback, session)
    await callback.answer()

# --- Logic handlers ---

@router.message(Command("book"))
async def cmd_book(message: types.Message, session: AsyncSession, state: FSMContext):
    await start_booking(message, session, state)

async def start_booking(event: types.Message | types.CallbackQuery, session: AsyncSession, state: FSMContext):
    services = await crud.get_active_services(session)
    if not services:
        return await (event.message if isinstance(event, types.CallbackQuery) else event).answer("К сожалению, сейчас нет доступных услуг.")
    
    text = "✂️ Выберите услугу:"
    reply_markup = kb.get_services_kb(services)
    
    if isinstance(event, types.CallbackQuery):
        await event.message.answer(text, reply_markup=reply_markup)
    else:
        await event.answer(text, reply_markup=reply_markup)
        
    await state.set_state(Booking.choosing_service)

@router.callback_query(Booking.choosing_service, ServiceCD.filter())
async def process_service(callback: types.CallbackQuery, callback_data: ServiceCD, session: AsyncSession, state: FSMContext):
    await state.update_data(service_id=callback_data.id)
    dates = await crud.get_available_dates(session)
    if not dates:
        return await callback.message.edit_text("Извините, свободных дат для записи пока нет.")
    await callback.message.edit_text("📅 Выберите дату:", reply_markup=kb.get_dates_kb(dates))
    await state.set_state(Booking.choosing_date)

@router.callback_query(Booking.choosing_date, DateCD.filter())
async def process_date(callback: types.CallbackQuery, callback_data: DateCD, session: AsyncSession, state: FSMContext):
    selected_date = date.fromisoformat(callback_data.d)
    await state.update_data(date=callback_data.d)
    
    fsm_data = await state.get_data()
    service_res = await session.execute(select(Service).where(Service.id == fsm_data['service_id']))
    service = service_res.scalar_one()
    
    slots_res = await session.execute(
        select(Slot).where(Slot.date == selected_date).order_by(Slot.time)
    )
    all_slots = slots_res.scalars().all()
    
    available_start_slots = []
    for i, slot in enumerate(all_slots):
        if slot.is_booked or slot.is_locked:
            continue
            
        needed_duration = service.duration
        is_enough_time = False
        temp_duration = 0
        valid_chain = True
        for j in range(i, len(all_slots)):
            s = all_slots[j]
            if s.is_booked or s.is_locked:
                valid_chain = False
                break
            if j + 1 < len(all_slots):
                diff = (datetime.combine(date.today(), all_slots[j+1].time) - 
                        datetime.combine(date.today(), s.time)).total_seconds() / 60
                temp_duration += diff
            else:
                temp_duration += 30 
            if temp_duration >= needed_duration:
                is_enough_time = True
                break
        if is_enough_time and valid_chain:
            available_start_slots.append(slot)

    if not available_start_slots:
        return await callback.message.answer('На эту дату нет подходящих свободных "окон" под вашу услугу.')

    await callback.message.edit_text("🕒 Выберите время начала:", reply_markup=kb.get_slots_kb(available_start_slots))
    await state.set_state(Booking.choosing_time)

@router.callback_query(Booking.choosing_time, TimeCD.filter())
async def process_time(callback: types.CallbackQuery, callback_data: TimeCD, session: AsyncSession, state: FSMContext):
    await state.update_data(slot_id=callback_data.slot_id)
    data = await state.get_data()
    user = await crud.get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        return await callback.answer("Пользователь не найден. Используйте /start", show_alert=True)
    
    service_res = await session.execute(select(Service).where(Service.id == data['service_id']))
    service = service_res.scalar_one()
    
    can_use_bonuses = user.bonus_balance > 0
    await callback.message.edit_text(
        f"✅ *Подтверждение записи*\n\n"
        f"✂️ Услуга: {service.name}\n"
        f"📅 Дата: {data['date']}\n"
        f"💰 Стоимость: {service.price}₽\n"
        f"💎 Ваши бонусы: {user.bonus_balance}",
        reply_markup=kb.get_confirm_kb(can_use_bonuses, user.bonus_balance),
        parse_mode="Markdown"
    )
    await state.set_state(Booking.confirming)

@router.callback_query(Booking.confirming, ConfirmCD.filter())
async def confirm_booking(callback: types.CallbackQuery, callback_data: ConfirmCD, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    user = await crud.get_user_by_tg_id(session, callback.from_user.id)
    if not user:
        return await callback.answer("Пользователь не найден.", show_alert=True)
    
    result = await session.execute(select(Service).where(Service.id == data['service_id']))
    service = result.scalar_one()
    
    slot_result = await session.execute(select(Slot).where(Slot.id == data['slot_id']))
    start_slot = slot_result.scalar_one()
    
    slots_res = await session.execute(
        select(Slot).where(Slot.date == start_slot.date).order_by(Slot.time)
    )
    all_day_slots = slots_res.scalars().all()
    
    idx = 0
    for i, s in enumerate(all_day_slots):
        if s.id == start_slot.id:
            idx = i
            break
            
    slots_to_book_ids = []
    temp_dur = 0
    for j in range(idx, len(all_day_slots)):
        s = all_day_slots[j]
        slots_to_book_ids.append(s.id)
        if j + 1 < len(all_day_slots):
            diff = (datetime.combine(date.today(), all_day_slots[j+1].time) - 
                    datetime.combine(date.today(), s.time)).total_seconds() / 60
            temp_dur += diff
        else:
            temp_dur += 30
        if temp_dur >= service.duration:
            break

    total_price = service.price
    bonuses_to_use = 0
    if callback_data.use_bonuses:
        max_discount = (service.price * settings.max_bonus_payment_percent) / 100
        bonuses_to_use = min(user.bonus_balance, int(max_discount))
        total_price -= bonuses_to_use
        
    appointment = Appointment(
        user_id=user.id,
        service_id=service.id,
        slot_id=start_slot.id,
        total_price=total_price,
        bonuses_used=bonuses_to_use,
        status=AppointmentStatus.PENDING
    )
    session.add(appointment)
    await session.flush()
    
    from sqlalchemy import update
    await session.execute(
        update(Slot)
        .where(Slot.id.in_(slots_to_book_ids))
        .values(is_booked=True, appointment_id=appointment.id)
    )
    
    if bonuses_to_use > 0:
        user.bonus_balance -= bonuses_to_use
        
    await session.commit()
    
    await callback.message.edit_text(f"🎉 Запись подтверждена!\n💰 К оплате: {total_price}₽")
    await state.clear()
    
    from services.scheduler import schedule_appointment_reminders
    await schedule_appointment_reminders(callback.bot, appointment.id, start_slot.date, start_slot.time)
    
    from services.notifications import notify_admin_new_appointment
    await notify_admin_new_appointment(callback.bot, settings.admin_ids, user, service, start_slot, appointment)

@router.message(Command("profile"))
async def cmd_profile(message: types.Message, session: AsyncSession):
    await show_profile(message, session)

async def show_profile(event: types.Message | types.CallbackQuery, session: AsyncSession):
    tg_id = event.from_user.id
    user = await crud.get_user_by_tg_id(session, tg_id)
    if not user:
        msg = event.message if isinstance(event, types.CallbackQuery) else event
        return await msg.answer("Вы не зарегистрированы. Пожалуйста, используйте /start")
        
    result = await session.execute(
        select(Appointment)
        .where(Appointment.user_id == user.id, Appointment.status == AppointmentStatus.PENDING)
        .options(selectinload(Appointment.slot), selectinload(Appointment.service))
        .join(Slot, Appointment.slot_id == Slot.id)
        .join(Service)
    )
    appointments = result.scalars().all()
    
    bot_info = await (event.bot if isinstance(event, types.CallbackQuery) else event.bot).get_me()
    ref_link = f"https://t.me/{bot_info.username}?start={user.tg_id}"
    
    text = (
        f"👤 *Профиль:* {user.name}\n"
        f"💰 *Баланс:* {user.bonus_balance} баллов\n\n"
        f"🎁 *Бонусная программа:*\n"
        f"• Получайте {settings.cashback_percent}% кешбэка с каждого визита.\n"
        f"• Приглашайте друзей и получайте {settings.referral_reward} баллов после их первого посещения!\n"
        f"• Списывайте баллы при оплате (до {settings.max_bonus_payment_percent}% от цены).\n\n"
        f"🔗 *Ваша ссылка для друзей:*\n`{ref_link}`\n\n"
    )
    
    builder = InlineKeyboardBuilder()
    if appointments:
        text += "📅 *Ваши активные записи:*\n"
        for app in appointments:
            text += f"• {app.slot.date} {app.slot.time.strftime('%H:%M')} - {app.service.name}\n"
            builder.row(InlineKeyboardButton(
                text=f"❌ Отменить {app.slot.date}",
                callback_data=AppointmentCD(id=app.id, action="client_cancel").pack()
            ))
    else:
        text += "У вас пока нет активных записей."
    
    if isinstance(event, types.CallbackQuery):
        await event.message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    else:
        await event.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(AppointmentCD.filter(F.action == "client_cancel"))
async def client_cancel_appointment(callback: types.CallbackQuery, callback_data: AppointmentCD, session: AsyncSession):
    result = await session.execute(
        select(Appointment)
        .where(Appointment.id == callback_data.id)
        .options(selectinload(Appointment.user), selectinload(Appointment.slot), selectinload(Appointment.service))
    )
    appointment = result.scalar_one_or_none()
    if appointment:
        await crud.cancel_appointment(session, callback_data.id)
        await callback.message.edit_text(f"✅ Запись на {appointment.slot.date} {appointment.slot.time.strftime('%H:%M')} успешно отменена.")
        for admin_id in settings.admin_ids:
            try:
                await callback.bot.send_message(admin_id, f"❗ Клиент {appointment.user.name} отменил запись на {appointment.slot.date}")
            except: pass
    else:
        await callback.answer("Запись не найдена.")
    await callback.answer()

@router.message(Command("bonuses"))
async def cmd_bonuses(event: types.Message | types.CallbackQuery, session: AsyncSession):
    user = await crud.get_user_by_tg_id(session, event.from_user.id)
    if not user:
        msg = event.message if isinstance(event, types.CallbackQuery) else event
        return await msg.answer("Вы не зарегистрированы.")
    
    text = f"💰 Ваш баланс бонусов: {user.bonus_balance} баллов."
    if isinstance(event, types.CallbackQuery):
        await event.message.answer(text)
    else:
        await event.answer(text)

@router.message(Command("help"))
async def cmd_help_client(message: types.Message):
    text = ("📖 *Инструкция для клиента*\n\n"
            "1. Кнопка 'Записаться' для выбора услуги.\n"
            "2. В 'Мой профиль' ваши записи и бонусы.\n"
            "📞 Контакт мастера: +7 (999) 000-00-00")
    await message.answer(text, parse_mode="Markdown")

@router.callback_query(F.data == "cancel_booking")
async def cancel_booking_fsm(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Запись отменена.")
