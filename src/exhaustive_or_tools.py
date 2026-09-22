from dataclasses import dataclass
import time
from typing import Any

from ortools.sat.python import cp_model

from optimizer.actions import Action
from optimizer.costs import CostCalculator
from optimizer.state import State


@dataclass(frozen=True)
class ExhaustiveResult:
    """Risultato della ricerca esaustiva delle configurazioni ammissibili."""

    final_state: State
    initial_score: float
    final_score: float
    net_cost: int
    remaining_budget: int
    feasible_solutions: int
    configuration_upper_bound: int
    solver_status: str
    completed: bool
    elapsed_seconds: float


class _SecFogSolutionCallback(cp_model.CpSolverSolutionCallback):
    """Valuta con SecFog ogni configurazione generata da CP-SAT."""

    EPSILON = 1e-12

    def __init__(
        self,
        variables: dict[tuple[str, str], dict[int, cp_model.IntVar]],
        initial_state: State,
        costs: CostCalculator,
        score_wrapper: Any,
        initial_score: float,
        max_solutions: int | None,
    ) -> None:
        super().__init__()
        self.variables = variables
        self.initial_state = initial_state
        self.costs = costs
        self.score_wrapper = score_wrapper
        self.max_solutions = max_solutions

        self.best_state = initial_state.copy()
        self.best_score = initial_score
        self.best_net_cost = 0
        self.feasible_solutions = 0
        self.stopped_by_limit = False

    def _decode_state(self) -> State:
        levels = {}
        for key, level_variables in self.variables.items():
            selected = [
                level
                for level, variable in level_variables.items()
                if self.Value(variable)
            ]
            if len(selected) != 1:
                raise RuntimeError(
                    f"OR-Tools ha selezionato {len(selected)} livelli per {key}."
                )
            levels[key] = selected[0]
        return State(levels)

    def _is_better(self, state: State, score: float, net_cost: int) -> bool:
        if score > self.best_score + self.EPSILON:
            return True
        if abs(score - self.best_score) > self.EPSILON:
            return False
        if net_cost != self.best_net_cost:
            return net_cost < self.best_net_cost
        return state.key() < self.best_state.key()

    def OnSolutionCallback(self) -> None:
        state = self._decode_state()
        score = self.score_wrapper.evaluate(state)
        net_cost = self.costs.calculate_net_cost(self.initial_state, state)
        self.feasible_solutions += 1

        if self._is_better(state, score, net_cost):
            self.best_state = state
            self.best_score = score
            self.best_net_cost = net_cost

        if (
            self.max_solutions is not None
            and self.feasible_solutions >= self.max_solutions
        ):
            self.stopped_by_limit = True
            self.StopSearch()


class ExhaustiveOrToolsOptimizer:
    """
    Enumeratore esatto delle configurazioni ammissibili.

    CP-SAT impone i vincoli discreti e di budget. Lo score, essendo una
    funzione black-box, viene calcolato esternamente da ScoreWrapper per
    ogni soluzione ammissibile generata dal solver.
    """

    def __init__(self, catalog: dict, score_wrapper: Any) -> None:
        self.catalog = catalog
        self.score_wrapper = score_wrapper
        self.costs = CostCalculator(catalog)

    def _available_levels(self, capability: str) -> tuple[int, ...]:
        try:
            levels = self.catalog["capabilities"][capability]["levels"]
        except KeyError as exc:
            raise ValueError(
                f"Capability {capability} non presente nel catalogo."
            ) from exc

        result = tuple(sorted(map(int, levels)))
        if not result:
            raise ValueError(f"La capability {capability} non ha livelli.")
        return result

    def _build_model(
        self,
        initial_state: State,
        budget: int,
    ) -> tuple[
        cp_model.CpModel,
        dict[tuple[str, str], dict[int, cp_model.IntVar]],
        int,
    ]:
        model = cp_model.CpModel()
        variables = {}
        final_cost_terms = []
        configuration_upper_bound = 1

        for node, capability in sorted(initial_state.levels):
            initial_level = initial_state[(node, capability)]
            levels = self._available_levels(capability)
            if initial_level not in levels:
                raise ValueError(
                    f"Livello iniziale L{initial_level} non valido per "
                    f"{node}.{capability}."
                )

            level_variables = {
                level: model.NewBoolVar(
                    f"x__{node}__{capability}__L{level}"
                )
                for level in levels
            }
            model.AddExactlyOne(level_variables.values())
            variables[(node, capability)] = level_variables
            configuration_upper_bound *= len(levels)

            for level, variable in level_variables.items():
                level_cost = self.costs.get_capability_cost(
                    capability, level
                )
                final_cost_terms.append(level_cost * variable)

        initial_cost = self.costs.calculate_state_cost(initial_state)
        model.Add(sum(final_cost_terms) <= initial_cost + budget)
        return model, variables, configuration_upper_bound

    def optimize(
        self,
        initial_state: State,
        budget: int,
        *,
        max_time_seconds: float | None = None,
        max_solutions: int | None = None,
    ) -> ExhaustiveResult:
        if budget < 0:
            raise ValueError("Il budget iniziale deve essere non negativo.")
        if max_time_seconds is not None and max_time_seconds <= 0:
            raise ValueError("Il limite di tempo deve essere positivo.")
        if max_solutions is not None and max_solutions <= 0:
            raise ValueError("Il limite di soluzioni deve essere positivo.")

        model, variables, upper_bound = self._build_model(
            initial_state, budget
        )
        initial_score = self.score_wrapper.evaluate(initial_state)
        callback = _SecFogSolutionCallback(
            variables=variables,
            initial_state=initial_state,
            costs=self.costs,
            score_wrapper=self.score_wrapper,
            initial_score=initial_score,
            max_solutions=max_solutions,
        )

        solver = cp_model.CpSolver()
        solver.parameters.enumerate_all_solutions = True
        # L'enumerazione di tutte le soluzioni richiede un solo worker.
        solver.parameters.num_search_workers = 1
        if max_time_seconds is not None:
            solver.parameters.max_time_in_seconds = max_time_seconds

        started_at = time.perf_counter()
        status = solver.Solve(model, callback)
        elapsed = time.perf_counter() - started_at
        status_name = solver.StatusName(status)
        completed = (
            status == cp_model.OPTIMAL
            and not callback.stopped_by_limit
        )

        if callback.feasible_solutions == 0 and status == cp_model.INFEASIBLE:
            raise RuntimeError("Il modello OR-Tools non ha soluzioni ammissibili.")

        return ExhaustiveResult(
            final_state=callback.best_state,
            initial_score=initial_score,
            final_score=callback.best_score,
            net_cost=callback.best_net_cost,
            remaining_budget=budget - callback.best_net_cost,
            feasible_solutions=callback.feasible_solutions,
            configuration_upper_bound=upper_bound,
            solver_status=status_name,
            completed=completed,
            elapsed_seconds=elapsed,
        )


def build_adjacent_policy(
    initial_state: State,
    final_state: State,
    catalog: dict,
) -> list[Action]:
    """Espande ogni modifica finale in transizioni di livello adiacenti."""
    if set(initial_state.levels) != set(final_state.levels):
        raise ValueError(
            "Stato iniziale e finale devono contenere le stesse coppie."
        )

    policy = []
    for (node, capability), initial_level in sorted(initial_state.items()):
        final_level = final_state[(node, capability)]
        levels = tuple(
            sorted(
                map(
                    int,
                    catalog["capabilities"][capability]["levels"],
                )
            )
        )
        initial_index = levels.index(initial_level)
        final_index = levels.index(final_level)

        if final_index > initial_index:
            transitions = zip(
                levels[initial_index:final_index],
                levels[initial_index + 1 : final_index + 1],
            )
        else:
            descending = levels[final_index : initial_index + 1][::-1]
            transitions = zip(descending, descending[1:])

        policy.extend(
            Action.modify(node, capability, old_level, new_level)
            for old_level, new_level in transitions
        )

    return policy
