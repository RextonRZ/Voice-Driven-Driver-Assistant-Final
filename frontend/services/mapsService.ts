import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Backend API URL - adjust based on your development environment
// const API_URL = 'http://10.0.2.2:8000/api/v1'; // Use this for Android emulator
//const API_URL = 'http://10.167.74.96:8000/api/v1';  // Use this for Samsung A52s (Vanness)
const API_URL = 'http://10.168.104.2:8000/api/v1';  
// const API_URL = 'http://localhost:8000/api/v1'; // Use this for iOS simulator
// const API_URL = 'https://your-production-api.com/api/v1'; // Production URL

export class MapsService {
  /**
   * Gets the Google Maps API key from environment variables or backend
   */
  static async getApiKey(): Promise<string> {
    const apiKey = process.env.EXPO_PUBLIC_GOOGLE_MAPS_API_KEY;

    try {
      // First try to get from environment variables
      if (apiKey) {
        console.log('Using API key from environment variables');
        return apiKey;
      }

      console.warn('Unable to load API key from @env, will try backend');

      // Get the token from storage
      const token = await AsyncStorage.getItem('userToken');

      if (!token) {
        // For development purposes - provide a dummy key if not authenticated
        // Remove or modify this section for production
        console.warn('No authentication token found, using development fallback');
        return 'DEVELOPMENT_KEY';
      }

      // Add the token to the request
      const response = await axios.get(`${API_URL}/maps/google-maps-key`, {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      return response.data.api_key;
    } catch (error) {
      console.error('Error fetching Google Maps API key:', error);

      // For development only - fallback to a placeholder key
      if (__DEV__) {
        console.warn('Using development placeholder key');
        return 'DEVELOPMENT_KEY';
      }

      throw error;
    }
  }

  /**
   * Get directions from origin to destination from the backend.
   */
  static async getDirections(origin: string, destination: string): Promise<any> {
    try {
      console.log('Requesting directions with origin:', origin, 'destination:', destination);
      const response = await axios.get(`${API_URL}/maps/directions`, {
        params: { origin, destination },
      });
      const responseData = await response.data;
      console.log('Directions response:', response.data);
      return response.data;
    } catch (error) {
      console.error('Error fetching directions:', error);
      throw error;
    }
  }

  /**
   * Get the coordinates of a place by name from the backend.
   */
  static async getPlaceCoordinates(placeName: string): Promise<{ latitude: number; longitude: number }> {
    try {
      console.log(`Fetching coordinates for place: ${placeName}`);
      const response = await axios.get(`${API_URL}/maps/place-coordinates`, {
        params: { placeName },
      });

      if (response.data.status !== "OK") {
        throw new Error(`Place not found: ${placeName}`);
      }

      const location = response.data.coordinates;
      console.log(`Coordinates for ${placeName}:`, location);
      return location;
    } catch (error) {
      console.error(`Error fetching place coordinates for ${placeName}:`, error);
      throw error;
    }
  }

  /**
   * Utility function to calculate the distance between two geographical points.
   */
  static calculateDistance = (lat1: number, lon1: number, lat2: number, lon2: number): number => {
    const toRadians = (degrees: number) => (degrees * Math.PI) / 180;

    const R = 6371; // Radius of the Earth in kilometers
    const dLat = toRadians(lat2 - lat1);
    const dLon = toRadians(lon2 - lon1);

    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(toRadians(lat1)) * Math.cos(toRadians(lat2)) *
      Math.sin(dLon / 2) * Math.sin(dLon / 2);

    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    const distance = R * c; // Distance in kilometers

    return distance * 1000; // Convert to meters
  };
}
