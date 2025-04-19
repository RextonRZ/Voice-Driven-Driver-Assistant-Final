import React, { useMemo, useRef, useEffect, useState } from 'react'
import { StatusBar, StyleSheet, Text, TouchableOpacity, View, TouchableWithoutFeedback, Animated, TextStyle } from 'react-native'
import MapView, { Marker, Region, PROVIDER_GOOGLE, Polyline } from 'react-native-maps'
import { SafeAreaView } from 'react-native-safe-area-context'
import { Feather, Ionicons, MaterialIcons } from '@expo/vector-icons'
import BottomSheet, { BottomSheetView } from '@gorhom/bottom-sheet';
import * as Location from 'expo-location'
import { router } from 'expo-router'
import { MapsService } from '../services/mapsService'
import { ScrollView } from 'react-native-gesture-handler'

export default function Driver() {
    const [region, setRegion] = useState<Region | null>(null)
    const [apiKey, setApiKey] = useState<string | null>(null)
    const [messages, setMessages] = useState<string[]>([]);
    const [distance, setDistance] = useState<string | null>(null);
    const [durationInTraffic, setDurationInTraffic] = useState<string | null>(null);
    const [mapType, setMapType] = useState<'standard' | 'satellite' | 'hybrid'>('standard');
    const [routeCoordinates, setRouteCoordinates] = useState<{ latitude: number; longitude: number }[]>([]);
    const [customerCoords, setCustomerCoords] = useState<{ latitude: number; longitude: number } | null>(null);
    const [currentMarker, setCurrentMarker] = useState<{ latitude: number; longitude: number } | null>(null);
    const [destinationMarker, setDestinationMarker] = useState<{ latitude: number; longitude: number } | null>(null);
    const [loading, setLoading] = useState(true)
    const [approve, setApprove] = useState(false);
    const [showTraffic, setShowTraffic] = useState(false);
    const [showModal, setShowModal] = useState(false);
    const [isProcessingPayment, setIsProcessingPayment] = useState(false);
    const [isPowerOn, setIsPowerOn] = useState(false);
    const [showCountdownModal, setShowCountdownModal] = useState(false);
    const [showMessageModal, setShowMessageModal] = useState(false);
    const [showSuccessModal, setShowSuccessModal] = useState(false);
    const [isNavigatingToCustomer, setIsNavigatingToCustomer] = useState(false);
    const [isNavigatingToDestination, setIsNavigatingToDestination] = useState(false);
    const [currentIndex, setCurrentIndex] = useState(0);
    const [animatedIndex, setAnimatedIndex] = useState(0);
    const [countdown, setCountdown] = useState(5);
    const [steps, setSteps] = useState<any[]>([]);
    const [currentStepIndex, setCurrentStepIndex] = useState(0);
    const [nextInstruction, setNextInstruction] = useState<string | null>(null);

    const mapRef = useRef<MapView>(null);
    const bottomSheetRef = useRef<BottomSheet>(null);
    const animatedValue = useRef(new Animated.Value(0)).current;
    const pulseAnim = useRef(new Animated.Value(1)).current;
    const snapPoints = useMemo(() => (approve ? ['18%', '62%'] : ['18%']), [approve]);

    // Utility function to strip HTML tags
    const stripHtml = (html: string): string => {
        // Remove <div> and its content
        html = html.replace(/<div[^>]*>.*?<\/div>/g, '');
        // Remove other HTML tags
        return html.replace(/<[^>]*>/g, '').trim();
    };

    // Format distance to show in meters if less than 1 km
    const formatDistance = (distance: string): string => {
        if (distance.includes('km')) {
            const kmValue = parseFloat(distance);
            if (kmValue < 1) {
                return `${Math.round(kmValue * 1000)} m`; // Convert to meters
            }
            return distance; // Keep as is for 1 km or more
        }
        return distance; // Return as is for other formats
    };

    // Used for the bottom sheet
    useEffect(() => {
        if (!approve) {
            bottomSheetRef.current?.snapToIndex(0); // Collapse to the first snap point
        }
    }, [approve]);

    useEffect(() => {
        console.log('Snap points updated:', snapPoints);
    }, [snapPoints]);

    // Start the pulse animation for loading effects
    useEffect(() => {
        if (loading || isProcessingPayment) {
            Animated.loop(
                Animated.sequence([
                    Animated.timing(pulseAnim, {
                        toValue: 1.2,
                        duration: 800,
                        useNativeDriver: true
                    }),
                    Animated.timing(pulseAnim, {
                        toValue: 1,
                        duration: 800,
                        useNativeDriver: true
                    })
                ])
            ).start();
        } else {
            pulseAnim.setValue(1);
        }
    }, [loading, isProcessingPayment]);

    // Customer details
    const customer =
    {
        name: "Angel Chan",
        rating: "4.5",
        phone: "+6011 9876 5432",
        //origin: "Faculty of Computer Science and Information Technology",
        origin: "Faculty of Science",
        // destination: "Mid Valley Megamall North Court Entrance",
        destination: "Perdana Siswa Complex (KPS)",
        fare: "RM 15.00",
    };

    // Find current user location
    useEffect(() => {
        const setupMap = async () => {
            try {
                let { status } = await Location.requestForegroundPermissionsAsync()
                if (status !== 'granted') {
                    console.error('Permission to access location was denied')
                    setLoading(false)
                    return
                }

                let location = await Location.getCurrentPositionAsync({});
                const userLocation = {
                    latitude: location.coords.latitude,
                    longitude: location.coords.longitude,
                };
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

    // Find the customer origin
    useEffect(() => {
        if (region && apiKey && !isNavigatingToDestination) {
            // Fetch the customer's origin coordinates
            MapsService.getPlaceCoordinates(customer.origin).then((coords) => {
                setDestinationMarker(coords);
            });
        }
    }, [region, apiKey, isNavigatingToDestination]);

    // Animation for the path
    const startAnimation = (length: number) => {
        animatedValue.setValue(0);
        Animated.loop(
            Animated.timing(animatedValue, {
                toValue: length,
                duration: 5000, // 5 seconds for the full animation
                useNativeDriver: false,
            })
        ).start();

        // Use an Animated.event to update the state
        animatedValue.addListener(({ value }) => {
            setAnimatedIndex(Math.floor(value));
        });
    };

    // Decode polyline function
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

    // Modify your showMessageModal function
    const handleShowMessageModal = () => {
        setShowMessageModal(true);
        setCurrentIndex(0); // Reset the bottom sheet index
        bottomSheetRef.current?.snapToIndex(0); // Open the bottom sheet
        // Reset messages when opening the modal
        setMessages([]);
    };

    // Function to close message modal
    const closeMessageModal = () => {
        setShowMessageModal(false);
    };

    // Approve customer button
    const handleApprove = async () => {
        setApprove(true);
        setShowModal(false);
        setIsNavigatingToCustomer(true);

        if (!region) {
            console.warn("No region defined");
            return;
        }

        // Set current marker if not available
        if (currentMarker === null) {
            setCurrentMarker({
                latitude: region.latitude,
                longitude: region.longitude,
            });
        }

        const origin = `${region.latitude},${region.longitude}`;

        try {
            // Get customer coordinates
            const customerCoordsResponse = await MapsService.getPlaceCoordinates(customer.origin);
            if (!customerCoordsResponse || !customerCoordsResponse.latitude || !customerCoordsResponse.longitude) {
                throw new Error("Invalid customer coordinates");
            }

            setCustomerCoords(customerCoordsResponse);
            setDestinationMarker(customerCoordsResponse);

            // Get directions
            const destination = `${customerCoordsResponse.latitude},${customerCoordsResponse.longitude}`;
            const directions = await MapsService.getDirections(origin, destination);

            const route = directions.directions.routes[0];

            const leg = route.legs[0];
            if (!leg || !leg.steps || !Array.isArray(leg.steps)) {
                throw new Error("Invalid leg structure");
            }

            // Process steps
            const steps = leg.steps.map((step: Step) => ({
                ...step,
                plain_instructions: step.html_instructions ? stripHtml(step.html_instructions) : "Continue",
                distance: step.distance || { text: "Unknown distance", value: 0 },
            }));

            setSteps(steps);
            setNextInstruction(steps[0]?.plain_instructions || 'Start navigation');

            // Extract trip info
            if (leg.duration_in_traffic && leg.duration_in_traffic.text) {
                setDurationInTraffic(leg.duration_in_traffic.text);
            }

            if (leg.distance && leg.distance.text) {
                setDistance(leg.distance.text);
            }

            // Process route polyline
            if (route.overview_polyline && route.overview_polyline.points) {
                const points = decodePolyline(route.overview_polyline.points);
                if (Array.isArray(points) && points.length > 0) {
                    setRouteCoordinates(points);
                    startAnimation(points.length);
                } else {
                    console.warn("Decoded polyline has no valid points");
                }
            } else {
                console.warn("No polyline points found in the route");
            }

        } catch (error) {
            console.error('Error fetching route to customer:', error);
            // Consider adding user-facing error handling here
            setIsNavigatingToCustomer(false);
        }
    };

    // Check if the driver is close to the customer
    useEffect(() => {
        if (isNavigatingToCustomer && customerCoords) {
            const interval = setInterval(async () => {
                const location = await Location.getCurrentPositionAsync({});
                const distanceToCustomer = MapsService.calculateDistance(
                    location.coords.latitude,
                    location.coords.longitude,
                    // customerCoords.latitude,
                    3.120864,
                    // customerCoords.longitude,
                    101.655115
                );

                if (distanceToCustomer < 50) {
                    clearInterval(interval);
                    startCountdown();
                }
            }, 2000);

            return () => clearInterval(interval);
        }
    }, [isNavigatingToCustomer, customerCoords]);

    const startCountdown = () => {
        setShowCountdownModal(true); // Show the countdown modal
        let timer = 5; // 5-second countdown
        setCountdown(timer);

        const interval = setInterval(() => {
            timer -= 1;
            setCountdown(timer);

            if (timer === 0) {
                clearInterval(interval);
                setShowCountdownModal(false); // Hide the countdown modal

                navigateToDestination(); // Navigate to the customer's destination
            }
        }, 1000); // 1-second interval
    };

    const navigateToDestination = async () => {
        setIsNavigatingToCustomer(false); // Stop navigating to the customer
        setIsNavigatingToDestination(true);

        const customerCoords = await MapsService.getPlaceCoordinates(customer.origin);
        const destinationCoords = await MapsService.getPlaceCoordinates(customer.destination);

        // Update markers
        setCurrentMarker(customerCoords); // Move "You Are Here" marker to customer's origin
        setDestinationMarker(destinationCoords); // Move destination marker to customer's destination

        try {
            const directions = await MapsService.getDirections(
                `${customerCoords.latitude},${customerCoords.longitude}`,
                `${destinationCoords.latitude},${destinationCoords.longitude}`
            );

            const route = directions.directions.routes[0];

            const leg = route.legs[0];
            if (!leg || !leg.steps || !Array.isArray(leg.steps)) {
                throw new Error("Invalid leg structure");
            }

            // Process steps
            const steps = leg.steps.map((step: Step) => ({
                ...step,
                plain_instructions: step.html_instructions ? stripHtml(step.html_instructions) : "Continue",
                distance: step.distance || { text: "Unknown distance", value: 0 },
            }));

            setSteps(steps);
            setNextInstruction(steps[0]?.plain_instructions || 'Start navigation');

            // Extract trip info
            if (leg.duration_in_traffic && leg.duration_in_traffic.text) {
                setDurationInTraffic(leg.duration_in_traffic.text);
            }

            if (leg.distance && leg.distance.text) {
                setDistance(leg.distance.text);
            }

            // Process route polyline
            if (route.overview_polyline && route.overview_polyline.points) {
                const points = decodePolyline(route.overview_polyline.points);
                if (Array.isArray(points) && points.length > 0) {
                    setRouteCoordinates(points);
                    startAnimation(points.length);
                } else {
                    console.warn("Decoded polyline has no valid points");
                }
            } else {
                console.warn("No polyline points found in the route");
            }

            // Monitor proximity to the destination
            const interval = setInterval(async () => {
                const location = await Location.getCurrentPositionAsync({});
                const distanceToDestination = MapsService.calculateDistance(
                    location.coords.latitude,
                    location.coords.longitude,
                    destinationCoords.latitude,
                    // 3.120864,
                    destinationCoords.longitude,
                    // 101.655115
                );

                if (distanceToDestination < 50) { // Within 50 meters
                    clearInterval(interval);
                    handleDestinationReached(); // Handle destination reached
                }
            }, 2000); // Check every 2 seconds
        } catch (error) {
            console.error('Error fetching route to destination:', error);
        }
    };

    const checkNextStep = (currentLocation: Location.LocationObjectCoords) => {
        if (!steps || currentStepIndex >= steps.length) return;

        const nextStep = steps[currentStepIndex];
        const distanceToNextStep = MapsService.calculateDistance(
            currentLocation.latitude,
            currentLocation.longitude,
            nextStep.end_location.lat,
            nextStep.end_location.lng
        );

        if (distanceToNextStep < 50) { // If close to the next step
            setCurrentStepIndex(currentStepIndex + 1); // Move to the next step
            setNextInstruction(steps[currentStepIndex + 1]?.plain_instructions || ''); // Update the instruction
        }
    };

    useEffect(() => {
        const watchPosition = async () => {
            await Location.watchPositionAsync(
                { accuracy: Location.Accuracy.High, distanceInterval: 10 },
                (location) => {
                    setRegion({
                        latitude: location.coords.latitude,
                        longitude: location.coords.longitude,
                        latitudeDelta: 0.01,
                        longitudeDelta: 0.01,
                    });

                    // Check for the next step in the route
                    checkNextStep(location.coords);
                }
            );
        };

        watchPosition();
    }, [steps, currentStepIndex]);

    const handleDestinationReached = () => {
        // Show the success modal
        setShowSuccessModal(true);

        // Show "Nice driving!" for 5 seconds, then start payment processing
        setTimeout(() => {
            setIsProcessingPayment(true);

            // Simulate payment processing for 10 seconds
            setTimeout(() => {
                setIsProcessingPayment(false);
                setShowSuccessModal(false);

                // Reset all states
                animatedValue.stopAnimation();
                setRouteCoordinates([]);
                setCurrentMarker(null);
                setDestinationMarker(null);
                setApprove(false);
                setCustomerCoords(null);
                setDistance(null);
                setDurationInTraffic(null);
                setSteps([]);
                setCurrentStepIndex(0);
                setNextInstruction(null);
                closeMessageModal();
            }, 10000);
        }, 5000);
    };

    // Header and Bottom Sheet styles
    const headerStyle = {
        backgroundColor: '#00B14F', // Green for light mode
        padding: 16,
    };
    const headerTextStyle: TextStyle = {
        color: '#FFFFFF', // White for light mode
        fontSize: 20,
        fontWeight: 'bold',
    };
    const bottomSheetStyle = {
        backgroundColor: '#FFFFFF', // White for light mode
        borderTopLeftRadius: 20,
        borderTopRightRadius: 20,
    };
    const bottomSheetTextStyle: TextStyle = {
        color: '#000000', // Black for light mode
        fontSize: 16,
        fontWeight: 'bold',
    };

    return (
        <SafeAreaView style={{ flex: 1 }}>
            <StatusBar translucent backgroundColor="#00B14F" barStyle="dark-content" />

            {/* Header */}
            <View style={headerStyle}>
                <View className="flex-row items-center">
                    <TouchableOpacity
                        onPress={() => router.push('/')}
                        className="h-10 w-10 rounded-full items-center bg-green-100 justify-center"
                    >
                        <Feather name="arrow-left" size={24} color="#00B14F" />
                    </TouchableOpacity>

                    <Text style={[headerTextStyle, { marginLeft: 16 }]}>Driver</Text>
                </View>
            </View>

            <TouchableOpacity
                style={{
                    position: 'absolute',
                    top: 116, // Below the header
                    left: 16,
                    backgroundColor: isPowerOn ? '#00B14F' : '#FFFFFF', // Green when on, white when off
                    borderRadius: 25,
                    padding: 10,
                    elevation: 5,
                    shadowColor: '#000',
                    shadowOffset: { width: 0, height: 2 },
                    shadowOpacity: 0.3,
                    shadowRadius: 3,
                    zIndex: 1,
                }}
                onPress={() => {
                    if (region) {
                        setIsPowerOn(!isPowerOn); // Toggle the button state

                        // Only show the modal if turning on the power and navigation/payment is not finished
                        if (!isPowerOn) {
                            if (!approve && !isProcessingPayment) {
                                setTimeout(() => {
                                    setShowModal(true); // Show the modal after a delay
                                }, 2000);
                            }
                        } else {
                            setShowModal(false); // Hide the modal when turning off the power
                        }
                    }
                }}
            >
                <Feather
                    name="power"
                    size={24}
                    color={isPowerOn ? '#FFFFFF' : '#00B14F'} // White when on, green when off
                />
            </TouchableOpacity>

            {/* Container below the header */}
            {approve && steps.length > 0 && (
                <View
                    style={{
                        position: 'absolute',
                        top: 116,
                        left: 16,
                        right: 16,
                        backgroundColor: '#fff',
                        paddingTop: 12,
                        paddingBottom: 16,
                        paddingLeft: 16,
                        paddingRight: 16,
                        borderTopWidth: 1,
                        borderColor: '#ddd',
                        borderRadius: 20,
                        shadowColor: '#000',
                        shadowOffset: { width: 0, height: 2 },
                        shadowOpacity: 0.1,
                        shadowRadius: 4,
                        elevation: 3,
                        zIndex: 2,
                    }}
                >
                    <Text style={{ fontSize: 20, color: '#00b14f', fontWeight: 'bold', textAlign: 'right' }}>
                        {formatDistance(steps[currentStepIndex]?.distance?.text || 'Calculating...')}
                    </Text>

                    <Text style={{ fontSize: 16, fontWeight: 'bold', color: '#333', paddingTop: 4, textAlign: 'justify' }}>
                        {steps[currentStepIndex]?.plain_instructions || 'No instructions available'}
                    </Text>
                </View>
            )}

            {loading ? (
                <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#EAEAEA' }}>
                    <View style={{ justifyContent: 'center', alignItems: 'center' }}>
                        {/* Pulsing Circle */}
                        <Animated.View
                            style={[
                                styles.pulse,
                                {
                                    transform: [{ scale: pulseAnim }], // Apply the pulse animation
                                    opacity: pulseAnim.interpolate({
                                        inputRange: [1, 1.2],
                                        outputRange: [0.6, 0.3], // Fade out as it scales up
                                    }),
                                },
                            ]}
                        />

                        {/* Static Pin */}
                        <View style={styles.pin} />
                    </View>
                    <Text className='text-xl mt-14 font-bold'>Setting things up for you...</Text>
                </View>
            ) : region && apiKey ? (
                <MapView
                    ref={mapRef}
                    style={{ flex: 1 }}
                    provider={PROVIDER_GOOGLE}
                    region={region}
                    showsUserLocation={true}
                    followsUserLocation={true}
                    userInterfaceStyle="light"
                    mapType={mapType}
                    showsTraffic={showTraffic}
                    showsMyLocationButton={false}
                    customMapStyle={lightMapStyle}
                >
                    {/* "You Are Here" Marker */}
                    {currentMarker && approve && (
                        <Marker
                            coordinate={currentMarker}
                            title="You are here"
                            image={require('../assets/images/origin-icon.png')}
                        />
                    )}

                    {/* Destination Marker */}
                    {destinationMarker && approve && (
                        <Marker
                            coordinate={destinationMarker}
                            title="Destination"
                            image={require('../assets/images/destination-icon.png')}
                        />
                    )}

                    {/* Route Polyline */}
                    {routeCoordinates.length > 0 && (
                        <Polyline
                            coordinates={routeCoordinates.slice(0, animatedIndex)}
                            strokeWidth={4}
                            strokeColor="#00b14f"
                        />
                    )}
                </MapView>
            ) : (
                <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center' }}>
                    <Text>Failed to load map. Please try again later.</Text>
                </View>
            )}

            {/* Relocate Button */}
            <TouchableOpacity
                style={[styles.relocateButton]}
                onPress={() => {
                    if (region) {
                        mapRef.current?.animateToRegion(region, 1000); // Animate to user's location
                    }
                }}
            >
                <Feather name="crosshair" size={24} color="#fff" />
            </TouchableOpacity>

            {/* Toggle Map Type */}
            <TouchableOpacity
                style={[styles.toggleButton]}
                onPress={() => setMapType(mapType === 'standard' ? 'hybrid' : 'standard')}
            >
                <MaterialIcons name="satellite-alt" size={24} color="#fff" />
            </TouchableOpacity>

            {/* Toggle Traffic */}
            <TouchableOpacity
                style={[styles.trafficButton]}
                onPress={() => setShowTraffic(!showTraffic)}
            >
                <MaterialIcons name="traffic" size={24} color="#fff" />
            </TouchableOpacity>

            {showModal && !approve && region && (
                <View
                    style={{
                        position: 'absolute',
                        top: 98,
                        bottom: 0,
                        left: 0,
                        right: 0,
                        backgroundColor: 'rgba(0,0,0,0.5)',
                        justifyContent: 'space-evenly',
                        alignItems: 'center',
                        padding: 16,
                    }}
                >
                    <View
                        style={{
                            position: 'absolute',
                            backgroundColor: 'white',
                            borderRadius: 12,
                            bottom: '30%',
                            shadowColor: '#000',
                            shadowOffset: { width: 0, height: 2 },
                            shadowOpacity: 0.25,
                            shadowRadius: 3.84,
                            elevation: 5,
                            width: '100%',
                            maxWidth: 400,
                        }}
                    >
                        <View style={{ padding: 16, borderBottomWidth: 1, borderColor: '#ddd', flexDirection: 'row', alignItems: 'center' }}>
                            <Text style={{ fontSize: 18, fontWeight: 'bold', color: '#333' }}>
                                New Ride Request
                            </Text>
                        </View>

                        <View className="p-4">
                            <View className="flex-row items-center mb-3">
                                <View className="h-10 w-10 bg-slate-100 rounded-full items-center justify-center mr-3">
                                    <Feather name="user" size={18} color="000000" />
                                </View>
                                <View>
                                    <Text className="font-medium text-gray-800">{customer.name}</Text>
                                    <View className="flex-row items-center">
                                        <Feather name="star" size={12} color="#f59e0b" />
                                        <Text className="text-gray-600 ml-1 text-sm">{customer.rating}</Text>
                                    </View>
                                </View>
                            </View>

                            <View className="flex-row items-center mb-3">
                                <View className="h-10 w-10 bg-blue-50 rounded-full items-center justify-center mr-3">
                                    <Feather name="play-circle" size={18} color="#1595E6" />
                                </View>
                                <View className='pr-10'>
                                    <Text className="font-medium text-gray-800 max-w-fit text-ellipsis">{customer.origin}</Text>
                                </View>
                            </View>

                            <View className="flex-row items-center mb-3">
                                <View className="h-10 w-10 bg-red-100 rounded-full items-center justify-center mr-3">
                                    <Feather name="map-pin" size={18} color="#ef4444" />
                                </View>
                                <View className='pr-10'>
                                    <Text className="font-medium text-gray-800 max-w-fit text-ellipsis">{customer.destination}</Text>
                                </View>
                            </View>

                            <View className="flex-row items-center mb-3">
                                <View className="h-10 w-10 bg-green-100 rounded-full items-center justify-center mr-3">
                                    <Feather name="dollar-sign" size={18} color="#00B14F" />
                                </View>
                                <Text className="text-gray-800">{customer.fare}</Text>
                            </View>

                            <View style={{ flexDirection: 'row', marginTop: 16 }}>
                                <TouchableOpacity
                                    style={{
                                        flex: 1,
                                        backgroundColor: '#ddd',
                                        padding: 12,
                                        borderRadius: 8,
                                        alignItems: 'center',
                                        marginRight: 8,
                                    }}
                                    onPress={() => {
                                        animatedValue.stopAnimation();
                                        setRouteCoordinates([]);

                                        setCurrentMarker(null);
                                        setDestinationMarker(null);

                                        setApprove(false)
                                        setShowModal(false);
                                    }}
                                >
                                    <Text style={{ color: '#333', fontWeight: 'bold' }}>Decline</Text>
                                </TouchableOpacity>

                                <TouchableOpacity
                                    style={{
                                        flex: 1,
                                        backgroundColor: '#00B14F',
                                        padding: 12,
                                        borderRadius: 8,
                                        alignItems: 'center',
                                    }}
                                    onPress={handleApprove} // Approve and navigate to customer
                                >
                                    <Text style={{ color: 'white', fontWeight: 'bold' }}>Approve</Text>
                                </TouchableOpacity>
                            </View>
                        </View>
                    </View>
                </View>

            )
            }

            {
                showCountdownModal && (
                    <View
                        style={{
                            position: 'absolute',
                            top: 0,
                            bottom: 0,
                            left: 0,
                            right: 0,
                            backgroundColor: 'rgba(0,0,0,0.5)',
                            justifyContent: 'center',
                            alignItems: 'center',
                            zIndex: 3
                        }}
                    >
                        <View
                            style={{
                                backgroundColor: 'white',
                                borderRadius: 12,
                                padding: 24,
                                alignItems: 'center',
                                shadowColor: '#000',
                                shadowOffset: { width: 0, height: 2 },
                                shadowOpacity: 0.25,
                                shadowRadius: 3.84,
                                elevation: 5,
                            }}
                        >
                            <Text style={{ fontSize: 16, fontWeight: 'bold', color: '#333', marginBottom: 8 }}>
                                You've reached the customer!
                            </Text>

                            <Animated.View
                                style={{
                                    marginBottom: 16,
                                    transform: [
                                        {
                                            rotate: animatedValue.interpolate({
                                                inputRange: [0, 1],
                                                outputRange: ['0deg', '360deg'],
                                            }),
                                        },
                                    ],
                                }}
                            >
                                <Feather name="clock" size={48} color="#00B14F" />
                            </Animated.View>
                            <Text style={{ fontSize: 16, color: '#333', marginBottom: 8 }}>
                                Rerouting in {countdown}...
                            </Text>
                        </View>
                    </View>
                )
            }

            {/* Message Modal */}
            {showMessageModal && (
                <View
                    style={{
                        position: 'absolute',
                        top: 98, // Position below the header
                        bottom: 0,
                        left: 0,
                        right: 0,
                        backgroundColor: 'rgba(0,0,0,0.5)',
                        justifyContent: 'flex-start',
                        alignItems: 'center',
                        padding: 16,
                        zIndex: 3
                    }}
                >
                    <View
                        style={{
                            backgroundColor: 'white',
                            borderRadius: 12,
                            shadowColor: "#000",
                            shadowOffset: { width: 0, height: 2 },
                            shadowOpacity: 0.25,
                            shadowRadius: 3.84,
                            elevation: 5,
                            width: '100%',
                            maxWidth: 400,
                            height: '70%',
                        }}
                    >
                        {/* Modal Header */}
                        <View className="p-4 border-b border-gray-100 flex-row justify-between items-center">
                            <View className="flex-row items-center">
                                <View className="h-10 w-10 bg-green-100 rounded-full items-center justify-center mr-3">
                                    <Feather name="user" size={18} color="#00B14F" />
                                </View>
                                <Text className="font-bold text-lg text-gray-800">{customer.name}</Text>
                            </View>
                            <TouchableOpacity
                                className="h-10 w-10 rounded-full items-center justify-center"
                                onPress={closeMessageModal}
                            >
                                <Feather name="x" size={24} color="#6b7280" />
                            </TouchableOpacity>
                        </View>

                        {/* Messages Container */}
                        <ScrollView
                            className="flex-1 p-4"
                            contentContainerStyle={{ flexGrow: 1 }}
                        >

                            <View className="flex-1 items-center justify-center">
                                <Text className="text-gray-500 text-center">Start your conversation with {customer.name}</Text>
                            </View>

                        </ScrollView>

                        {/* Message Input */}
                        <View className="p-3 border-t border-gray-100 flex-row justify-between">
                            <View className="flex-row w-10/12 rounded-full border border-accent bg-gray-100 px-4 py-2">
                                <Text className="text-gray-500">Send a message...</Text>
                            </View>
                            <TouchableOpacity
                                className="h-10 w-10 bg-green-50 rounded-full items-center justify-center mr-2"
                            // onPress={sendMessage}
                            // disabled={isSending}
                            >
                                <Feather name="send" size={18} color="#00B14F"></Feather>
                            </TouchableOpacity>
                        </View>
                    </View>
                </View>
            )}

            {showSuccessModal && (
                <View
                    style={{
                        position: 'absolute',
                        top: 0,
                        bottom: 0,
                        left: 0,
                        right: 0,
                        backgroundColor: 'rgba(0,0,0,0.5)',
                        justifyContent: 'center',
                        alignItems: 'center',
                        zIndex: 3
                    }}
                >
                    <View
                        style={{
                            backgroundColor: 'white',
                            borderRadius: 12,
                            padding: 24,
                            alignItems: 'center',
                            shadowColor: '#000',
                            shadowOffset: { width: 0, height: 2 },
                            shadowOpacity: 0.25,
                            shadowRadius: 3.84,
                            elevation: 5,
                        }}
                    >
                        {isProcessingPayment ? (
                            <>
                                <View className='pt-6 h-20'>
                                    <View style={{ justifyContent: 'center', alignItems: 'center' }}>
                                        {/* Pulsing Circle */}
                                        <Animated.View
                                            style={[
                                                styles.pulse,
                                                {
                                                    transform: [{ scale: pulseAnim }], // Apply the pulse animation
                                                    opacity: pulseAnim.interpolate({
                                                        inputRange: [1, 1.2],
                                                        outputRange: [0.6, 0.3], // Fade out as it scales up
                                                    }),
                                                },
                                            ]}
                                        />

                                        {/* Static Pin */}
                                        <View style={styles.pin} />
                                    </View>
                                </View>
                                <Text
                                    style={{
                                        fontSize: 18,
                                        fontWeight: 'bold',
                                        color: '#333',
                                        textAlign: 'center',
                                        marginTop: 8,
                                    }}
                                >
                                    Processing payment...
                                </Text>
                            </>
                        ) : (
                            <>
                                <Feather name="check-circle" size={48} color="#00B14F" />
                                <Text
                                    style={{
                                        fontSize: 18,
                                        fontWeight: 'bold',
                                        color: '#333',
                                        textAlign: 'center',
                                        marginTop: 8,
                                    }}
                                >
                                    You have reached {customer.destination}!
                                </Text>
                            </>
                        )}
                    </View>
                </View>
            )}

            <BottomSheet
                snapPoints={snapPoints}
                enablePanDownToClose={false}
                index={0}
                onAnimate={(fromIndex, toIndex) => {
                    if (!approve && toIndex !== 0) {
                        bottomSheetRef.current?.snapToIndex(0); // Force collapse
                    }
                }}
                onChange={(index) => {
                    setCurrentIndex(index); // Update the current index
                }}
                ref={bottomSheetRef}
                handleIndicatorStyle={{
                    width: 35,
                    height: 4.5,
                    backgroundColor: '#D3D3D3',
                    borderRadius: 3,
                }}
                backgroundStyle={bottomSheetStyle}>

                <TouchableWithoutFeedback
                    onPress={() => {
                        // Toggle between the first and second snap points
                        if (approve) {
                            const nextIndex = currentIndex === 0 ? 1 : 0;
                            bottomSheetRef.current?.snapToIndex(nextIndex);
                        }
                    }}
                >
                    <BottomSheetView style={{
                        flex: 1,
                        alignItems: 'center',
                        padding: 15,
                        backgroundColor: '#FFFFFF', // White for light mode
                        borderTopLeftRadius: 20,
                        borderTopRightRadius: 20
                    }}>
                        {/* 18% View */}
                        {!approve ? (
                            <>
                                <View className="pt-2 flex-row justify-center">
                                    <Ionicons name="car-sport-outline" size={48} color="#00B14F" />
                                </View>
                                <View className="pt-1 flex-row justify-center">
                                    <Text className="text-1xl font-bold text-primary">Let's ride!</Text>
                                </View>
                            </>
                        ) : (
                            <>
                                <View className="flex-row justify-between w-full px-5">
                                    <Text className="text-xl font-bold text-gray-800">
                                        {isNavigatingToCustomer
                                            ? `Pick up at ${customer.origin}`
                                            : `Drop off at ${customer.destination}`}
                                    </Text>
                                </View>
                                <View className="pt-3 flex-row justify-between w-full px-5">
                                    <Text className="text-m text-gray-600">
                                        Arriving in: {durationInTraffic || 'Calculating...'}
                                    </Text>
                                    <Text className="text-m text-gray-600">
                                        Distance: {formatDistance(distance ? distance : '0m') || 'Calculating...'}
                                    </Text>
                                </View>
                            </>
                        )}

                        {/* 62% View */}
                        {approve && (
                            <View className="pt-6 w-full">
                                <View
                                    style={{
                                        height: 1,
                                        backgroundColor: '#ddd',
                                        marginVertical: 8,
                                        width: '100%',
                                    }}
                                />
                                <View className='p-2 flex-row items-center'>
                                    <Text className="font-bold text-lg text-gray-800">Customer Details</Text>
                                </View>
                                <View
                                    style={{
                                        backgroundColor: 'white',
                                        borderWidth: 1,
                                        borderColor: '#ddd',
                                        borderRadius: 12,
                                        padding: 16,
                                        shadowColor: '#000',
                                        shadowOffset: { width: 0, height: 2 },
                                        shadowOpacity: 0.1,
                                        shadowRadius: 4,
                                        flexDirection: 'row',
                                        alignItems: 'center',
                                        marginVertical: 8, // Add spacing around the container
                                    }}
                                >
                                    <View className="h-12 w-12 bg-green-100 rounded-full items-center justify-center mr-3">
                                        <Feather name="user" size={24} color="#00B14F" />
                                    </View>
                                    <View className="flex-1">
                                        <View className="flex-row items-center">
                                            <Text className="font-bold text-lg text-gray-800">{customer.name}</Text>
                                            <View className="flex-row items-center ml-2">
                                                <Feather name="star" size={14} color="#f59e0b" />
                                                <Text className="text-gray-600 ml-1">{customer.rating}</Text>
                                            </View>
                                        </View>
                                    </View>

                                    <TouchableOpacity
                                        className="h-10 w-10 bg-green-50 rounded-full items-center justify-center">
                                        <Feather name="phone" size={18} color="#00B14F" />
                                    </TouchableOpacity>

                                    <View className="ml-2" />

                                    <TouchableOpacity
                                        className="h-10 w-10 bg-green-50 rounded-full items-center justify-center"
                                        onPress={handleShowMessageModal}>
                                        <Feather name="message-square" size={18} color="#00B14F" />
                                    </TouchableOpacity>
                                </View>

                                <View className="pt-16 flex-row justify-center">
                                    <Ionicons name="car-sport-outline" size={48} color="#00B14F" />
                                </View>
                                <View className="pt-1 flex-row justify-center">
                                    <Text className="text-1xl font-bold text-primary">Focus on driving!</Text>
                                </View>
                            </View>
                        )}
                    </BottomSheetView>
                </TouchableWithoutFeedback>
            </BottomSheet>
        </SafeAreaView >
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
    sheetTitle: {
        fontSize: 20,
        fontWeight: 'bold',
        marginBottom: 12,
        color: '#FFFFFF',
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
    originMarker: {
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#E6F4EA',
        borderRadius: 20,
        padding: 5,
    },
    destinationMarker: {
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#FDE6E6',
        borderRadius: 20,
        padding: 5,
    },
    relocateButton: {
        position: 'absolute',
        bottom: 170,
        left: 15,
        backgroundColor: '#00B14F',
        borderRadius: 25,
        padding: 10,
        elevation: 5,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.3,
        shadowRadius: 3,
    },
    toggleButton: {
        position: 'absolute',
        bottom: 280,
        left: 15,
        backgroundColor: '#00B14F',
        borderRadius: 25,
        padding: 10,
        elevation: 5,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.3,
        shadowRadius: 3,
    },
    trafficButton: {
        position: 'absolute',
        bottom: 225,
        left: 15,
        backgroundColor: '#00B14F',
        borderRadius: 25,
        padding: 10,
        elevation: 5,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.3,
        shadowRadius: 3,
    },
    toggleButtonText: {
        color: '#333',
        fontWeight: 'bold',
    },
    pulse: {
        position: 'absolute',
        height: 80,
        width: 80,
        borderRadius: 40,
        backgroundColor: '#00A651', // grab green
    },
    pin: {
        height: 20,
        width: 20,
        backgroundColor: 'white',
        borderRadius: 10,
        elevation: 3,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.2,
        shadowRadius: 1.5,
    },
});

// Map Styles
const lightMapStyle = [
    {
        elementType: 'geometry',
        stylers: [{ color: '#f5f5f5' }],
    },
    {
        elementType: 'labels.text.fill',
        stylers: [{ color: '#616161' }],
    },
    {
        elementType: 'labels.text.stroke',
        stylers: [{ color: '#f5f5f5' }],
    },
    {
        featureType: 'road',
        elementType: 'geometry',
        stylers: [{ color: '#ffffff' }],
    },
    {
        featureType: 'water',
        elementType: 'geometry',
        stylers: [{ color: '#a2daf2' }],
    },
    {
        featureType: 'water',
        elementType: 'labels.text.fill',
        stylers: [{ color: '#blue' }],
    },
    {
        featureType: 'administrative.country',
        elementType: 'geometry.stroke',
        stylers: [{ color: '#CCCCCCC' }, { weight: 1.5 }],
    },
    {
        featureType: 'administrative.province',
        elementType: 'geometry.stroke',
        stylers: [{ color: '#CCCCCCC' }, { weight: 1 }],
    },
    {
        featureType: 'landscape.natural.landcover',
        elementType: 'geometry.fill',
        stylers: [{ color: '#EAEAEA' }],
    },
];

type Step = {
    html_instructions: string;
    distance: {
        text: string;
        value: number;
    };
    duration: {
        text: string;
        value: number;
    };
    start_location: {
        lat: number;
        lng: number;
    };
    end_location: {
        lat: number;
        lng: number;
    };
    polyline: {
        points: string;
    };
};