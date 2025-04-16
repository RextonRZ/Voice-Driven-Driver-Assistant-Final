import React, { useCallback, useMemo, useRef, useEffect, useState } from 'react'
import { Button, StatusBar, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import MapView, { Marker, Region, PROVIDER_GOOGLE, Polyline } from 'react-native-maps'
import { SafeAreaView } from 'react-native-safe-area-context'
import { Feather } from '@expo/vector-icons'
import BottomSheet, { BottomSheetView } from '@gorhom/bottom-sheet';
import * as Location from 'expo-location'
import { router } from 'expo-router'
import { MapsService } from '../services/mapsService'

export default function Driver() {
    const [region, setRegion] = React.useState<Region | null>(null)
    const [apiKey, setApiKey] = React.useState<string | null>(null)
    const [routeCoordinates, setRouteCoordinates] = useState<{ latitude: number; longitude: number }[]>([]);
    const [durationInTraffic, setDurationInTraffic] = useState<string | null>(null);
    const [distance, setDistance] = useState<string | null>(null);
    const destination = { latitude: 3.1175, longitude: 101.6773 }; // temporary remember to settle this

    const [loading, setLoading] = React.useState(true)
    const snapPoints = useMemo(() => ['18%', '60%'], []);

    useEffect(() => {
        const setupMap = async () => {
            try {
                let { status } = await Location.requestForegroundPermissionsAsync()
                if (status !== 'granted') {
                    console.error('Permission to access location was denied')
                    setLoading(false)
                    return
                }

                let location = await Location.getCurrentPositionAsync({})
                setRegion({
                    latitude: location.coords.latitude,
                    longitude: location.coords.longitude,
                    latitudeDelta: 0.01,
                    longitudeDelta: 0.01,
                })

                const key = await MapsService.getApiKey()
                setApiKey(key)

                setLoading(false)
            } catch (error) {
                console.error('Error setting up map:', error)
                setLoading(false)
            }
        }

        setupMap()
    }, [])

    const fetchRoute = async () => {
        if (!region) {
            console.log('Region is not set');
            return;
        }

        console.log('Fetching route...');
        const origin = `${region.latitude},${region.longitude}`;
        const placeName = "Mid Valley Megamall North Court Entrance"; // Hardcoded place name

        try {
            // Fetch the destination coordinates dynamically
            const destinationCoords = await MapsService.getPlaceCoordinates(placeName);
            console.log(`Destination coordinates for ${placeName}:`, destinationCoords);

            // Fetch directions using the origin and destination coordinates
            const directions = await MapsService.getDirections(origin, `${destinationCoords.latitude},${destinationCoords.longitude}`);
            console.log('Directions fetched:', directions);

            // Extract estimated time in traffic
            const durationInTraffic = directions.routes[0].legs[0].duration_in_traffic.text;
            console.log(`Estimated time in traffic: ${durationInTraffic}`);
            setDurationInTraffic(durationInTraffic);

            // Extract distance
            const distanceText = directions.routes[0].legs[0].distance.text;
            console.log(`Distance: ${distanceText}`);
            setDistance(distanceText);

            // Decode the polyline and update the route
            const points = decodePolyline(directions.routes[0].overview_polyline.points);
            console.log('Decoded polyline points:', points);
            setRouteCoordinates(points);
        } catch (error) {
            console.error('Error fetching route:', error);
        }
    };

    const decodePolyline = (encoded: string) => {
        let points: { latitude: number; longitude: number }[] = [];
        let index = 0, len = encoded.length;
        let lat = 0, lng = 0;

        while (index < len) {
            let b, shift = 0, result = 0;
            do {
                b = encoded.charCodeAt(index++) - 63;
                result |= (b & 0x1f) << shift;
                shift += 5;
            } while (b >= 0x20);
            let dlat = result & 1 ? ~(result >> 1) : result >> 1;
            lat += dlat;

            shift = 0;
            result = 0;
            do {
                b = encoded.charCodeAt(index++) - 63;
                result |= (b & 0x1f) << shift;
                shift += 5;
            } while (b >= 0x20);
            let dlng = result & 1 ? ~(result >> 1) : result >> 1;
            lng += dlng;

            points.push({ latitude: lat / 1e5, longitude: lng / 1e5 });
        }

        return points;
    };

    return (
        <SafeAreaView style={{ flex: 1 }}>
            <StatusBar translucent backgroundColor="#00B14F" barStyle="dark-content" />

            <View className="p-4 bg-primary border-b border-gray-200">
                <View className="flex-row items-center">
                    <TouchableOpacity
                        onPress={() => router.push('/')}
                        className="h-10 w-10 rounded-full items-center bg-green-100 justify-center"
                    >
                        <Feather name="arrow-left" size={24} color="#00B14F" />
                    </TouchableOpacity>

                    <Text className="text-2xl ml-6 font-bold text-accent">Driver</Text>
                </View>
            </View>

            {loading ? (
                <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
                    <Text>Loading map...</Text>
                </View>
            ) : region && apiKey ? (
                <MapView
                    style={{ flex: 1 }}
                    provider={PROVIDER_GOOGLE}
                    region={region}
                    showsUserLocation={true}
                    followsUserLocation={true}
                    userInterfaceStyle='light'
                >
                    {region && (
                        <Marker coordinate={region} title="You are here" />
                    )}
                    <Marker coordinate={destination} title="Mid Valley Megamall" />
                    {routeCoordinates.length > 0 && (
                        <Polyline coordinates={routeCoordinates} strokeWidth={4} strokeColor="blue" />
                    )}
                </MapView>
            ) : (
                <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
                    <Text>Failed to load map. Please try again later.</Text>
                </View>
            )}

            <TouchableOpacity onPress={fetchRoute} style={styles.button}>
                <Text style={styles.buttonText}>Get Directions</Text>
            </TouchableOpacity>

            <BottomSheet snapPoints={snapPoints}>
                <BottomSheetView style={styles.contentContainer}>
                    <Text style={styles.sheetTitle}>Bottom Sheet Content</Text>
                    {durationInTraffic && <Text>Estimated Time: {durationInTraffic}</Text>}
                    {distance && <Text>Distance: {distance}</Text>}
                </BottomSheetView>
            </BottomSheet>
        </SafeAreaView>
    )
}

const styles = StyleSheet.create({
    container: {
        flex: 1,
        padding: 24,
        justifyContent: 'center',
        backgroundColor: 'white',
    },
    title: {
        fontSize: 24,
        fontWeight: 'bold',
        marginBottom: 20,
    },
    contentContainer: {
        flex: 1,
        alignItems: 'center',
        padding: 15,
    },
    sheetTitle: {
        fontSize: 20,
        fontWeight: 'bold',
        marginBottom: 12,
    },
    button: {
        position: 'absolute',
        top: 100,
        left: '50%',
        transform: [{ translateX: -50 }],
        backgroundColor: '#00B14F',
        padding: 10,
        borderRadius: 5,
    },
    buttonText: {
        color: 'white',
        fontWeight: 'bold',
    },
});