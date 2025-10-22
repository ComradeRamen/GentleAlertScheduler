# GentleAlertScheduler

A simple desktop application for scheduling alerts/reminders on Windows. When an alert triggers, it displays a semi-transparent click-through overlay that gently expands to cover the screen over a configured duration.

<img width="1367" alt="Screenshot 2025-04-23 012722" src="https://github.com/user-attachments/assets/8a68aeb9-e82f-4236-90ef-4f96e7a648b9" />

## Features

* Schedule alerts with specific dates, times, and recurrence (daily, weekly, monthly).
* Customize overlay appearance: expansion time, duration, transparency, color, start size, and optional text.
* Configure default settings for new alerts.
* Manage alerts via a table interface (add, edit, remove, test).
* System tray icon for basic control (stop/delay active alerts, open scheduler, exit).
![image](https://github.com/user-attachments/assets/b536c287-d724-4c54-8ba4-51afbac20d07)
* Optional: Run at Windows startup.

## Disclaimer

This code was primarily machine-generated for my personal use. While it's been functional in my use, it may contain bugs or limitations.

I am sharing it publicly in the hope that it might be useful to others, but use it at your own discretion.

Feel free to open pull requests with any improvements.

## Building

This project uses Python with PyQt5. A GitHub Actions workflow is included in `.github/workflows/` to automatically build a Windows executable using PyInstaller upon manual trigger or tag push. The built executable can be found in the Releases section.
