# Issue triage: brkakyldz/issue-triage-sandbox

| # | Title | Suggested labels | Reason | Duplicate of | Applied |
|---|---|---|---|---|---|
| 10 | Dark-terminal friendly colours for `streaks stats` | enhancement | Requests theme support or automatic colour adjustment to improve chart readability. | - | labelled |
| 15 | Streak dropped from 41 to 1 after checking in again | bug, duplicate | Reports same-day duplicate check-ins resetting a streak, matching the existing report. | #6 | labelled, commented |
| 16 | Sync check-ins to Google Calendar | enhancement | Requests a new calendar integration for check-ins. | - | labelled |
| 17 | `--json` output for `streaks list` | enhancement | Requests machine-readable output for shell integrations. | - | labelled |
| 18 | Can I use streaks on two computers? | question | Asks about supported sync and potential data-file corruption across computers. | - | labelled |
| 19 | `streaks stats` shows 0% for a habit created today | bug | Reports likely incorrect same-day stats calculation after a check-in. | - | labelled |
| 20 | CONTRIBUTING link in the README returns a 404 | documentation, good first issue | Reports an incorrect documentation link; correcting it is a small, approachable fix. | - | labelled |

## Duplicates
- #15 duplicates #6: Both report that checking in twice on the same day resets the streak to 1.

## Draft replies
### #10 Dark-terminal friendly colours for `streaks stats`
Thanks for reporting the chart visibility issue. Theme-aware colours or a dark-theme option could make the stats output easier to read; we’ll consider this enhancement.

### #15 Streak dropped from 41 to 1 after checking in again
Thanks for the report! This looks like a duplicate of #6, which describes the same-day check-in resetting a streak. We’ll track the issue there.

### #16 Sync check-ins to Google Calendar
Thanks for suggesting this integration. Showing check-ins in Google Calendar could be useful, and we’ll consider it as a feature request.

### #17 `--json` output for `streaks list`
Thanks for the suggestion. Machine-readable output would help with shell integrations, and we’ll consider adding a JSON option.

### #18 Can I use streaks on two computers?
Thanks for asking. We’ll clarify the supported options for syncing between computers and the risks of sharing the data file through a cloud-synced folder.

### #19 `streaks stats` shows 0% for a habit created today
Thanks for reporting this unexpected result. We’ll investigate whether today’s check-in should count in the stats calculation on the day the habit is created.

### #20 CONTRIBUTING link in the README returns a 404
Thanks for catching the broken link. The README should point to the file’s actual location, and this looks like a straightforward fix for a first contribution.
