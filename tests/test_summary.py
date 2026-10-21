from summary import summarize


def test_counts():
    data = {
        "taches": {
            "t-a": {"prio": "maintenant", "items": [{"id": "a1"}, {"id": "a2"}]},
            "t-b": {"prio": "semaine", "items": [{"id": "b1"}]},
            "t-c": {"prio": "fait", "items": []},
            "t-d": {"prio": "maintenant", "items": [{"id": "d1"}]},
        },
        "fait": {"d1": {"fait": True}, "a1": {"fait": True}},
        "demandes": {"x": {"texte": "?"}},
        "revoir": {"a2": {"tache": "t-a"}, "b1": {"tache": "t-b", "reponse": "done"}, "zz": {"tache": "gone"}},
        "verifier": {"a1": {"tache": "t-a"}, "b1": {"tache": "t-b", "resultat": "attente"}, "a2": {"tache": "t-a", "resultat": "contredit"}},
        "decisions": {"t-b": {"tache": "t-b"}, "q1": {"tache": "t-a", "reponse": "ok"}},
    }
    n = summarize(data)
    assert n == {
        "demandes": 1,
        "a_revoir": 1,
        "a_verifier": 1,  # a1 is already checked, a2 contradicted, b1 still waiting
        "decisions": 1,
        "maintenant": 1,  # t-d is done (all its items checked)
        "taches_ouvertes": 2,
        "pour_les_agents": 4,
    }


def test_empty():
    assert summarize({})["pour_les_agents"] == 0
