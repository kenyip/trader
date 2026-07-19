import tempfile
import unittest
from pathlib import Path

from trader_platform.research.living_registry import (
    LivingRegistry,
    LivingSeat,
    load_living_registry,
    save_living_registry,
)
from trader_platform.research.promote_paper import promote_top_f2_to_paper


class PromotePaperTest(unittest.TestCase):
    def test_promotes_f2_to_paper_eligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "reg.json"
            reg = LivingRegistry()
            reg.upsert(
                LivingSeat(
                    seat_id="A_INTC",
                    candidate_id="A",
                    family_id="F",
                    status="f2_holdout",
                    symbols=["INTC"],
                )
            )
            reg.upsert(
                LivingSeat(
                    seat_id="B_KO",
                    candidate_id="B",
                    family_id="G",
                    status="f2_holdout",
                    symbols=["KO"],
                )
            )
            save_living_registry(reg, path)
            out = promote_top_f2_to_paper(top_n=2, registry_path=path)
            self.assertEqual(out["n_promoted"], 2)
            reloaded = load_living_registry(path)
            statuses = {s.seat_id: s.status for s in reloaded.seats}
            self.assertEqual(statuses["A_INTC"], "paper_eligible")
            self.assertEqual(statuses["B_KO"], "paper_eligible")


if __name__ == "__main__":
    unittest.main()
