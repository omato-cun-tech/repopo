from typing import List, Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, Service, Slot, Appointment, AppointmentStatus
from datetime import date, time

# User CRUD
async def get_user_by_tg_id(session: AsyncSession, tg_id: int) -> Optional[User]:
    result = await session.execute(select(User).where(User.tg_id == tg_id))
    return result.scalar_one_or_none()

async def create_user(session: AsyncSession, tg_id: int, name: str, phone: str, referred_by_id: Optional[int] = None) -> User:
    user = User(tg_id=tg_id, name=name, phone=phone, referred_by_id=referred_by_id)
    session.add(user)
    await session.commit()
    return user

async def complete_appointment(session: AsyncSession, appointment_id: int, cashback_percent: int, referral_reward: int):
    # Load appointment with user
    from sqlalchemy.orm import selectinload
    result = await session.execute(
        select(Appointment)
        .where(Appointment.id == appointment_id)
        .options(selectinload(Appointment.user))
    )
    app = result.scalar_one_or_none()
    
    if app and app.status == AppointmentStatus.PENDING:
        app.status = AppointmentStatus.COMPLETED
        
        # 1. Add cashback to the client
        bonus_earned = int(app.total_price * cashback_percent / 100)
        app.user.bonus_balance += bonus_earned
        
        # 2. Check if this was the first completed visit and reward referrer
        if app.user.referred_by_id:
            # Check for other completed appointments
            count_res = await session.execute(
                select(Appointment).where(
                    Appointment.user_id == app.user_id, 
                    Appointment.status == AppointmentStatus.COMPLETED
                )
            )
            is_first = len(count_res.scalars().all()) == 0
            
            if is_first:
                referrer_res = await session.execute(
                    select(User).where(User.id == app.user.referred_by_id)
                )
                referrer = referrer_res.scalar_one_or_none()
                if referrer:
                    referrer.bonus_balance += referral_reward
                    # Return info to notify referrer later
                    return bonus_earned, referrer.tg_id
                    
        await session.commit()
        return bonus_earned, None
    return 0, None

async def get_all_users(session: AsyncSession) -> List[User]:
    result = await session.execute(select(User))
    return list(result.scalars().all())

# Service CRUD
async def get_active_services(session: AsyncSession) -> List[Service]:
    result = await session.execute(select(Service).where(Service.is_active == True))
    return list(result.scalars().all())

async def add_service(session: AsyncSession, name: str, price: float, duration: int) -> Service:
    service = Service(name=name, price=price, duration=duration)
    session.add(service)
    await session.commit()
    return service

# Slot CRUD
async def get_available_dates(session: AsyncSession) -> List[date]:
    result = await session.execute(
        select(Slot.date).where(Slot.is_booked == False, Slot.is_locked == False).distinct()
    )
    return sorted(list(result.scalars().all()))

async def get_available_slots_on_date(session: AsyncSession, selected_date: date) -> List[Slot]:
    result = await session.execute(
        select(Slot).where(Slot.date == selected_date, Slot.is_booked == False, Slot.is_locked == False)
    )
    return list(result.scalars().all())

async def create_slots(session: AsyncSession, slots_data: List[Slot]):
    session.add_all(slots_data)
    await session.commit()

# Appointment CRUD
async def create_appointment(
    session: AsyncSession, 
    user_id: int, 
    service_id: int, 
    slot_id: int, 
    total_price: float, 
    bonuses_used: int
) -> Appointment:
    appointment = Appointment(
        user_id=user_id,
        service_id=service_id,
        slot_id=slot_id,
        total_price=total_price,
        bonuses_used=bonuses_used,
        status=AppointmentStatus.PENDING
    )
    # Mark slot as booked
    await session.execute(update(Slot).where(Slot.id == slot_id).values(is_booked=True))
    session.add(appointment)
    
    # Deduct bonuses from user
    if bonuses_used > 0:
        await session.execute(
            update(User).where(User.id == user_id).values(bonus_balance=User.bonus_balance - bonuses_used)
        )
        
    await session.commit()
    return appointment

async def cancel_appointment(session: AsyncSession, appointment_id: int):
    result = await session.execute(select(Appointment).where(Appointment.id == appointment_id))
    app = result.scalar_one_or_none()
    if app:
        app.status = AppointmentStatus.CANCELED
        # Free all associated slots
        await session.execute(
            update(Slot).where(Slot.appointment_id == appointment_id).values(is_booked=False, appointment_id=None)
        )
        # Refund bonuses? Depends on policy. Let's refund for now.
        if app.bonuses_used > 0:
            await session.execute(
                update(User).where(User.id == app.user_id).values(bonus_balance=User.bonus_balance + app.bonuses_used)
            )
        await session.commit()

async def get_appointments_on_date(session: AsyncSession, target_date: date) -> List[Appointment]:
    result = await session.execute(
        select(Appointment)
        .join(Slot)
        .where(Slot.date == target_date)
        .options(
            # We can use selectinload or similar if we needed relationships
            # but for simplicity we'll just join
        )
    )
    return list(result.scalars().all())
