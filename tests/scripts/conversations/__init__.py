from .couple_dinner import COUPLE_DINNER
from .big_group import BIG_GROUP
from .picky_customer import PICKY_CUSTOMER
from .solo_lunch import SOLO_LUNCH

SCENARIOS = {
    "A": COUPLE_DINNER,
    "B": BIG_GROUP,
    "C": PICKY_CUSTOMER,
    "D": SOLO_LUNCH,
}

__all__ = ["SCENARIOS"]
