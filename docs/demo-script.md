# MargaMitra · demo script (5 minutes)

Test case 1: Surathkal, 2–29 Nov 2026. Day 0 is 2 Nov, so 10 Nov is day 8 and "today" on the timeline is 10 Nov.

Every date and count below comes from the project brief. Each one is marked **(check)** until the timed run in Phase 4 confirms it on screen.

## Roles

| Who | Does |
|---|---|
| Saumya | Speaks. Says the sentence in each "Say" cell. |
| Tanuj | Drives the laptop (1440×900): clicks, copilot questions. |
| Dhruv | Holds the officer phone and the crew phone. |
| Nidhi | Holds the resident phone and runs the record scripts. |

## Before you start

- [ ] On the demo server, run `python -m scripts.seed_demo` (run it again after every rehearsal). **(check)**
- [ ] Set `LLM_CACHE=1` and do one full rehearsal on that server, so most answers replay from its cache. The `.cache` folder is not copied into the image.
- [ ] Set `WEATHER_MODE=fixture`.
- [ ] The laptop shows `/`. Dhruv's phone shows `/approvals`. Nidhi's phone shows `/confirm/W-104`.
- [ ] The backup video is open in a second window, paused at 0:00.
- [ ] All phones are charged.

## Beat 1 · 0:00–0:30 · Landing

| Time | Who | Click | Say | Must appear | If it fails |
|---|---|---|---|---|---|
| 0:00 | Saumya | Tanuj stays on `/`, then picks Ward engineer and opens the command centre (check the button names on screen). | Every department digs the same road on its own calendar, so roads are cut again and again. MargaMitra makes the city dig once. | The landing page with the role choices. | Reload once, then play the backup video from 0:00. |

## Beat 2 · 0:30–1:10 · The old way

| Time | Who | Click | Say | Must appear | If it fails |
|---|---|---|---|---|---|
| 0:30 | Saumya | Tanuj opens `/command` and turns "Compare with the old way" on. | The old way digs Munchur Road four times in a month. Nine clashes: same road same days, digging after resurfacing, and cutting protected roads. | The old-way plan on the map; Munchur Road dug 4 times in the month (check on screen); 9 clashes (check on screen). | Reload once, then play the backup video from 0:30. |

## Beat 3 · 1:10–2:10 · Orchestrate

| Time | Who | Click | Say | Must appear | If it fails |
|---|---|---|---|---|---|
| 1:10 | Saumya | Tanuj starts the orchestrate run (check the button name on screen). | Six department agents negotiate live. Water and Telecom agree to dig one shared trench from 10 to 15 November. | Messages arriving one by one on the Negotiation tab; Water and Telecom both accept a shared trench, 10–15 Nov (check on screen); the clashes fall to 0 (check on screen). | Reload once, then play the backup video from 1:10. |
| 1:40 | Saumya | Tanuj types copilot question 1: `Show every dig on Munchur Road next week` | The copilot reads the same plan the screens use, and shows every dig on Munchur Road on the map. | Steps "Finding works on Munchur Road" (W-104, T-221, G-310, R-501) and "Showing them on the map"; the Works tab opens and W-104 is selected; reply "4 works are planned on Munchur Road. W-104 and T-221 share one trench on 10–15 Nov." (check on screen). | Open the Works tab and click W-104. |

## Beat 4 · 2:10–2:40 · Approval

| Time | Who | Click | Say | Must appear | If it fails |
|---|---|---|---|---|---|
| 2:10 | Saumya | Dhruv opens the pending plan on `/approvals` and approves it. | The plan needs a ward engineer's approval. Dhruv approves on his phone, and the command centre updates by itself. | A pending approval on the phone; after approving, the command centre shows the plan as approved without a reload. | Reload `/approvals` once, then play the backup video from 2:10. |

## Beat 5 · 2:40–3:30 · Rain

| Time | Who | Click | Say | Must appear | If it fails |
|---|---|---|---|---|---|
| 2:40 | Saumya | Tanuj types copilot question 2: `Rain is coming on 14 Nov. Re-plan and show me what moved.` | Seventy millimetres of rain is coming. Three works leave the rain window, trench-hours in rain fall to zero, and the procession road stays free. | The five steps: "Reading the rain forecast for 14–15 Nov", "Finding works on low-lying roads", "Asking the departments to move", "Re-planning with the scheduler", "Waiting for your approval". D-412, P-118 and W-118 move out (check on screen). Trench-hours in rain fall to 0. The procession on 20 Nov keeps its road free (check on screen). The timeline jumps to 12 Nov and the Risk tab opens. | Click Simulate rain on the timeline card. If it is greyed out, the re-plan has already started: open the Risk tab. |
| 3:15 | Saumya | Dhruv approves the new plan on `/approvals`. | Dhruv approves the new plan, and it is in force. | The approval clears on the phone; the command centre shows the new plan. | Reload `/approvals` once, then play the backup video from 3:15. |

## Beat 6 · 3:30–4:15 · Money only after proof

| Time | Who | Click | Say | Must appear | If it fails |
|---|---|---|---|---|---|
| 3:30 | Saumya | Dhruv opens `/field/T-230/result` on the crew phone. | A crew reused T-221's before photo for T-230. The money is held and an inspector is called. | "Money held" with "Photo reused". | Reload once, then play the backup video from 3:30. |
| 3:50 | Saumya | Dhruv uploads W-104's after photo; Nidhi answers Yes on `/confirm/W-104`. | W-104's after photo passes the place and time checks, and the resident says yes. The deposit is released. | The result for W-104 shows the repair passed and the deposit released. | Reload once, then play the backup video from 3:50. |

## Beat 7 · 4:15–4:40 · Public record

| Time | Who | Click | Say | Must appear | If it fails |
|---|---|---|---|---|---|
| 4:15 | Saumya | Tanuj opens `/record` and clicks "Check the record". Nidhi runs `python -m scripts.tamper_demo`, then Tanuj checks again. Nidhi runs `python -m scripts.tamper_demo --restore`, then Tanuj checks again. (**check:** the scripts are not on `main` yet.) | Anyone can check the public record. One changed entry breaks the check at exactly that entry, and restoring it makes it pass. | The check passes; after the change it fails at that entry; after the restore it passes again. | Reload once, then play the backup video from 4:15. |

## Beat 8 · 4:40–5:00 · Impact

| Time | Who | Click | Say | Must appear | If it fails |
|---|---|---|---|---|---|
| 4:40 | Saumya | Tanuj opens `/impact` and points at three numbers on the page (check which three on screen). | Across fifty test cases the full system cuts clashes, rain exposure and digs per road. Dig once. Fix right. Keep roads moving. | The impact page with results for test cases 1 to 50 and what each part adds. | Reload once, then play the backup video from 4:40. |

## The spare question for judges

Copilot question 3: `Why does W-104 start on 10 Nov?` The drawer for W-104 opens with the reasons, and the copilot reads the first one aloud.

## The 30-second version (beats 3, 5 and 6)

1. Saumya: "Six department agents negotiate live, and Water and Telecom agree to dig one shared trench." Tanuj starts orchestrate.
2. Saumya: "Seventy millimetres of rain is coming. The copilot re-plans, and three works leave the rain window." Tanuj asks copilot question 2.
3. Saumya: "Money is released only after proof: a reused photo is held, a real repair with a resident's yes is paid." Dhruv and Nidhi show beat 6.

## Three likely judge questions

**What do the departments' agents add to the scheduler?**
They bring each department's own needs into the plan before the scheduler runs, so a shared trench or a move is agreed rather than imposed. The scheduler still fixes the dates, and anything the agents cannot settle goes to it.

**Why does no number come from a model?**
Every date, cost and count comes from the city's cost tables, the scenario or the scheduler's own metrics. A model only picks an option number and writes one sentence, and any sentence with a digit in it is dropped.

**How can anyone check the record was not changed?**
Each entry carries a fingerprint of the entry before it, so changing one entry breaks every link after it. Anyone can press "Check the record" and see the first entry that fails.
