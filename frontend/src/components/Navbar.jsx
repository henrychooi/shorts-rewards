import React from "react";
import { Link, useLocation } from "react-router-dom";

export default function Navbar() {
  const location = useLocation();
  const isActive = (path) =>
    location.pathname === path ? "text-foreground" : "text-muted-foreground";

  return (
    <header className="border-b border-border bg-card/50">
      <div className="container mx-auto px-4 py-4 flex items-center justify-between">
        <Link to="/users" className="text-xl font-bold text-foreground">
          StreamHub
        </Link>
        <nav className="flex items-center gap-6">
          <Link to="/users" className={`${isActive("/users")} hover:text-foreground`}>
            Users
          </Link>
          <Link
            to="/streamers"
            className={`${isActive("/streamers")} hover:text-foreground`}
          >
            Streamers
          </Link>
        </nav>
        <Link
          to="/logout"
          className="text-sm px-3 py-2 rounded-md border border-input hover:bg-accent hover:text-accent-foreground"
        >
          Logout
        </Link>
      </div>
    </header>
  );
}


