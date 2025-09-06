import { useState, useEffect, useRef } from "react";
import { shortsApi } from "../services/shortsApi";
import VideoPlayer from "../components/VideoPlayer";
import "./Profile.css";
import api from "../api";
import { ACCESS_TOKEN, REFRESH_TOKEN } from "../constants";

const Profile = ({ username, onClose }) => {
  const [profile, setProfile] = useState(null);
  const [shorts, setShorts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedShort, setSelectedShort] = useState(null);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [deletingShortId, setDeletingShortId] = useState(null);
  const currentUsername = typeof window !== 'undefined' ? localStorage.getItem('username') : null;
  const menuRef = useRef(null);
  const menuBtnRef = useRef(null);

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

  const canDeleteAccount = username && currentUsername && username === currentUsername;
  const canModifyShorts = canDeleteAccount;

  // Close header dropdown on outside click
  useEffect(() => {
    const onDocClick = (e) => {
      if (!showMenu) return;
      const menuEl = menuRef.current;
      const btnEl = menuBtnRef.current;
      if (menuEl && menuEl.contains(e.target)) return;
      if (btnEl && btnEl.contains(e.target)) return;
      setShowMenu(false);
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [showMenu]);

  const handleDeleteAccount = async () => {
    try {
      setDeleting(true);
      const resp = await api.post("/api/user/delete-account/", { confirm: deleteConfirm });
      if (resp.data?.success) {
        // Clear tokens and redirect to login
        localStorage.removeItem(ACCESS_TOKEN);
        localStorage.removeItem(REFRESH_TOKEN);
        localStorage.removeItem("username");
        window.location.href = "/login";
      }
    } catch (err) {
      alert(err?.response?.data?.error || "Failed to delete account");
    } finally {
      setDeleting(false);
    }
  };

  const handleDeleteShort = async (shortId) => {
    if (!canModifyShorts) return;
    const confirmMsg = "Delete this short? This cannot be undone.";
    if (!window.confirm(confirmMsg)) return;
    try {
      setDeletingShortId(shortId);
      await shortsApi.deleteShort(shortId);
      setShorts((prev) => prev.filter((s) => s.id !== shortId));
    } catch (err) {
      console.error("Failed to delete short", err);
      alert(err?.response?.data?.detail || "Failed to delete short");
    } finally {
      setDeletingShortId(null);
    }
  };

  if (loading) {
    return (
      <div className="profile-loading">
        <div className="loading-container">
          <div className="loading-spinner" />
          <p>Loading profile...</p>
        </div>
      </div>
    );
  }

  if (error && !profile) {
    return (
      <div className="profile-error">
        <h3>Failed to load profile</h3>
        <button onClick={handleRetry}>Retry</button>
        <button onClick={onClose}>Go Back</button>
      </div>
    );
  }

  return (
    <div className="profile-overlay">
      <div className="profile-container">
        {/* Animated background elements */}
        <div className="background-gradient-1"></div>
        <div className="background-gradient-2"></div>
        <div className="background-gradient-3"></div>

        <div className="profile-header">
          <div className="header-left">
            <button className="back-btn" onClick={onClose}>
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M20 11H7.83l5.59-5.59L12 4l-8 8 8 8 1.41-1.41L7.83 13H20v-2z" />
              </svg>
            </button>
            <h2>Profile</h2>
          </div>

          <div className="header-actions">
            <button className="action-btn">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92s2.92-1.31 2.92-2.92-1.31-2.92-2.92-2.92z" />
              </svg>
            </button>
            <div style={{ position: 'relative' }}>
              <button className="action-btn" ref={menuBtnRef} onClick={() => setShowMenu((v) => !v)}>
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z" />
                </svg>
              </button>
              {showMenu && (
                <div ref={menuRef} style={{ position: 'absolute', top: 36, right: 0, background: '#111', border: '1px solid #333', borderRadius: 8, padding: 8, minWidth: 180, boxShadow: '0 8px 24px rgba(0,0,0,0.4)', zIndex: 5 }}>
                  <button
                    className="action-btn"
                    onClick={() => { setShowMenu(false); /* hook up edit later */ }}
                    style={{ width: '100%', justifyContent: 'flex-start', padding: '8px 10px', background: 'transparent' }}
                  >
                    Edit Profile
                  </button>
                  {canDeleteAccount && (
                    <button
                      className="action-btn"
                      onClick={() => { setShowMenu(false); setShowDeleteModal(true); }}
                      style={{ width: '100%', justifyContent: 'flex-start', padding: '8px 10px', color: '#ff6b6b', background: 'transparent' }}
                    >
                      Delete Account
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Profile Info */}
        <div className="profile-info">
          <div className="profile-avatar">
            <div className="profile-avatar-inner">
              {profile?.username?.charAt(0).toUpperCase() || "U"}
            </div>
          </div>

          <h1 className="profile-username">@{profile?.username || "user"}</h1>
          <p className="profile-subtitle">Content Creator & Storyteller</p>

          <button className="profile-edit-btn">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
            </svg>
            Edit Profile
          </button>

          <div className="profile-stats">
            <div className="stat">
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
            </div>

            <div className="stat">
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
            </div>

            <div className="stat">
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

        {/* Content Section */}
        <div className="profile-content">
          <div className="content-header">
            <h3>Latest Shorts</h3>
          </div>

          <div className="shorts-grid">
            {shorts.length > 0 ? (
              shorts.map((short, index) => (
                <div
                  key={short.id}
                  className="short-thumbnail"
                  onClick={() => handleVideoClick(short)}
                  style={{
                    animationDelay: `${index * 100}ms`,
                  }}
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
                    {canModifyShorts && (
                      <button
                        className="delete-short-btn"
                        title="Delete short"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteShort(short.id);
                        }}
                        disabled={deletingShortId === short.id}
                      >
                        {deletingShortId === short.id ? (
                          <span style={{ fontSize: 12 }}>Deleting…</span>
                        ) : (
                          <svg
                            width="18"
                            height="18"
                            viewBox="0 0 24 24"
                            fill="currentColor"
                          >
                            <path d="M16 9v10H8V9h8m-1.5-6h-5l-1 1H5v2h14V4h-3.5l-1-1z" />
                          </svg>
                        )}
                      </button>
                    )}
                  </div>
                </div>
              ))
            ) : (
              <div className="no-shorts">
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

      {showDeleteModal && (
        <div className="video-modal">
          <div className="video-modal-content" style={{ maxWidth: 420 }}>
            <h3 style={{ marginBottom: 8 }}>Delete Account</h3>
            <p style={{ fontSize: 14, opacity: 0.8 }}>
              This action permanently deletes your account and all related data.
              Type <b>DELETE</b> or your username (<b>{currentUsername}</b>) to confirm.
            </p>
            <input
              type="text"
              placeholder="Type DELETE or your username"
              value={deleteConfirm}
              onChange={(e) => setDeleteConfirm(e.target.value)}
              style={{ width: "100%", marginTop: 12, padding: 10, borderRadius: 8, border: "1px solid #444", background: "#111", color: "#fff" }}
            />
            <div style={{ display: "flex", gap: 12, marginTop: 16, justifyContent: "flex-end" }}>
              <button className="close-modal" onClick={() => setShowDeleteModal(false)}>
                Cancel
              </button>
              <button
                className="close-modal"
                disabled={deleting || !(deleteConfirm === 'DELETE' || deleteConfirm === currentUsername)}
                onClick={handleDeleteAccount}
                style={{ background: "#b00020", borderColor: "#b00020" }}
              >
                {deleting ? "Deleting..." : "Confirm Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Profile;
