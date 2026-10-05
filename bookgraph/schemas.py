"""The JSON the model returns at each stage.

llama-server turns these into a grammar, so the answer always parses; the
field descriptions are for people, the prompts tell the model what goes in.
"""

from typing import Literal

from pydantic import BaseModel, Field

Kind = Literal[
    "действие", "бой", "конфликт", "решение", "откровение", "отношения",
    "путешествие", "смерть", "воспоминание", "прочее",
]


class Character(BaseModel):
    name: str = Field(description="fullest known name, nominative")
    forms: list[str] = Field(description="every way the chunk names them, as written")
    about: str = Field(description="what this chunk tells about them, one sentence")


class Entity(BaseModel):
    name: str
    about: str


class Event(BaseModel):
    n: int = Field(description="order in the chunk, from 1")
    title: str
    what: str
    who: list[str] = Field(description="Character.name values")
    where: str
    when: str
    kind: Kind
    importance: int = Field(ge=1, le=3)
    causes: list[int] = Field(description="n of earlier events in this chunk")
    threads: list[str] = Field(description="free storyline labels")


class Relation(BaseModel):
    a: str
    b: str
    kind: str
    note: str


class ChunkFacts(BaseModel):
    summary: str
    characters: list[Character] = Field(max_length=30)
    places: list[Entity] = Field(max_length=15)
    groups: list[Entity] = Field(max_length=15)
    events: list[Event] = Field(min_length=1, max_length=15)
    relations: list[Relation] = Field(max_length=15)
