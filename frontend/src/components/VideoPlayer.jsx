import { useState, useRef, useEffect } from "react";
import { shortsApi } from "../services/shortsApi";
import "./VideoPlayer.css";

const VideoPlayer = ({ short, isActive, onProfileClick }) => {
  const videoRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false); // Start with audio enabled
  const [isLiked, setIsLiked] = useState(short.is_liked);
  const [likeCount, setLikeCount] = useState(short.like_count);
  const [viewCount, setViewCount] = useState(short.view_count);
  const [showComments, setShowComments] = useState(false);
  const [comments, setComments] = useState([]);
  const [newComment, setNewComment] = useState("");
  const [viewTracked, setViewTracked] = useState(false);

  // Enhanced watch tracking
  const [watchProgress, setWatchProgress] = useState({
    watchPercentage: 0,
    isCompleteView: false,
    rewatchCount: 0,
    engagementScore: 0,
  });

  const watchTimeRef = useRef(0);
  const watchStartRef = useRef(null);
  const viewTrackingTimer = useRef(null);
  const progressTrackingTimer = useRef(null);
  const sessionId = useRef(Math.random().toString(36).substring(2, 15));
  const hasTrackedInitialView = useRef(false);
  const lastTrackedPosition = useRef(0);
  const maxWatchedPosition = useRef(0);

  // Handle video play/pause based on isActive
  useEffect(() => {
    if (isActive && videoRef.current) {
      videoRef.current.play();
      setIsPlaying(true);
      watchStartRef.current = Date.now();

      // Start view tracking timer (track basic view first)
      if (!viewTracked) {
        viewTrackingTimer.current = setTimeout(() => {
          trackView();
        }, 10); // Track after 0.1 seconds
      }

      // Start progress tracking timer
      progressTrackingTimer.current = setInterval(() => {
        trackWatchProgress();
      }, 2000); // Track progress every 2 seconds
    } else if (videoRef.current) {
      videoRef.current.pause();
      setIsPlaying(false);

      // Clear tracking timers
      if (viewTrackingTimer.current) {
        clearTimeout(viewTrackingTimer.current);
        viewTrackingTimer.current = null;
      }

      if (progressTrackingTimer.current) {
        clearInterval(progressTrackingTimer.current);
        progressTrackingTimer.current = null;
      }

      // Update watch time and track final progress
      if (watchStartRef.current) {
        watchTimeRef.current += (Date.now() - watchStartRef.current) / 1000;
        watchStartRef.current = null;
        trackWatchProgress(); // Final progress update
      }
    }

    // Cleanup timers on unmount or when isActive changes
    return () => {
      if (viewTrackingTimer.current) {
        clearTimeout(viewTrackingTimer.current);
        viewTrackingTimer.current = null;
      }
      if (progressTrackingTimer.current) {
        clearInterval(progressTrackingTimer.current);
        progressTrackingTimer.current = null;
      }
    };
  }, [isActive, viewTracked]);

  const trackView = async () => {
    if (viewTracked) return;

    try {
      console.log(`Tracking view for short: ${short.id}`);
      const response = await shortsApi.trackView(
        short.id,
        watchTimeRef.current || 1.0
      );

      if (response.data.status === "success") {
        setViewTracked(true);
        setViewCount(response.data.view_count);
        console.log(`View tracked! New count: ${response.data.view_count}`);
      }
    } catch (error) {
      console.error("Error tracking view:", error);
    }
  };

  const trackWatchProgress = async () => {
    if (!videoRef.current) return;

    try {
      const currentTime = videoRef.current.currentTime;
      const videoDuration = videoRef.current.duration || short.duration;

      // Update total watch time if video is playing
      if (watchStartRef.current && !videoRef.current.paused) {
        watchTimeRef.current += (Date.now() - watchStartRef.current) / 1000;
        watchStartRef.current = Date.now(); // Reset the timer
      }

      const totalWatchTime = watchTimeRef.current;

      // Don't track if we don't have valid duration
      if (!videoDuration || videoDuration <= 0) {
        return;
      }

      // Update max watched position
      if (currentTime > maxWatchedPosition.current) {
        maxWatchedPosition.current = currentTime;
      }

      // Check if it's a rewatch (user went back to beginning after watching significant portion)
      const isRewatch =
        currentTime < lastTrackedPosition.current - 10 &&
        lastTrackedPosition.current > videoDuration * 0.3;

      const progressData = {
        current_position: currentTime,
        duration_watched: totalWatchTime,
        session_id: sessionId.current,
        is_rewatch: isRewatch,
      };

      const response = await shortsApi.trackWatchProgress(
        short.id,
        progressData
      );

      if (response.data.status === "success") {
        setWatchProgress({
          watchPercentage: response.data.watch_percentage,
          isCompleteView: response.data.is_complete_view,
          rewatchCount: response.data.rewatch_count,
          engagementScore: response.data.engagement_score,
        });

        console.log(`Watch progress: ${response.data.watch_percentage}%`);
      }

      lastTrackedPosition.current = currentTime;
    } catch (error) {
      console.error("Error tracking watch progress:", error);
    }
  };

  const togglePlay = () => {
    if (!videoRef.current) return;

    if (videoRef.current.paused) {
      videoRef.current.play();
      setIsPlaying(true);
      watchStartRef.current = Date.now();
    } else {
      videoRef.current.pause();
      setIsPlaying(false);
      if (watchStartRef.current) {
        watchTimeRef.current += (Date.now() - watchStartRef.current) / 1000;
        watchStartRef.current = null;
      }
    }
  };

  const toggleMute = (e) => {
    e.stopPropagation(); // Prevent triggering play/pause
    if (!videoRef.current) return;

    setIsMuted(!isMuted);
    videoRef.current.muted = !isMuted;
  };

  const handleLike = async () => {
    try {
      const response = await shortsApi.toggleLike(short.id);
      setIsLiked(response.data.liked);
      setLikeCount(response.data.like_count);
    } catch (error) {
      console.error("Error toggling like:", error);
    }
  };

  const handleComment = async (e) => {
    e.preventDefault();
    if (!newComment.trim()) return;

    try {
      await shortsApi.addComment(short.id, newComment);
      setNewComment("");
      loadComments();
    } catch (error) {
      console.error("Error adding comment:", error);
    }
  };

  const loadComments = async () => {
    try {
      const response = await shortsApi.getComments(short.id);
      setComments(response.data);
    } catch (error) {
      console.error("Error loading comments:", error);
    }
  };

  const toggleComments = () => {
    setShowComments((prev) => !prev);
    if (!showComments && comments.length === 0) {
      loadComments();
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

  const formatTimeAgo = (dateString) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffInSeconds = Math.floor((now - date) / 1000);

    if (diffInSeconds < 60) return "just now";
    if (diffInSeconds < 3600) return `${Math.floor(diffInSeconds / 60)}m ago`;
    if (diffInSeconds < 86400)
      return `${Math.floor(diffInSeconds / 3600)}h ago`;
    return `${Math.floor(diffInSeconds / 86400)}d ago`;
  };

  return (
    <div className="video-container">
      <div className="video-wrapper">
        <video
          ref={videoRef}
          className="video-player"
          src={short.video}
          loop
          muted={isMuted}
          playsInline
          preload="metadata"
          onClick={togglePlay}
          onEnded={() => setIsPlaying(false)}
          onLoadedData={() => {
            console.log("Video loaded for:", short.title);
            // Auto-play when active and video is loaded
            if (isActive && videoRef.current) {
              videoRef.current.play().catch(console.error);
            }
          }}
          onError={(e) => {
            console.error("Video loading error:", e);
          }}
        />

        {!isPlaying && (
          <div className="play-overlay" onClick={togglePlay}>
            <div className="play-button">
              <svg width="60" height="60" viewBox="0 0 24 24" fill="black">
                <path d="M8 5v14l11-7z" />
              </svg>
            </div>
          </div>
        )}

        <div className="video-info">
          <div
            className="user-info"
            onClick={() =>
              onProfileClick && onProfileClick(short.author.username)
            }
            style={{ cursor: "pointer" }}
          >
            <div className="avatar">
              {short.author.username.charAt(0).toUpperCase()}
            </div>
            <div className="user-details">
              <h3 className="username">@{short.author.username}</h3>
              <p className="timestamp">{formatTimeAgo(short.created_at)}</p>
            </div>
          </div>

          {short.title && <h4 className="video-title">{short.title}</h4>}
          {short.description && (
            <p className="video-description">{short.description}</p>
          )}

          <div className="video-stats">
            <span className="stat">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z" />
              </svg>
              {formatCount(viewCount)}
            </span>
          </div>
        </div>
      </div>

      <div className="action-buttons">
        <button
          className={`action-btn like-btn ${isLiked ? "liked" : ""}`}
          onClick={handleLike}
        >
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill={isLiked ? "#ff3040" : "white"}
          >
            <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
          </svg>
          <span>{formatCount(likeCount)}</span>
        </button>

        <button className="action-btn comment-btn" onClick={toggleComments}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
            <path d="M21.99 4c0-1.1-.89-2-2-2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14l4 4-.01-18zM18 14H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z" />
          </svg>
          <span>{formatCount(short.comment_count)}</span>
        </button>

        <button className="action-btn mute-btn" onClick={toggleMute}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
            {isMuted ? (
              // Muted icon (speaker with X)
              <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z" />
            ) : (
              // Unmuted icon (speaker)
              <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" />
            )}
          </svg>
        </button>

        <button className="action-btn share-btn">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
            <path d="M18 16.08c-.76 0-1.44.3-1.96.77L8.91 12.7c.05-.23.09-.46.09-.7s-.04-.47-.09-.7l7.05-4.11c.54.5 1.25.81 2.04.81 1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3c0 .24.04.47.09.7L8.04 9.81C7.5 9.31 6.79 9 6 9c-1.66 0-3 1.34-3 3s1.34 3 3 3c.79 0 1.5-.31 2.04-.81l7.12 4.16c-.05.21-.08.43-.08.65 0 1.61 1.31 2.92 2.92 2.92s2.92-1.31 2.92-2.92-1.31-2.92-2.92-2.92z" />
          </svg>
        </button>
      </div>

      {showComments && (
        <>
          <div className="page-overlay" onClick={toggleComments}></div>
          <div className="comments-overlay">
            <div className="comments-header">
              <h3>{formatCount(short.comment_count)} Comments</h3>
              <button className="close-comments" onClick={toggleComments}>
                <svg width="24" height="24" viewBox="0 0 24 24" fill="white">
                  <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
                </svg>
              </button>
            </div>

            <div className="comments-list">
              {comments.map((comment) => (
                <div key={comment.id} className="comment">
                  <div className="comment-avatar">
                    {comment.user.username.charAt(0).toUpperCase()}
                  </div>
                  <div className="comment-content">
                    <div className="comment-header">
                      <span className="comment-username">
                        @{comment.user.username}
                      </span>
                      <span className="comment-time">
                        {formatTimeAgo(comment.created_at)}
                      </span>
                    </div>
                    <p className="comment-text">{comment.content}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="comment-form">
              <input
                type="text"
                placeholder="Add a comment..."
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                onKeyPress={(e) => e.key === "Enter" && handleComment(e)}
                className="comment-input"
              />
              <button onClick={handleComment} className="comment-submit">
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="currentColor"
                >
                  <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
                </svg>
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default VideoPlayer;
