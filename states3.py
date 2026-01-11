from aiogram.fsm.state import StatesGroup, State

class Appointment(StatesGroup):
    service = State()
    path = State()
    specialist = State()
    date = State()
    time = State()
    name = State()
    phone = State()

class AdminBook(StatesGroup):
    service = State()
    path = State()        # ✅ ДОБАВЬ ЭТО
    specialist = State()
    date = State()
    time = State()
    name = State()
    phone = State()
