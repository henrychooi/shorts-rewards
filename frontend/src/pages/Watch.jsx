import React, { useEffect, useState } from "react";
import Navbar from "../components/Navbar";
import GiftButton from "../components/GiftButton";
import { Link, useLocation } from "react-router-dom";
import api from "../api";

export default function Watch() {
  const [gifts, setGifts] = useState([]);
  const [liveStreams, setLiveStreams] = useState([]);
  const [selectedStreamId, setSelectedStreamId] = useState(null);
  const location = useLocation();

  useEffect(() => {
    const load = async () => {
      try {
        const res = await api.get("/api/streams/");
        setLiveStreams(res.data);
        const params = new URLSearchParams(location.search);
        const idFromQuery = Number(params.get("id")) || null;
        setSelectedStreamId(idFromQuery || res.data?.[0]?.id || null);
      } catch {}
    };
    load();
  }, [location.search]);

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
            <div className="aspect-video w-full bg-muted rounded flex items-center justify-center">
              <span className="text-muted-foreground">Live video (mock)</span>
            </div>
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
                    <option key={s.id} value={s.id}>{s.title}</option>
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
                  <li key={idx}>{g.amount}× {g.gift}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}


