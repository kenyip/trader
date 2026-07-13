import unittest

from scripts.double_diagonal_chronological_lab import complete_evidence_gate


class DoubleDiagonalChronologicalLabTest(unittest.TestCase):
    def test_complete_gate_rejects_passing_holdout_when_train_failed(self):
        passing = {
            "ok": True,
            "gate_pass": True,
            "ledger_delta": 0.0,
            "same_bar_reentries": 0,
        }
        failing_train = {**passing, "gate_pass": False}
        windows = {
            "integrity": True,
            "window_max_dd": 50.0,
            "dense_negative_n": 2,
        }

        self.assertFalse(complete_evidence_gate(failing_train, passing, windows))
        self.assertTrue(complete_evidence_gate(passing, passing, windows))


if __name__ == "__main__":
    unittest.main()
