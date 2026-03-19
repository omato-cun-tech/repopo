from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession
from database.database import async_session_maker
from database.models import Appointment, AppointmentStatus, User, Slot
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta, date, time
from core.config import settings
import logging

scheduler = AsyncIOScheduler()

async def send_reminder(bot: Bot, appointment_id: int):
    async with async_session_maker() as session:
        result = await session.execute(
            select(Appointment)
            .where(Appointment.id == appointment_id)
            .options(selectinload(Appointment.user), selectinload(Appointment.slot))
        )
        app = result.scalar_one_or_none()
        if app and app.status == AppointmentStatus.PENDING:
            try:
                await bot.send_message(
                    app.user.tg_id,
                    f"⏰ Напоминание! У вас запись на {app.slot.date} в {app.slot.time.strftime('%H:%M')}"
                )
            except Exception as e:
                logging.error(f"Failed to send reminder for app {appointment_id}: {e}")

def setup_scheduler(bot: Bot):
    if not scheduler.running:
        scheduler.start()

async def schedule_appointment_reminders(bot: Bot, appointment_id: int, app_date: date, app_time: time):
    app_datetime = datetime.combine(app_date, app_time)
    
    # 24 hours before
    rem24 = app_datetime - timedelta(hours=24)
    if rem24 > datetime.now():
        scheduler.add_job(send_reminder, 'date', run_date=rem24, args=[bot, appointment_id])
        
    # 2 hours before
    rem2 = app_datetime - timedelta(hours=2)
    if rem2 > datetime.now():
        scheduler.add_job(send_reminder, 'date', run_date=rem2, args=[bot, appointment_id])
