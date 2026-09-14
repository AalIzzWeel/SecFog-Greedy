from optimizer.actions import Action
from optimizer.state import State


class CostCalculator:
    """Calcola i costi dei livelli e le variazioni di costo."""

    def __init__(self, catalog: dict):
        self.capabilities = catalog.get("capabilities", {})

    def get_capability_cost(self, capability: str, level: int) -> int:
        if capability not in self.capabilities:
            raise ValueError(f"Capability {capability} non presente nel catalogo.")

        levels = self.capabilities[capability].get("levels", {})
        level_key = str(level)

        if level_key not in levels:
            raise ValueError(
                f"Livello {level} non trovato per la capability {capability}."
            )

        return int(levels[level_key]["cost"])

    def calculate_action_cost(self, action: Action) -> int:
        """Calcola delta c = c(new) - c(old), con c(None) = 0."""
        new_cost = self.get_capability_cost(
            action.capability,
            action.new_level,
        )

        old_cost = 0
        if action.old_level is not None:
            old_cost = self.get_capability_cost(
                action.capability,
                action.old_level,
            )

        return new_cost - old_cost

    def calculate_state_cost(self, state: State) -> int:
        total = 0

        for (_, capability), level in state.items():
            if level is None:
                continue

            total += self.get_capability_cost(capability, level)

        return total

    def calculate_net_cost(
        self,
        initial_state: State,
        final_state: State,
    ) -> int:
        """Calcola il costo netto finale rispetto allo stato iniziale."""
        if set(initial_state.levels) != set(final_state.levels):
            raise ValueError(
                "Stato iniziale e finale devono contenere le stesse coppie."
            )

        return (
            self.calculate_state_cost(final_state)
            - self.calculate_state_cost(initial_state)
        )
