import { StatusBar, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import React from 'react'
import {Feather, Ionicons} from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context'
import { router } from 'expo-router'

export default function Driver() {
    return (
        <SafeAreaView>
            <StatusBar translucent backgroundColor="#00B14F" barStyle="dark-content" />

            <View className="p-4 bg-primary border-b border-gray-200 flex-row justify-between items-center">
                {/* Back button + Title group */}
                <View className="flex-row items-center">
                    <TouchableOpacity
                        onPress={() => router.push('/')}
                        className="h-10 w-10 rounded-full items-center bg-green-100 justify-center"
                    >
                        <Feather name="arrow-left" size={24} color="#00B14F"/>
                    </TouchableOpacity>

                    <Text className="text-2xl ml-6 font-bold text-accent">Driver</Text>
                </View>

                {/* Mic button */}
                <TouchableOpacity
                    className="h-10 w-10 bg-green-100 rounded-full items-center justify-center"
                >
                    <Feather name="mic" size={20} color="#00B14F"/>
                </TouchableOpacity>
            </View>
        </SafeAreaView>
    )
}

const styles = StyleSheet.create({})