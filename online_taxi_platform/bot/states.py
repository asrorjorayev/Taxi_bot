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


class GroupRegistrationStates(StatesGroup):
    selecting_routes = State()
