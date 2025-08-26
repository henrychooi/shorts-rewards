import React, { useEffect, useState } from "react";
import Navbar from "../components/Navbar";
import { Link } from "react-router-dom";
import api from "../api";

export default function Users() {
  const [streams, setStreams] = useState([]);

  useEffect(() => {
    let timer;
    const load = async () => {
      try {
        const res = await api.get("/api/streams/");
        setStreams(res.data || []);
      } catch {}
      timer = setTimeout(load, 5000);
    };
    load();
    return () => timer && clearTimeout(timer);
  }, []);
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Navbar />
      <main className="container mx-auto px-4 py-8">
        <h1 className="text-2xl font-semibold mb-4">Users</h1>
        <p className="text-muted-foreground mb-6">Pick a live stream to watch.</p>
        {streams.length === 0 ? (
          <div className="text-sm text-muted-foreground">No live streams. Check back soon.</div>
        ) : (
          <div className="grid sm:grid-cols-2 gap-4">
            {streams.map((s) => (
              <div key={s.id} className="rounded border bg-card p-4">
                <div className="font-medium">{s.title}</div>
                <div className="text-sm text-muted-foreground mb-3">by {s.host}</div>
                <Link
                  to={`/watch?id=${s.id}`}
                  className="inline-flex items-center gap-2 rounded-md border border-input bg-background px-3 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground"
                >
                  Watch
                </Link>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}


