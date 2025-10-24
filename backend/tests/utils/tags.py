from sqlmodel import Session

from app import crud
from app.models import Tag, TagCreate
from tests.utils.utils import random_lower_string


def create_random_tag(db: Session) -> Tag:
    name = random_lower_string()
    description = random_lower_string()
    tag_in = TagCreate(name=name, description=description)
    return crud.create_tag(session=db, tag_in=tag_in)
