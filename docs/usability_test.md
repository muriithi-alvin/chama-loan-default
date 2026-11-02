# Usability test: Kibaba with chama officials and members

A short session per person, run by Alvin with the deployed site on the
participant's own phone. It answers the Sprint III question: can the people
Kibaba is for use it without help, and do they understand what it tells them?
Results go into Chapter 5 of the report.

## Who and how

- **Participants:** 3 officials (a chair, a treasurer and a secretary if
  possible) and 3 members, from a real chama. Five or six people find most of
  the problems that matter.
- **Accounts:** the demo chama's official and member accounts, so nobody sees
  real names, including their own chama's. Tell participants the names are
  made up.
- **Time:** about 25 minutes each: 2 to introduce, 15 for the tasks, 5 for
  the questionnaire, 3 for questions.
- **Language:** read the tasks in English or Kiswahili, whichever the
  participant prefers, and note which.
- **Consent:** ask before starting (wording below). No recording of faces or
  voices; notes only, with no names (P1, P2, …).

## Before each session

- [ ] The site opens at its https address on the participant's phone
- [ ] Signed out, so the session starts at the landing page
- [ ] The demo official and member passwords to hand
- [ ] For the scan task: the handwritten demo page (fictional names), dated
      after the demo chama's last accepted page
- [ ] The worker is running (the scan task needs it); `/api/health` says ready
- [ ] A copy of the record sheet below and a phone stopwatch

## What to say first

> Thank you for helping. I am testing the website, not you: if something is
> hard, that is the website's fault, and it is exactly what I need to know.
> Please say out loud what you are looking at and thinking as you go. The
> names you will see are made up. I will take notes without your name, and you
> can stop at any time. Is that all right?

Then give the phone and read one task at a time. Do not help unless the
participant is stuck for two minutes or asks; if you help, mark the task
"with help".

## Tasks for officials

| # | Read aloud | Success means |
| --- | --- | --- |
| O1 | "Open the website and sign in with this email and password." | Reaches the Overview |
| O2 | "After the last meeting, who should you talk to first, and why?" | Names a member marked "Follow up now" and gives one of the reasons shown |
| O3 | "What does the yellow colour, 'Keep an eye on', mean?" | Explains it in their own words (could miss a repayment soon; check in) |
| O4 | "How much does Muthoni Ndegwa still have to repay?" | Finds KSh 460,000 on her page |
| O5 | "This is the page from this month's meeting. Add it to Kibaba." | Photographs the page, corrects the flagged line and the misspelt name, and accepts |
| O6 | "Find what was recorded at the meeting of 5 April 2026." | Opens that meeting's page in Records |

## Tasks for members

| # | Read aloud | Success means |
| --- | --- | --- |
| M1 | "Sign in with this email and password." | Reaches My summary |
| M2 | "How much do you still owe, and when is your next payment due?" | Reads the loan balance and the next due month |
| M3 | "Did you pay your monthly contribution at every meeting this year?" | Reads the contribution beads correctly |
| M4 | "Can you see how much other members owe?" | Says no, and does not find a way (members see only their own records) |

## After each task

Ask: **"How easy or hard was that, from 1 (very hard) to 7 (very easy)?"**
and write the number down.

## At the end: the 10 questions (System Usability Scale)

Read each statement; the participant answers from 1 (strongly disagree) to 5
(strongly agree).

1. I think I would like to use Kibaba often.
2. I found Kibaba more complicated than it needs to be.
3. I thought Kibaba was easy to use.
4. I think I would need help from someone technical to use Kibaba.
5. I found the parts of Kibaba worked well together.
6. I thought there was too much that did not fit together in Kibaba.
7. I think most people would learn to use Kibaba very quickly.
8. I found Kibaba awkward to use.
9. I felt confident using Kibaba.
10. I needed to learn a lot before I could get going with Kibaba.

**Score:** for odd statements take (answer − 1); for even statements take
(5 − answer); add the ten and multiply by 2.5. The result is 0 to 100; about
68 is average, above 80 is good.

Then ask:

- What was confusing or surprising?
- Is anything missing that you would need?
- Would your chama use this? Why or why not?

## Record sheet (one per participant)

Participant: P__ · Official / Member · Language: ______ · Date: ______

| Task | Done (yes / with help / no) | Time | Ease 1–7 | What happened (words, hesitations, wrong taps) |
| --- | --- | --- | --- | --- |
| O1 / M1 | | | | |
| O2 / M2 | | | | |
| O3 / M3 | | | | |
| O4 / M4 | | | | |
| O5 | | | | |
| O6 | | | | |

SUS answers 1–10: __ __ __ __ __ __ __ __ __ __ → score ____

Comments:

## Afterwards

1. Work out each participant's SUS score and the average, and each task's
   success rate and median ease.
2. List every problem seen, with how many participants met it, and rate it:
   **blocker** (could not finish), **serious** (finished with help or with
   a wrong understanding), **minor** (slowed down).
3. Fix the blockers and serious problems that fit before the deadline; the
   rest go to future work.
4. Add a results table to [m4_test_record.md](m4_test_record.md) and the
   findings to the report.
