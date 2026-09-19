from dataclasses import dataclass, field

from optimizer.actions import Action


@dataclass
class State:
    """Livelli delle sole capability richieste e gia' attive."""

    levels: dict[tuple[str, str], int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if any(level is None for level in self.levels.values()):
            raise ValueError("Lo stato non puo' contenere capability inattive.")

    def copy(self) -> "State":
        return State(self.levels.copy())

    def get_level(self, node: str, capability: str) -> int:
        return self.levels[(node, capability)]

    def set_level(self, node: str, capability: str, level: int) -> None:
        if level is None:
            raise ValueError("Una capability non puo' essere disattivata.")
        self.levels[(node, capability)] = level

    def is_active(self, node: str, capability: str) -> bool:
        return (node, capability) in self.levels

    def is_feasible(self, action: Action) -> bool:
        return self.levels.get(action.key) == action.old_level

    def apply(self, action: Action) -> None:
        if not self.is_feasible(action):
            raise ValueError(
                "Lo stato corrente non coincide con il vecchio livello "
                "indicato dall'azione."
            )
        self.levels[action.key] = action.new_level

    def key(self) -> tuple:
        return tuple(sorted(self.levels.items()))

    def items(self):
        return self.levels.items()

    def __getitem__(self, key: tuple[str, str]) -> int:
        return self.levels[key]

    def __contains__(self, key: tuple[str, str]) -> bool:
        return key in self.levels

    def __str__(self) -> str:
        return "\n".join(
            f"{node:10} | {capability:25} | L{level}"
            for (node, capability), level in sorted(self.levels.items())
        )

    def count_summary(self) -> tuple[int, int, int]:
        total = len(self.levels)
        return total, total, 0
