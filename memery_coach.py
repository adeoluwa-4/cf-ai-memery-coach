#!/usr/bin/env python3
"""AI Memery Coach

A local memory coaching assistant with optional OpenAI powered responses.
"""

from __future__ import annotations

import json
import os
import random
import sys
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime
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


class MemeryCoach:
    def __init__(self, data_file: Path = DATA_FILE) -> None:
        self.data_file = data_file
        self.memories: list[Memory] = []
        self._load()

    def _load(self) -> None:
        if not self.data_file.exists():
            self.memories = []
            return

        with self.data_file.open("r", encoding="utf-8") as f:
            raw = json.load(f)

        self.memories = [Memory(**item) for item in raw]

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
        memory = Memory(
            created_at=datetime.now().isoformat(timespec="seconds"),
            title=title.strip(),
            details=details.strip(),
            feeling=feeling.strip(),
            lesson=lesson.strip(),
            tags=[t.strip().lower() for t in tags if t.strip()],
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

    def summary(self) -> str:
        if not self.memories:
            return "You do not have memories saved yet. Add one to start coaching."

        tag_counts = self.tag_counts()
        top_tags = list(tag_counts.keys())[:3]
        last = self.memories[-1]

        lines = [
            f"You have saved {len(self.memories)} memories.",
            f"Most recent memory: {last.title}.",
        ]

        if top_tags:
            lines.append(f"Top themes: {', '.join(top_tags)}.")

        lessons = [m.lesson for m in self.memories if m.lesson]
        if lessons:
            lines.append(f"Repeat this lesson today: {lessons[-1]}")

        return "\n".join(lines)

    def recall_prompt(self) -> tuple[str, str]:
        if not self.memories:
            return (
                "No memories available for recall.",
                "Add a memory first.",
            )

        memory = random.choice(self.memories)
        question = (
            "Recall check\n"
            f"When you wrote '{memory.title}', what lesson did you capture?"
        )
        answer = f"Saved lesson: {memory.lesson or 'No lesson was saved for this one.'}"
        return question, answer

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

    def local_coach_response(self, question: str) -> str:
        if not self.memories:
            return (
                "You do not have memory data yet. Start by adding one real event from today, "
                "the feeling, and one lesson."
            )

        tags = self.tag_counts()
        top = next(iter(tags), "growth")
        last = self.memories[-1]
        action = (
            f"Action for today: spend 10 minutes on one task tied to '{top}', "
            "then write one sentence about what changed."
        )

        return (
            f"Question: {question}\n\n"
            f"Pattern I see: your latest memory focused on '{last.title}' and felt '{last.feeling}'.\n"
            f"Likely theme: {top}.\n"
            f"Recent lesson to apply: {last.lesson or 'Name one clear lesson from that moment.'}\n"
            f"{action}"
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
        print("6 Exit")

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

        elif choice == "5":
            question = prompt("Ask your coaching question: ")
            print()
            print(coach.ask_ai_coach(question))

        elif choice == "6":
            print("See you next time.")
            return 0

        else:
            print("Please choose a number from 1 to 6.")


def main() -> None:
    try:
        raise SystemExit(run_cli())
    except KeyboardInterrupt:
        print("\nSession ended.")
        raise SystemExit(0)


if __name__ == "__main__":
    main()
