import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Backend API URL - adjust based on your development environment
const API_URL = 'http://10.0.2.2:8000/api/v1'; // Use this for Android emulator
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
}
