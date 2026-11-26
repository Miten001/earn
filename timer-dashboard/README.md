# Window Timers

A standalone dashboard for manually tracking multiple countdowns. It does not read your screen, detect challenges, switch windows, or click anything in your browser.

1. Extract the repository ZIP and open `timer-dashboard/index.html` in your laptop browser. No installation is needed.
2. Give a timer a name, such as `Chrome — Window 1`, enter its duration, then click **Start timer**. Repeat for other windows. Each timer has independent Pause, Restart, and Remove controls.
3. At zero the timer shows **Time’s up**. **Enable notifications** requests system notifications where your browser and OS allow them. If it isn’t available when opening the file directly, you can run `python -m http.server 8000 --directory timer-dashboard` from the repo and open `http://localhost:8000`.
4. If **Open floating panel** is available, use it to keep a read-only view above other windows (supported Chrome/Edge versions only). Manage timers in the main dashboard. Keep that tab open and avoid refreshing; timers are stored in memory for the current session. Sleeping the laptop or suspending the tab can delay alerts until it resumes.

This page is separate from Captcha Lab and the existing homepage.

## Tests

Run `node --test timer-dashboard/timer-model.test.cjs` from the repository root.
