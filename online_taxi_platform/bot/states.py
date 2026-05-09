from aiogram.fsm.state import State, StatesGroup


class AnnouncementStates(StatesGroup):
    full_name = State()
    phone = State()
    car_model = State()
    car_number = State()
    car_photo = State()
    route = State()
    seats = State()
    people_count = State()
    baggage = State()
    departure_time = State()
    price = State()
    note = State()
    repeat_interval = State()
    preview = State()


class GroupRegistrationStates(StatesGroup):
    selecting_routes = State()
