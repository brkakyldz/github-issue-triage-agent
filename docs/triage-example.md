# Issue triage: brkakyldz/issue-triage-sandbox

| # | Title | Suggested labels | Reason | Duplicate of | Applied |
|---|---|---|---|---|---|
| 1 | Crash when a habit name contains an emoji | bug | Emoji characters trigger a Windows UnicodeEncodeError when listing habits. | - | labelled |
| 2 | Streak count is wrong for a few hours after midnight | bug | Check-ins in the local early morning are assigned to the previous day, breaking streak calculations. | - | labelled |
| 3 | Support weekly habits, not only daily ones | enhancement | Requests an additional weekly habit schedule and weekly streak counting. | - | labelled |
| 4 | Export check-in history to CSV | enhancement | Requests a CSV export of check-in history for spreadsheet analysis. | - | labelled |
| 5 | How do I back up my data? | question | Asks whether data backup and restore are supported and where to find the data. | - | labelled |
| 6 | Logging a habit twice on the same day resets the streak to 1 | bug | Repeated same-day check-ins incorrectly reduce the streak instead of leaving it unchanged. | - | labelled |
| 7 | Daily reminder notifications | enhancement | Requests configurable notifications or a reminder command for unfinished habits. | - | labelled |
| 8 | README install steps fail on Python 3.13 | documentation | Installation guidance does not account for an extra dependency that lacks a Python 3.13 wheel. | - | labelled |
| 9 | Where is the data file stored on macOS? | question | Asks for the database location on macOS. | - | labelled |
| 10 | Dark-terminal friendly colours for `streaks stats` | enhancement | Requests improved chart colors or theme detection for dark terminals. | - | rejected by reviewer |
| 11 | UnicodeEncodeError on Windows when listing habits | bug, duplicate | Reports the same Windows emoji-display UnicodeEncodeError as issue #1. | #1 | commented |
| 12 | Feature request: download my habit log as a spreadsheet | enhancement, duplicate | Requests the same spreadsheet-compatible check-in history CSV export as issue #4. | #4 | rejected by reviewer |
| 13 | Typo in `streaks --help`: "recieve" | documentation, good first issue | A small help-text spelling correction is explicitly suitable for a first contribution. | - | labelled |
| 14 | Allow editing or removing a past day's check-in | enhancement | Requests commands to correct or undo historical check-ins. | - | labelled |

## Duplicates
- #11 duplicates #1: Both report Windows UnicodeEncodeError when `streaks list` displays an emoji habit name.
- #12 duplicates #4: Both request exporting check-in history as a spreadsheet-compatible CSV.

## Draft replies
### #1 Crash when a habit name contains an emoji
Thanks for reporting this, including the Windows and Python details. We'll investigate the console encoding behavior when displaying Unicode habit names.

### #2 Streak count is wrong for a few hours after midnight
Thanks for the clear timezone example. We'll look into how check-in dates are assigned relative to local time and how that affects streaks.

### #3 Support weekly habits, not only daily ones
Thanks for the suggestion. Weekly schedules and streak tracking would be a useful addition for habits that don't happen every day.

### #4 Export check-in history to CSV
Thanks for suggesting this. A CSV export with one row per check-in sounds useful for spreadsheet analysis.

### #5 How do I back up my data?
Thanks for asking. We'll clarify the supported backup and restore approach, including where the data is stored.

### #6 Logging a habit twice on the same day resets the streak to 1
Thanks for reporting this and confirming it is reproducible. We'll investigate why a duplicate same-day check-in changes the streak.

### #7 Daily reminder notifications
Thanks for the idea. A scheduled notification or a cron-friendly reminder command could help people keep up with their habits.

### #8 README install steps fail on Python 3.13
Thanks for reporting the Python 3.13 installation issue. We'll review the dependency constraint and update the README so its instructions reflect supported installations.

### #9 Where is the data file stored on macOS?
Thanks for the question. We'll make the macOS data location easier to find in the documentation.

### #10 Dark-terminal friendly colours for `streaks stats`
Thanks for pointing out the contrast problem. We'll consider a dark-friendly palette or a theme option for the stats chart.

### #11 UnicodeEncodeError on Windows when listing habits
Thanks for the report! This looks like a duplicate of #1, which describes the same Windows UnicodeEncodeError when listing emoji habit names. We'll track the issue there.

### #12 Feature request: download my habit log as a spreadsheet
Thanks for the report! This looks like a duplicate of #4, which requests a CSV export of check-in history. We'll track the request there.

### #13 Typo in `streaks --help`: "recieve"
Thanks for spotting the typo and offering to make a first contribution. This looks like a small, well-scoped correction to the help text.

### #14 Allow editing or removing a past day's check-in
Thanks for the suggestion. The ability to correct or undo an earlier check-in would help recover from mistakes while preserving history.
