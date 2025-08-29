import { useState, useEffect } from "react";
import { shortsApi } from "../services/shortsApi";
import VideoPlayer from "../components/VideoPlayer";
import "./Profile.css";

const Profile = ({ username, onClose }) => {
  const [profile, setProfile] = useState(null);
  const [shorts, setShorts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedShort, setSelectedShort] = useState(null);

  useEffect(() => {
    if (username) {
      loadProfile();
    }
  }, [username]);

  const loadProfile = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await shortsApi.getUserProfile(username);
      setProfile(response.data.user);
      setShorts(response.data.shorts);
    } catch (error) {
      console.error("Error loading profile:", error);
      setError("Failed to load profile");
      // Set mock data for demo
      setProfile({
        username: username || "user",
        shorts_count: 24,
        total_views: 125000,
        total_likes: 8500,
      });
      setShorts([
        {
          id: "1",
          video: "/api/placeholder/400/600",
          view_count: 12500,
          like_count: 890,
        },
        {
          id: "2",
          video: "/api/placeholder/400/600",
          view_count: 8200,
          like_count: 650,
        },
        {
          id: "3",
          video: "/api/placeholder/400/600",
          view_count: 15600,
          like_count: 1200,
        },
        {
          id: "4",
          video: "/api/placeholder/400/600",
          view_count: 9800,
          like_count: 720,
        },
        {
          id: "5",
          video: "/api/placeholder/400/600",
          view_count: 22100,
          like_count: 1800,
        },
        {
          id: "6",
          video: "/api/placeholder/400/600",
          view_count: 6700,
          like_count: 450,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const formatCount = (count) => {
    if (count >= 1000000) {
      return `${(count / 1000000).toFixed(1)}M`;
    } else if (count >= 1000) {
      return `${(count / 1000).toFixed(1)}K`;
    }
    return count.toString();
  };

  const handleVideoClick = (short) => {
    setSelectedShort(short);
  };

  const handleRetry = () => {
    loadProfile();
  };

  if (loading) {
    return (
      <div className="modern-profile-loading">
        <div className="background-blur-1" />
        <div className="background-blur-2" />

        <div className="loading-container">
          <div className="modern-spinner" />
          <p className="loading-text">Loading profile...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="modern-profile-overlay">
      {/* Background decorative elements */}
      <div className="bg-decoration-1" />
      <div className="bg-decoration-2" />
      <div className="bg-decoration-3" />

      <div className="modern-profile-container">
        {/* Header */}
        <div className="modern-profile-header">
          <div className="header-left">
            <button onClick={onClose} className="modern-back-btn">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M19 12H5M12 19l-7-7 7-7" />
              </svg>
            </button>
            <h2 className="header-title">Profile</h2>
          </div>

          <div className="header-actions">
            <button className="action-btn">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8" />
                <polyline points="16,6 12,2 8,6" />
                <line x1="12" y1="2" x2="12" y2="15" />
              </svg>
            </button>
            <button className="action-btn">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <circle cx="12" cy="12" r="1" />
                <circle cx="19" cy="12" r="1" />
                <circle cx="5" cy="12" r="1" />
              </svg>
            </button>
          </div>
        </div>

        {/* Profile Info */}
        <div className="modern-profile-info">
          <div className="profile-info-bg" />

          <div className="profile-content">
            <div className="avatar-container">
              <div className="avatar-ring" />
              <div className="modern-avatar">
                {profile?.username?.charAt(0).toUpperCase() || "U"}
              </div>
            </div>

            <h1 className="profile-username">@{profile?.username || "user"}</h1>
            <p className="profile-subtitle">Content Creator & Storyteller</p>

            <button className="edit-profile-btn">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M20 6L9 17l-5-5" />
              </svg>
              Edit Profile
            </button>

            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-icon">
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M23 7l-7 5 7 5V7z" />
                    <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
                  </svg>
                </div>
                <div className="stat-number">
                  {formatCount(profile?.shorts_count || 0)}
                </div>
                <div className="stat-label">Shorts</div>
              </div>

              <div className="stat-card">
                <div className="stat-icon">
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </svg>
                </div>
                <div className="stat-number">
                  {formatCount(profile?.total_views || 0)}
                </div>
                <div className="stat-label">Views</div>
              </div>

              <div className="stat-card">
                <div className="stat-icon">
                  <svg
                    width="20"
                    height="20"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                  </svg>
                </div>
                <div className="stat-number">
                  {formatCount(profile?.total_likes || 0)}
                </div>
                <div className="stat-label">Likes</div>
              </div>
            </div>
          </div>
        </div>

        {/* Shorts Grid */}
        <div className="modern-content-section">
          <div className="content-container">
            <h3 className="section-title">Latest Shorts</h3>

            {shorts.length > 0 ? (
              <div className="modern-shorts-grid">
                {shorts.map((short, index) => (
                  <div
                    key={short.id}
                    className="modern-short-card"
                    onClick={() => handleVideoClick(short)}
                    style={{ animationDelay: `${index * 100}ms` }}
                  >
                    <img
                      src={short.video || "/api/placeholder/400/600"}
                      alt="Video thumbnail"
                      className="short-thumbnail"
                    />

                    <div className="short-overlay">
                      <div className="play-button">
                        <svg
                          width="20"
                          height="20"
                          viewBox="0 0 24 24"
                          fill="currentColor"
                        >
                          <polygon points="5,3 19,12 5,21" />
                        </svg>
                      </div>

                      <div className="short-stats">
                        <div className="stat-chip">
                          <svg
                            width="12"
                            height="12"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                          >
                            <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                            <circle cx="12" cy="12" r="3" />
                          </svg>
                          {formatCount(short.view_count)}
                        </div>
                        <div className="stat-chip">
                          <svg
                            width="12"
                            height="12"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                          >
                            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
                          </svg>
                          {formatCount(short.like_count)}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <svg
                  width="64"
                  height="64"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1"
                >
                  <path d="M23 7l-7 5 7 5V7z" />
                  <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
                </svg>
                <h3>No shorts yet</h3>
                <p>Start creating amazing short videos!</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Video Modal */}
      {selectedShort && (
        <div className="modern-video-modal">
          <div className="modal-content">
            <button
              onClick={() => setSelectedShort(null)}
              className="modal-close-btn"
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <path d="M19 12H5M12 19l-7-7 7-7" />
              </svg>
            </button>

            <div className="video-placeholder">
              <svg
                width="64"
                height="64"
                viewBox="0 0 24 24"
                fill="currentColor"
                opacity="0.5"
              >
                <polygon points="5,3 19,12 5,21" />
              </svg>
              <p className="video-title">Video Player</p>
              <p className="video-stats">
                {formatCount(selectedShort.view_count)} views •{" "}
                {formatCount(selectedShort.like_count)} likes
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Profile;
