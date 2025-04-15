import { GOOGLE_MAPS_API_KEY } from '@env'
import { StatusBar, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import React from 'react'
import { useEffect, useState } from 'react'
import { Feather } from '@expo/vector-icons'
import MapView, { Marker, Region } from 'react-native-maps'
import { SafeAreaView } from 'react-native-safe-area-context'
import * as Location from 'expo-location'
import { router } from 'expo-router'

export default function Driver() {
    const [region, setRegion] = useState<Region | null>(null)

    useEffect(() => {
        (async () => {
            let { status } = await Location.requestForegroundPermissionsAsync()
            if (status !== 'granted') {
                console.error('Permission to access location was denied')
                return
            }

            let location = await Location.getCurrentPositionAsync({})
            setRegion({
                latitude: location.coords.latitude,
                longitude: location.coords.longitude,
                latitudeDelta: 0.01,
                longitudeDelta: 0.01,
            })
        })()
    }, [])

    return (
        <SafeAreaView style={{ flex: 1 }}>
            <StatusBar translucent backgroundColor="#00B14F" barStyle="dark-content" />

            <View className="p-4 bg-primary border-b border-gray-200 flex-row justify-between items-center">
                {/* Back button + Title group */}
                <View className="flex-row items-center">
                    <TouchableOpacity
                        onPress={() => router.push('/')}
                        className="h-10 w-10 rounded-full items-center bg-green-100 justify-center"
                    >
                        <Feather name="arrow-left" size={24} color="#00B14F" />
                    </TouchableOpacity>

                    <Text className="text-2xl ml-6 font-bold text-accent">Driver</Text>
                </View>

                {/* Mic button */}
                <TouchableOpacity
                    className="h-10 w-10 bg-green-100 rounded-full items-center justify-center"
                >
                    <Feather name="mic" size={20} color="#00B14F" />
                </TouchableOpacity>
            </View>

            {/* Google Maps */}
            {region ? (
                <MapView
                    style={{ flex: 1 }}
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
                <Text style={{ flex: 1, textAlign: 'center', marginTop: 20 }}>Loading map...</Text>
            )}
        </SafeAreaView>
    )
}

const styles = StyleSheet.create({})