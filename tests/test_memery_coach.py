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

    def test_relevant_memories_prioritizes_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_file = Path(tmp) / "memories.json"
            coach = MemeryCoach(data_file=data_file)
            coach.add_memory(
                title="Career planning",
                details="I mapped steps for my software career",
                feeling="focused",
                lesson="small weekly progress wins",
                tags=["career", "work"],
            )
            coach.add_memory(
                title="Gym routine",
                details="I completed a short workout",
                feeling="energized",
                lesson="consistency matters",
                tags=["health"],
            )

            relevant = coach.relevant_memories("How do I improve in my career at work?")
            self.assertGreater(len(relevant), 0)
            self.assertEqual(relevant[0].title, "Career planning")

    def test_most_repeated_lesson_counts_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_file = Path(tmp) / "memories.json"
            coach = MemeryCoach(data_file=data_file)
            coach.add_memory(
                title="Study block",
                details="I studied for one hour",
                feeling="calm",
                lesson="start before I feel ready",
                tags=["study"],
            )
            coach.add_memory(
                title="Project session",
                details="I built one feature",
                feeling="proud",
                lesson="start before I feel ready",
                tags=["work"],
            )

            lesson, count = coach.most_repeated_lesson()
            self.assertEqual(lesson, "start before I feel ready")
            self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
