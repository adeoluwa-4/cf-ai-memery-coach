#!/usr/bin/env python3
"""AI Memery Coach

A local memory coaching assistant with optional OpenAI powered responses.
"""

from __future__ import annotations

import json
import os
import random
import re
import textwrap
import urllib.error
import urllib.request
from collections import Counter
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


DATA_DIR = Path("data")
DATA_FILE = DATA_DIR / "memories.json"


@dataclass
class Memory:
    created_at: str
    title: str
    details: str
    feeling: str
    lesson: str
    tags: list[str]
    review_count: int = 0
    last_reviewed_at: str = ""
    next_review_at: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Memory":
        return cls(
            created_at=str(raw.get("created_at", "")),
            title=str(raw.get("title", "")),
            details=str(raw.get("details", "")),
            feeling=str(raw.get("feeling", "")),
            lesson=str(raw.get("lesson", "")),
            tags=list(raw.get("tags", [])),
            review_count=int(raw.get("review_count", 0)),
            last_reviewed_at=str(raw.get("last_reviewed_at", "")),
            next_review_at=str(raw.get("next_review_at", "")),
        )


class MemeryCoach:
    def __init__(self, data_file: Path = DATA_FILE) -> None:
        self.data_file = data_file
        self.memories: list[Memory] = []
        self._last_recall_index: int | None = None
        self._load()

    def _load(self) -> None:
        if not self.data_file.exists():
            self.memories = []
            return

        with self.data_file.open("r", encoding="utf-8") as f:
            raw = json.load(f)

        self.memories = [Memory.from_dict(item) for item in raw]

    def _save(self) -> None:
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with self.data_file.open("w", encoding="utf-8") as f:
            json.dump([asdict(m) for m in self.memories], f, indent=2)

    def add_memory(
        self,
        title: str,
        details: str,
        feeling: str,
        lesson: str,
        tags: list[str],
    ) -> Memory:
        now = datetime.now().isoformat(timespec="seconds")
        memory = Memory(
            created_at=now,
            title=title.strip(),
            details=details.strip(),
            feeling=feeling.strip(),
            lesson=lesson.strip(),
            tags=[t.strip().lower() for t in tags if t.strip()],
            review_count=0,
            last_reviewed_at="",
            next_review_at=now,
        )
        self.memories.append(memory)
        self._save()
        return memory

    def list_recent(self, limit: int = 5) -> list[Memory]:
        return list(reversed(self.memories[-limit:]))

    def tag_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for memory in self.memories:
            for tag in memory.tags:
                counts[tag] = counts.get(tag, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))

    @staticmethod
    def _tokens(text: str) -> set[str]:
        words = set(re.findall(r"[a-zA-Z0-9']+", text.lower()))
        stop_words = {
            "the",
            "and",
            "for",
            "with",
            "that",
            "this",
            "from",
            "you",
            "your",
            "are",
            "was",
            "have",
            "had",
            "what",
            "when",
            "where",
            "how",
            "why",
            "into",
            "about",
            "today",
            "then",
        }
        return {w for w in words if len(w) > 2 and w not in stop_words}

    @staticmethod
    def _memory_blob(memory: Memory) -> str:
        return " ".join(
            [memory.title, memory.details, memory.feeling, memory.lesson, " ".join(memory.tags)]
        )

    def relevant_memories(self, question: str, limit: int = 3) -> list[Memory]:
        if not self.memories:
            return []

        question_tokens = self._tokens(question)
        if not question_tokens:
            return self.list_recent(limit=limit)
        scored: list[tuple[float, Memory]] = []
        total = len(self.memories)

        for index, memory in enumerate(self.memories, start=1):
            memory_tokens = self._tokens(self._memory_blob(memory))
            overlap = len(question_tokens.intersection(memory_tokens))
            tag_hits = len(question_tokens.intersection(set(memory.tags)))
            if overlap == 0 and tag_hits == 0:
                continue
            recency_bonus = index / max(total, 1)
            score = (overlap * 2.0) + (tag_hits * 1.5) + recency_bonus
            if score > 0:
                scored.append((score, memory))

        if not scored:
            return self.list_recent(limit=limit)

        scored.sort(key=lambda item: item[0], reverse=True)
        return [memory for _, memory in scored[:limit]]

    def search_memories(self, query: str, limit: int = 10) -> list[Memory]:
        query = query.strip()
        if not query:
            return []
        return self.relevant_memories(query, limit=limit)

    def most_repeated_lesson(self) -> tuple[str, int]:
        lessons = [m.lesson.strip() for m in self.memories if m.lesson.strip()]
        if not lessons:
            return ("", 0)
        counts = Counter(lessons)
        lesson, count = counts.most_common(1)[0]
        return (lesson, count)

    def feeling_trend(self, limit: int = 7) -> list[str]:
        if not self.memories:
            return []

        recent = self.memories[-limit:]
        tokens: list[str] = []
        for memory in recent:
            parts = re.findall(r"[a-zA-Z']+", memory.feeling.lower())
            if parts:
                tokens.append(parts[0])

        counts = Counter(tokens)
        return [name for name, _ in counts.most_common(3)]

    def summary(self) -> str:
        if not self.memories:
            return "You do not have memories saved yet. Add one to start coaching."

        tag_counts = self.tag_counts()
        top_tags = list(tag_counts.keys())[:3]
        last = self.memories[-1]
        top_feelings = self.feeling_trend(limit=7)
        repeated_lesson, lesson_count = self.most_repeated_lesson()

        lines = [
            f"You have saved {len(self.memories)} memories.",
            f"Most recent memory: {last.title}.",
        ]

        if top_tags:
            lines.append(f"Top themes: {', '.join(top_tags)}.")

        if top_feelings:
            lines.append(f"Recent feeling trend: {', '.join(top_feelings)}.")

        if lesson_count > 1:
            lines.append(f"Most repeated lesson: {repeated_lesson}")
        elif last.lesson:
            lines.append(f"Repeat this lesson today: {last.lesson}")

        return "\n".join(lines)

    def recall_prompt(self) -> tuple[str, str]:
        if not self.memories:
            self._last_recall_index = None
            return (
                "No memories available for recall.",
                "Add a memory first.",
            )

        due_indexes = self._due_memory_indexes()
        if due_indexes:
            index = due_indexes[0]
            memory = self.memories[index]
        else:
            index = random.randrange(len(self.memories))
            memory = self.memories[index]

        self._last_recall_index = index
        question = (
            "Recall check\n"
            f"When you wrote '{memory.title}', what lesson did you capture?"
        )
        answer = f"Saved lesson: {memory.lesson or 'No lesson was saved for this one.'}"
        return question, answer

    @staticmethod
    def _parse_iso(value: str) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _due_memory_indexes(self) -> list[int]:
        now = datetime.now()
        due: list[tuple[datetime, int]] = []
        for index, memory in enumerate(self.memories):
            next_review = self._parse_iso(memory.next_review_at)
            if next_review is None or next_review <= now:
                # Oldest due item first so we review neglected items.
                reference = next_review or datetime.min
                due.append((reference, index))
        due.sort(key=lambda item: item[0])
        return [index for _, index in due]

    def complete_last_recall(self, remembered: bool) -> str:
        index = getattr(self, "_last_recall_index", None)
        if index is None or index >= len(self.memories):
            return "No recall session is active."

        memory = self.memories[index]
        now = datetime.now()
        intervals = [1, 3, 7, 14, 30, 45]

        if remembered:
            memory.review_count += 1
            step = min(memory.review_count - 1, len(intervals) - 1)
            next_days = intervals[step]
        else:
            memory.review_count = max(memory.review_count - 1, 0)
            next_days = 1

        memory.last_reviewed_at = now.isoformat(timespec="seconds")
        memory.next_review_at = (now + timedelta(days=next_days)).isoformat(timespec="seconds")
        self._save()
        self._last_recall_index = None
        return f"Next review for '{memory.title}' is in {next_days} day(s)."

    def coaching_context(self, limit: int = 8) -> str:
        recent = self.list_recent(limit=limit)
        chunks: list[str] = []
        for idx, memory in enumerate(recent, start=1):
            chunks.append(
                textwrap.dedent(
                    f"""
                    Memory {idx}
                    Date: {memory.created_at}
                    Title: {memory.title}
                    Details: {memory.details}
                    Feeling: {memory.feeling}
                    Lesson: {memory.lesson}
                    Tags: {', '.join(memory.tags) if memory.tags else 'none'}
                    """
                ).strip()
            )
        return "\n\n".join(chunks)

    def ask_ai_coach(self, question: str) -> str:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            return self.local_coach_response(question)

        model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        system_prompt = (
            "You are a thoughtful memory coach. Use the user memory log to help them "
            "reflect, notice patterns, and choose one realistic action for today. "
            "Be concise, warm, and direct."
        )

        user_content = (
            "User memory log:\n"
            f"{self.coaching_context()}\n\n"
            f"Most relevant memories for this question:\n{self._relevant_context(question)}\n\n"
            f"User question: {question}"
        )

        payload = {
            "model": model,
            "input": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.7,
        }

        request = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            return (
                "The API request failed. I used local coaching instead.\n"
                f"Error details: {details}\n\n"
                f"{self.local_coach_response(question)}"
            )
        except Exception as exc:  # noqa: BLE001
            return (
                "Could not reach the API. I used local coaching instead.\n"
                f"Error details: {exc}\n\n"
                f"{self.local_coach_response(question)}"
            )

        text = self._extract_response_text(raw)
        if not text:
            return (
                "The API returned no text, so here is local coaching instead.\n\n"
                f"{self.local_coach_response(question)}"
            )
        return text

    @staticmethod
    def _extract_response_text(raw: dict[str, Any]) -> str:
        output = raw.get("output", [])
        parts: list[str] = []
        for item in output:
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    parts.append(content.get("text", ""))
        return "\n".join(p for p in parts if p).strip()

    def _relevant_context(self, question: str) -> str:
        relevant = self.relevant_memories(question, limit=3)
        if not relevant:
            return "No memories found."
        chunks: list[str] = []
        for memory in relevant:
            chunks.append(
                f"{memory.created_at} | {memory.title} | feeling: {memory.feeling} | lesson: {memory.lesson}"
            )
        return "\n".join(chunks)

    def local_coach_response(self, question: str) -> str:
        if not self.memories:
            return (
                "You do not have memory data yet. Start by adding one real event from today, "
                "the feeling, and one lesson."
            )

        tags = self.tag_counts()
        top = next(iter(tags), "growth")
        last = self.memories[-1]
        relevant = self.relevant_memories(question, limit=3)
        repeated_lesson, lesson_count = self.most_repeated_lesson()

        if relevant:
            anchors = ", ".join(f"'{m.title}'" for m in relevant[:2])
        else:
            anchors = f"'{last.title}'"

        if lesson_count > 1:
            lesson_line = f"Recurring lesson to apply: {repeated_lesson}"
        else:
            lesson_line = (
                f"Recent lesson to apply: {last.lesson or 'Name one clear lesson from that moment.'}"
            )

        return (
            f"Question: {question}\n\n"
            f"Pattern I see: your strongest related memories are {anchors}.\n"
            f"Likely theme: {top}.\n"
            f"{lesson_line}\n"
            f"Action for today:\n"
            f"1. Spend 10 minutes on one task tied to '{top}'.\n"
            f"2. Reuse this cue from your log: {anchors}.\n"
            f"3. Write one sentence tonight about what improved."
        )


def prompt(label: str, allow_empty: bool = False) -> str:
    while True:
        value = input(label).strip()
        if value or allow_empty:
            return value
        print("Please enter a value.")


def run_cli() -> int:
    coach = MemeryCoach()

    print("Memery Coach")
    print("Type the number for what you want to do.")

    while True:
        print()
        print("1 Save memory")
        print("2 View recent memories")
        print("3 View summary")
        print("4 Recall practice")
        print("5 Ask coach")
        print("6 Search memories")
        print("7 Exit")

        choice = prompt("Choice: ")

        if choice == "1":
            title = prompt("Title: ")
            details = prompt("Details: ")
            feeling = prompt("Feeling: ")
            lesson = prompt("Lesson: ")
            tags_raw = prompt("Tags (comma separated): ", allow_empty=True)
            tags = [t.strip() for t in tags_raw.split(",")] if tags_raw else []
            memory = coach.add_memory(title, details, feeling, lesson, tags)
            print(f"Saved memory from {memory.created_at}.")

        elif choice == "2":
            memories = coach.list_recent(limit=10)
            if not memories:
                print("No memories yet.")
                continue
            for m in memories:
                print()
                print(f"Date: {m.created_at}")
                print(f"Title: {m.title}")
                print(f"Feeling: {m.feeling}")
                print(f"Lesson: {m.lesson}")
                print(f"Tags: {', '.join(m.tags) if m.tags else 'none'}")

        elif choice == "3":
            print(coach.summary())

        elif choice == "4":
            q, a = coach.recall_prompt()
            print(q)
            input("Press enter to reveal the saved lesson.")
            print(a)
            remembered = prompt("Did you remember it well? (y/n): ", allow_empty=True).lower()
            print(coach.complete_last_recall(remembered.startswith("y")))

        elif choice == "5":
            question = prompt("Ask your coaching question: ")
            print()
            print(coach.ask_ai_coach(question))

        elif choice == "6":
            query = prompt("Search query: ")
            matches = coach.search_memories(query, limit=10)
            if not matches:
                print("No matches found.")
                continue
            for m in matches:
                print()
                print(f"Date: {m.created_at}")
                print(f"Title: {m.title}")
                print(f"Feeling: {m.feeling}")
                print(f"Lesson: {m.lesson}")
                print(f"Tags: {', '.join(m.tags) if m.tags else 'none'}")

        elif choice == "7":
            print("See you next time.")
            return 0

        else:
            print("Please choose a number from 1 to 7.")


def main() -> None:
    try:
        raise SystemExit(run_cli())
    except KeyboardInterrupt:
        print("\nSession ended.")
        raise SystemExit(0)


if __name__ == "__main__":
    main()
