import { useState, useEffect } from "react";
import ShortsFeed from "../components/ShortsFeed";
import VideoUpload from "../components/VideoUpload";
import Navigation from "../components/Navigation";
import Profile from "./Profile";
import api from "../api";
import "../styles/Home.css";

function Home() {
  const [showUpload, setShowUpload] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [refreshFeed, setRefreshFeed] = useState(0);
  const [currentView, setCurrentView] = useState("home");
  const [profileUsername, setProfileUsername] = useState(null);

  useEffect(() => {
    getCurrentUser();
  }, []);

  const getCurrentUser = async () => {
    try {
      // For now, we'll get username from localStorage
      // In a real app, you'd fetch this from an API endpoint
      const token = localStorage.getItem("access");
      if (token) {
        // Decode JWT token to get username (simplified)
        try {
          const payload = JSON.parse(atob(token.split(".")[1]));
          setCurrentUser({ username: payload.username || "user" });
        } catch {
          // Fallback to stored username or default
          const storedUsername = localStorage.getItem("username") || "user";
          setCurrentUser({ username: storedUsername });
        }
      }
    } catch (error) {
      console.error("Error getting current user:", error);
      setCurrentUser({ username: "user" });
    }
  };

  const handleUploadSuccess = () => {
    setShowUpload(false);
    setRefreshFeed((prev) => prev + 1); // Trigger feed refresh
  };

  const handleProfileView = (username = null) => {
    setProfileUsername(username || currentUser?.username);
    setCurrentView("profile");
  };

  const handleBackToHome = () => {
    setCurrentView("home");
    setProfileUsername(null);
  };

  const renderCurrentView = () => {
    switch (currentView) {
      case "profile":
        return (
          <Profile username={profileUsername} onClose={handleBackToHome} />
        );
      case "home":
      default:
        return <ShortsFeed key={refreshFeed} />;
    }
  };

  return (
    <div className="home-container">
      <Navigation
        onCreateShort={() => setShowUpload(true)}
        onProfileClick={() => handleProfileView()}
        currentUser={currentUser}
        currentView={currentView}
        onViewChange={setCurrentView}
      />

      <main className="main-content">{renderCurrentView()}</main>

      {showUpload && (
        <VideoUpload
          onUploadSuccess={handleUploadSuccess}
          onClose={() => setShowUpload(false)}
        />
      )}
    </div>
  );
}

export default Home;
