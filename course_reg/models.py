from dataclasses import dataclass

@dataclass
class Filters:
    ge_cat: int
    department: int
    course_num: str
    course_code: int
    course_level: str
    instructor: str


@dataclass
class AdvancedFilters(Filters):
    modality: str
    days: str
    starts_after: str
    ends_before: str
    course_full_option: str
    cancel_option: str
    building_code: str
    room_no: str
    credits: int