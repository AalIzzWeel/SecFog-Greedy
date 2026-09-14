from dataclasses import dataclass
from typing import Optional

from optimizer.actions import Action, ActionType


@dataclass
class State:
    """
    Rappresenta i livelli delle capability disponibili sui nodi.

    Un livello intero indica una capability attiva.
    None indica una capability disponibile ma non attiva.
    """

    levels: Optional[dict[tuple[str, str], Optional[int]]] = None

    def __post_init__(self) -> None:
        if self.levels is None:
            self.levels = {}

    def copy(self) -> "State":
        """Restituisce una copia indipendente dello stato."""
        return State(self.levels.copy())

    def get_level(self, node: str, capability: str) -> Optional[int]:
        """Restituisce il livello corrente della capability."""
        return self.levels[(node, capability)]

    def set_level(
        self,
        node: str,
        capability: str,
        level: Optional[int],
    ) -> None:
        """Imposta il livello della capability."""
        self.levels[(node, capability)] = level

    def is_active(self, node: str, capability: str) -> bool:
        """Controlla se la capability e' attiva."""
        return self.get_level(node, capability) is not None

    def apply(self, action: Action) -> None:
        """Applica un'azione gia' validata."""
        if action.type == ActionType.ADD:
            if self.is_active(action.node, action.capability):
                raise ValueError(f"La capability {action.key} e' gia' attiva.")

        elif action.type == ActionType.MODIFY:
            current_level = self.get_level(
                action.node,
                action.capability,
            )

            if current_level is None:
                raise ValueError(f"La capability {action.key} non e' attiva.")

            if current_level != action.old_level:
                raise ValueError(
                    "Lo stato corrente non coincide con il vecchio livello "
                    "indicato dall'azione."
                )

        self.set_level(
            action.node,
            action.capability,
            action.new_level,
        )

    def key(self) -> tuple:
        """Restituisce una chiave immutabile usata dalla cache."""
        return tuple(sorted(self.levels.items()))

    def items(self):
        return self.levels.items()

    def __getitem__(self, key: tuple[str, str]) -> Optional[int]:
        return self.levels[key]

    def __contains__(self, key: tuple[str, str]) -> bool:
        return key in self.levels

    def __str__(self) -> str:
        rows = []

        for (node, capability), level in sorted(self.levels.items()):
            status = "inactive" if level is None else f"L{level}"
            rows.append(f"{node:10} | {capability:25} | {status}")

        return "\n".join(rows)

    def count_summary(self) -> tuple[int, int, int]:
        """Restituisce il numero di capability totali, attive e inattive."""
        total = len(self.levels)
        active = sum(level is not None for level in self.levels.values())
        inactive = total - active

        return total, active, inactive