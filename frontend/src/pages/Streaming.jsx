import React, { useState } from "react";
import Navbar from "../components/Navbar";

export default function Streaming() {
  const [isLive, setIsLive] = useState(false);

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
              <input className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm" placeholder="My awesome stream" />
            </div>
            <button
              className="w-full rounded-md bg-primary text-primary-foreground px-4 py-2 hover:bg-primary/90"
              onClick={() => setIsLive((v) => !v)}
            >
              {isLive ? "End Stream" : "Start Stream"}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}


