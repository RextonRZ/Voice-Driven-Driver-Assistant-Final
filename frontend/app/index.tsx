import React, { useState, useEffect } from 'react';
import { View, Image, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';

export default function Index() {
    const [showSplash, setShowSplash] = useState(true); // State to control splash visibility
    const router = useRouter(); // Router for navigation

    useEffect(() => {
        // Set a delay of 3 seconds before redirecting
        const timeout = setTimeout(() => {
            setShowSplash(false); // Hide the splash screen
            router.push('/driver'); // Redirect to /driver
        }, 3000); // 3-second delay

        return () => clearTimeout(timeout); // Cleanup timeout on unmount
    }, []);

    if (showSplash) {
        // Render the splash screen
        return (
            <View style={styles.container}>
                <Image
                    source={require('../assets/images/splash.png')} // Replace with your splash image
                    style={styles.splashImage}
                />
            </View>
        );
    }

    return null; // Render nothing after the splash screen
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: '#FFFFFF', // Background color for the splash screen
    },
    splashImage: {
      width: '100%', // Stretch the image to fit the screen width
      height: '100%', // Stretch the image to fit the screen height
      resizeMode: 'cover', // Change to 'contain' if you want the entire image to fit without cropping
  },
});