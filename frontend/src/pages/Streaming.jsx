import React, { useState } from "react";
import Navbar from "../components/Navbar";
import api from "../api";

export default function Streaming() {
  const [isLive, setIsLive] = useState(false);
  const [title, setTitle] = useState("My awesome stream");
  const [streamId, setStreamId] = useState(null);
  const [error, setError] = useState("");

  const startStream = async () => {
    setError("");
    try {
      const res = await api.post("/api/streams/", { title });
      setIsLive(true);
      setStreamId(res.data.id);
    } catch (e) {
      if (e?.response?.status === 401) {
        setError("Please log in to start streaming.");
      } else {
        setError("Failed to start stream.");
      }
    }
  };

  const endStream = async () => {
    setError("");
    try {
      if (streamId) {
        await api.patch(`/api/streams/end/${streamId}/`, { is_live: false });
      }
      setIsLive(false);
      setStreamId(null);
    } catch (e) {
      setError("Failed to end stream.");
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar />
      <main className="container mx-auto px-4 py-8">
        <h1 className="text-2xl font-semibold mb-4">Go Live</h1>
        <div className="grid md:grid-cols-3 gap-6">
          <div className="md:col-span-2 rounded-lg border bg-card p-4">
            <div className="aspect-video w-full bg-muted flex items-center justify-center rounded">
              <span className="text-muted-foreground">
                {isLive ? "Live preview" : "Camera preview (mock)"}
              </span>
            </div>
          </div>
          <div className="space-y-4">
            <div className="rounded-lg border bg-card p-4">
              <label className="block text-sm mb-2">Title</label>
              <input
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                placeholder="My awesome stream"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
              {streamId && (
                <div className="text-xs text-muted-foreground mt-2">Stream ID: {streamId}</div>
              )}
              {error && (
                <div className="text-xs text-destructive mt-2">{error}</div>
              )}
            </div>
            {isLive ? (
              <button
                className="w-full rounded-md bg-primary text-primary-foreground px-4 py-2 hover:bg-primary/90"
                onClick={endStream}
              >
                End Stream
              </button>
            ) : (
              <button
                className="w-full rounded-md bg-primary text-primary-foreground px-4 py-2 hover:bg-primary/90"
                onClick={startStream}
              >
                Start Stream
              </button>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}


