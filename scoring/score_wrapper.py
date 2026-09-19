import time
from typing import Any

#from optimizer.profiler import profile
from optimizer.utils import validate_placement


class ScoreWrapper:
    """
    Converte uno State in un programma ProbLog e restituisce lo score SecFog.

    Il catalogo descrive le security capability.
    L'infrastruttura descrive i nodi disponibili.
    L'applicazione descrive servizi e security requirements.
    Il placement fissa l'assegnazione servizio -> nodo.
    """

    CATEGORY_ORDER = [
        "virtualization",
        "communication",
        "data",
        "physical",
    ]

    def __init__(
        self,
        catalog: dict,
        infrastructure: dict,
        application: dict,
        placement: dict,
        base_path: str = "prolog/secfog_base.pl",
    ):
        validate_placement(
            catalog,
            infrastructure,
            placement,
        )

        self.catalog = catalog
        self.infrastructure = infrastructure
        self.application = application
        self.placement = placement
        self.base_path = base_path

        self._validate_application()

        self._cache: dict[tuple, float] = {}
        self._solver_evaluations = 0

        with open(
            self.base_path,
            "r",
            encoding="utf-8",
        ) as file:
            self._base_rules = file.read()

    @property
    def cache_size(self) -> int:
        return len(self._cache)

    @property
    def solver_evaluations(self) -> int:
        return self._solver_evaluations

    def clear_cache(self) -> None:
        self._cache.clear()

    def _validate_application(self) -> None:
        """
        Verifica che i componenti presenti nel placement
        esistano anche nell'applicazione.
        """
        services = self.application.get(
            "services",
            {},
        )

        if not services:
            raise ValueError(
                "L'applicazione non contiene servizi."
            )

        placement_services = {
            component["name"]
            for component in self.placement["components"]
        }

        missing = placement_services - set(services)

        if missing:
            raise ValueError(
                "Servizi del placement non presenti "
                f"nell'applicazione: {sorted(missing)}"
            )

    #@profile("3. ScoreWrapper.evaluate")
    def evaluate(self, state: Any) -> float:
        state_key = state.key()

        if state_key in self._cache:
            return self._cache[state_key]

        program = self._build_program(state)
        score = self._run_problog_api(program)

        self._cache[state_key] = score

        return score

    #@profile("3.1 ScoreWrapper._build_program")
    def _build_program(self, state: Any) -> str:
        return (
            "%%% BASE RULES %%%\n"
            f"{self._base_rules}\n\n"
            "%%% STRUCTURE %%%\n"
            f"{self._build_structure()}\n\n"
            "%%% SECURITY REQUIREMENTS %%%\n"
            f"{self._build_security_requirements()}\n\n"
            "%%% ACTIVE PROBABILISTIC FACTS %%%\n"
            f"{self._build_probabilistic_facts(state)}\n\n"
            "%%% QUERY %%%\n"
            f"{self._build_query()}\n"
        )

    def _build_structure(self) -> str:
        """
        Genera i fatti ProbLog relativi ai nodi
        e alla struttura dell'applicazione.
        """
        lines = [
            "%%% Nodi dell'infrastruttura"
        ]

        for node_name, node_data in (
            self.infrastructure
            .get("nodes", {})
            .items()
        ):
            operator = node_data.get(
                "operator",
                f"{node_data.get('type', 'edge')}Op",
            )

            lines.append(
                f"node({node_name}, {operator})."
            )

        service_names = list(
            self.application["services"]
        )

        application_name = self.application.get(
            "name",
            self.placement.get(
                "application",
                "scalable_app",
            ),
        )

        lines.extend(
            [
                "",
                "%%% Applicazione",
                (
                    f"app({application_name}, "
                    f"[{', '.join(service_names)}])."
                ),
            ]
        )

        return "\n".join(lines)

    def _requirement_to_prolog(
        self,
        requirement,
    ) -> str:
        """
        Traduce ricorsivamente un requirement JSON
        nella corrispondente espressione ProbLog.
        """
        if isinstance(requirement, str):
            return f"{requirement}(N)"

        if not isinstance(requirement, dict):
            raise ValueError(
                f"Requirement non valido: {requirement}"
            )

        if "all" in requirement:
            children = requirement["all"]

            if not children:
                raise ValueError(
                    "Un requirement 'all' non puo' essere vuoto."
                )

            translated = [
                self._requirement_to_prolog(child)
                for child in children
            ]

            return (
                "("
                + ", ".join(translated)
                + ")"
            )

        if "any" in requirement:
            children = requirement["any"]

            if not children:
                raise ValueError(
                    "Un requirement 'any' non puo' essere vuoto."
                )

            translated = [
                self._requirement_to_prolog(child)
                for child in children
            ]

            return (
                "("
                + "; ".join(translated)
                + ")"
            )

        raise ValueError(
            f"Operatore requirement sconosciuto: {requirement}"
        )

    def _build_security_requirements(self) -> str:
        """
        Genera le regole securityRequirements/2
        per tutti i servizi dell'applicazione.
        """
        lines = []

        for service_name, service_data in (
            self.application["services"].items()
        ):
            requirement = service_data.get(
                "requirements"
            )

            if requirement is None:
                raise ValueError(
                    f"Il servizio {service_name} "
                    "non contiene requirements."
                )

            body = self._requirement_to_prolog(
                requirement
            )

            lines.append(
                f"securityRequirements({service_name}, N) :-"
            )
            lines.append(
                f"    {body}."
            )
            lines.append("")

        return "\n".join(lines).rstrip()

    def _build_query(self) -> str:
        """
        Costruisce la query SecFog relativa
        al placement fissato.
        """
        app_operator = self.placement.get(
            "operator",
            "appOp",
        )

        application_name = self.application.get(
            "name",
            self.placement.get(
                "application",
                "scalable_app",
            ),
        )

        terms = []

        for component in self.placement["components"]:
            component_name = component["name"]
            node_name = component["node"]

            node_data = self.infrastructure[
                "nodes"
            ][node_name]

            node_operator = node_data.get(
                "operator",
                f"{node_data.get('type', 'edge')}Op",
            )

            terms.append(
                f"d("
                f"{component_name}, "
                f"{node_name}, "
                f"{node_operator}"
                f")"
            )

        deployment = (
            "["
            + ", ".join(terms)
            + "]"
        )

        return (
            f"query(secFog("
            f"{app_operator}, "
            f"{application_name}, "
            f"{deployment}"
            f"))."
        )

    #@profile("3.2 ScoreWrapper._build_probabilistic_facts")
    def _build_probabilistic_facts(
        self,
        state: Any,
    ) -> str:
        capabilities = self.catalog.get(
            "capabilities",
            {},
        )

        nodes = []

        for node, _ in state.levels:
            if node not in nodes:
                nodes.append(node)

        # ProbLog solleva UnknownClause se un predicato menzionato in un
        # security requirement non compare in nessun fatto dell'istanza.
        # I fatti fittizi a probabilita' zero dichiarano tutti i predicati
        # del catalogo senza attivare capability su alcun nodo reale.
        lines = [
            "%%% DECLARED SECURITY CAPABILITY PREDICATES %%%",
            *(
                f"0.0::{capability}(secfog_dummy)."
                for capability in sorted(capabilities)
            ),
            "",
        ]

        for node_name in nodes:
            facts_by_category = {
                category: []
                for category in self.CATEGORY_ORDER
            }

            for (node, capability), level in state.items():
                if node != node_name or level is None:
                    continue

                cap_info = capabilities[
                    capability
                ]

                probability = cap_info[
                    "levels"
                ][str(level)][
                    "probability"
                ]

                category = cap_info[
                    "category"
                ]

                facts_by_category[
                    category
                ].append(
                    f"{probability}::"
                    f"{capability}"
                    f"({node_name})."
                )

            if not any(
                facts_by_category.values()
            ):
                continue

            lines.append(
                "%%%%%%%%%%%%%%%%%%%%%%%%%"
            )
            lines.append(
                f"%%%%%%%%% {node_name} %%%%%%%%%"
            )
            lines.append(
                "%%%%%%%%%%%%%%%%%%%%%%%%%"
            )
            lines.append("")

            for category in self.CATEGORY_ORDER:
                facts = facts_by_category[
                    category
                ]

                if not facts:
                    continue

                lines.append(
                    f"%{category}"
                )
                lines.extend(facts)
                lines.append("")

        return "\n".join(lines)

    #@profile("4. ProbLog (API nativa)")
    def _run_problog_api(
        self,
        program_str: str,
    ) -> float:
        try:
            from problog import get_evaluatable
            from problog.program import PrologString

            self._solver_evaluations += 1

            program = PrologString(
                program_str
            )

            result = (
                get_evaluatable()
                .create_from(program)
                .evaluate()
            )

            scores = [
                float(probability)
                for probability in result.values()
                if probability is not None
            ]

            if not scores:
                raise ValueError(
                    "Nessuno score SecFog trovato."
                )

            return max(scores)

        except Exception as exc:
            raise RuntimeError(
                "Errore durante l'esecuzione "
                "di ProbLog:\n"
                f"{exc}"
            ) from exc
