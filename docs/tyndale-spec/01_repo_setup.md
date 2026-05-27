# Task 01 — Initialize the Tyndale intelligence layer repository

**Phase:** 1 · Foundation files
**Who:** Brock + Claude Code
**Estimated time:** 20 minutes
**Depends on:** Nothing — this is the first task

## What this task does

Creates the git repository structure that every subsequent task will populate. After this task, you'll have an empty but well-organized repo ready for the Skills, subagents, tools, and documentation that follow.

## How to run it

Open a new Claude Code session in the directory where you want the repo to live (e.g., `~/code/`). Paste the prompt below into the chat. Claude Code will execute the setup.

---

## Prompt to paste into Claude Code

```
I'm starting a new project: the Tyndale intelligence layer. Tyndale is an
AI-powered medical billing reconciliation and health advocacy platform built
on the Claude Agent SDK. This repository will hold the prompts, Skills, tool
descriptions, knowledge collection scaffolding, and eval test data — the
non-runtime parts that I'm building before handing off to my engineering
team for the actual application code.

Please do the following:

1. Initialize a new git repository in the current directory called
   `tyndale-intelligence-layer`.

2. Create the following directory structure:

    tyndale-intelligence-layer/
    ├── README.md                       (placeholder — Task 30 will fill this)
    ├── reference/                      (cross-cutting reference files)
    ├── skills/                         (8 Skills — Tasks 08–15 will fill)
    ├── subagents/                      (6 subagent system prompts — Tasks 16–21)
    ├── tools/
    │   └── descriptions/               (~22 tool description files — Task 22)
    ├── collections/                    (knowledge collection scaffolding — Tasks 23–25)
    │   ├── schemas/
    │   ├── ingestion/
    │   └── fixtures/
    ├── evals/
    │   ├── golden/                     (expert-labeled examples — Tasks 26–27)
    │   └── synthetic/                  (adversarial generation — Tasks 28–29)
    ├── operational/                    (BAA tracker, handoff brief — Tasks 31–32)
    └── docs/                           (architecture diagrams, supporting docs)

3. Add a top-level `.gitignore` with appropriate Python ignores (.venv,
   __pycache__, *.pyc, .DS_Store, .env, .env.local) plus IDE configs.

4. Add a top-level `CLAUDE.md` file that briefly tells Claude Code:
   - This repo holds Tyndale's intelligence layer (prompts, Skills, tool
     descriptions, eval data) — NOT runtime application code
   - The runtime code (FastAPI app, LiteLLM proxy, Qdrant deployment,
     Stripe integration, FHIR OAuth, hooks) lives in a separate repository
     and is built by Phil, Jonas, Josh
   - The audience for files in this repo is: (a) the engineering team who
     will wire it into the application, and (b) future Claude Code sessions
     building additional Skills, subagent prompts, or tool descriptions
   - All Skill files must follow the SKILL.md frontmatter pattern and stay
     under 500 lines (reference files at one level deep handle the detail)
   - All subagent prompts reference reference/principles.md, reference/voice_tiering.md, etc.

5. Make an initial commit with the message "Initial repository structure".

After running, show me the directory tree and the commit log.
```

---

## Done when

You can run `tree -L 2` (or `find . -maxdepth 2`) in the new repo and see the expected structure. `git log` shows the initial commit. The CLAUDE.md file contains an accurate summary of what the repo holds.

## Next task

[Task 02 — Write the principles reference file](02_principles.md)
