# GT7 AI Race Engineer

An AI-powered race engineering and telemetry analysis system for Gran Turismo 7.

This project parses live telemetry data directly from GT7, analyzes driver behavior against reference laps, and generates real-time coaching feedback similar to what race engineers provide in professional motorsports.

## Features

- Live telemetry parsing from Gran Turismo 7
- Real-time braking and throttle analysis
- Corner-by-corner performance evaluation
- Reference lap comparisons
- AI-generated coaching feedback
- Playback system for post-lap turn analysis
- Racing line deviation analysis
- Speed delta and exit performance tracking

## Demo

https://github.com/user-attachments/assets/1f248581-6be7-4321-ad6e-58303ea06968

## How It Works

The system receives live telemetry packets from Gran Turismo 7 over UDP and processes them in real time.

Telemetry data is analyzed against a reference lap to identify:
- Over-braking
- Late throttle pickup
- Poor corner exits
- Racing line inconsistencies
- Entry speed losses
- Instability during cornering

An AI analysis layer then converts telemetry differences into concise driver coaching feedback.


## Example Feedback

```text
Turn 5:
Carrying too little speed on entry and delaying throttle pickup on exit.
Try braking slightly later and getting back on throttle earlier to improve exit speed onto the straight.
