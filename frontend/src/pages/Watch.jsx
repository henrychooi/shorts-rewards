import React, { useState } from "react";
import Navbar from "../components/Navbar";
import GiftButton from "../components/GiftButton";
import { Link } from "react-router-dom";

export default function Watch() {
  const [gifts, setGifts] = useState([]);

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
              <GiftButton
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


