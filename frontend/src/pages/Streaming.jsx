import { useEffect, useState } from "react";
import { StreamVideoClient, StreamVideo } from "@stream-io/video-react-sdk";
import api from "../api";
import { ACCESS_TOKEN } from "../constants";

function Streaming() {
  const [client, setClient] = useState(null);
  const [call, setCall] = useState(null);

  useEffect(() => {
    const initStream = async () => {
      try {
        // Grab JWT access token from localStorage
        const jwtToken = localStorage.getItem(ACCESS_TOKEN);
        if (!jwtToken) {
          console.error("No JWT access token found in localStorage.");
          return;
        }

        // Ask backend for a Stream call token (signed with Stream secret)
        const res = await api.post(
          "/api/stream/token/",
          {},
          {
            headers: { Authorization: `Bearer ${jwtToken}` },
          }
        );

        const { user, streamToken, apiKey } = res.data;

        // Init client
        const client = new StreamVideoClient({
          apiKey,
          user,
          token: streamToken,
        });

        // Create a livestream call
        const call = client.call("livestream", "my-livestream");
        await call.join({ create: true });

        setClient(client);
        setCall(call);
      } catch (err) {
        console.error("Failed to init Stream client:", err);
      }
    };

    initStream();
  }, []);

  if (!client || !call) {
    return <div>Starting livestream...</div>;
  }

  return (
    <StreamVideo client={client}>
      <div className="flex flex-col items-center p-6">
        <h1 className="text-2xl font-bold mb-4">You are Live 🎥</h1>
        <call.UI />
      </div>
    </StreamVideo>
  );
}

export default Streaming;
