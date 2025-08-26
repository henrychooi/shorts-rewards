import React, { useEffect, useState, useRef } from "react";
import { Link } from "react-router-dom";
import api from "../api";
import Navbar from "../components/Navbar";
import GiftButton from "../components/GiftButton";

export default function Watch() {
  const [liveStreams, setLiveStreams] = useState([]);
  const [selectedStreamId, setSelectedStreamId] = useState(null);
  const [error, setError] = useState(null);
  const [gifts, setGifts] = useState([]);
  const videoRef = useRef(null);
  const peerConnection = useRef(null);

  // Load available streams
  useEffect(() => {
    const load = async () => {
      try {
        const res = await api.get("/api/streams/");
        setLiveStreams(res.data);
        const params = new URLSearchParams(location.search);
        const idFromQuery = Number(params.get("id")) || null;
        setSelectedStreamId(idFromQuery || res.data?.[0]?.id || null);
      } catch (err) {
        console.error("Failed to load streams:", err);
      }
    };

    load();
    const interval = setInterval(load, 5000);
    return () => clearInterval(interval);
  }, [location.search]);

  // Handle WebRTC connection
  useEffect(() => {
    let pc = null;

    const connectToStream = async () => {
      if (!selectedStreamId) return;

      if (peerConnection.current && peerConnection.current.signalingState !== "closed") {
        peerConnection.current.close();
        peerConnection.current = null;
      }

      try {
        pc = new RTCPeerConnection({
          iceServers: [
            { urls: "stun:stun.l.google.com:19302" },
            { urls: "stun:stun1.l.google.com:19302" },
            { urls: "stun:stun2.l.google.com:19302" },
          ],
          iceCandidatePoolSize: 10,
        });

        peerConnection.current = pc;

        pc.ontrack = (event) => {
          if (videoRef.current && event.streams[0]) {
            videoRef.current.srcObject = event.streams[0];
          }
        };

        pc.onicecandidate = (event) => {
          if (event.candidate) {
            console.log("New ICE candidate:", event.candidate.candidate);
          }
        };

        pc.onconnectionstatechange = () => {
          if (pc.connectionState === "failed" || pc.connectionState === "disconnected") {
            if (pc && pc.signalingState !== "closed") {
              pc.close();
            }
            setTimeout(() => connectToStream(), 1000);
          }
        };

        const offerRes = await api.get(`/api/streams/${selectedStreamId}/offer/`);
        if (!offerRes.data.offer) throw new Error("No offer available from streamer");

        await pc.setRemoteDescription(new RTCSessionDescription(offerRes.data.offer));
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);

        await new Promise((resolve, reject) => {
          const timeoutId = setTimeout(() => reject(new Error("ICE gathering timeout")), 8000);
          if (pc.iceGatheringState === "complete") {
            clearTimeout(timeoutId);
            resolve();
          } else {
            pc.onicegatheringstatechange = () => {
              if (pc.iceGatheringState === "complete") {
                clearTimeout(timeoutId);
                resolve();
              }
            };
          }
        });

        await api.post(`/api/streams/${selectedStreamId}/answer/`, {
          answer: { type: "answer", sdp: answer.sdp },
        });

        setError(null);
      } catch (err) {
        console.error("Error connecting to stream:", err);
        setError(err.response?.data?.error || "Failed to connect to stream");

        if (pc && pc.signalingState !== "closed") pc.close();
        if (peerConnection.current && peerConnection.current.signalingState !== "closed") {
          peerConnection.current.close();
          peerConnection.current = null;
        }
        if (videoRef.current && videoRef.current.srcObject) {
          videoRef.current.srcObject.getTracks().forEach((track) => track.stop());
          videoRef.current.srcObject = null;
        }
      }
    };

    connectToStream();

    return () => {
      if (peerConnection.current && peerConnection.current.signalingState !== "closed") {
        peerConnection.current.close();
        peerConnection.current = null;
      }
      if (videoRef.current && videoRef.current.srcObject) {
        videoRef.current.srcObject.getTracks().forEach((track) => track.stop());
        videoRef.current.srcObject = null;
      }
    };
  }, [selectedStreamId]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar />
      <main className="container mx-auto px-4 py-8">
        <div className="mb-4">
          <Link
            to="/users"
            className="inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground"
          >
            ← Back to Users
          </Link>
        </div>
        <div className="grid md:grid-cols-3 gap-6">
          <div className="md:col-span-2 space-y-4">
            <div className="aspect-video w-full bg-muted rounded overflow-hidden">
              {selectedStreamId ? (
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center">
                  <span className="text-muted-foreground">Select a stream to watch</span>
                </div>
              )}
            </div>
            {error && (
              <div className="p-4 bg-destructive/10 border-destructive border rounded text-destructive">
                {error}
              </div>
            )}
            {selectedStreamId && liveStreams.find((s) => s.id === selectedStreamId) && (
              <div className="p-4 bg-card border rounded">
                <h2 className="font-semibold text-lg">
                  {liveStreams.find((s) => s.id === selectedStreamId)?.title}
                </h2>
                <p className="text-sm text-muted-foreground">
                  Streamed by:{" "}
                  {liveStreams.find((s) => s.id === selectedStreamId)?.host_username}
                </p>
              </div>
            )}
            <div className="rounded border p-4 bg-card">
              <h2 className="font-semibold mb-2">Chat (mock)</h2>
              <div className="h-40 overflow-auto text-sm text-muted-foreground">No messages yet.</div>
            </div>
          </div>
          <div className="space-y-4">
            <div className="rounded border p-4 bg-card">
              <h2 className="font-semibold mb-3">Support the streamer</h2>
              <div className="mb-3">
                <label className="block text-sm mb-1">Select Stream</label>
                <select
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={selectedStreamId || ""}
                  onChange={(e) => setSelectedStreamId(Number(e.target.value) || null)}
                >
                  <option value="">No live streams</option>
                  {liveStreams.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.title}
                    </option>
                  ))}
                </select>
              </div>
              <GiftButton
                streamId={selectedStreamId}
                onGift={(g) => setGifts((prev) => [g, ...prev].slice(0, 6))}
              />
              <ul className="mt-4 space-y-2 text-sm">
                {gifts.length === 0 && (
                  <li className="text-muted-foreground">No gifts yet.</li>
                )}
                {gifts.map((g, idx) => (
                  <li key={idx}>
                    {g.amount}× {g.gift}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
