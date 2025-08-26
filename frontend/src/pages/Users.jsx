import React from "react";
import Navbar from "../components/Navbar";
import { Link } from "react-router-dom";

export default function Users() {
  const sampleStreams = [
    { id: 1, title: "Epic Gaming Session", streamer: "Alice" },
    { id: 2, title: "Art & Chill", streamer: "Bob" },
  ];
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar />
      <main className="container mx-auto px-4 py-8">
        <h1 className="text-2xl font-semibold mb-4">Users</h1>
        <p className="text-muted-foreground mb-6">Pick a stream to watch.</p>
        <div className="grid sm:grid-cols-2 gap-4">
          {sampleStreams.map((s) => (
            <div key={s.id} className="rounded border bg-card p-4">
              <div className="font-medium">{s.title}</div>
              <div className="text-sm text-muted-foreground mb-3">by {s.streamer}</div>
              <Link
                to="/watch"
                className="inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground"
              >
                Watch
              </Link>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}


