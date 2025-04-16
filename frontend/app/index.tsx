import { useEffect } from "react";
import { Text, View } from "react-native";
import { useRouter } from "expo-router";
import { LogBox } from 'react-native';
import 'react-native-gesture-handler';
import 'expo-router/entry';

export default function Index() {
  const router = useRouter();

  // Optionally suppress warnings for reanimated
  useEffect(() => {
    LogBox.ignoreLogs(['Reanimated 2']);
  }, []);

  useEffect(() => {
    // Navigate to driver.tsx on component mount
    const timer = setTimeout(() => {
      router.replace("/driver");
    }, 100);

    return () => clearTimeout(timer);
  }, [router]);

  return (
    <View className="flex justify-center items-center mt-4">
      <Text>Starting driver page</Text>
    </View>
  );
}
