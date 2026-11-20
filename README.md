# FogGuard

### IoT-Based Vehicle Proximity Detection System for Low-Visibility Conditions

FogGuard is an IoT-based vehicle proximity detection prototype that uses ultrasonic sensors to monitor nearby obstacles and presents distance information and directional warnings through a real-time web dashboard.

## Features

- Six HC-SR04 ultrasonic sensors for multi-directional obstacle detection.
- Directional distance monitoring for front, left-front, right-front, left-side, right-side, and overhead positions.
- Arduino-based sensor acquisition.
- ESP32-based wireless communication.
- Real-time dashboard updates using WebSockets.
- Detection records and dashboard analytics.

## Hardware

| Component | Purpose |
|---|---|
| Arduino Uno | Reads ultrasonic sensor measurements |
| ESP32 | Wireless communication |
| HC-SR04 ultrasonic sensors × 6 | Measures distance to nearby obstacles |
| Jumper wires, breadboard, and power supply | Prototype connections and power |
| Laptop or mobile device | Dashboard access |

## Sensor Configuration

| Sensor | Position |
|---|---|
| S1 | Front |
| S2 | Left-front |
| S3 | Right-front |
| S4 | Left side |
| S5 | Right side |
| S6 | Overhead |

## Technology Stack

- **Firmware:** Arduino C/C++
- **Backend:** Python, FastAPI, SQLAlchemy, SQLite
- **Real-time communication:** WebSockets
- **Frontend:** React, TypeScript, Vite
- **UI and visualization:** Tailwind CSS, Recharts, Three.js

## Project Structure

```text
FogGuard/
├── arduino/       # Arduino sketch
├── assets/        # Project assets and diagrams
├── backend/       # FastAPI backend
├── docs/          # Project documentation
├── firmware/      # Device firmware
├── frontend/      # React dashboard
└── README.md
```

## Run Locally

### Prerequisites

- Python
- Node.js and npm
- Git

### 1. Clone the repository

```bash
git clone https://github.com/Vishwanath-aiml/FogGuard.git
cd FogGuard
```

### 2. Start the backend

Open a terminal in the project root:

```bash
cd backend
python -m venv venv
```

Activate the virtual environment:

| Windows (PowerShell) | Windows (CMD) | macOS / Linux |
|---|---|---|
| `.\venv\Scripts\Activate.ps1` | `venv\Scripts\activate` | `source venv/bin/activate` |

Install dependencies:

```bash
pip install -r requirements.txt
```

Create the environment file:

| Windows | macOS / Linux |
|---|---|
| `copy .env.example .env` | `cp .env.example .env` |

Start the backend:

```bash
python -m uvicorn app.main:app --reload
```

Backend: `http://localhost:8000`  
API documentation: `http://localhost:8000/docs`

### 3. Start the frontend

Open a second terminal from the project root:

```bash
cd frontend
npm ci
npm run dev
```

Dashboard: `http://localhost:5173`

The Vite development server proxies API requests and WebSocket connections to the backend at `http://localhost:8000`.

### 4. Run with the hardware

- Upload the Arduino sketch from `arduino/` to the Arduino Uno using the Arduino IDE.
- Connect the sensors according to the pin assignments in the sketch.
- Configure and flash the ESP32 firmware from the relevant directory under `firmware/`.
- Ensure the device and backend are configured to communicate over the same network.

The backend's sample environment configuration enables simulation mode by default, allowing the dashboard to run without physical hardware.

## Future Improvements

- Improve sensor calibration and filtering.
- Refine warning thresholds and prioritization.
- Improve dashboard analytics and mobile responsiveness.

## Team

**Department of Computer Science and Engineering**  
**National Institute of Technology Delhi**

| Name | Roll Number |
|---|---|
| Vishwanath V | 251210138 |
| Satyam Jha | 251210105 |
| Shivam Rattan | 251210109 |
| Somya Garg | 251210118 |