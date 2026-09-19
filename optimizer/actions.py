from dataclasses import dataclass


@dataclass(frozen=True)
class Action:
    """Modulazione del livello di una capability gia' attiva."""

    node: str
    capability: str
    old_level: int
    new_level: int

    def __post_init__(self) -> None:
        if self.old_level == self.new_level:
            raise ValueError("Il livello deve cambiare.")

    @classmethod
    def modify(
        cls, node: str, capability: str, old_level: int, new_level: int
    ) -> "Action":
        return cls(node, capability, old_level, new_level)

    @property
    def key(self) -> tuple[str, str]:
        return self.node, self.capability

    @property
    def is_upgrade(self) -> bool:
        return self.new_level > self.old_level

    @property
    def is_downgrade(self) -> bool:
        return self.new_level < self.old_level

    def __str__(self) -> str:
        return (
            f"MODIFY({self.node}, {self.capability}, "
            f"L{self.old_level} -> L{self.new_level})"
        )