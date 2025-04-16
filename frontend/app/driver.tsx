import React, { useCallback, useMemo, useRef, useEffect } from 'react'
import { Button, StatusBar, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import MapView, { Marker, Region, PROVIDER_GOOGLE } from 'react-native-maps'
import { SafeAreaView } from 'react-native-safe-area-context'
import { Feather } from '@expo/vector-icons'
import BottomSheet, { BottomSheetView } from '@gorhom/bottom-sheet';
import * as Location from 'expo-location'
import { router } from 'expo-router'
import { MapsService } from '../services/mapsService'

export default function Driver() {
    const [region, setRegion] = React.useState<Region | null>(null)
    const [apiKey, setApiKey] = React.useState<string | null>(null)
    const [loading, setLoading] = React.useState(true)
    const snapPoints = useMemo(() =>['10%', '50%', '90%'], []);

    const handleSheetChanges = useCallback((index: number) => {
        console.log('Bottom sheet index:', index)
    }, [])

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
                    initialRegion={region}
                    showsUserLocation={true}
                    followsUserLocation={true}
                >
                    <Marker
                        coordinate={{
                            latitude: region.latitude,
                            longitude: region.longitude,
                        }}
                        title="You are here"
                    />
                </MapView>
            ) : (
                <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
                    <Text>Failed to load map. Please try again later.</Text>
                </View>
            )}

            <BottomSheet snapPoints={snapPoints}>
                <BottomSheetView style={styles.contentContainer}>
                    <Text style={styles.sheetTitle}>Bottom Sheet Content</Text>
                    <Text>Here you can add your content</Text>
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
});