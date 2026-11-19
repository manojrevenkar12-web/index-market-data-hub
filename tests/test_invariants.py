"""The rules in AGENTS.md, checked."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCT = [p for p in (ROOT / "imdh").rglob("*.py") if not ({"world", "eval"} & set(p.relative_to(ROOT).parts))]


def _imports(path: Path) -> set[str]:
    out = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module)
    return out


def test_the_truth_stays_in_the_world():
    for p in PRODUCT:
        assert not any(m.startswith("imdh.world") or m.startswith("imdh.eval") for m in _imports(p)), p


def test_the_world_does_not_read_the_hubs_settings():
    for p in (ROOT / "imdh" / "world").rglob("*.py"):
        text = p.read_text()
        assert "hub.yaml" not in text and "gate.yaml" not in text, p
        assert not any(m.startswith(("imdh.decide", "imdh.pipeline", "imdh.indexcalc", "imdh.vendors",
                                     "imdh.symbology", "imdh.store", "imdh.service")) for m in _imports(p)), p


def test_same_luck_every_draw_is_keyed():
    for p in (ROOT / "imdh" / "world").rglob("*.py"):
        text = p.read_text()
        assert "np.random.default_rng(" not in text and "random.random(" not in text, p


def test_reports_are_generated_and_the_readme_matches():
    from imdh.eval import report

    assert report.write_readme(check=True), "README results block is stale"
    assert report.load("dev")["gate"]["passed"]


def test_heldout_is_locked_once_it_has_run():
    lock, held = ROOT / "config" / "heldout.lock", ROOT / "reports" / "heldout.json"
    assert lock.exists() == held.exists()
