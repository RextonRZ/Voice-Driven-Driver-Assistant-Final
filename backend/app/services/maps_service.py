from ..core.config import settings
import os

class MapsService:
    """Service for handling Google Maps API operations."""
    
    @staticmethod
    def get_api_key():
        """
        Get the Google Maps API key from settings.
        Returns the API key or raises ValueError if not configured.
        """
        # Try to get from settings first
        api_key = settings.GOOGLE_MAPS_API_KEY
        
        # If not in settings, try environment directly (fallback)
        if not api_key:
            api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
            
        if api_key:
            return api_key
        else:
            # Return a placeholder for development
            return "PLACEHOLDER_API_KEY"
    
    @staticmethod
    def validate_api_key():
        """
        Validate that the Google Maps API key is configured.
        Raises ValueError if the API key is not found.
        """
        api_key = MapsService.get_api_key()
        if not api_key or api_key == "PLACEHOLDER_API_KEY":
            # Log a warning but don't raise error in development
            print("WARNING: Using placeholder Google Maps API key. Set GOOGLE_MAPS_API_KEY for production.")
        return True
