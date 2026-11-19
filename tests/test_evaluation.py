from imdh.eval.run import evaluate


def test_quick_world_hub_beats_every_baseline(cfg, settings, gate):
    r = evaluate(cfg, settings, gate)
    d = r["designs"]
    for base in ("single_vendor", "primary_backup", "median_consensus"):
        assert d["hub"]["wrong_index_closes"] <= d[base]["wrong_index_closes"]
        assert d["hub"]["max_index_error_bps"] <= d[base]["max_index_error_bps"]
    assert r["calculators_agree"] < 1e-9
    assert set(r["gate"]["checks"]) == {"wrong_index_closes", "max_index_error_bps", "wrong_actions",
                                        "desk_lookups_busiest_day"}
    assert d["hub"]["desk_lookups"] <= d["hub_unranked_desk"]["desk_lookups"]
