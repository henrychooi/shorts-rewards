import { useEffect, useState } from "react";
import { StreamVideoClient, StreamVideo } from "@stream-io/video-react-sdk";
import api from "../api";
import { ACCESS_TOKEN } from "../constants";

function Watch() {
  const [client, setClient] = useState(null);
  const [call, setCall] = useState(null);

  useEffect(() => {
    const initViewer = async () => {
      try {
        // Get JWT access token
        const jwtToken = localStorage.getItem(ACCESS_TOKEN);
        if (!jwtToken) {
          console.error("No JWT access token found in localStorage.");
          return;
        }

        // Ask backend for a Stream call token (again, signed with Stream secret)
        const res = await api.post(
          "/api/stream/token/",
          {},
          {
            headers: { Authorization: `Bearer ${jwtToken}` },
          }
        );

        const { user, streamToken, apiKey } = res.data;

        const client = new StreamVideoClient({
          apiKey,
          user,
          token: streamToken,
        });

        // Join the same livestream
        const call = client.call("livestream", "my-livestream");
        await call.join();

        setClient(client);
        setCall(call);
      } catch (err) {
        console.error("Failed to join Stream call:", err);
      }
    };

    initViewer();
  }, []);

  if (!client || !call) {
    return <div>Loading stream...</div>;
  }

  return (
    <StreamVideo client={client}>
      <div className="flex flex-col items-center p-6">
        <h1 className="text-2xl font-bold mb-4">Watching Live 📺</h1>
        <call.UI />
      </div>
    </StreamVideo>
  );
}

export default Watch;
