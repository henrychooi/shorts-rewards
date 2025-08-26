import React from "react";
import Navbar from "../components/Navbar";
import { Link } from "react-router-dom";

export default function Streamers() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar />
      <main className="container mx-auto px-4 py-8">
        <h1 className="text-2xl font-semibold mb-4">Streamers</h1>
        <p className="text-muted-foreground mb-4">Explore streamers and live sessions.</p>
        <Link
          to="/stream"
          className="inline-flex items-center gap-2 rounded-md border border-input bg-background px-4 py-2 text-sm hover:bg-accent hover:text-accent-foreground"
        >
          Go Live
        </Link>
      </main>
    </div>
  );
}


