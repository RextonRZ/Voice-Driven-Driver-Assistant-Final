# Voice-Driven Driver Assistant

A mobile application that provides a voice-driven interface for drivers, featuring maps integration and driver assistance features.

## Project Structure

- **Frontend**: React Native with Expo
- **Backend**: FastAPI (Python)

## Setup Instructions

### Prerequisites

- Python 3.10+ for backend
- Node.js and npm/yarn for frontend
- Google Maps API key

### Backend Setup

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   ```

3. Activate the virtual environment:
   - Windows:
     ```
     venv\Scripts\activate
     ```
   - macOS/Linux:
     ```
     source venv/bin/activate
     ```

4. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
   
   If requirements.txt doesn't exist, install the following:
   ```
   pip install fastapi uvicorn pydantic pydantic-settings python-dotenv requests
   ```

5. Create a `.env` file in the backend directory:
   ```
   GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
   ```

### Frontend Setup

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Install dependencies:
   ```
   npm install
   # or
   yarn install
   ```

3. Create a `.env` file in the frontend directory:
   ```
   GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
   ```

## Running the Application

### Backend

1. Navigate to the backend directory:
   ```
   cd backend
   ```

2. Activate the virtual environment (if not already activated)

3. Run the FastAPI server:
   ```
   python -m uvicorn app.main:app --reload
   ```

4. The backend API will be available at:
   ```
   http://localhost:8000
   ```

5. API documentation is available at:
   ```
   http://localhost:8000/docs
   ```

### Frontend

1. Navigate to the frontend directory:
   ```
   cd frontend
   ```

2. Start the Expo development server:
   ```
   npx expo start
   ```

3. Follow the instructions in the terminal to run the app on a device or emulator

## Testing

### Testing the Backend

1. Make sure the backend server is running

2. Run the test script:
   ```
   cd backend
   python test_maps_api.py
   ```

### Testing the Frontend

The app includes built-in functionality for testing maps integration and other features.

## Development Notes

- The backend API runs in development mode by default, which disables authentication for easier testing
- To enable production mode, set `DEV_MODE = False` in `backend/app/api/v1/maps.py`
- Both frontend and backend should use the same Google Maps API key

## Troubleshooting

- If you encounter import errors in the backend, ensure all directories have `__init__.py` files
- For frontend mapping issues, verify that the Google Maps API key is correctly set in both .env files
- For API connectivity issues from the app, ensure the API_URL in mapsService.ts is correctly pointing to your backend