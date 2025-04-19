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
    const [distance, setDistance] = useState<string | null>(null);
    const [durationInTraffic, setDurationInTraffic] = useState<string | null>(null);
    const [mapType, setMapType] = useState<'standard' | 'satellite' | 'hybrid'>('standard');
    const [routeCoordinates, setRouteCoordinates] = useState<{ latitude: number; longitude: number }[]>([]);
    const [customerCoords, setCustomerCoords] = useState<{ latitude: number; longitude: number } | null>(null);
    const [currentMarker, setCurrentMarker] = useState<{ latitude: number; longitude: number } | null>(null);
    const [destinationMarker, setDestinationMarker] = useState<{ latitude: number; longitude: number } | null>(null);
    const [approve, setApprove] = useState(false);
    const [loading, setLoading] = useState(true)
    const [currentIndex, setCurrentIndex] = useState(0);
    const [showTraffic, setShowTraffic] = useState(false);
    const [animatedIndex, setAnimatedIndex] = useState(0);
    const [showModal, setShowModal] = useState(false);
    const [showCountdownModal, setShowCountdownModal] = useState(false);
    const [showMessageModal, setShowMessageModal] = useState(false);
    const [showSuccessModal, setShowSuccessModal] = useState(false);
    const [messages, setMessages] = useState<string[]>([]);
    const [isNavigatingToCustomer, setIsNavigatingToCustomer] = useState(false);
    const [countdown, setCountdown] = useState(5);
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

    const mapRef = useRef<MapView>(null);
    const bottomSheetRef = useRef<BottomSheet>(null);
    const animatedValue = useRef(new Animated.Value(0)).current;
    const pulseAnim = useRef(new Animated.Value(1)).current;
    const opacityAnimation = useRef(new Animated.Value(0.6)).current;
    const snapPoints = useMemo(() => ['18%', '62%'], []);

    useEffect(() => {
        if (loading) {
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
    }, [region]);

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

    const customer =
    {
        name: "Angel Chan",
        rating: "4.5",
        phone: "+6011 9876 5432",
        origin: "Tun Ahmad Zaidi Residential College",
        destination: "Mid Valley Megamall North Court Entrance",
        fare: "RM 15.00",
    };

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

    useEffect(() => {
        if (region && apiKey) {
            setCurrentMarker({
                latitude: region.latitude,
                longitude: region.longitude,
            });

            MapsService.getPlaceCoordinates(customer.origin).then((coords) => {
                setDestinationMarker(coords);
            });

            setTimeout(() => {
                setShowModal(true);
            }, 2000);
        }
    }, [region, apiKey]);

    const testBackendConnection = async () => {
        try {
            const response = await fetch('http://172.20.10.3:8000/', { method: 'GET' });
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

    const startAnimation = (length: number) => {
        animatedValue.setValue(0);
        Animated.loop(
            Animated.timing(animatedValue, {
                toValue: length,
                duration: 5000,
                useNativeDriver: false,
            })
        ).start();

        animatedValue.addListener(({ value }) => {
            setAnimatedIndex(Math.floor(value));
        });
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

    const handleShowMessageModal = () => {
        setShowMessageModal(true);
        setCurrentIndex(0);
        bottomSheetRef.current?.snapToIndex(0);
        setMessages([]);
    };

    const closeMessageModal = () => {
        setShowMessageModal(false);
    };

    const handleApprove = async () => {
        setApprove(true);
        setShowModal(false);
        setIsNavigatingToCustomer(true);

        if (!region) return;

        if (currentMarker === null || destinationMarker === null) {
            setCurrentMarker({
                latitude: region.latitude,
                longitude: region.longitude,
            });

            MapsService.getPlaceCoordinates(customer.origin).then((coords) => {
                setDestinationMarker(coords);
            });
        }

        const origin = `${region.latitude},${region.longitude}`;
        const customerOrigin = customer.origin;

        try {
            const customerCoordsResponse = await MapsService.getPlaceCoordinates(customerOrigin);
            setCustomerCoords(customerCoordsResponse);

            const directions = await MapsService.getDirections(origin, `${customerCoordsResponse.latitude},${customerCoordsResponse.longitude}`);

            const durationInTraffic = directions.routes[0].legs[0].duration_in_traffic.text;
            console.log(`Estimated time in traffic: ${durationInTraffic}`);
            setDurationInTraffic(durationInTraffic);

            const distanceText = directions.routes[0].legs[0].distance.text;
            console.log(`Distance: ${distanceText}`);
            setDistance(distanceText);

            const points = decodePolyline(directions.routes[0].overview_polyline.points);
            console.log('Decoded polyline points:', points);
            setRouteCoordinates(points);

            startAnimation(points.length);
        } catch (error) {
            console.error('Error fetching route to customer:', error);
        }
    };

    useEffect(() => {
        if (isNavigatingToCustomer && customerCoords) {
            const interval = setInterval(async () => {
                const location = await Location.getCurrentPositionAsync({});
                const distanceToCustomer = MapsService.calculateDistance(
                    location.coords.latitude,
                    location.coords.longitude,
                    customerCoords.latitude,
                    customerCoords.longitude,
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
        setShowCountdownModal(true);
        let timer = 5;
        setCountdown(timer);

        const interval = setInterval(() => {
            timer -= 1;
            setCountdown(timer);

            if (timer === 0) {
                clearInterval(interval);
                setShowCountdownModal(false);

                if (customerCoords) {
                    setCurrentMarker(customerCoords);
                }

                MapsService.getPlaceCoordinates(customer.destination).then((coords) => {
                    setDestinationMarker(coords);
                });

                navigateToDestination();
            }
        }, 1000);
    };

    const navigateToDestination = async () => {
        setIsNavigatingToCustomer(false);

        const customerCoords = await MapsService.getPlaceCoordinates(customer.origin);
        const destinationCoords = await MapsService.getPlaceCoordinates(customer.destination);

        try {
            const directions = await MapsService.getDirections(
                `${customerCoords.latitude},${customerCoords.longitude}`,
                `${destinationCoords.latitude},${destinationCoords.longitude}`
            );
            const points = decodePolyline(directions.routes[0].overview_polyline.points);

            setRouteCoordinates(points);

            const durationInTraffic = directions.routes[0].legs[0].duration_in_traffic.text;
            console.log(`Estimated time in traffic: ${durationInTraffic}`);
            setDurationInTraffic(durationInTraffic);

            const distanceText = directions.routes[0].legs[0].distance.text;
            console.log(`Distance: ${distanceText}`);
            setDistance(distanceText);

            startAnimation(points.length);

            const interval = setInterval(async () => {
                const location = await Location.getCurrentPositionAsync({});
                const distanceToDestination = MapsService.calculateDistance(
                    location.coords.latitude,
                    location.coords.longitude,
                    destinationCoords.latitude,
                    destinationCoords.longitude,
                );

                if (distanceToDestination < 50) {
                    clearInterval(interval);
                    handleDestinationReached();
                }
            }, 2000);
        } catch (error) {
            console.error('Error fetching route to destination:', error);
        }
    };

    const handleDestinationReached = () => {
        setShowSuccessModal(true);

        setTimeout(() => {
            setShowSuccessModal(false);
            animatedValue.stopAnimation();
            setRouteCoordinates([]);
            setCurrentMarker(null);
            setDestinationMarker(null);
            setApprove(false);
            setCustomerCoords(null);
            setDistance(null);
            setDurationInTraffic(null);
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
                interruptionModeIOS: 1, // Audio.INTERRUPTION_MODE_IOS_DO_NOT_MIX
                interruptionModeAndroid: 1, // Audio.INTERRUPTION_MODE_ANDROID_DO_NOT_MIX
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
        } catch (error: any) {
            console.error('Failed to start recording:', error);
            Alert.alert("Recording Error", "Could not start recording: " + (error.message || "Unknown error"));
            setListeningStatus('idle');
        }
    };

    const stopRecording = async () => {
        if (!recording) {
            console.warn('No active recording to stop');
            return;
        }

        try {
            console.log('Stopping recording...');
            await recording.stopAndUnloadAsync();

            await Audio.setAudioModeAsync({
                allowsRecordingIOS: false,
                playsInSilentModeIOS: true,
                staysActiveInBackground: true,
                interruptionModeIOS: 1, // Audio.INTERRUPTION_MODE_IOS_DO_NOT_MIX
                interruptionModeAndroid: 1, // Audio.INTERRUPTION_MODE_ANDROID_DO_NOT_MIX
            });

            const uri = recording.getURI();
            console.log('Recording stopped and stored at', uri);

            if (uri) {
                await sendAudioToAPI(uri);
                saveAudioAsWav(uri).catch(err => console.error("Error saving audio:", err));
            } else {
                console.error("Recording URI is null");
                setApiResponse("Error: Could not access recording.");
                setListeningStatus('idle');
            }

            setRecording(null);
            setIsRecording(false);

        } catch (error: any) {
            console.error('Failed to stop recording:', error);
            setApiResponse("Error stopping recording: " + (error.message || "Unknown error"));
            setRecording(null);
            setIsRecording(false);
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

            {loading ? (
                <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#EAEAEA' }}>
                    <View style={{ justifyContent: 'center', alignItems: 'center' }}>
                        <Animated.View
                            style={[
                                styles.pulse,
                                {
                                    transform: [{ scale: pulseAnim }],
                                    opacity: pulseAnim.interpolate({
                                        inputRange: [1, 1.2],
                                        outputRange: [0.6, 0.3],
                                    }),
                                },
                            ]}
                        />

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
                    {currentMarker && approve && (
                        <Marker
                            coordinate={currentMarker}
                            title="You are here"
                            image={require('../assets/images/origin-icon.png')}
                        />
                    )}

                    {destinationMarker && approve && (
                        <Marker
                            coordinate={destinationMarker}
                            title="Destination"
                            image={require('../assets/images/destination-icon.png')}
                        />
                    )}

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

            <TouchableOpacity
                style={styles.relocateButton}
                onPress={() => {
                    if (region) {
                        mapRef.current?.animateToRegion(region, 1000);
                    }
                }}
            >
                <Feather name="crosshair" size={24} color="#fff" />
            </TouchableOpacity>

            <TouchableOpacity
                style={styles.toggleButton}
                onPress={() => setMapType(mapType === 'standard' ? 'hybrid' : 'standard')}
            >
                <MaterialIcons name="satellite-alt" size={24} color="#fff" />
            </TouchableOpacity>

            <TouchableOpacity
                style={styles.trafficButton}
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
                    onPress={handleVoiceAssistant}
                    onLongPress={startRecording}
                    onPressOut={() => {
                        if (isRecording) {
                            stopRecording();
                        }
                    }}
                    delayLongPress={500}
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

            {showModal && (
                <View
                    style={{
                        position: 'absolute',
                        top: 98,
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
                                <View className="h-10 w-10 bg-blue-50 rounded-full items-center justify-center mr-3">
                                    <Feather name="user" size={18} color="#1595E6" />
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
                                        setTimeout(() => {
                                            setShowModal(true);
                                        }, 10000);
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
                                    onPress={handleApprove}
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
                                Looks like you've reached the customer!
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
                        <Feather name="check-circle" size={48} color="#00B14F" />
                        <View
                            style={{
                                justifyContent: 'center',
                                alignItems: 'center',
                                marginTop: 8,
                            }}
                        >
                            <Text style={{ fontSize: 18, fontWeight: 'bold', color: '#333', textAlign: 'center' }}>
                                You have reached {customer.destination}. Nice driving!
                            </Text>
                        </View>
                    </View>
                </View>
            )}

            <BottomSheet snapPoints={snapPoints}
                enablePanDownToClose={false}
                index={0}
                onChange={(index) => setCurrentIndex(index)}
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
                        const nextIndex = currentIndex === 0 ? 1 : 0;
                        bottomSheetRef.current?.snapToIndex(nextIndex);
                    }}
                >
                    <BottomSheetView style={{
                        flex: 1,
                        alignItems: 'center',
                        padding: 15,
                        backgroundColor: '#FFFFFF',
                        borderTopLeftRadius: 20,
                        borderTopRightRadius: 20
                    }}>
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
                                        Distance: {distance || 'Calculating...'}
                                    </Text>
                                </View>
                            </>
                        )}

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
                                        marginVertical: 8,
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
        top: 220,
        right: 15,
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
        top: 110,
        right: 15,
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
        top: 165,
        right: 15,
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