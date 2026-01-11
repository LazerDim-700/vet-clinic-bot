from aiogram import types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from states3 import Appointment
from database3 import (
    get_services,
    get_specialists,
    get_specialist_id,
    get_specialist_name_by_id,
    get_free_slots,
    get_free_dates_for_specialist,
    get_free_dates_all,
    get_free_times_all_on_date,
    get_specialists_free_on,
    book_slot,
    save_appointment,
    get_user_appointments,
    cancel_appointment,
    get_specialists_for_service,
    get_specialists_free_on_for_service,
    unbook_slot,
    admin_book_appointment
)
from aiogram.filters import Filter
from datetime import date, timedelta
from database3 import get_appointments_on
from states3 import AdminBook
import database3
print("DATABASE FUNCTIONS:", hasattr(database3, "admin_book_appointment"))
print("HANDLERS MODULE LOADED")

import os
print("HANDLERS LOADED FROM:", os.path.abspath(__file__))

from aiogram import types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

async def cmd_myid(message: types.Message):
    print("CMD_MYID FIRED", message.from_user.id)
    await message.answer(f"Ваш ID: {message.from_user.id}")

async def ping(message: types.Message):
    print("PING HANDLER FIRED")
    await message.answer("PONG ✅")

async def cmd_book_denied(message: types.Message):
    await message.answer("⛔ Команда /book доступна только администратору.")

#def register_handlers(dp):
#    dp.message.register(ping, Command("ping"))


async def admin_book_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("📞 Админ-запись: выберите услугу", reply_markup=kb_services_admin())
    await state.set_state(AdminBook.service)

async def admin_service_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    service = callback.data.split("ab_service:", 1)[1]
    await state.update_data(service=service)

    await callback.message.edit_text(
        f"📞 Админ-запись\nУслуга: {service}\n\nКак будем подбирать запись?",
        reply_markup=kb_admin_path()
    )
    await state.set_state(AdminBook.path)

async def admin_path_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    path = callback.data.split("ab_path:", 1)[1]
    await state.update_data(path=path)

    data = await state.get_data()
    service = data["service"]

    if path == "specialist":
        specs = get_specialists_for_service(service)
        if not specs:
            await callback.message.edit_text("😔 Для этой услуги нет специалистов.")
            await state.clear()
            return

        await callback.message.edit_text(
            "📞 Админ-запись\nВыберите специалиста:",
            reply_markup=kb_admin_specs(specs)
        )
        await state.set_state(AdminBook.specialist)
        return

    # datetime-first
    dates = get_free_dates_all()
    if not dates:
        await callback.message.edit_text("😔 Нет доступных слотов.")
        await state.clear()
        return

    await callback.message.edit_text(
    "📞 Админ-запись\nВыберите дату:",
    reply_markup=kb_dates_admin(dates, "ab_date", back_to="path")
)

    await state.set_state(AdminBook.date)

async def admin_date_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    date_ = callback.data.split("ab_date:", 1)[1]
    await state.update_data(date=date_)

    times = get_free_times_all_on_date(date_)
    if not times:
        await callback.message.edit_text("На эту дату уже нет слотов. Выберите другую дату.")
        return

    await callback.message.edit_text(
    f"📞 Админ-запись\nДата: {date_}\nВыберите время:",
    reply_markup=kb_times_admin(times, "ab_time", back_to="date_list")
)


    await state.set_state(AdminBook.time)


async def admin_time_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    time_ = callback.data.split("ab_time:", 1)[1]
    data = await state.get_data()
    date_ = data["date"]
    service = data["service"]
    await state.update_data(time=time_)

    spec_rows = get_specialists_free_on_for_service(service, date_, time_)
    if not spec_rows:
        await callback.message.edit_text("Этот слот уже заняли. Выберите другое время.")
        return

    await callback.message.edit_text(
    f"📞 Админ-запись\nДата: {date_}\nВремя: {time_}\n\nВыберите специалиста:",
    reply_markup=kb_specs_for_slot_admin(spec_rows, back_to="time_list")
)

    await state.set_state(AdminBook.specialist)

async def admin_specialist_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    # ab_spec:123
    specialist_id = int(callback.data.split(":", 1)[1])

    specialist_name = get_specialist_name_by_id(specialist_id)
    if not specialist_name:
        await callback.answer("Специалист не найден", show_alert=True)
        return

    data = await state.get_data()
    await state.update_data(specialist_id=specialist_id, specialist=specialist_name)

    if data.get("date") and data.get("time"):
        await callback.message.edit_text(
            f"📞 Админ-запись\n"
            f"Услуга: {data['service']}\n"
            f"Дата: {data['date']}\n"
            f"Время: {data['time']}\n"
            f"Специалист: {specialist_name}\n\n"
            f"Введите имя клиента:"
        )
        await state.set_state(AdminBook.name)
        return

    dates = get_free_dates_for_specialist(specialist_id)
    if not dates:
        await callback.message.edit_text("😔 У специалиста нет свободных дат.")
        await state.clear()
        return

    await callback.message.edit_text(
    f"📞 Админ-запись\nСпециалист: {specialist_name}\nВыберите дату:",
    reply_markup=kb_dates_admin(dates, "ab_date_spec", back_to="spec_list")
)
    
    await state.set_state(AdminBook.date)

async def admin_date_spec_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    date_ = callback.data.split("ab_date_spec:", 1)[1]
    data = await state.get_data()
    specialist_id = data["specialist_id"]
    await state.update_data(date=date_)

    times = get_free_slots(specialist_id, date_)
    if not times:
        await callback.message.edit_text("На эту дату нет времени. Выберите другую дату.")
        return

    await callback.message.edit_text(
    f"📞 Админ-запись\nДата: {date_}\nВыберите время:",
    reply_markup=kb_times_admin(times, "ab_time_spec", back_to="date_spec_list")
)

    await state.set_state(AdminBook.time)

async def admin_name_chosen(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Введите телефон клиента:")
    await state.set_state(AdminBook.phone)

async def admin_time_spec_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    time_ = callback.data.split("ab_time_spec:", 1)[1]
    await state.update_data(time=time_)

    await callback.message.edit_text("Введите имя клиента:")
    await state.set_state(AdminBook.name)

async def admin_back_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    target = callback.data.split("ab_back:", 1)[1]
    data = await state.get_data()

    # 0) назад к выбору услуги
    if target == "service":
        await state.clear()
        await callback.message.edit_text(
            "📞 Админ-запись: выберите услугу",
            reply_markup=kb_services_admin()
        )
        await state.set_state(AdminBook.service)
        return

    # 1) назад к выбору пути
    if target == "path":
        service = data.get("service")
        await callback.message.edit_text(
            f"📞 Админ-запись\nУслуга: {service}\n\nКак будем подбирать запись?",
            reply_markup=kb_admin_path()
        )
        await state.set_state(AdminBook.path)
        return

    # 2) назад к списку специалистов (specialist-first)
    if target == "spec_list":
        service = data.get("service")
        specs = get_specialists_for_service(service)
        await callback.message.edit_text(
            "📞 Админ-запись\nВыберите специалиста:",
            reply_markup=kb_admin_specs(specs)
        )
        await state.set_state(AdminBook.specialist)
        return

    # 3) назад к списку дат (datetime-first)
    if target == "date_list":
        dates = get_free_dates_all()
        await callback.message.edit_text(
            "📞 Админ-запись\nВыберите дату:",
            reply_markup=kb_dates_admin(dates, "ab_date", back_to="path")
        )
        await state.set_state(AdminBook.date)
        return

    # 4) назад к списку времени (datetime-first)
    if target == "time_list":
        date_ = data.get("date")
        times = get_free_times_all_on_date(date_)
        await callback.message.edit_text(
            f"📞 Админ-запись\nДата: {date_}\nВыберите время:",
            reply_markup=kb_times_admin(times, "ab_time", back_to="date_list")
        )
        await state.set_state(AdminBook.time)
        return

    # 5) назад к выбору даты врача (specialist-first)
    if target == "date_spec_list":
        specialist_id = data.get("specialist_id")
        specialist_name = data.get("specialist")
        dates = get_free_dates_for_specialist(specialist_id)
        await callback.message.edit_text(
            f"📞 Админ-запись\nСпециалист: {specialist_name}\nВыберите дату:",
            reply_markup=kb_dates_admin(dates, "ab_date_spec", back_to="spec_list")
        )
        await state.set_state(AdminBook.date)
        return

    # 6) назад к выбору времени врача (specialist-first)
    if target == "time_spec_list":
        specialist_id = data.get("specialist_id")
        date_ = data.get("date")
        times = get_free_slots(specialist_id, date_)
        await callback.message.edit_text(
            f"📞 Админ-запись\nДата: {date_}\nВыберите время:",
            reply_markup=kb_times_admin(times, "ab_time_spec", back_to="date_spec_list")
        )
        await state.set_state(AdminBook.time)
        return



async def admin_phone_chosen(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    data = await state.get_data()

    ok = admin_book_appointment(
        service=data["service"],
        specialist_id=data["specialist_id"],
        date=data["date"],
        time=data["time"],
        name=data["name"],
        phone=data["phone"]
    )

    if not ok:
        await message.answer("❌ Этот слот уже заняли. Начните заново: /book")
        await state.clear()
        return

    await message.answer(
        "✅ Запись по телефону создана!\n"
        f"Услуга: {data['service']}\n"
        f"Специалист: {data['specialist']}\n"
        f"Дата: {data['date']}\n"
        f"Время: {data['time']}\n"
        f"Клиент: {data['name']}\n"
        f"Телефон: {data['phone']}\n"
        f"Источник: phone"
    )
    await state.clear()




ADMIN_IDS = {1071651315}  # тот же список (можно импортировать из bot.py)

class IsAdmin(Filter):
    async def __call__(self, message: types.Message) -> bool:
        return bool(message.from_user) and message.from_user.id in ADMIN_IDS

BACK = "⬅️ Назад"

def add_back(builder: InlineKeyboardBuilder, back_to: str):
    builder.button(text=BACK, callback_data=f"back:{back_to}")
    return builder

ADMIN_BACK = "⬅️ Назад"

def add_admin_back(builder: InlineKeyboardBuilder, back_to: str):
    builder.button(text=ADMIN_BACK, callback_data=f"ab_back:{back_to}")
    return builder




# ---------- keyboards ----------

def kb_services():
    builder = InlineKeyboardBuilder()
    for service in get_services():
        builder.button(text=service, callback_data=f"service:{service}")
    builder.adjust(1)
    return builder.as_markup()

def kb_services_admin():
    b = InlineKeyboardBuilder()
    for service in get_services():
        b.button(text=service, callback_data=f"ab_service:{service}")
    b.adjust(1)
    return b.as_markup()

def kb_path():
    builder = InlineKeyboardBuilder()
    builder.button(text="👨‍⚕️ Сначала выбрать специалиста", callback_data="path:specialist")
    builder.button(text="🗓️ Сначала выбрать дату и время", callback_data="path:datetime")
    builder.adjust(1)
    add_back(builder, "service")
    return builder.as_markup()

def kb_admin_path():
    b = InlineKeyboardBuilder()
    b.button(text="👨‍⚕️ Сначала специалист", callback_data="ab_path:specialist")
    b.button(text="🗓️ Сначала дата и время", callback_data="ab_path:datetime")
    b.adjust(1)
    add_admin_back(b, "service")
    return b.as_markup()



def kb_admin_specs(specs):
    b = InlineKeyboardBuilder()
    for name in specs:
        sid = get_specialist_id(name)
        b.button(text=name, callback_data=f"ab_spec:{sid}")
    b.adjust(1)
    add_admin_back(b, "path")
    return b.as_markup()




def kb_specialists(specs, back_to: str = "path"):
    builder = InlineKeyboardBuilder()
    for s in specs:
        builder.button(text=s, callback_data=f"spec:{s}")
    builder.adjust(1)
    add_back(builder, back_to)
    return builder.as_markup()



def kb_dates(dates, prefix: str, back_to: str):
    builder = InlineKeyboardBuilder()
    for d in dates:
        builder.button(text=d, callback_data=f"{prefix}:{d}")
    builder.adjust(2)
    add_back(builder, back_to)
    return builder.as_markup()

def kb_dates_admin(dates, prefix, back_to: str):
    b = InlineKeyboardBuilder()
    for d in dates:
        b.button(text=d, callback_data=f"{prefix}:{d}")
    b.adjust(2)
    add_admin_back(b, back_to)
    return b.as_markup()




def kb_times(times, prefix: str, back_to: str):
    builder = InlineKeyboardBuilder()
    for t in times:
        builder.button(text=t, callback_data=f"{prefix}:{t}")
    builder.adjust(3)
    add_back(builder, back_to)
    return builder.as_markup()

def kb_times_admin(times, prefix, back_to: str):
    b = InlineKeyboardBuilder()
    for t in times:
        b.button(text=t, callback_data=f"{prefix}:{t}")
    b.adjust(3)
    add_admin_back(b, back_to)
    return b.as_markup()




def kb_specs_for_slot(spec_rows, back_to: str = "time_all"):
    builder = InlineKeyboardBuilder()
    for sid, name in spec_rows:
        builder.button(text=name, callback_data=f"specid:{sid}")
    builder.adjust(1)
    add_back(builder, back_to)
    return builder.as_markup()

def kb_specs_for_slot_admin(spec_rows, back_to: str = "time_list"):
    b = InlineKeyboardBuilder()
    for sid, name in spec_rows:
        b.button(text=name, callback_data=f"ab_spec:{sid}")
    b.adjust(1)
    add_admin_back(b, back_to)
    return b.as_markup()





def kb_cancel_list(rows):
    b = InlineKeyboardBuilder()
    for appt_id, service, specialist_id, date, time in rows:
        spec_name = get_specialist_name_by_id(specialist_id) or f"ID {specialist_id}"
        b.button(
            text=f"{date} {time} — {service} — {spec_name}",
            callback_data=f"cancel:{appt_id}"
        )
    b.adjust(1)
    return b.as_markup()



async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    rows = get_user_appointments(message.from_user.id)
    if not rows:
        await message.answer("У вас нет активных записей.")
        return
    await message.answer("Выберите запись для отмены:", reply_markup=kb_cancel_list(rows))
    rows = get_user_appointments(message.from_user.id)
    print("ROWS:", rows)
    await message.answer(f"ROWS COUNT: {len(rows)}")

    print("CMD_CANCEL FIRED", message.from_user.id)
    await message.answer("CMD_CANCEL FIRED ✅")




async def cancel_chosen(callback: CallbackQuery):
    appt_id = int(callback.data.split("cancel:", 1)[1])

    ok = cancel_appointment(appt_id, callback.from_user.id)
    if ok:
        await callback.message.edit_text("✅ Запись отменена. Слот снова доступен.")
    else:
        await callback.message.edit_text("❌ Не удалось отменить (возможно, запись уже отменили).")

    await callback.answer()


# ---------- start ----------

async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Выберите услугу:", reply_markup=kb_services())
    await state.set_state(Appointment.service)


# ---------- service -> path ----------

async def service_chosen(callback: CallbackQuery, state: FSMContext):
    service = callback.data.split("service:", 1)[1]
    await state.update_data(service=service)

    await callback.message.edit_text(
        f"Вы выбрали услугу: {service}\n\nКак будем подбирать запись?",
        reply_markup=kb_path()
    )
    await state.set_state(Appointment.path)
    await callback.answer()

async def path_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()  # убираем "крутилку"

    path = callback.data.split("path:", 1)[1]
    await state.update_data(path=path)

    data = await state.get_data()
    service = data["service"]

    if path == "specialist":
        # показываем специалистов по услуге
        specs = get_specialists_for_service(service)
        if not specs:
            await callback.message.edit_text(
                "Для выбранной услуги нет специалистов 😔\nНачните заново: /start"
            )
            await state.clear()
            return

        await callback.message.edit_text(
            "Выберите специалиста:",
            reply_markup=kb_specialists(specs, back_to="path")  # ⬅️ ВАЖНО: back_to="path"
        )
        await state.set_state(Appointment.specialist)

    else:
        # сначала выбираем дату
        dates = get_free_dates_all()
        if not dates:
            await callback.message.edit_text("Пока нет доступных слотов 😔")
            await state.clear()
            return

        await callback.message.edit_text(
            "Выберите дату:",
            reply_markup=kb_dates(dates, "date_all", back_to="path")  # ⬅️ ВАЖНО: back_to="path"
        )
        await state.set_state(Appointment.date)

# ---------- specialist-first branch ----------

async def specialist_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()  # убираем "крутилку" сразу

    specialist_name = callback.data.split("spec:", 1)[1]
    data = await state.get_data()
    service = data.get("service")

    # ✅ Проверяем: выбранный специалист действительно оказывает выбранную услугу
    allowed_specs = get_specialists_for_service(service)
    if specialist_name not in allowed_specs:
        await callback.answer("Этот специалист не оказывает выбранную услугу.", show_alert=True)
        # возвращаем список правильных специалистов
        await callback.message.edit_text(
            "Выберите специалиста:",
            reply_markup=kb_specialists(allowed_specs, back_to="path")
        )
        await state.set_state(Appointment.specialist)
        return

    specialist_id = get_specialist_id(specialist_name)
    if not specialist_id:
        await callback.answer("Специалист не найден.", show_alert=True)
        return

    # сохраняем выбранного специалиста
    await state.update_data(specialist=specialist_name, specialist_id=specialist_id)

    # получаем даты, где у него есть свободные слоты
    dates = get_free_dates_for_specialist(specialist_id)
    if not dates:
        await callback.message.edit_text(
            f"У специалиста {specialist_name} нет свободных слотов 😔\nВыберите другого специалиста:",
            reply_markup=kb_specialists(allowed_specs, back_to="path")  # ⬅️ назад к выбору пути
        )
        await state.set_state(Appointment.specialist)
        return

    # показываем даты + кнопку назад (на список специалистов)
    await callback.message.edit_text(
        f"Специалист: {specialist_name}\nВыберите дату:",
        reply_markup=kb_dates(dates, "date_spec", back_to="specialist")
    )
    await state.set_state(Appointment.date)


async def date_spec_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    date = callback.data.split("date_spec:", 1)[1]
    data = await state.get_data()
    specialist_id = data["specialist_id"]

    times = get_free_slots(specialist_id, date)
    if not times:
        # если пока ты выбирал(а), кто-то занял время — обновим даты специалиста
        dates = get_free_dates_for_specialist(specialist_id)
        await callback.message.edit_text(
            "На эту дату уже нет времени. Выберите другую дату:",
            reply_markup=kb_dates(dates, "date_spec", back_to="specialist")
        )
        await state.set_state(Appointment.date)
        return

    await state.update_data(date=date)

    await callback.message.edit_text(
        f"Дата: {date}\nВыберите время:",
        reply_markup=kb_times(times, "time_spec", back_to="date_spec")  # ⬅️ назад к выбору даты
    )
    await state.set_state(Appointment.time)



async def time_spec_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    time = callback.data.split("time_spec:", 1)[1]
    data = await state.get_data()

    specialist_id = data["specialist_id"]
    date = data["date"]

    # бронируем слот
    if not book_slot(specialist_id, date, time):
        times = get_free_slots(specialist_id, date)
        await callback.message.edit_text(
            "Этот слот уже заняли. Выберите другое время:",
            reply_markup=kb_times(times, "time_spec", back_to="date_spec")
        )
        await state.set_state(Appointment.time)
        return

    # ✅ важно для кнопки Назад
    await state.update_data(time=time, slot_booked=True)

    await callback.message.edit_text("Введите ваше имя:")
    await state.set_state(Appointment.name)



# ---------- datetime-first branch ----------

async def date_all_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    date = callback.data.split("date_all:", 1)[1]
    times = get_free_times_all_on_date(date)

    if not times:
        dates = get_free_dates_all()
        await callback.message.edit_text(
            "На эту дату слотов уже нет. Выберите другую дату:",
            reply_markup=kb_dates(dates, "date_all", back_to="path")
        )
        await state.set_state(Appointment.date)
        return

    await state.update_data(date=date)

    await callback.message.edit_text(
        f"Дата: {date}\nВыберите время:",
        reply_markup=kb_times(times, "time_all", back_to="date_all")  # ⬅️ назад к выбору даты
    )
    await state.set_state(Appointment.time)


async def time_all_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    time = callback.data.split("time_all:", 1)[1]
    data = await state.get_data()
    date = data["date"]
    service = data["service"]

    # показываем только тех, кто делает услугу и свободен в этот слот
    spec_rows = get_specialists_free_on_for_service(service, date, time)
    if not spec_rows:
        times = get_free_times_all_on_date(date)
        await callback.message.edit_text(
            "Этот слот уже заняли. Выберите другое время:",
            reply_markup=kb_times(times, "time_all", back_to="date_all")
        )
        await state.set_state(Appointment.time)
        return

    await state.update_data(time=time)

    await callback.message.edit_text(
        f"Дата: {date}\nВремя: {time}\nВыберите специалиста:",
        reply_markup=kb_specs_for_slot(spec_rows, back_to="time_all")
    )
    await state.set_state(Appointment.specialist)


async def specialist_id_chosen(callback: CallbackQuery, state: FSMContext):
    await callback.answer()  # чтобы не было "крутилки" (один раз в начале)

    specialist_id = int(callback.data.split("specid:", 1)[1])
    data = await state.get_data()

    # подтверждаем имя специалиста
    specialist_name = get_specialist_name_by_id(specialist_id)
    if not specialist_name:
        await callback.answer("Специалист не найден.", show_alert=True)
        return

    date = data["date"]
    time = data["time"]

    # бронируем слот только тут (после выбора специалиста)
    if not book_slot(specialist_id, date, time):
        await callback.message.edit_text("К сожалению, этот слот уже заняли. Начните заново: /start")
        await state.clear()
        return

    # ✅ ВСТАВЛЕНО: помечаем, что слот уже забронирован (для кнопки "Назад")
    await state.update_data(
        specialist_id=specialist_id,
        specialist=specialist_name,
        slot_booked=True  # <-- важно
    )

    await callback.message.edit_text("Введите ваше имя:")
    await state.set_state(Appointment.name)



# ---------- name/phone/save ----------

async def name_chosen(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Введите ваш телефон:")
    await state.set_state(Appointment.phone)

async def phone_chosen(message: types.Message, state: FSMContext):
    phone = message.text.strip()
    await state.update_data(phone=phone)
    data = await state.get_data()

    tg_user_id = message.from_user.id  # <-- это ты уже сделал

    save_appointment(
        service=data["service"],
        specialist_id=data["specialist_id"],
        date=data["date"],
        time=data["time"],
        name=data["name"],
        phone=data["phone"],
        tg_user_id=tg_user_id
    )

    await message.answer(
        "✅ Вы успешно записаны!\n"
        f"Услуга: {data['service']}\n"
        f"Специалист: {data['specialist']}\n"
        f"Дата: {data['date']}\n"
        f"Время: {data['time']}\n"
        f"Имя: {data['name']}\n"
        f"Телефон: {data['phone']}"
    )
    await state.clear()

# ---------- register ----------

async def debug_any_callback(callback: CallbackQuery):
    # Это поймает любые нажатия, если основной хендлер не сработал
    await callback.answer(f"DEBUG: {callback.data}", show_alert=True)

async def back_callback(callback: CallbackQuery, state: FSMContext):

    await callback.answer()

    target = callback.data.split("back:", 1)[1]
    data = await state.get_data()

    # Если слот уже забронирован и мы уходим назад — освобождаем
    if data.get("slot_booked") and data.get("specialist_id") and data.get("date") and data.get("time"):
        unbook_slot(data["specialist_id"], data["date"], data["time"])
        await state.update_data(slot_booked=False, time=None)

    # ---- маршрутизация назад ----

    if target == "service":
        await state.clear()
        await callback.message.edit_text("Выберите услугу:", reply_markup=kb_services())
        await state.set_state(Appointment.service)
        return

    if target == "path":
        service = data.get("service")
        await callback.message.edit_text(
            f"Вы выбрали услугу: {service}\n\nКак будем подбирать запись?",
            reply_markup=kb_path()
        )
        await state.set_state(Appointment.path)
        return

    if target == "date_spec":
        specialist_id = data.get("specialist_id")
        specialist = data.get("specialist")
        dates = get_free_dates_for_specialist(specialist_id)
        await callback.message.edit_text(
            f"Специалист: {specialist}\nВыберите дату:",
            reply_markup=kb_dates(dates, "date_spec", back_to="specialist")
        )
        await state.set_state(Appointment.date)
        return

    if target == "date_all":
        dates = get_free_dates_all()
        await callback.message.edit_text(
            "Выберите дату:",
            reply_markup=kb_dates(dates, "date_all", back_to="path")
        )
        await state.set_state(Appointment.date)
        return

    if target == "time_spec":
        specialist_id = data.get("specialist_id")
        date = data.get("date")
        times = get_free_slots(specialist_id, date)
        await callback.message.edit_text(
            f"Дата: {date}\nВыберите время:",
            reply_markup=kb_times(times, "time_spec", back_to="date_spec")
        )
        await state.set_state(Appointment.time)
        return

    if target == "time_all":
        date = data.get("date")
        times = get_free_times_all_on_date(date)
        await callback.message.edit_text(
            f"Дата: {date}\nВыберите время:",
            reply_markup=kb_times(times, "time_all", back_to="date_all")
        )
        await state.set_state(Appointment.time)
        return
    if target == "specialist":
        service = data.get("service")
        specs = get_specialists_for_service(service)
        await callback.message.edit_text(
            "Выберите специалиста:",
            reply_markup=kb_specialists(specs, back_to="path")
        )
        await state.set_state(Appointment.specialist)
        return

async def back_text(message: types.Message, state: FSMContext):
    data = await state.get_data()

    # если уже бронировали слот — освобождаем
    if data.get("slot_booked") and data.get("specialist_id") and data.get("date") and data.get("time"):
        unbook_slot(data["specialist_id"], data["date"], data["time"])
        await state.update_data(slot_booked=False, time=None)

    path = data.get("path")
    if path == "specialist":
        # вернуть на выбор времени врача
        times = get_free_slots(data["specialist_id"], data["date"])
        await message.answer(
            f"Дата: {data['date']}\nВыберите время:",
            reply_markup=kb_times(times, "time_spec", back_to="date_spec")
        )
        await state.set_state(Appointment.time)
    else:
        times = get_free_times_all_on_date(data["date"])
        await message.answer(
            f"Дата: {data['date']}\nВыберите время:",
            reply_markup=kb_times(times, "time_all", back_to="date_all")
        )
        await state.set_state(Appointment.time)

async def cmd_today(message: types.Message):
    d = date.today().isoformat()
    rows = get_appointments_on(d)
    if not rows:
        await message.answer(f"На {d} записей нет.")
        return

    text = [f"📅 Записи на {d}:"]
    for appt_id, service, spec_name, t, client, phone, source in rows:
        text.append(f"• {t} — {service} — {spec_name} — {client} ({phone}) [{source}]")
    await message.answer("\n".join(text))

async def cmd_tomorrow(message: types.Message):
    d = (date.today() + timedelta(days=1)).isoformat()
    rows = get_appointments_on(d)
    if not rows:
        await message.answer(f"На {d} записей нет.")
        return

    text = [f"📅 Записи на {d}:"]
    for appt_id, service, spec_name, t, client, phone, source in rows:
        text.append(f"• {t} — {service} — {spec_name} — {client} ({phone}) [{source}]")
    await message.answer("\n".join(text))


async def debug_any_command(message: types.Message):
    print("GOT COMMAND:", message.text)
    await message.answer(f"Команда дошла: {message.text}")


async def debug_cb(callback: CallbackQuery, state: FSMContext):
    st = await state.get_state()
    print("DEBUG CALLBACK:", callback.data, "STATE:", st)
    await callback.answer(f"{callback.data} | {st}", show_alert=True)

def register_handlers(dp):
    print("REGISTER_HANDLERS ENTERED")

    # =========================
    # COMMANDS
    # =========================
    dp.message.register(cmd_start, Command("start"), StateFilter("*"))
    dp.message.register(cmd_cancel, Command("cancel"), StateFilter("*"))
    dp.message.register(cmd_myid, Command("myid"), StateFilter("*"))
    dp.message.register(ping, Command("ping"), StateFilter("*"))

    dp.message.register(cmd_today, Command("today"), StateFilter("*"))
    dp.message.register(cmd_tomorrow, Command("tomorrow"), StateFilter("*"))
    dp.message.register(admin_book_start, Command("book"), StateFilter("*"))

    # =========================
    # ADMIN BOOK
    # =========================
    # /book только один раз!
    dp.message.register(admin_book_start, Command("book"), IsAdmin(), StateFilter("*"))
    dp.message.register(cmd_book_denied, Command("book"), StateFilter("*"))

    dp.callback_query.register(admin_service_chosen, F.data.startswith("ab_service:"), StateFilter(AdminBook.service))
    dp.callback_query.register(admin_path_chosen, F.data.startswith("ab_path:"), StateFilter(AdminBook.path))
    dp.callback_query.register(admin_specialist_chosen, F.data.startswith("ab_spec:"), StateFilter(AdminBook.specialist))

    dp.callback_query.register(admin_date_chosen, F.data.startswith("ab_date:"), StateFilter(AdminBook.date))    
    dp.callback_query.register(admin_time_chosen, F.data.startswith("ab_time:"), StateFilter(AdminBook.time))

    dp.callback_query.register(admin_date_spec_chosen, F.data.startswith("ab_date_spec:"), StateFilter(AdminBook.date))
    dp.callback_query.register(admin_time_spec_chosen, F.data.startswith("ab_time_spec:"), StateFilter(AdminBook.time))

    dp.callback_query.register(admin_back_callback, F.data.startswith("ab_back:"), StateFilter("*"))

    dp.message.register(admin_name_chosen, StateFilter(AdminBook.name), ~F.text.startswith("/"))
    dp.message.register(admin_phone_chosen, StateFilter(AdminBook.phone), ~F.text.startswith("/"))

    # =========================
    # CLIENT FLOW
    # =========================
    dp.callback_query.register(service_chosen, F.data.startswith("service:"), StateFilter(Appointment.service))
    dp.callback_query.register(path_chosen, F.data.startswith("path:"), StateFilter(Appointment.path))

    dp.callback_query.register(specialist_chosen, F.data.startswith("spec:"), StateFilter(Appointment.specialist))
    dp.callback_query.register(date_spec_chosen, F.data.startswith("date_spec:"), StateFilter(Appointment.date))
    dp.callback_query.register(time_spec_chosen, F.data.startswith("time_spec:"), StateFilter(Appointment.time))

    dp.callback_query.register(date_all_chosen, F.data.startswith("date_all:"), StateFilter(Appointment.date))
    dp.callback_query.register(time_all_chosen, F.data.startswith("time_all:"), StateFilter(Appointment.time))
    dp.callback_query.register(specialist_id_chosen, F.data.startswith("specid:"), StateFilter(Appointment.specialist))

    dp.callback_query.register(cancel_chosen, F.data.startswith("cancel:"))
    dp.callback_query.register(back_callback, F.data.startswith("back:"), StateFilter("*"))

    dp.message.register(back_text, F.text == BACK, StateFilter(Appointment.name))
    dp.message.register(back_text, F.text == BACK, StateFilter(Appointment.phone))

    dp.message.register(name_chosen, StateFilter(Appointment.name), ~F.text.startswith("/"))
    dp.message.register(phone_chosen, StateFilter(Appointment.phone), ~F.text.startswith("/"))

    # DEBUG (по желанию)
    dp.callback_query.register(debug_cb, StateFilter("*"))