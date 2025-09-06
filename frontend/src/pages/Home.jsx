import { useState, useEffect } from "react";
import ShortsFeed from "../components/ShortsFeed";
import VideoUpload from "../components/VideoUpload";
import Navigation from "../components/Navigation";
import Profile from "./Profile";
import Wallet from "../components/Wallet";
import api from "../api";
import { shortsApi } from "../services/shortsApi";
import { useViewCount } from "../contexts/ViewCountContext";
import { useLikeCount } from "../contexts/LikeCountContext";
import "../styles/Home.css";

// Helper function to format numbers
const formatCount = (count) => {
  if (count >= 1000000) {
    return (count / 1000000).toFixed(1) + "M";
  } else if (count >= 1000) {
    return (count / 1000).toFixed(1) + "K";
  }
  return count.toString();
};

function Home() {
  const [showUpload, setShowUpload] = useState(false);
  const [showWallet, setShowWallet] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [refreshFeed, setRefreshFeed] = useState(0);
  const [currentView, setCurrentView] = useState("home");
  const [profileUsername, setProfileUsername] = useState(null);
  const [previewShorts, setPreviewShorts] = useState([]);
  const [loadingShorts, setLoadingShorts] = useState(true);
  const { viewCounts } = useViewCount();
  const { likeCounts } = useLikeCount();

  useEffect(() => {
    getCurrentUser();
    loadPreviewShorts();
  }, []);

  // Refresh preview shorts when returning to home view
  useEffect(() => {
    if (currentView === "home") {
      loadPreviewShorts();
    }
  }, [currentView]);

  const loadPreviewShorts = async () => {
    try {
      setLoadingShorts(true);
      const response = await shortsApi.getShorts();
      if (response.data && Array.isArray(response.data)) {
        // Take first 6 shorts for preview
        setPreviewShorts(response.data.slice(0, 6));
      } else {
        // Fallback to mock data
        setPreviewShorts([
          {
            id: 1,
            title: "Sample Short 1",
            view_count: 12500,
            like_count: 890,
          },
          { id: 2, title: "Sample Short 2", view_count: 8200, like_count: 650 },
          {
            id: 3,
            title: "Sample Short 3",
            view_count: 15600,
            like_count: 1200,
          },
          { id: 4, title: "Sample Short 4", view_count: 9800, like_count: 540 },
          {
            id: 5,
            title: "Sample Short 5",
            view_count: 22100,
            like_count: 1800,
          },
          { id: 6, title: "Sample Short 6", view_count: 7300, like_count: 420 },
        ]);
      }
    } catch (error) {
      console.error("Error loading preview shorts:", error);
      // Set fallback data
      setPreviewShorts([
        { id: 1, title: "Sample Short 1", view_count: 12500, like_count: 890 },
        { id: 2, title: "Sample Short 2", view_count: 8200, like_count: 650 },
        { id: 3, title: "Sample Short 3", view_count: 15600, like_count: 1200 },
        { id: 4, title: "Sample Short 4", view_count: 9800, like_count: 540 },
        { id: 5, title: "Sample Short 5", view_count: 22100, like_count: 1800 },
        { id: 6, title: "Sample Short 6", view_count: 7300, like_count: 420 },
      ]);
    } finally {
      setLoadingShorts(false);
    }
  };

  const getCurrentUser = () => {
    const storedUsername = localStorage.getItem("username");
    if (storedUsername) {
      setCurrentUser({ username: storedUsername });
    } else {
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

  const handleWalletView = () => {
    setShowWallet(true);
  };

  const handleCloseWallet = () => {
    setShowWallet(false);
  };

  const renderCurrentView = () => {
    switch (currentView) {
      case "profile":
        return (
          <Profile username={profileUsername} onClose={handleBackToHome} />
        );
      case "feed":
        return (
          <div className="feed-view">
            <div className="feed-header">
              <button
                className="back-btn-feed"
                onClick={() => setCurrentView("home")}
              >
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" />
                </svg>
              </button>
              <h2>All Shorts</h2>
            </div>
            <ShortsFeed 
              key={`${refreshFeed}-${currentView}`} 
              onProfileClick={handleProfileView} 
            />
          </div>
        );
      case "home":
      default:
        return (
          <div className="content-wrapper">
            {/* Welcome Section */}
            <div className="home-welcome">
              <h1>Welcome to ShortsHub</h1>
              <p>
                Discover amazing short videos, connect with creators, and share
                your own stories with the world.
              </p>

              <div className="home-actions">
                <button
                  className="home-action-btn"
                  onClick={() => setShowUpload(true)}
                >
                  <svg
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M23 7l-7 5 7 5V7z" />
                    <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
                  </svg>
                  Create Short
                </button>
              </div>
            </div>

            {/* Stats Section */}
            <div className="home-stats">
              <div className="home-stat-card">
                <div className="home-stat-icon">
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M23 7l-7 5 7 5V7z" />
                    <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
                  </svg>
                </div>
                <div className="home-stat-number">1.2K</div>
                <div className="home-stat-label">Total Shorts</div>
              </div>

              <div className="home-stat-card">
                <div className="home-stat-icon">
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                </div>
                <div className="home-stat-number">45.6M</div>
                <div className="home-stat-label">Total Views</div>
              </div>

              <div className="home-stat-card">
                <div className="home-stat-icon">
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                    <circle cx="9" cy="7" r="4" />
                    <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                  </svg>
                </div>
                <div className="home-stat-number">8.9K</div>
                <div className="home-stat-label">Creators</div>
              </div>
            </div>

            {/* Shorts Feed */}
            <div className="home-content-section">
              <div className="content-section-header">
                <h2>Trending Shorts</h2>
                <p>Discover the most popular short videos</p>
              </div>

              <div className="modern-shorts-preview">
                <div className="shorts-preview-grid">
                  {loadingShorts
                    ? // Loading state
                      [1, 2, 3, 4, 5, 6].map((item) => (
                        <div key={item} className="preview-short-card loading">
                          <div className="preview-video-placeholder">
                            <div className="loading-spinner"></div>
                          </div>
                        </div>
                      ))
                    : // Real data
                      previewShorts.map((short) => (
                        <div
                          key={short.id}
                          className="preview-short-card"
                          onClick={() => setCurrentView("feed")}
                        >
                          <div
                            className={`preview-video-placeholder ${
                              short.video ? "has-video" : ""
                            }`}
                          >
                            <div className="preview-play-btn">
                              <svg
                                width="24"
                                height="24"
                                viewBox="0 0 24 24"
                                fill="white"
                              >
                                <path d="M8 5v14l11-7z" />
                              </svg>
                            </div>
                            {short.video && (
                              <video
                                className="preview-video-thumbnail"
                                src={short.video}
                                muted
                                playsInline
                              />
                            )}
                          </div>
                          <div className="preview-short-info">
                            <div className="preview-title">
                              {short.title || "Untitled"}
                            </div>
                            <div className="preview-stats">
                              <span>
                                <svg
                                  width="14"
                                  height="14"
                                  viewBox="0 0 24 24"
                                  fill="currentColor"
                                >
                                  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                                  <circle cx="12" cy="12" r="3" />
                                </svg>
                                {formatCount(viewCounts[short.id] || short.view_count || 0)}
                              </span>
                              <span>
                                <svg
                                  width="14"
                                  height="14"
                                  viewBox="0 0 24 24"
                                  fill="currentColor"
                                >
                                  <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                                </svg>
                                {formatCount(likeCounts[short.id]?.likeCount ?? short.like_count ?? 0)}
                              </span>
                            </div>
                          </div>
                        </div>
                      ))}
                </div>

                <div className="view-all-section">
                  <button
                    className="view-all-btn"
                    onClick={() => setCurrentView("feed")}
                  >
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <path d="M23 7l-7 5 7 5V7z" />
                      <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
                    </svg>
                    View All Shorts
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
    }
  };

  return (
    <div
      className={`home-container ${
        currentView === "profile" || currentView === "feed"
          ? "profile-view"
          : ""
      }`}
    >
      {/* Animated background decorations */}
      <div className="home-bg-decoration home-bg-decoration-1"></div>
      <div className="home-bg-decoration home-bg-decoration-2"></div>
      <div className="home-bg-decoration home-bg-decoration-3"></div>

      <Navigation
        onCreateShort={() => setShowUpload(true)}
        onProfileClick={() => handleProfileView()}
        onWalletClick={handleWalletView}
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

      {showWallet && <Wallet onClose={handleCloseWallet} />}
    </div>
  );
}

export default Home;
