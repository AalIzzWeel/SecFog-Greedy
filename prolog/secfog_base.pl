%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%% SecFog - regole generiche
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


secFog(OpA, A, D) :-
    app(A, L),
    deployment(OpA, L, D).


deployment(_, [], []).

deployment(
    OpA,
    [C|Cs],
    [d(C, N, OpN)|D]
) :-
    node(N, OpN),
    securityRequirements(C, N),
    deployment(OpA, Cs, D).