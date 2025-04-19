# UMHackathon 2025: Grab DAX Handsfree Voice Assistant

**Team:** Ctrl+C Ctrl+V
**Members:** 
1. Khor Rui Zhe
2. Ooi Rui Zhe
3. Vanness Liu Chuen Wei
4. Lim Hong Yu
---

## Table of Contents

1.  [Overview](#overview)
2.  [Problem Statement (Hackathon Task 1)](#problem-statement-hackathon-task-1)
3.  [Features](#features)
    *   [Backend](#backend)
    *   [Frontend](#frontend)
4.  [Technology Stack](#technology-stack)
    *   [Backend](#backend-1)
    *   [Frontend](#frontend-1)
5.  [Project Structure](#project-structure)
    *   [Backend Structure](#backend-structure)
    *   [Frontend Structure](#frontend-structure)
6.  [Setup and Installation](#setup-and-installation)
    *   [Prerequisites](#prerequisites)
    *   [Backend Setup](#backend-setup)
    *   [Frontend Setup](#frontend-setup)
7.  [Running the Application](#running-the-application)
    *   [Running the Backend](#running-the-backend)
    *   [Running the Frontend](#running-the-frontend)
8.  [API Endpoints](#api-endpoints)
9.  [Key Challenges Addressed](#key-challenges-addressed)
10. [Future Improvements](#future-improvements)
11. [License](#license)

---

## Overview

This project is our submission for the **UMHackathon 2025**, addressing **Task 1: DAX Assistant – Handsfree** from the Grab Problem Statement.

The goal is to develop a proof-of-concept voice-driven assistant for Grab's driver-partners (DAX). Currently, drivers interact with AI assistants via text, which is impractical and unsafe while driving. This project aims to create a robust, voice-centric interface that allows drivers to receive guidance and perform tasks handsfree, enhancing safety and convenience.

The system processes driver voice input, understands their intent even in noisy environments typical of Southeast Asian roads, performs relevant actions (like navigation, communication checks), and responds with synthesized voice output. The frontend provides a simulated driver experience, including map navigation and ride workflow visualization.

---

## Problem Statement (Hackathon Task 1)

Grab aims to empower drivers through technology. The challenge lies in transitioning from text-based AI interaction to a voice-first approach suitable for active driving scenarios. This requires overcoming significant real-world hurdles:

1.  **Challenging Audio Conditions:** Traffic/road noise, engine sounds, weather (rain/wind), urban ambient noise, and audio system feedback.
2.  **Speech Pattern Complexities:** Regional accents, dialects, variations in speech speed, and colloquial expressions common in Southeast Asia.
3.  **Partial Audio Clarity:** The system must be able to interpret incomplete or unclear voice inputs.
4.  **Environmental Resilience:** The solution needs to be adaptable and maintain reliable communication across diverse environmental conditions.

Our objective is to build a robust voice interaction system addressing these challenges, enabling reliable driver-assistant communication.

---

## Features

### Backend (FastAPI)

*   **Audio Processing:**
    *   Handles various audio input formats (via pydub/FFmpeg).
    *   Audio decoding (Base64).
    *   Audio conversion to required format (LINEAR16 WAV).
    *   **Noise Reduction:** Implements tunable noise reduction (`noisereduce` library) to improve transcription accuracy in noisy environments.
*   **Speech-to-Text (STT):**
    *   Uses Google Cloud Speech-to-Text API with automatic language detection hints based on supported SEA languages.
    *   **Fallback Mechanism:** Utilizes OpenAI Whisper API as a fallback if Google STT fails or doesn't detect language confidently.
*   **Language Detection:**
    *   Leverages Google Cloud Translate API to detect the language of the transcript if needed (especially after Whisper fallback).
*   **Transcription Refinement:**
    *   (Optional, via config) Uses Google Gemini to refine the raw STT transcript, correcting errors and improving clarity based on context and language.
*   **Translation:**
    *   Translates refined user input (from detected language) to a common NLU processing language (e.g., English) using Google Cloud Translate API.
    *   Translates the assistant's response back from the NLU language to the driver's original language.
*   **Natural Language Understanding (NLU):**
    *   Uses Google Gemini (`gemini-pro`) to understand the driver's intent and extract relevant entities (e.g., destination, message content) from the (translated) user query, considering conversation history and context.
    *   Handles intents like `get_route`, `send_message`, `check_flood`, `ask_gate_info`, `reroute_check`, and `general_chat`.
*   **Intent Dispatching & Action Handling:**
    *   **Navigation:** Integrates with Google Maps Platform:
        *   **Routing:** Uses the new **Routes API v2** for traffic-aware routing and ETA calculation.
        *   **Geocoding/Places:** Uses legacy Maps APIs (via `googlemaps` library) for address-to-coordinate lookup, reverse geocoding, and place details (including checking location complexity for `ask_gate_info`).
        *   **Rerouting Check:** Periodically checks for significantly faster routes.
        *   **Flood Check:** *Experimental* feature using scraped data from Malaysia's `publicinfobanjir.water.gov.my` based on driver's current state (determined via reverse geocoding).
    *   **Communication:** Placeholder for sending messages (e.g., to passengers). Requires `TwilioClient` implementation and configuration.
    *   **Safety:**
        *   **Crash Detection Handling:** Placeholder endpoint and service logic for receiving crash reports and notifying emergency contacts (requires contact lookup integration and configured `TwilioClient`).
        *   **Drowsiness Detection:** Analyzes batches of image frames (sent from frontend as base64) using MediaPipe FaceMesh for landmarks and YOLOv8 models for eye state (open/closed) and yawn detection. Reports potential drowsiness based on configurable thresholds.
*   **Text-to-Speech (TTS):**
    *   Synthesizes the final assistant response into audible speech using Google Cloud Text-to-Speech API.
    *   Selects appropriate voices based on the detected input language.
    *   Returns audio as a base64 encoded string.
*   **API & Infrastructure:**
    *   FastAPI framework for robust and efficient API endpoints.
    *   Dependency Injection for managing services and clients.
    *   Configuration management using Pydantic and `.env` files.
    *   Structured logging.
    *   CORS middleware for frontend integration.
    *   Basic health check endpoint.

### Frontend (React Native with Expo)

*   **UI Framework:** React Native with Expo Router for file-based routing.
*   **Map Integration:** Uses `react-native-maps` (with Google Maps provider) to display the driver's location, destination markers, and route polylines.
*   **Location Services:** Uses `expo-location` to get the driver's current location and track position updates.
*   **Ride Simulation Workflow:**
    *   Splash screen (`index.tsx`).
    *   Driver screen (`driver.tsx`) with map view.
    *   Simulated ride request modal with customer details.
    *   Functionality to "Approve" or "Decline" ride requests.
    *   Navigation polyline display and animation for the route (to customer, then to destination).
    *   Dynamic display of current navigation instruction, distance, and ETA.
    *   Simulated arrival detection (proximity check).
    *   Countdown modal upon reaching the customer before rerouting to the destination.
    *   Success modal upon reaching the final destination.
    *   Simulated payment processing UI state.
*   **UI Components:**
    *   `@gorhom/bottom-sheet` for displaying ride status and customer details contextually.
    *   Custom map controls (Relocate, Toggle Map Type, Toggle Traffic).
    *   Modal dialogs for ride requests, countdowns, success, and messaging (placeholder).
*   **Styling:** Uses Tailwind CSS (`nativewind`) and StyleSheet for UI design.
*   **API Integration:** Includes a `mapsService.ts` for interacting with Google Maps (API key fetch, geocoding, directions) and potentially the backend API (though voice interaction logic isn't fully shown in the provided `driver.tsx`).

---

## Technology Stack

### Backend

*   **Framework:** FastAPI
*   **Language:** Python 3.10+
*   **AI/ML Services:**
    *   Google Cloud STT API
    *   Google Cloud TTS API
    *   Google Cloud Translate API v2
    *   Google Gemini API (`gemini-2.0-flash`)
    *   OpenAI Whisper API (Fallback for STT)
*   **Navigation:**
    *   Google Maps Routes API v2
    *   Google Maps Geocoding API
    *   Google Maps Places API
*   **Audio Processing:** Pydub, Noisereduce, Librosa, NumPy
*   **Drowsiness Detection:** OpenCV (`opencv-python`), MediaPipe, Ultralytics YOLOv8 (`ultralytics`)
*   **HTTP/Async:** `httpx`, `requests` (for flood scraping)
*   **Configuration:** Pydantic, `python-dotenv`
*   **Web Server:** Uvicorn
*   **Other:** `pycountry`, `certifi`

### Frontend

*   **Framework:** React Native (with Expo SDK)
*   **Language:** TypeScript
*   **Routing:** Expo Router
*   **Mapping:** `react-native-maps`
*   **Location:** `expo-location`
*   **UI Components:** `@gorhom/bottom-sheet`, `react-native-gesture-handler`
*   **Styling:** Tailwind CSS (`nativewind`), React Native StyleSheet
*   **State Management:** React Hooks (`useState`, `useEffect`, `useRef`, etc.)

---

## Project Structure

### Backend Structure
backend/
├── app/
│ ├── api/ # FastAPI routers/endpoints
│ │ ├── assistant.py
│ │ ├── dependencies.py # Dependency injection setup
│ │ ├── navigation.py
│ │ └── safety.py
│ ├── core/ # Core logic, clients, config
│ │ ├── clients/ # Clients for external APIs (Google, OpenAI, Twilio)
│ │ │ ├── gemini.py
│ │ │ ├── google_maps.py
│ │ │ ├── google_stt.py
│ │ │ ├── google_tts.py
│ │ │ ├── google_translate.py
│ │ │ ├── openai_client.py
│ │ │ └── twilio_client.py (Placeholder)
│ │ ├── audio_enhancement.py # Noise reduction, VAD logic
│ │ ├── config.py # Pydantic settings model
│ │ └── exception.py # Custom exception classes
│ ├── models/ # Pydantic models
│ │ ├── internal.py # Internal data structures (NluResult, RouteInfo, etc.)
│ │ ├── request.py # API request models
│ │ └── response.py # API response models
│ ├── services/ # Business logic services
│ │ ├── conversation_service.py
│ │ ├── navigation_service.py
│ │ ├── nlu_service.py
│ │ ├── safety_service.py
│ │ ├── synthesis_service.py
│ │ ├── transcription_service.py
│ │ └── translation_service.py
│ ├── ml_models/ # Pre-trained models (e.g., YOLO .pt files)
│ │ ├── detect_eye_best.pt
│ │ └── detect_yawn_best.pt
│ ├── main.py # FastAPI app initialization, middleware, exception handlers
│ └── init.py
├── requirements.txt # Python dependencies
└── .env.example # Example environment variables file


### Frontend Structure
frontend/
├── app/ # Expo Router pages
│ ├── (tabs)/ # Example grouping if tabs were used
│ │ └── ...
│ ├── _layout.tsx # Root layout component
│ ├── driver.tsx # Main driver screen component
│ └── index.tsx # Splash screen / initial route
├── assets/ # Static assets (images, fonts)
│ └── images/
│ ├── destination-icon.png
│ ├── origin-icon.png
│ └── splash.png
├── components/ # Reusable UI components (if any)
├── services/ # Service layer for API calls, etc.
│ └── mapsService.ts
├── app.json # Expo configuration
├── babel.config.js # Babel configuration
├── globals.css # Tailwind CSS global styles
├── package.json # Node.js dependencies
├── tailwind.config.js # Tailwind CSS configuration
└── tsconfig.json # TypeScript configuration


---

## Setup and Installation

### Prerequisites

*   **Git:** For cloning the repository.
*   **Python:** 3.10 or higher recommended.
*   **pip:** Python package installer.
*   **Node.js:** LTS version recommended (includes npm).
*   **Yarn:** (Optional) Alternative Node.js package manager.
*   **FFmpeg:** Required by `pydub` for audio processing. Download from [ffmpeg.org](https://ffmpeg.org/download.html) and ensure it's in your system's PATH or configure the path explicitly in `backend/app/services/transcription_service.py`.
*   **Expo Go App:** Install on your mobile device for testing the frontend.
*   **Google Cloud Account:** Required for Google APIs (STT, TTS, Translate, Maps, Gemini).
    *   Enable the necessary APIs in your Google Cloud Console.
    *   Set up **Application Default Credentials (ADC)** by running `gcloud auth application-default login` OR download a service account key JSON file.
*   **OpenAI Account:** Required for Whisper API key (if using fallback).
*   **Gemini API Key:** Required for NLU and refinement. Obtain from Google AI Studio.
*   **Google Map API Key:** Required for routing, location capturing and travel time estimation.

### Backend Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-name>/backend
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up Google Cloud Credentials:**
    *   **Recommended:** Use Application Default Credentials (ADC). Run `gcloud auth application-default login` in your terminal and follow the prompts. The backend code will automatically pick these up.
    *   **Alternative:** Download a service account key JSON file from Google Cloud Console. Set the environment variable `GOOGLE_APPLICATION_CREDENTIALS` to the *full path* of this JSON file.
      ```bash
      # Example (macOS/Linux)
      export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/keyfile.json"
      # Example (Windows PowerShell)
      $env:GOOGLE_APPLICATION_CREDENTIALS="C:\path\to\your\keyfile.json"
      ```

5.  **Create `.env` file:**
    *   Copy the example file: `cp .env.example .env` (or `copy .env.example .env` on Windows).
    *   Edit the `.env` file and fill in your API keys and configuration:
        *   `GEMINI_API_KEY`: Your Google Gemini API key.
        *   `GOOGLE_MAPS_API_KEY`: Your Google Maps Platform API key (ensure Routes API, Geocoding API, Places API are enabled).
        *   `OPENAI_API_KEY`: (Optional) Your OpenAI API key if using Whisper fallback.
        *   *(Optional)* `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`: For SMS/call features (currently placeholder).
        *   Update `YAWN_MODEL_PATH` and `EYE_MODEL_PATH` in `app/core/config.py` if the paths to your `.pt` files are different.

### Frontend Setup

1.  **Navigate to the frontend directory:**
    ```bash
    cd ../frontend
    # Or from the root: cd <repository-name>/frontend
    ```

2.  **Install Node.js dependencies:**
    ```bash
    npm install
    # OR if using yarn
    # yarn install
    ```

3.  **(Optional) Configure Backend API URL:** If your backend isn't running on `http://localhost:8000`, you might need to update the base URL used in API calls within the frontend code (e.g., in `services/mapsService.ts` or wherever backend calls are made).

---

## Running the Application

### Running the Backend

1.  **Ensure your virtual environment is activated** and you are in the `backend` directory.
2.  **Ensure Google Cloud credentials and `.env` variables are set.**
3.  **Start the FastAPI server using Uvicorn:**
    ```bash
    uvicorn app.api.main:app --reload --host 0.0.0.0 --port 8000
    ```
    *   `--reload`: Automatically restarts the server on code changes (for development).
    *   `--host 0.0.0.0`: Makes the server accessible on your local network (needed for Expo Go).
    *   `--port 8000`: Specifies the port (ensure it's not blocked).

4.  The backend API should now be running at `http://<your-local-ip>:8000`.
5.  You can access the automatically generated API documentation at `http://<your-local-ip>:8000/docs`.

### Running the Frontend

1.  **Navigate to the `frontend` directory.**
2.  **Start the Expo development server:**
    ```bash
    npx expo start
    # OR
    # yarn start
    ```
3.  Expo DevTools will open in your browser.
4.  **Connect your device:**
    *   Open the Expo Go app on your iOS or Android device.
    *   Scan the QR code displayed in the terminal or Expo DevTools using the Expo Go app.
    *   Ensure your device is on the **same Wi-Fi network** as your computer running the backend and frontend servers.
5.  The app should load on your device.

---

## API Endpoints

The backend exposes the following main API endpoints (running on port 8000 by default):

*   `GET /`: Basic health check.
*   `POST /assistant/interact`: **(Core Endpoint)** Processes voice input (multipart form data: audio, session\_id, context) and returns transcription, response text, and response audio (base64).
*   `POST /assistant/detect-speech`: Checks a small audio chunk (base64 JSON body) for the presence of speech (used for frontend VAD).
*   `POST /safety/crash-detected`: Receives crash detection reports (JSON body). (Placeholder notification logic).
*   `POST /safety/analyze-sleepiness`: Receives image frames (base64 JSON body) for drowsiness analysis.
*   `POST /api/navigation/reroute-check`: Checks if a better route exists (JSON body).
*   `GET /api/navigation/directions`: Gets route details between origin/destination coordinates.
*   `GET /api/navigation/place-coordinates`: Gets coordinates for a place name.

Access the interactive OpenAPI documentation at `/docs` (e.g., `http://localhost:8000/docs`) for detailed request/response schemas.

---

## Key Challenges Addressed

This project attempts to address the key challenges outlined in the Hackathon problem statement:

1.  **Audio Conditions on the Road:**
    *   Implemented **noise reduction** (`noisereduce`) during audio preprocessing to mitigate background noise before STT.
2.  **Speech Pattern Complexities:**
    *   Leveraged **Google STT's language detection** capabilities with hints for common SEA languages.
    *   Used **OpenAI Whisper fallback** which is known for robustness across accents.
    *   Implemented **Transcription Refinement** using Gemini to potentially correct colloquialisms or errors based on context.
    *   **Translation layers** allow core NLU processing in a single language (English) while interacting with the user in their detected language.
3.  **Partial Audio Clarity / Resilience:**
    *   **STT Fallback:** Provides resilience if the primary STT service fails.
    *   **Transcription Refinement:** Attempts to infer intent even from potentially fragmented STT output.
    *   **NLU Confidence:** Gemini provides a confidence score, though its use in the current logic is basic.
4.  **Environmental Adaptability:**
    *   The combination of noise reduction, robust STT options, and language flexibility aims to improve adaptability across different environments and speakers. The **Flood Check** feature is an example of adapting to environmental conditions (though experimental).

---

## Future Improvements

*   **Real Voice Activation:** Implement "Hey Grab" or similar wake-word detection on the frontend to trigger recording automatically.
*   **Multiagent System:** Manage multiple different intent with single master agent to better handle the tasks.
*   **Frontend Voice Interaction:** Fully integrate frontend voice recording, sending audio to `/assistant/interact`, and playing back the received `response_audio`.
*   **Robust Communication Service:** Implement the `TwilioClient` (or alternative) properly for sending actual SMS/calls for `send_message`, `ask_gate_info`, and `crash_detected` intents.
*   **Contact Lookup:** Integrate with a real or mock user profile service to fetch emergency contacts.
*   **Persistent Storage:** Replace in-memory chat history storage with Redis or a database for persistence across server restarts.
*   **State Management:** Implement more robust state management for the driver's current context (e.g., current route details for better reroute comparison, active order status).
*   **Advanced Dialogue Management:** Move beyond simple intent-response to handle multi-turn conversations, context carry-over, and more complex dialogue flows using Gemini or another framework.
*   **Improved Drowsiness Model:** Fine-tune YOLO models, refine ROI extraction, potentially incorporate head pose estimation, and develop a more sophisticated confidence scoring mechanism. Integrate alerts into the frontend UI.
*   **Testing:** Add unit and integration tests for backend services and API endpoints.
*   **Error Handling:** Enhance error handling and provide more informative feedback to the user/frontend.
*   **UI/UX Refinements:** Improve the frontend UI based on user feedback.
*   **Deployment:** Add Dockerfiles and deployment scripts (e.g., for Google Cloud Run).

---
