import React, { useCallback, useMemo, useRef, useEffect, useState } from 'react'
import { Button, StatusBar, StyleSheet, Text, TouchableOpacity, View, TouchableWithoutFeedback, Animated, TextStyle, FlatList, Alert } from 'react-native'
import MapView, { Marker, Region, PROVIDER_GOOGLE, Polyline } from 'react-native-maps'
import { SafeAreaView } from 'react-native-safe-area-context'
import { Feather, FontAwesome5, Ionicons, MaterialIcons } from '@expo/vector-icons'
import BottomSheet, { BottomSheetView } from '@gorhom/bottom-sheet';
import * as Location from 'expo-location'
import { router } from 'expo-router'
import { MapsService } from '../services/mapsService'
import { ScrollView } from 'react-native-gesture-handler'
import { Audio } from 'expo-av'
import * as FileSystem from 'expo-file-system'

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
    const opacityAnimation = useRef(new Animated.Value(0.6)).current;
    const snapPoints = useMemo(() => ['18%', '62%'], []);

    const [showVoiceModal, setShowVoiceModal] = useState(false);
    const chatBubbleOpacity = useRef(new Animated.Value(0)).current;
    const [recording, setRecording] = useState<Audio.Recording | null>(null);
    const [isRecording, setIsRecording] = useState(false);
    const [audioUri, setAudioUri] = useState<string | null>(null);
    const [recordings, setRecordings] = useState<{ uri: string, filename: string, date: Date }[]>([]);
    const [showRecordingsModal, setShowRecordingsModal] = useState(false);
    const [playingAudio, setPlayingAudio] = useState<Audio.Sound | null>(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [apiResponse, setApiResponse] = useState<string | null>(null);
    const [isProcessing, setIsProcessing] = useState(false);
    const [sessionId] = useState(`driver-session-${Date.now()}`);
    const [listeningStatus, setListeningStatus] = useState<'idle' | 'listening' | 'processing'>('idle');
    const [userQuery, setUserQuery] = useState<string | null>(null);
    const [dots, setDots] = useState<string>('');
    const [isSmartRecording, setIsSmartRecording] = useState(false);
    const [silenceDetectionTimer, setSilenceDetectionTimer] = useState<NodeJS.Timeout | null>(null);
    const [chunkRecording, setChunkRecording] = useState<Audio.Recording | null>(null);
    const [hasDetectedSpeech, setHasDetectedSpeech] = useState(false);
    const [silenceCounter, setSilenceCounter] = useState(0);

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

    useEffect(() => {
        const getAudioPermissions = async () => {
            try {
                const { status } = await Audio.requestPermissionsAsync();
                if (status !== 'granted') {
                    console.error('Permission to access audio was denied');
                }
            } catch (error) {
                console.error('Error requesting audio permissions:', error);
            }
        };

        getAudioPermissions();
    }, []);

    // Customer details
    const customer =
    {
        name: "Angel Chan",
        rating: "4.5",
        phone: "+6011 9876 5432",
        //origin: "Faculty of Computer Science and Information Technology",
        origin: "Tun Ahmad Zaidi Residential College",
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

    const testBackendConnection = async () => {
        try {
            const response = await fetch('http://172.20.10.8:8000/', { method: 'GET' });
            if (!response.ok) {
                throw new Error(`Backend responded with status ${response.status}`);
            }
            console.log('Backend is reachable');
        } catch (error) {
            console.error('Error connecting to backend:', error);
        }
    };

    useEffect(() => {
        testBackendConnection();
    }, []);

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

    const handleShowMessageModal = () => {
        setShowMessageModal(true);
        setCurrentIndex(0);
        bottomSheetRef.current?.snapToIndex(0);
        setMessages([]);
    };

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
                    customerCoords.latitude,
                    // 3.120864,
                    customerCoords.longitude,
                    // 101.655115
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
                    // destinationCoords.latitude,
                    3.120864,
                    // destinationCoords.longitude,
                    101.655115
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

    const playOutputAudio = async (audioPath: string) => {
        try {
            console.log('Playing output audio from path:', audioPath);
            
            // Construct the full URL to the audio file
            const audioUrl = `http://172.20.10.3:8000${audioPath}`;
            console.log('Full audio URL:', audioUrl);
            
            // Create and play the sound
            const { sound } = await Audio.Sound.createAsync({ uri: audioUrl });
            await sound.playAsync();
            
            sound.setOnPlaybackStatusUpdate((status) => {
                if (status.isLoaded && status.didJustFinish) {
                    console.log('Audio playback finished');
                    sound.unloadAsync();
                }
            });
        } catch (error) {
            console.error('Error playing output audio:', error);
        }
    };

    const sendAudioToAPI = async (audioUri: string) => {
        try {
            console.log('Sending audio to API:', audioUri);
            setIsProcessing(true);
            setListeningStatus('processing');
            setApiResponse(null);

            const fileInfo = await FileSystem.getInfoAsync(audioUri);
            if (!fileInfo.exists) {
                console.error("Audio file doesn't exist at URI:", audioUri);
                setApiResponse("Error: Audio file not found.");
                setIsProcessing(false);
                setListeningStatus('idle');
                return;
            }

            console.log(`Audio file size: ${fileInfo.size} bytes`);
            
            const requestSessionId = `driver-session-${Date.now()}`;
            
            const formData = new FormData();
            formData.append('session_id', requestSessionId);

            const fileExtension = audioUri.split('.').pop() || 'm4a';
            console.log(`File extension detected: ${fileExtension}`);
            
            const fileName = `recording_${Date.now()}.${fileExtension}`;
            
            formData.append('audio_data', {
                uri: audioUri,
                name: fileName,
                type: `audio/${fileExtension === 'wav' ? 'wav' : 'x-m4a'}`,
            } as any);

            if (region) {
                formData.append('current_location', JSON.stringify({
                    lat: region.latitude,
                    lon: region.longitude
                }));
            }

            if (approve && customerCoords) {
                formData.append('order_context', JSON.stringify({
                    passenger_name: customer.name,
                    passenger_pickup_address: customer.origin,
                    passenger_destination_address: customer.destination,
                    ride_in_progress: true,
                    is_navigating_to_customer: isNavigatingToCustomer
                }));
            }

            console.log("Sending request to backend with session ID:", requestSessionId);
            
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 30000);

            try {
                const response = await fetch('http://172.20.10.3:8000/assistant/interact', {
                    method: 'POST',
                    body: formData,
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                
                console.log(`API response status: ${response.status}`);
                
                if (!response.ok) {
                    const errorText = await response.text();
                    console.error(`API error (${response.status}):`, errorText);
                    throw new Error(`API responded with status ${response.status}: ${errorText}`);
                }
                
                try {
                    const data = await response.json();
                    console.log("API response data:", data);
                    
                    if (data.request_transcription) {
                        setUserQuery(data.request_transcription);
                    }
                    
                    setApiResponse(data.response_text || "No response from assistant.");
                    
                    // Play the audio if available
                    if (data.audio_file_path) {
                        console.log('Audio file path received:', data.audio_file_path);
                        await playOutputAudio(data.audio_file_path);
                    }
                    
                    showChatBubbleWithTimeout(8000);
                    
                } catch (jsonError) {
                    console.error("Failed to parse JSON response:", jsonError);
                    setApiResponse("Received response but couldn't parse it.");
                }
                
            } catch (fetchError: any) {
                clearTimeout(timeoutId);
                
                if (fetchError.name === 'AbortError') {
                    console.error('Request timed out');
                    setApiResponse("Request timed out. Please try again.");
                } else {
                    console.error('Network error during fetch:', fetchError);
                    setApiResponse("Network error. Please check your connection.");
                }
            }
        } catch (error: any) {
            console.error('Error in sendAudioToAPI:', error);
            setApiResponse(`Error: ${error.message || "Unknown error occurred"}`);
        } finally {
            setIsProcessing(false);
            setListeningStatus('idle');
        }
    };

    const detectSpeechInAudio = async (audioUri: string): Promise<boolean> => {
        try {
            const base64Audio = await FileSystem.readAsStringAsync(audioUri, { 
                encoding: FileSystem.EncodingType.Base64 
            });
            
            console.log(`Sending audio chunk for speech detection, size: ${base64Audio.length} characters`);
            
            const response = await fetch('http://172.20.10.3:8000/assistant/detect-speech', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: sessionId,
                    audio_data: base64Audio,
                }),
            });
            
            if (!response.ok) {
                console.error(`Speech detection API returned status ${response.status}`);
                return true;
            }
            
            const result = await response.json();
            console.log(`Speech detection result: ${result.speech_detected}`);
            return result.speech_detected;
            
        } catch (error) {
            console.error('Error detecting speech:', error);
            return true;
        }
    };

    const checkForSpeech = async () => {
        try {
            if (!isRecording || !recording) {
                console.log('Recording stopped, aborting speech detection');
                return;
            }
            
            console.log('Creating chunk recording for speech detection...');
            const { recording: newChunkRecording } = await Audio.Recording.createAsync(
                Audio.RecordingOptionsPresets.HIGH_QUALITY
            );
            setChunkRecording(newChunkRecording);
            
            // Record for about 3 seconds before checking
        const timer = setTimeout(async () => {
            try {
                if (!isRecording) {
                    console.log('Main recording stopped, aborting chunk processing');
                    if (newChunkRecording) {
                        await newChunkRecording.stopAndUnloadAsync().catch(e => console.log('Error stopping chunk:', e));
                    }
                    return;
                }
                
                // Stop the chunk recording
                await newChunkRecording.stopAndUnloadAsync();
                const chunkUri = newChunkRecording.getURI();
                
                if (!chunkUri) {
                    console.error('Failed to get URI for chunk recording');
                    checkForSpeech(); // Try again
                    return;
                }
                
                // Read the audio file as base64
                try {
                    const base64Audio = await FileSystem.readAsStringAsync(chunkUri, { 
                        encoding: FileSystem.EncodingType.Base64 
                    });
                    
                    console.log(`Sending audio chunk for speech detection, size: ${base64Audio.length} characters`);
                    
                    // Send to backend for speech detection
                    const response = await fetch('http://172.20.10.3:8000/assistant/detect-speech', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            session_id: sessionId,
                            audio_data: base64Audio,
                        }),
                    });
                    
                    if (!response.ok) {
                        console.error(`Speech detection API returned status ${response.status}`);
                        // On error, assume speech detected to avoid premature stopping
                        setSilenceCounter(0);
                        checkForSpeech(); // Continue checking
                        return;
                    }
                    
                    const result = await response.json();
                    console.log(`Speech detection result: ${result.speech_detected}`);
                    
                    if (result.speech_detected) {
                        console.log('✓ Speech detected, continuing recording...');
                        setHasDetectedSpeech(true); // Mark that speech has been detected at some point
                        setSilenceCounter(0); // Reset silence counter when speech is detected
                        checkForSpeech(); // Continue checking
                    } else {
                        console.log('✗ No speech detected in this chunk');
                        
                        if (!hasDetectedSpeech) {
                            console.log('No speech detected yet in entire recording, waiting for speech...');
                            checkForSpeech(); // Continue checking
                            return;
                        }
                        
                        // Speech was detected earlier, now increment silence counter
                        const newSilenceCount = silenceCounter + 1;
                        console.log(`SILENCE COUNTER: ${newSilenceCount}/2`);
                        setSilenceCounter(newSilenceCount);
                        
                        if (newSilenceCount >= 2) {
                            console.log('🛑 SILENCE THRESHOLD REACHED: 2 consecutive silent chunks detected');
                            console.log('Auto-stopping recording...');
                            
                            // Update UI immediately to show recording has stopped
                            setIsRecording(false); 
                            
                            // Then call stopRecording to handle the actual stopping and processing
                            stopRecording();
                        } else {
                            console.log(`Silence detected (${newSilenceCount}/2), continuing recording...`);
                            checkForSpeech(); // Continue checking
                        }
                    }
                    
                } catch (error) {
                    console.error('Error processing audio chunk:', error);
                    // On error, assume speech detected to avoid premature stopping
                    checkForSpeech();
                }
                
            } catch (error) {
                console.error('Error in chunk recording processing:', error);
                if (isRecording) {
                    checkForSpeech(); // Try again if still recording
                }
            }
        }, 3000); // 3-second chunks
        
        setSilenceDetectionTimer(timer);
        
    } catch (error) {
        console.error('Error starting chunk recording:', error);
        if (isRecording) {
            checkForSpeech(); // Try again if still recording
        }
    }
};

    const cleanupRecording = () => {
        if (silenceDetectionTimer) {
            clearTimeout(silenceDetectionTimer);
            setSilenceDetectionTimer(null);
        }
        
        if (chunkRecording) {
            chunkRecording.stopAndUnloadAsync().catch(err => {
                console.log('Error stopping chunk recording:', err);
            });
            setChunkRecording(null);
        }
        
        setIsSmartRecording(false);
        setIsRecording(false);
        setHasDetectedSpeech(false);
        setSilenceCounter(0);
    };

    const getChatBubbleMessage = () => {
        if (listeningStatus === 'listening') {
            return `Listening${dots}`;
        } else if (listeningStatus === 'processing' && userQuery) {
            return `"${userQuery}"`;
        } else if (listeningStatus === 'processing') {
            return `Processing${dots}`;
        } else {
            return apiResponse || "How can I help?";
        }
    };

    useEffect(() => {
        let dotInterval: NodeJS.Timeout;
        
        if (listeningStatus === 'listening' || listeningStatus === 'processing') {
            dotInterval = setInterval(() => {
                setDots(prev => {
                    if (prev.length >= 3) return '';
                    return prev + '.';
                });
            }, 500);
        }
        
        return () => {
            if (dotInterval) clearInterval(dotInterval);
        };
    }, [listeningStatus]);

    const showChatBubbleWithTimeout = (duration: number) => {
        setShowVoiceModal(true);
        Animated.timing(chatBubbleOpacity, {
            toValue: 1,
            duration: 300,
            useNativeDriver: true,
        }).start();
        
        const bubbleTimeout = setTimeout(() => {
            Animated.timing(chatBubbleOpacity, {
                toValue: 0,
                duration: 300,
                useNativeDriver: true,
            }).start(() => {
                setShowVoiceModal(false);
            });
        }, duration);
        
        return () => clearTimeout(bubbleTimeout);
    };

    const startRecording = async () => {
        try {
            if (recording) {
                console.log('Stopping existing recording before starting new one');
                try {
                    await recording.stopAndUnloadAsync();
                } catch (e) {
                    console.log('Error stopping previous recording:', e);
                }
                setRecording(null);
            }
    
            console.log('Starting audio recording...');
            await Audio.setAudioModeAsync({
                allowsRecordingIOS: true,
                playsInSilentModeIOS: true,
                staysActiveInBackground: true,
                interruptionModeIOS: 1,
                interruptionModeAndroid: 1,
            });
    
            const { recording: newRecording } = await Audio.Recording.createAsync(
                Audio.RecordingOptionsPresets.HIGH_QUALITY
            );
    
            console.log('Recording started successfully');
            setRecording(newRecording);
            setIsRecording(true);
    
            setListeningStatus('listening');
            setUserQuery(null);
            setApiResponse(null);
    
            setShowVoiceModal(true);
            chatBubbleOpacity.setValue(1);
    
            // Reset VAD state
            setHasDetectedSpeech(false);
            setSilenceCounter(0);
            setIsSmartRecording(true);
    
            // Start the VAD checking
            checkForSpeech();
        } catch (error) {
            console.error('Failed to start recording:', error);
            const errorMessage = error instanceof Error ? error.message : "Unknown error";
            Alert.alert("Recording Error", "Could not start recording: " + errorMessage);
            setListeningStatus('idle');
        }
    };

    const stopRecording = async () => {
        setIsRecording(false);
        cleanupRecording();

        if (!recording) {
            console.warn('No active recording to stop');
            return;
        }

        try {
            console.log('Stopping recording device...');
            await recording.stopAndUnloadAsync();

            await Audio.setAudioModeAsync({
                allowsRecordingIOS: false,
                playsInSilentModeIOS: true,
                staysActiveInBackground: true,
                interruptionModeIOS: 1,
                interruptionModeAndroid: 1,
            });

            const uri = recording.getURI();
            console.log('Recording stopped and stored at', uri);

            if (uri) {
                console.log('Processing completed recording...');
                await sendAudioToAPI(uri);
                saveAudioAsWav(uri).catch(err => console.error("Error saving audio:", err));
            } else {
                console.error("Recording URI is null");
                setApiResponse("Error: Could not access recording.");
                setListeningStatus('idle');
            }

            setRecording(null);
            // setIsRecording(false);

        } catch (error) {
            console.error('Failed to stop recording:', error);
            setApiResponse("Error stopping recording: " + (error.message || "Unknown error"));
            setRecording(null);
            // setIsRecording(false);
            setListeningStatus('idle');
        }
    };

    const saveAudioAsWav = async (uri: string) => {
        try {
            const audioDir = `${FileSystem.documentDirectory}audiofiles/`;

            const dirInfo = await FileSystem.getInfoAsync(audioDir);
            if (!dirInfo.exists) {
                console.log("Creating audio directory...");
                await FileSystem.makeDirectoryAsync(audioDir, { intermediates: true });
            }

            const sourceExt = uri.split('.').pop() || 'm4a';
            
            const timestamp = new Date().getTime();
            const fileName = `recording_${timestamp}.${sourceExt}`;
            const filePath = `${audioDir}${fileName}`;

            console.log(`Copying audio from ${uri} to ${filePath}`);
            await FileSystem.copyAsync({
                from: uri,
                to: filePath
            });

            console.log(`Audio saved successfully at: ${filePath}`);
            setAudioUri(filePath);

            loadRecordings();
            return filePath;
        } catch (error) {
            console.error('Error saving audio file:', error);
            return uri;
        }
    };

    const loadRecordings = async () => {
        try {
            const audioDir = `${FileSystem.documentDirectory}audiofiles/`;

            const dirInfo = await FileSystem.getInfoAsync(audioDir);
            if (!dirInfo.exists) {
                console.log("Audio directory doesn't exist yet");
                return;
            }

            const files = await FileSystem.readDirectoryAsync(audioDir);

            const audioFiles = files.filter(file => 
                file.endsWith('.wav') || 
                file.endsWith('.m4a') || 
                file.endsWith('.mp3') ||
                file.endsWith('.aac')
            );

            const recordingsData = await Promise.all(
                audioFiles.map(async (filename) => {
                    const fileUri = `${audioDir}${filename}`;
                    const fileInfo = await FileSystem.getInfoAsync(fileUri);
                    return {
                        uri: fileUri,
                        filename: filename,
                        date: 'modificationTime' in fileInfo && fileInfo.modificationTime
                            ? new Date(fileInfo.modificationTime * 1000)
                            : new Date()
                    };
                })
            );

            recordingsData.sort((a, b) => b.date.getTime() - a.date.getTime());
            setRecordings(recordingsData);

        } catch (error) {
            console.error('Error loading recordings:', error);
        }
    };

    const playRecording = async (uri: string) => {
        try {
            if (playingAudio) {
                await playingAudio.unloadAsync();
            }

            console.log(`Playing recording: ${uri}`);
            const { sound } = await Audio.Sound.createAsync({ uri });
            setPlayingAudio(sound);
            setIsPlaying(true);

            await sound.playAsync();

            sound.setOnPlaybackStatusUpdate((status) => {
                if (status.isLoaded && status.didJustFinish) {
                    setIsPlaying(false);
                }
            });

        } catch (error) {
            console.error('Error playing recording:', error);
        }
    };

    const deleteRecording = async (uri: string) => {
        try {
            await FileSystem.deleteAsync(uri);
            console.log(`Deleted recording: ${uri}`);
            loadRecordings();
        } catch (error) {
            console.error('Error deleting recording:', error);
        }
    };

    const confirmDeleteRecording = (uri: string, filename: string) => {
        Alert.alert(
            "Delete Recording",
            `Are you sure you want to delete ${filename}?`,
            [
                { text: "Cancel", style: "cancel" },
                {
                    text: "Delete",
                    onPress: () => deleteRecording(uri),
                    style: "destructive"
                }
            ]
        );
    };

    useEffect(() => {
        loadRecordings();
    }, []);

    const handleVoiceAssistant = () => {
        if (!isRecording) {
            setShowVoiceModal(true);
            Animated.sequence([
                Animated.timing(chatBubbleOpacity, {
                    toValue: 1,
                    duration: 300,
                    useNativeDriver: true,
                }),
                Animated.delay(3000),
                Animated.timing(chatBubbleOpacity, {
                    toValue: 0,
                    duration: 300,
                    useNativeDriver: true,
                })
            ]).start(() => {
                setShowVoiceModal(false);
            });
        }
    };

    const headerStyle = {
        backgroundColor: '#00B14F',
        padding: 16,
    };
    const headerTextStyle: TextStyle = {
        color: '#FFFFFF',
        fontSize: 20,
        fontWeight: 'bold',
    };
    const bottomSheetStyle = {
        backgroundColor: '#FFFFFF',
        borderTopLeftRadius: 20,
        borderTopRightRadius: 20,
    };
    const bottomSheetTextStyle: TextStyle = {
        color: '#000000',
        fontSize: 16,
        fontWeight: 'bold',
    };

    return (
        <SafeAreaView style={{ flex: 1 }}>
            <StatusBar translucent backgroundColor="#00B14F" barStyle="dark-content" />

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

            <View style={styles.voiceAssistantContainer}>
                {showVoiceModal && (
                    <Animated.View
                        style={[
                            styles.chatBubble,
                            { opacity: chatBubbleOpacity }
                        ]}
                    >
                        <Text style={styles.chatBubbleText}>
                            {getChatBubbleMessage()}
                        </Text>
                    </Animated.View>
                )}

                <TouchableOpacity
                    style={styles.recordingsBrowserButton}
                    onPress={() => {
                        loadRecordings();
                        setShowRecordingsModal(true);
                    }}
                >
                    <Feather name="list" size={20} color="#fff" />
                </TouchableOpacity>

                <TouchableOpacity
                    style={isRecording ? styles.recordingButton : styles.voiceAssistantButton}
                    onPress={() => {
                        if (!isRecording) {
                            console.log('Starting recording (button press)');
                            startRecording();
                        } else {
                            console.log('Stopping recording (manual button press)');
                            stopRecording();
                        }
                    }}
                    // Remove these longPress handlers
                    // onLongPress={startRecording}
                    // onPressOut={() => {
                    //     if (isRecording) {
                    //         stopRecording();
                    //     }
                    // }}
                    // delayLongPress={500}
                >
                    <FontAwesome5
                        name={isRecording ? "stop" : "microphone"}
                        size={20}
                        color="#fff"
                    />
                </TouchableOpacity>
            </View>

            {showRecordingsModal && (
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
                        padding: 16,
                    }}
                >
                    <View
                        style={{
                            backgroundColor: 'white',
                            borderRadius: 12,
                            shadowColor: '#000',
                            shadowOffset: { width: 0, height: 2 },
                            shadowOpacity: 0.25,
                            shadowRadius: 3.84,
                            elevation: 5,
                            width: '90%',
                            maxHeight: '80%',
                            padding: 16,
                        }}
                    >
                        <View className="flex-row justify-between items-center mb-4">
                            <Text style={{ fontSize: 18, fontWeight: 'bold' }}>Recorded Audio Files</Text>
                            <TouchableOpacity
                                onPress={() => setShowRecordingsModal(false)}
                                className="h-10 w-10 rounded-full items-center justify-center"
                            >
                                <Feather name="x" size={24} color="#6b7280" />
                            </TouchableOpacity>
                        </View>

                        {recordings.length === 0 ? (
                            <View className="py-10 items-center">
                                <Feather name="file-text" size={48} color="#9ca3af" />
                                <Text className="text-gray-500 mt-4 text-center">
                                    No recordings found. Long-press the microphone button to record.
                                </Text>
                            </View>
                        ) : (
                            <FlatList
                                data={recordings}
                                keyExtractor={(item) => item.uri}
                                renderItem={({ item }) => (
                                    <View
                                        style={{
                                            flexDirection: 'row',
                                            justifyContent: 'space-between',
                                            alignItems: 'center',
                                            padding: 12,
                                            borderBottomWidth: 1,
                                            borderBottomColor: '#e5e7eb',
                                        }}
                                    >
                                        <View style={{ flex: 1 }}>
                                            <Text style={{ fontWeight: 'medium' }} numberOfLines={1}>
                                                {item.filename}
                                            </Text>
                                            <Text style={{ color: '#6b7280', fontSize: 12 }}>
                                                {item.date.toLocaleString()}
                                            </Text>
                                        </View>
                                        <View style={{ flexDirection: 'row' }}>
                                            <TouchableOpacity
                                                style={{
                                                    height: 36,
                                                    width: 36,
                                                    borderRadius: 18,
                                                    backgroundColor: '#00B14F',
                                                    justifyContent: 'center',
                                                    alignItems: 'center',
                                                    marginRight: 8,
                                                }}
                                                onPress={() => playRecording(item.uri)}
                                            >
                                                <Feather name="play" size={16} color="#fff" />
                                            </TouchableOpacity>
                                            <TouchableOpacity
                                                style={{
                                                    height: 36,
                                                    width: 36,
                                                    borderRadius: 18,
                                                    backgroundColor: '#ef4444',
                                                    justifyContent: 'center',
                                                    alignItems: 'center',
                                                }}
                                                onPress={() => confirmDeleteRecording(item.uri, item.filename)}
                                            >
                                                <Feather name="trash-2" size={16} color="#fff" />
                                            </TouchableOpacity>
                                        </View>
                                    </View>
                                )}
                            />
                        )}

                        <TouchableOpacity
                            style={{
                                backgroundColor: '#00B14F',
                                padding: 12,
                                borderRadius: 8,
                                alignItems: 'center',
                                marginTop: 16,
                            }}
                            onPress={() => {
                                loadRecordings();
                            }}
                        >
                            <Text style={{ color: 'white', fontWeight: 'bold' }}>Refresh List</Text>
                        </TouchableOpacity>
                    </View>
                </View>
            )}

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

            {showMessageModal && (
                <View
                    style={{
                        position: 'absolute',
                        top: 98,
                        bottom: 0,
                        left: 0,
                        right: 0,
                        backgroundColor: 'rgba(0,0,0,0.5)',
                        justifyContent: 'flex-start',
                        alignItems: 'center',
                        padding: 16,
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

                        <ScrollView
                            className="flex-1 p-4"
                            contentContainerStyle={{ flexGrow: 1 }}
                        >

                            <View className="flex-1 items-center justify-center">
                                <Text className="text-gray-500 text-center">Start your conversation with {customer.name}</Text>
                            </View>

                        </ScrollView>

                        <View className="p-3 border-t border-gray-100 flex-row justify-between">
                            <View className="flex-row w-10/12 rounded-full border border-accent bg-gray-100 px-4 py-2">
                                <Text className="text-gray-500">Send a message...</Text>
                            </View>
                            <TouchableOpacity
                                className="h-10 w-10 bg-green-50 rounded-full items-center justify-center mr-2"
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
    voiceAssistantContainer: {
        position: 'absolute',
        right: 15,
        bottom: '22%',
        flexDirection: 'row',
        alignItems: 'center',
        zIndex: 999,
    },
    recordingsBrowserButton: {
        backgroundColor: '#3b82f6',
        width: 50,
        height: 50,
        borderRadius: 25,
        justifyContent: 'center',
        alignItems: 'center',
        elevation: 5,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.3,
        shadowRadius: 3,
        marginRight: 10,
    },
    voiceAssistantButton: {
        backgroundColor: '#00B14F',
        width: 50,
        height: 50,
        borderRadius: 25,
        justifyContent: 'center',
        alignItems: 'center',
        elevation: 5,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.3,
        shadowRadius: 3,
    },
    recordingButton: {
        backgroundColor: '#FF3B30',
        width: 50,
        height: 50,
        borderRadius: 25,
        justifyContent: 'center',
        alignItems: 'center',
        elevation: 5,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.3,
        shadowRadius: 3,
    },
    chatBubble: {
        backgroundColor: 'white',
        borderRadius: 16,
        padding: 10,
        marginRight: 10,
        elevation: 5,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.3,
        shadowRadius: 3,
        position: 'relative',
        maxWidth: 200,
    },
    chatBubbleText: {
        color: '#333',
        fontSize: 14,
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
        backgroundColor: '#00A651',
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