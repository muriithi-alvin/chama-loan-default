# Git workflow

One branch per milestone, one branch for everything else. Branches are kept
after merging and reused for the next round of work (decision D-007).

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

```powershell
# 1. Go to the branch and bring in anything merged to main since last time
git switch m1-data-pipeline
git pull origin main

# 2. Work, test, commit (as many commits as you like)
pytest
git add <files>
git commit -m "M1: short description (#issue)"

# 3. Push and open the pull request; edit the template that appears
git push
gh pr create --base main --title "M1: what this round does"

# 4. Merge with a merge commit; the branch stays for next time
gh pr merge --merge
```

The first push of a new branch needs `git push -u origin <branch>`.

## Starting a new milestone branch

```powershell
git switch main
git pull
git switch -c m2-features-models
git push -u origin m2-features-models
```

## Rules

- Never commit straight to `main`; every change arrives through a pull request.
- Merge with `gh pr merge --merge` (a merge commit). Do not squash and do not
  delete the branch.
- Commit messages and pull request titles start with the branch label: `M1:`
  to `M5:` or `Housekeeping:`.
- If a fix is needed for a milestone that is still in progress, make it on that
  milestone's branch. Use `housekeeping` for everything else.
