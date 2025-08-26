import React, { useState, useRef, useEffect } from "react";
import Navbar from "../components/Navbar";
import api from "../api";
import Webcam from "react-webcam";

export default function Streaming() {
  const [isLive, setIsLive] = useState(false);
  const [title, setTitle] = useState("My awesome stream");
  const [streamId, setStreamId] = useState(null);
  const [error, setError] = useState("");
  const [hasPermission, setHasPermission] = useState(false);
  const webcamRef = useRef(null);
  const peerConnection = useRef(null);
  const streamRef = useRef(null);
  
  useEffect(() => {
    async function requestPermissions() {
      try {
        // First check if permissions are already granted
        const permissions = await navigator.mediaDevices.enumerateDevices();
        const videoPermission = permissions.some(device => device.kind === 'videoinput');
        const audioPermission = permissions.some(device => device.kind === 'audioinput');
        
        if (videoPermission && audioPermission) {
          setHasPermission(true);
          return;
        }

        // Request permissions if not already granted
        const stream = await navigator.mediaDevices.getUserMedia({ 
          video: {
            width: { ideal: 1280 },
            height: { ideal: 720 }
          }, 
          audio: true 
        });
        setHasPermission(true);
        if (stream) {
          stream.getTracks().forEach(track => track.stop());
        }
      } catch (err) {
        console.error('Permission error:', err);
        setError("Camera/microphone access denied. Please check your browser settings and allow access.");
        setHasPermission(false);
      }
    }
    requestPermissions();
  }, []);

  useEffect(() => {
    return () => {
      if (isLive) {
        endStream();
      }
    };
  }, []);

  const startStream = async () => {
    setError("");
    try {
      // Request permissions first
      if (!hasPermission) {
        await requestPermissions();
        if (!hasPermission) {
          throw new Error("Camera permission denied");
        }
      }

      // Get media stream with explicit constraints
      const mediaStream = await navigator.mediaDevices.getUserMedia({ 
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          frameRate: { ideal: 30 }
        },
        audio: true
      });
      
      streamRef.current = mediaStream;
      if (webcamRef.current) {
        webcamRef.current.srcObject = mediaStream;
      }

      // Create the stream in the backend
      const res = await api.post("/api/streams/", { title });
      const newStreamId = res.data.id; // Access the id field directly
      if (!newStreamId) {
        throw new Error('Failed to get stream ID from response');
      }
      setStreamId(newStreamId);
      console.log('Stream created with ID:', newStreamId);

      // Set up WebRTC with more STUN servers for better connectivity
      const pc = new RTCPeerConnection({
        iceServers: [
          { urls: 'stun:stun.l.google.com:19302' },
          { urls: 'stun:stun1.l.google.com:19302' },
          { urls: 'stun:stun2.l.google.com:19302' },
          { urls: 'stun:stun3.l.google.com:19302' },
          { urls: 'stun:stun4.l.google.com:19302' }
        ],
        iceTransportPolicy: 'all',
        iceCandidatePoolSize: 10
      });
      
      // Add tracks to the peer connection and set up error handling
      mediaStream.getTracks().forEach(track => {
        try {
          pc.addTrack(track, mediaStream);
        } catch (err) {
          console.error('Error adding track:', err);
          throw new Error('Failed to set up stream');
        }
      });

      // Set up connection state monitoring
      pc.oniceconnectionstatechange = (event) => {
        console.log('ICE connection state:', pc.iceConnectionState);
        if (pc.iceConnectionState === 'failed' || pc.iceConnectionState === 'disconnected') {
          setError('Connection lost. Please refresh and try again.');
        }
      };

      // Create and send offer with timeout handling
      try {
        const offer = await pc.createOffer({
          offerToReceiveAudio: true,
          offerToReceiveVideo: true
        });
        await pc.setLocalDescription(offer);
        
        // Wait for ICE gathering to complete or timeout after 5 seconds
        await new Promise((resolve, reject) => {
          const timeout = setTimeout(() => {
            reject(new Error('ICE gathering timed out'));
          }, 5000);
          
          pc.onicegatheringstatechange = () => {
            if (pc.iceGatheringState === 'complete') {
              clearTimeout(timeout);
              resolve();
            }
          };
        });
        
        // Ensure we have a valid stream ID before sending the offer
        if (!newStreamId) {
          throw new Error('No stream ID available for offer');
        }

        try {
          await api.post(`/api/streams/${newStreamId}/offer/`, {
            offer: pc.localDescription
          });
          console.log('Successfully sent offer for stream:', newStreamId);
        } catch (offerErr) {
          console.error('Failed to send offer:', offerErr);
          // Clean up the created stream if we can't set up the WebRTC connection
          await api.post(`/api/streams/${newStreamId}/end/`);
          throw new Error('Failed to establish connection');
        }
      } catch (err) {
        console.error('Offer creation error:', err);
        // Also try to clean up the stream if we have an ID
        if (newStreamId) {
          try {
            await api.post(`/api/streams/${newStreamId}/end/`);
          } catch (cleanupErr) {
            console.error('Failed to cleanup stream:', cleanupErr);
          }
        }
        throw new Error('Failed to establish connection');
      }

      peerConnection.current = pc;
      setIsLive(true);
    } catch (e) {
      console.error("Stream start error:", e);
      // Clean up any media streams
      if (streamRef.current) {
        streamRef.current.getTracks().forEach(track => track.stop());
        streamRef.current = null;
      }
      if (webcamRef.current) {
        webcamRef.current.srcObject = null;
      }
      
      if (e?.response?.status === 401) {
        setError("Please log in to start streaming.");
      } else if (e?.response?.status === 404) {
        setError("Stream setup failed. Please try again.");
      } else if (e.message === 'Failed to get stream ID from response') {
        setError("Failed to create stream. Please try again.");
      } else if (e.message === 'No stream ID available for offer') {
        setError("Failed to setup stream connection. Please try again.");
      } else if (e.message === 'ICE gathering timed out') {
        setError("Connection setup timed out. Please check your network and try again.");
      } else {
        setError("Failed to start stream. Please check your connection and try again.");
      }
      // Reset stream ID if we failed
      setStreamId(null);
    }
  };

  const handleDataAvailable = ({ data }) => {
    if (data.size > 0) {
      chunksRef.current.push(data);
    }
  };

  const handleStop = async () => {
    const blob = new Blob(chunksRef.current, {
      type: "video/webm"
    });
    chunksRef.current = [];
    
    // Here you would typically send the blob to your streaming server
    // For now, we'll just create an object URL for preview
    const url = URL.createObjectURL(blob);
    console.log("Stream recording URL:", url);
  };

  const endStream = async () => {
    setError("");
    try {
      if (streamId) {
        await api.post(`/api/streams/${streamId}/end/`);
        
        // Close peer connection
        if (peerConnection.current) {
          peerConnection.current.close();
          peerConnection.current = null;
        }

        // Stop media tracks
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
          streamRef.current = null;
        }

        // Clear video element
        if (webcamRef.current) {
          webcamRef.current.srcObject = null;
        }
      }
      setIsLive(false);
      setStreamId(null);
    } catch (e) {
      console.error("Stream end error:", e);
      setError("Failed to end stream. Please try again.");
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar />
      <main className="container mx-auto px-4 py-8">
        <h1 className="text-2xl font-semibold mb-4">Go Live</h1>
        <div className="grid md:grid-cols-3 gap-6">
          <div className="md:col-span-2 rounded-lg border bg-card p-4">
            <div className="aspect-video w-full bg-muted flex items-center justify-center rounded overflow-hidden">
              {webcamRef.current || isLive ? (
                <Webcam
                  audio={true}
                  ref={webcamRef}
                  className="w-full h-full object-cover"
                />
              ) : (
                <span className="text-muted-foreground">
                  Camera preview (click Start Stream to enable)
                </span>
              )}
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


