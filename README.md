# AI Memery Coach

AI Memery Coach is a simple personal coach you run on your computer.
It helps you save memories, reflect on patterns, and turn lessons into daily action.
If you add an OpenAI API key, it can also answer with live AI coaching.

## What it does

1. Saves memory entries with title, details, feeling, lesson, and tags.
2. Stores your data in a local JSON file.
3. Finds relevant memories when you ask a question.
4. Shows trend signals from repeated lessons and feelings.
5. Runs adaptive recall timing so hard lessons come back sooner.
6. Lets you search your memories by keywords.
7. Answers coaching questions with local logic or OpenAI.

## How to run

1. Open a terminal in this folder.
2. Run `python3 memery_coach.py`.
3. Use the menu options to save, search, reflect, and review.

## Optional OpenAI setup

1. Set your key: `export OPENAI_API_KEY="your_key_here"`.
2. Optional model setting: `export OPENAI_MODEL="gpt4o"`.
3. Start the app with `python3 memery_coach.py`.

## Data location

Your memories are saved in `data/memories.json`.
