import React, { useState, useEffect, useRef } from "react";
import VideoPlayer from "./VideoPlayer";
import { shortsApi } from "../services/shortsApi";
import { useViewCount } from "../contexts/ViewCountContext";
import { useLikeCount } from "../contexts/LikeCountContext";
import "./ShortsFeed.css";

const ShortsFeed = ({ onProfileClick, feedType = "forYou" }) => {
  const [shorts, setShorts] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const containerRef = useRef(null);
  const touchStartY = useRef(0);
  const touchEndY = useRef(0);
  const { viewCounts } = useViewCount();
  const { likeCounts } = useLikeCount();

  useEffect(() => {
    loadShorts();
  }, [feedType]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "ArrowUp") {
        e.preventDefault();
        scrollToPrevious();
      } else if (e.key === "ArrowDown") {
        e.preventDefault();
        scrollToNext();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentIndex, shorts.length]);

  const loadShorts = async () => {
    try {
      setLoading(true);
      setError(null);
      console.log("🔄 Loading shorts from API...");

      // Try to fetch from API first
      const response = feedType === 'following' ? await shortsApi.getFollowingShorts() : await shortsApi.getShorts();
      console.log("📡 API Response:", response);

      if (response.data && Array.isArray(response.data)) {
        console.log("✅ Found", response.data.length, "shorts from API");
        // Map backend data structure to frontend expected format
        const mappedShorts = response.data.map((short) => ({
          id: short.id,
          title: short.title,
          description: short.description,
          video: short.video,
          username: short.author?.username || "Unknown",
          created_at: short.created_at,
          view_count: short.view_count || 0,
          like_count: short.like_count || 0,
          comment_count: short.comment_count || 0,
          is_liked: short.is_liked || false,
          is_following_author: short.is_following_author || short.author?.is_following || false,
          duration: short.duration,
          author: short.author,
          comments: short.comments || [],
        }));
        setShorts(mappedShorts);
      } else {
        throw new Error("Invalid API response format");
      }
    } catch (err) {
      console.error("❌ Error loading shorts from API:", err);
      console.log("🔄 Falling back to mock data...");
      setError("Could not connect to server - using demo content");

      // Fallback to mock data
      const mockShorts = [
        {
          id: "1",
          title: "Amazing Dance Moves",
          description: "Check out these incredible dance moves!",
          video: "/media/videos/red_ball.mp4",
          view_count: 12500,
          like_count: 890,
          comment_count: 45,
          username: "creator1",
          created_at: new Date().toISOString(),
          is_liked: false,
        },
        {
          id: "2",
          title: "Cooking Tutorial",
          description: "Learn to make the perfect pasta",
          video: "/media/videos/red_ball_ugEX5f3.mp4",
          view_count: 8200,
          like_count: 650,
          comment_count: 23,
          username: "creator2",
          created_at: new Date().toISOString(),
          is_liked: true,
        },
        {
          id: "3",
          title: "Travel Vlog",
          description: "Beautiful sunset in Bali",
          video: "/media/videos/red_ball.mp4",
          view_count: 15600,
          like_count: 1200,
          comment_count: 67,
          username: "creator3",
          created_at: new Date().toISOString(),
          is_liked: false,
        },
        {
          id: "4",
          title: "Tech Review",
          description: "Latest smartphone features",
          video: "/media/videos/red_ball_ugEX5f3.mp4",
          view_count: 9800,
          like_count: 720,
          comment_count: 34,
          username: "creator4",
          created_at: new Date().toISOString(),
          is_liked: false,
        },
        {
          id: "5",
          title: "Fitness Tips",
          description: "Quick morning workout routine",
          video: "/media/videos/red_ball.mp4",
          view_count: 22100,
          like_count: 1800,
          comment_count: 89,
          username: "creator5",
          created_at: new Date().toISOString(),
          is_liked: true,
        },
      ];
      setShorts(mockShorts);
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

  const scrollToNext = () => {
    if (currentIndex < shorts.length - 1) {
      setCurrentIndex(currentIndex + 1);
      scrollToIndex(currentIndex + 1);
    }
  };

  const scrollToPrevious = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1);
      scrollToIndex(currentIndex - 1);
    }
  };

  const scrollToIndex = (index) => {
    if (containerRef.current) {
      const container = containerRef.current;
      const targetScrollTop = index * container.clientHeight;
      container.scrollTo({
        top: targetScrollTop,
        behavior: "smooth",
      });
    }
  };

  const handleTouchStart = (e) => {
    touchStartY.current = e.touches[0].clientY;
  };

  const handleTouchMove = (e) => {
    touchEndY.current = e.touches[0].clientY;
  };

  const handleTouchEnd = () => {
    const deltaY = touchStartY.current - touchEndY.current;
    const threshold = 50;

    if (Math.abs(deltaY) > threshold) {
      if (deltaY > 0) {
        scrollToNext();
      } else {
        scrollToPrevious();
      }
    }
  };

  const handleScroll = () => {
    if (containerRef.current) {
      const container = containerRef.current;
      const scrollTop = container.scrollTop;
      const containerHeight = container.clientHeight;
      const newIndex = Math.round(scrollTop / containerHeight);

      if (
        newIndex !== currentIndex &&
        newIndex >= 0 &&
        newIndex < shorts.length
      ) {
        setCurrentIndex(newIndex);
      }
    }
  };

  if (loading) {
    return (
      <div className="modern-shorts-feed">
        <div className="modern-bg-gradient-1"></div>
        <div className="modern-bg-gradient-2"></div>
        <div className="modern-bg-gradient-3"></div>
        <div className="skeleton-feed">
          {[1,2,3].map((i) => (
            <div key={i} className="skeleton-card">
              <div className="skeleton-video" />
              <div className="skeleton-meta">
                <div className="skeleton-avatar" />
                <div className="skeleton-lines">
                  <div className="skeleton-line short" />
                  <div className="skeleton-line long" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="modern-shorts-error">
        <div className="modern-error-content">
          <svg
            width="64"
            height="64"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
          >
            <path d="M12 9v4m0 4h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
          </svg>
          <h3>Oops! Something went wrong</h3>
          <p>We couldn't load the shorts. Please try again.</p>
          <button onClick={loadShorts} className="modern-retry-btn">
            <svg
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8" />
              <path d="M21 3v5h-5" />
              <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16" />
              <path d="M3 21v-5h5" />
            </svg>
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (shorts.length === 0) {
    return (
      <div className="modern-shorts-empty">
        <div className="modern-empty-content">
          <svg
            width="80"
            height="80"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1"
          >
            <path d="M23 7l-7 5 7 5V7z" />
            <rect x="1" y="5" width="15" height="14" rx="2" ry="2" />
          </svg>
          <h3>No shorts available</h3>
          <p>Be the first to create amazing short videos!</p>
        </div>
      </div>
    );
  }

  return (
    <div className="modern-shorts-feed">
      {/* Background decorations */}
      <div className="modern-bg-gradient-1"></div>
      <div className="modern-bg-gradient-2"></div>
      <div className="modern-bg-gradient-3"></div>

      {/* Feed View - always active */}
      <div
        className="modern-shorts-container"
        ref={containerRef}
        onScroll={handleScroll}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        {shorts.map((short, index) => {
          const isActive = index === currentIndex;
          const inWindow = Math.abs(index - currentIndex) <= 1; // render only current and neighbors
          return (
            <div key={short.id} className="modern-short-item">
              {inWindow ? (
                <VideoPlayer
                  short={{
                    ...short,
                    view_count: viewCounts[short.id] || short.view_count,
                  }}
                  isActive={isActive}
                  onProfileClick={onProfileClick}
                />
              ) : (
                <div className="grid-video-placeholder">
                  <div className="grid-play-btn">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="white">
                      <path d="M8 5v14l11-7z" />
                    </svg>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Navigation controls */}
      <div className="modern-navigation">
        <button
          className={`modern-nav-btn nav-up ${
            currentIndex === 0 ? "disabled" : ""
          }`}
          onClick={scrollToPrevious}
          disabled={currentIndex === 0}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z" />
          </svg>
        </button>

        <button
          className={`modern-nav-btn nav-down ${
            currentIndex === shorts.length - 1 ? "disabled" : ""
          }`}
          onClick={scrollToNext}
          disabled={currentIndex === shorts.length - 1}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M7.41 8.59L12 13.17l4.59-4.58L18 10l-6 6-6-6 1.41-1.41z" />
          </svg>
        </button>
      </div>
    </div>
  );
};

export default ShortsFeed;
