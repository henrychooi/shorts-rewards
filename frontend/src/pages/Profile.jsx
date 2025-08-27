import { useState, useEffect } from "react";
import { shortsApi } from "../services/shortsApi";
import VideoPlayer from "../components/VideoPlayer";
import "./Profile.css";

const Profile = ({ username, onClose }) => {
  const [profile, setProfile] = useState(null);
  const [shorts, setShorts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedShort, setSelectedShort] = useState(null);

  useEffect(() => {
    if (username) {
      loadProfile();
    }
  }, [username]);

  const loadProfile = async () => {
    try {
      setLoading(true);
      const response = await shortsApi.getUserProfile(username);
      setProfile(response.data.user);
      setShorts(response.data.shorts);
    } catch (error) {
      console.error("Error loading profile:", error);
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

  if (loading) {
    return (
      <div className="profile-loading">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Loading profile...</p>
        </div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="profile-error">
        <h3>Profile not found</h3>
        <button onClick={onClose}>Go Back</button>
      </div>
    );
  }

  return (
    <div className="profile-overlay">
      <div className="profile-container">
        <div className="profile-header">
          <button className="back-btn" onClick={onClose}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" />
            </svg>
          </button>
          <h2>Profile</h2>
        </div>

        <div className="profile-info">
          <div className="profile-avatar">
            {profile.username.charAt(0).toUpperCase()}
          </div>
          <h1 className="profile-username">@{profile.username}</h1>

          <div className="profile-stats">
            <div className="stat">
              <span className="stat-number">
                {formatCount(profile.shorts_count)}
              </span>
              <span className="stat-label">Shorts</span>
            </div>
            <div className="stat">
              <span className="stat-number">
                {formatCount(profile.total_likes)}
              </span>
              <span className="stat-label">Likes</span>
            </div>
          </div>
        </div>

        <div className="profile-content">
          <div className="shorts-grid">
            {shorts.length > 0 ? (
              shorts.map((short) => (
                <div
                  key={short.id}
                  className="short-thumbnail"
                  onClick={() => handleVideoClick(short)}
                >
                  <video src={short.video} className="thumbnail-video" muted />
                  <div className="thumbnail-overlay">
                    <div className="play-icon">
                      <svg
                        width="24"
                        height="24"
                        viewBox="0 0 24 24"
                        fill="white"
                      >
                        <path d="M8 5v14l11-7z" />
                      </svg>
                    </div>
                    <div className="video-stats">
                      <span className="views">
                        <svg
                          width="16"
                          height="16"
                          viewBox="0 0 24 24"
                          fill="currentColor"
                        >
                          <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z" />
                        </svg>
                        {formatCount(short.view_count)}
                      </span>
                      <span className="likes">
                        <svg
                          width="16"
                          height="16"
                          viewBox="0 0 24 24"
                          fill="currentColor"
                        >
                          <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
                        </svg>
                        {formatCount(short.like_count)}
                      </span>
                    </div>
                  </div>
                  {short.title && (
                    <div className="thumbnail-title">{short.title}</div>
                  )}
                </div>
              ))
            ) : (
              <div className="no-shorts">
                <svg
                  width="64"
                  height="64"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z" />
                </svg>
                <h3>No shorts yet</h3>
                <p>Start creating amazing short videos!</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {selectedShort && (
        <div className="video-modal">
          <div className="video-modal-content">
            <button
              className="close-modal"
              onClick={() => setSelectedShort(null)}
            >
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
              </svg>
            </button>
            <VideoPlayer short={selectedShort} isActive={true} />
          </div>
        </div>
      )}
    </div>
  );
};

export default Profile;
