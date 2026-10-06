# Git workflow

All version control is done with `git` in the terminal. There are no pull
requests: each branch is merged into `main` on this computer and then pushed to
GitHub. One branch per milestone, one branch for everything else. Branches are
kept after merging and reused for the next round of work (decision D-007).

| Branch | Use it for | GitHub milestone |
| --- | --- | --- |
| `m1-data-pipeline` | Ingest, anonymise, validate, clean | M1 - Data pipeline |
| `m2-features-models` | Features, models, SHAP | M2 - Features and models |
| `m3-mlops` | MLflow, Evidently, Docker | M3 - MLOps |
| `m4-dashboard` | Streamlit dashboard | M4 - Dashboard |
| `m5-report` | Report and defence | M5 - Report and defence |
| `housekeeping` | Bug fixes, docs, templates, config, tooling not tied to a milestone | none |

Create a milestone branch only when that milestone starts.

## Each round of work

### 1. Start on the branch

```powershell
# Move to the branch you are working on. The files in the folder change to
# that branch's version.
git switch m1-data-pipeline

# Download main from GitHub and merge it into this branch, so you start with
# everything merged from the other branches since last time.
# --no-edit keeps git's automatic message instead of opening an editor.
git pull --no-edit origin main
```

### 2. Work, test and commit

Repeat this as often as you like while working.

```powershell
# Run the tests. Carry on only if they pass.
pytest

# List the files you changed. Check that no data files, photos or .env appear.
git status

# Choose the files to include in the next commit ("stage" them).
git add <file> <file>

# Save the staged files as one commit on this branch, with a short message.
git commit -m "M1: short description (#5)"

# Upload this branch's new commits to GitHub. This is a backup only;
# main does not change.
git push
```

### 3. Merge the branch into main

Do this when a piece of work is finished: tests pass and `CHANGELOG.md` is
updated.

```powershell
# Move to main.
git switch main

# Download any changes to main from GitHub, so your copy is up to date.
git pull

# Merge the branch into main as one merge commit. Fill in the message
# template below.
git merge --no-ff m1-data-pipeline `
  -m "M1: <what this round of work does>" `
  -m "Closes #<issue>" `
  -m "Problem: <what was wrong or missing>" `
  -m "Remedy: <what you changed, and why it solves the problem>"

# Upload main to GitHub. Issues named in "Closes #N" close automatically.
git push

# Go back to the branch, ready for the next round.
git switch m1-data-pipeline
```

About the merge command:

- `--no-ff` ("no fast-forward") always makes a merge commit, so `main` shows
  each round of work as one entry with its message.
- Each `-m` adds one paragraph to the message. Write one `-m "Closes #N"` per
  issue this merge finishes. Write `-m "Part of #N"` for an issue that is not
  finished yet.
- The backtick `` ` `` at the end of a line continues the command on the next
  line in PowerShell. It must be the last character, with no space after it.

## Starting a new branch

For a new milestone, or the first time you need `housekeeping`:

```powershell
# Move to main and bring it up to date from GitHub.
git switch main
git pull

# Create the new branch from main and move to it.
git switch -c m2-features-models

# Upload the new branch to GitHub. -u links the local and GitHub branches,
# so plain git push and git pull work from then on.
git push -u origin m2-features-models
```

## Checking where you are

```powershell
# Show the current branch and which files have changed.
git status

# Show every local branch, its last commit, and whether it is ahead of or
# behind GitHub.
git branch -vv

# Show the history as a graph, newest first.
git log --oneline --graph -15

# Show only the merges into main, one line per round of work.
git log --first-parent --oneline main
```

## If something goes wrong

```powershell
# A merge stopped with a conflict and you want to undo it and start again.
git merge --abort

# A merge stopped with a conflict and you want to finish it. Fix the files
# git status lists under "both modified", then stage them and commit.
git add <file>
git commit --no-edit
```

## Rules

- Never commit work directly on `main`. It only receives merges from the
  branches.
- Always merge into `main` with `--no-ff`. Never delete a branch after merging.
- Commit and merge messages start with the branch label: `M1:` to `M5:` or
  `Housekeeping:`.
- If a fix is needed for a milestone that is still in progress, make it on that
  milestone's branch. Use `housekeeping` for everything else.
