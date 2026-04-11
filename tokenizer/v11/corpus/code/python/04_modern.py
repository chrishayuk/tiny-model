from __future__ import annotations
from typing import Optional, TypeVar, Generic, Protocol
from dataclasses import dataclass, field
from enum import Enum


T = TypeVar("T")


class Status(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    ARCHIVED = "archived"


@dataclass
class User:
    id: int
    name: str
    email: str
    age: Optional[int] = None
    tags: list[str] = field(default_factory=list)

    def display_name(self) -> str:
        return f"{self.name} <{self.email}>"

    def with_tag(self, tag: str) -> User:
        return User(
            id=self.id,
            name=self.name,
            email=self.email,
            age=self.age,
            tags=[*self.tags, tag],
        )


class Repository(Protocol, Generic[T]):
    def get(self, id: int) -> Optional[T]: ...
    def save(self, item: T) -> T: ...
    def delete(self, id: int) -> bool: ...


class UserRepository:
    def __init__(self, session):
        self.session = session

    def get(self, id: int) -> Optional[User]:
        return self.session.query(User).filter_by(id=id).first()

    def save(self, user: User) -> User:
        self.session.add(user)
        self.session.commit()
        return user
