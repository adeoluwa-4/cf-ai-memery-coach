import tempfile
import unittest
from pathlib import Path

from memery_coach import MemeryCoach


class MemeryCoachTests(unittest.TestCase):
    def test_add_and_list_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_file = Path(tmp) / "memories.json"
            coach = MemeryCoach(data_file=data_file)
            coach.add_memory(
                title="Big meeting",
                details="I shared my project update",
                feeling="nervous then proud",
                lesson="prepare one clear point before speaking",
                tags=["work", "confidence"],
            )

            recent = coach.list_recent()
            self.assertEqual(len(recent), 1)
            self.assertEqual(recent[0].title, "Big meeting")

    def test_summary_without_memories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_file = Path(tmp) / "memories.json"
            coach = MemeryCoach(data_file=data_file)
            self.assertIn("do not have memories", coach.summary())


if __name__ == "__main__":
    unittest.main()
