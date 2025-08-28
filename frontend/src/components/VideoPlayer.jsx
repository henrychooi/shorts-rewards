import { useState, useRef, useEffect } from "react";
import { shortsApi } from "../services/shortsApi";
import "./VideoPlayer.css";

const VideoPlayer = ({ short, isActive, onProfileClick }) => {
  const videoRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLiked, setIsLiked] = useState(short.is_liked);
  const [likeCount, setLikeCount] = useState(short.like_count);
  const [showComments, setShowComments] = useState(false);
  const [comments, setComments] = useState([]);
  const [newComment, setNewComment] = useState("");
  const [viewTracked, setViewTracked] = useState(false);
  const watchTimeRef = useRef(0);
  const watchStartRef = useRef(null);

  useEffect(() => {
    if (isActive && videoRef.current) {
      videoRef.current.play();
      setIsPlaying(true);
      watchStartRef.current = Date.now();
    } else if (videoRef.current) {
      videoRef.current.pause();
      setIsPlaying(false);
      if (watchStartRef.current) {
        watchTimeRef.current += (Date.now() - watchStartRef.current) / 1000;
        watchStartRef.current = null;
      }
    }
  }, [isActive]);

  useEffect(() => {
    // Track view after 3 seconds of watch time
    if (watchTimeRef.current >= 3 && !viewTracked) {
      shortsApi.trackView(short.id, watchTimeRef.current);
      setViewTracked(true);
    }
  }, [short.id, viewTracked]);

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
          muted
          playsInline
          onClick={togglePlay}
          onEnded={() => setIsPlaying(false)}
        />

        {!isPlaying && (
          <div className="play-overlay" onClick={togglePlay}>
            <div className="play-button">
              <svg width="60" height="60" viewBox="0 0 24 24" fill="white">
                <path d="M8 5v14l11-7z" />
              </svg>
            </div>
          </div>
        )}

        {/* NEW: video-info now contains a white card (.video-info-card)
            that visually groups user-info + title + description + stats */}
        <div className="video-info">
          <div className="video-info-card">
            <div
              className="user-info"
              onClick={() => onProfileClick && onProfileClick(short.author.username)}
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

            {/* title + description are inside the same white card (visually bounded to user-info) */}
            {short.title && <h4 className="video-title">{short.title}</h4>}
            {short.description && (
              <p className="video-description">{short.description}</p>
            )}

            <div className="video-stats">
              <span className="stat" aria-hidden>
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
            </div>
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
            fill={isLiked ? "#ff3040" : "currentColor"}
          >
            <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" />
          </svg>
          <span>{formatCount(likeCount)}</span>
        </button>

        <button className="action-btn comment-btn" onClick={toggleComments}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
            <path d="M21.99 4c0-1.1-.89-2-2-2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h14l4 4-.01-18zM18 14H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z" />
          </svg>
          <span>{formatCount(short.comment_count)}</span>
        </button>

        <button className="action-btn share-btn">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
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
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
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

          <form className="comment-form" onSubmit={handleComment}>
            <input
              type="text"
              placeholder="Add a comment..."
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
              className="comment-input"
            />
            <button type="submit" className="comment-submit">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
              </svg>
            </button>
          </form>
        </div>
      </>
      )}
    </div>
  );
};

export default VideoPlayer;
