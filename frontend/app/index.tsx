import { useEffect } from "react";
import { Text, View } from "react-native";
import { useRouter } from "expo-router";

export default function Index() {
  const router = useRouter();

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
