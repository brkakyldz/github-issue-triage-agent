# Issue triage: brkakyldz/issue-triage-playground

| # | Title | Suggested labels | Reason | Duplicate of | Applied |
|---|---|---|---|---|---|
| 1 | Crash when a habit name contains an emoji | bug | Windows listing crashes on Unicode emoji characters. | - | labelled |
| 2 | Streak count is wrong for a few hours after midnight | bug | Check-ins near local midnight are assigned to the wrong day, disrupting streaks. | - | labelled |
| 3 | Support weekly habits, not only daily ones | enhancement | Requests weekly schedules and weekly streak counting. | - | labelled |
| 4 | Export check-in history to CSV | enhancement | Requests exporting check-in records for spreadsheet analysis. | - | labelled |
| 5 | How do I back up my data? | question | Asks how to back up and restore application data. | - | labelled |
| 6 | Logging a habit twice on the same day resets the streak to 1 | bug | Repeated same-day check-ins incorrectly reduce the streak. | - | labelled |
| 7 | Daily reminder notifications | enhancement | Requests scheduled reminders for incomplete habits. | - | labelled |
| 8 | README install steps fail on Python 3.13 | documentation | The README installation instructions do not work for Python 3.13. | - | labelled |
| 9 | Where is the data file stored on macOS? | question | Asks where the application stores its database on macOS. | - | labelled |
| 10 | Dark-terminal friendly colours for `streaks stats` | enhancement | Requests more legible chart colors or theme detection. | - | dropped by reviewer |
| 11 | UnicodeEncodeError on Windows when listing habits | bug, duplicate | Reports the same Windows emoji/Unicode listing crash as #1. | #1 | labelled, commented |
| 12 | Feature request: download my habit log as a spreadsheet | enhancement, duplicate | Requests CSV/spreadsheet export of check-in history, as in #4. | #4 | labelled |
| 13 | Typo in `streaks --help`: "recieve" | documentation, good first issue | A clearly scoped typo correction in command help text. | - | labelled |
| 14 | Allow editing or removing a past day's check-in | enhancement | Requests commands to correct or undo historical check-ins. | - | labelled |

## Duplicates
- #11 duplicates #1: Both report Windows UnicodeEncodeError when listing a habit whose name contains an emoji.
- #12 duplicates #4: Both request exporting check-in history as a CSV or spreadsheet.

## Draft replies
### #1 Crash when a habit name contains an emoji
Thanks for reporting this with clear reproduction steps and environment details. We’ll investigate how Windows terminal encoding is handled when listing Unicode habit names.

### #2 Streak count is wrong for a few hours after midnight
Thanks for reporting the timezone behavior and your local offset. We’ll check how check-in dates are calculated so they align with the intended local day.

### #3 Support weekly habits, not only daily ones
Thanks for the suggestion. Weekly schedules and streak tracking could be useful for habits that are not meant to happen every day.

### #4 Export check-in history to CSV
Thanks for the feature request. Exporting one row per check-in with the date, habit, and note sounds useful for spreadsheet analysis.

### #5 How do I back up my data?
Thanks for asking. We’ll clarify the supported backup and restore process, including where the data is stored.

### #6 Logging a habit twice on the same day resets the streak to 1
Thanks for the reproducible report. A repeated check-in on the same day should not unexpectedly reset the streak, and we’ll investigate.

### #7 Daily reminder notifications
Thanks for the suggestion. We’ll consider a scheduled reminder feature, including a simple command that can work with cron.

### #8 README install steps fail on Python 3.13
Thanks for reporting the Python 3.13 installation issue and the workaround. We’ll review the dependency pin and update the README instructions accordingly.

### #9 Where is the data file stored on macOS?
Thanks for asking. We’ll make the macOS data location easier to find and clarify whether it uses the Application Support directory.

### #10 Dark-terminal friendly colours for `streaks stats`
Thanks for the feedback. We’ll consider improving chart contrast on dark terminal themes, either through a theme option or automatic detection.

### #11 UnicodeEncodeError on Windows when listing habits
Thanks for the report. This appears to match #1, which describes the same Windows Unicode error when listing emoji-containing habit names; we’ll track the issue there.

### #12 Feature request: download my habit log as a spreadsheet
Thanks for the suggestion. This appears to match #4’s request for exporting check-in history as CSV, so we’ll track it there.

### #13 Typo in `streaks --help`: "recieve"
Thanks for spotting the typo and offering a clear first contribution. We’ll correct “recieve” to “receive” in the help text.

### #14 Allow editing or removing a past day's check-in
Thanks for describing the problem. Commands to edit or undo a past check-in would help correct mistakes while preserving accurate history.
