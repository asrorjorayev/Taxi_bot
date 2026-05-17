from aiogram.fsm.state import State, StatesGroup


class AnnouncementStates(StatesGroup):
    phone = State()
    car_model = State()
    car_photo = State()
    route = State()
    seats = State()
    people_count = State()
    gender = State()
    baggage = State()
    departure_time = State()
    repeat_interval = State()
    preview = State()


class DriverManualStates(StatesGroup):
    waiting_photo = State()
    waiting_text = State()
    waiting_interval = State()
    confirm = State()


class DriverAutoStates(StatesGroup):
    waiting_contact = State()
    waiting_car_type = State()
    waiting_photo = State()
    waiting_direction = State()
    waiting_seat = State()
    waiting_time = State()
    waiting_interval = State()
    confirm = State()


class GroupRegistrationStates(StatesGroup):
    selecting_routes = State()
