from dataclasses import dataclass
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from optimizer.state import State


class ActionType(Enum):
    ADD = "add"
    MODIFY = "modify"


@dataclass(frozen=True)
class Action:
    """Rappresenta una singola modifica della configurazione."""

    type: ActionType
    node: str
    capability: str
    old_level: Optional[int]
    new_level: int

    def __post_init__(self):
        if self.type == ActionType.ADD:
            if self.old_level is not None:
                raise ValueError("ADD non deve avere un livello precedente.")

        elif self.type == ActionType.MODIFY:
            if self.old_level is None:
                raise ValueError("MODIFY richiede un livello precedente.")

            if self.old_level == self.new_level:
                raise ValueError("Il livello deve cambiare.")

    @classmethod
    def add(cls, node: str, capability: str, level: int) -> "Action":
        return cls(ActionType.ADD, node, capability, None, level)

    @classmethod
    def modify(
        cls,
        node: str,
        capability: str,
        old_level: int,
        new_level: int,
    ) -> "Action":
        return cls(ActionType.MODIFY, node, capability, old_level, new_level)

    @property
    def key(self) -> tuple[str, str]:
        return self.node, self.capability

    def __str__(self) -> str:
        if self.type == ActionType.ADD:
            return f"ADD({self.node}, {self.capability}, L{self.new_level})"

        return (
            f"MODIFY({self.node}, {self.capability}, "
            f"L{self.old_level} -> L{self.new_level})"
        )