import { useState, useEffect, useRef } from "react";
import VideoPlayer from "./VideoPlayer";
import { shortsApi } from "../services/shortsApi";
import "./ShortsFeed.css";

const ShortsFeed = ({ onProfileClick }) => {
  const [shorts, setShorts] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const containerRef = useRef(null);
  const touchStartY = useRef(0);
  const touchEndY = useRef(0);

  useEffect(() => {
    loadShorts();
  }, []);

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
      const response = await shortsApi.getShorts();
      setShorts(response.data);
    } catch (err) {
      setError("Failed to load shorts");
      console.error("Error loading shorts:", err);
    } finally {
      setLoading(false);
    }
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
        // Swipe up - next video
        scrollToNext();
      } else {
        // Swipe down - previous video
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
      <div className="shorts-loading">
        <div className="loading-spinner">
          <div className="spinner"></div>
          <p>Loading awesome shorts...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="shorts-error">
        <div className="error-content">
          <svg width="64" height="64" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
          </svg>
          <h3>{error}</h3>
          <button onClick={loadShorts} className="retry-btn">
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (shorts.length === 0 && !loading && !error) {
    const dummyShort = {
      id: 1,
      title: "Dummy Short",
      description: "This is a dummy short for testing purposes.",
      video: "", // no video needed for this test
      author: { username: "testuser123" },
      created_at: new Date().toISOString(),
      view_count: 0,
      like_count: 0,
      comment_count: 0,
      is_liked: false,
      comments: [],
    };
    return (
      <div className="shorts-feed">
        <div className="shorts-container" ref={containerRef}>
          <div className="short-item">
            <VideoPlayer
              short={dummyShort}
              isActive={true}
              onProfileClick={onProfileClick}
            />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="shorts-feed">
      <div
        className="shorts-container"
        ref={containerRef}
        onScroll={handleScroll}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        {shorts.map((short, index) => (
          <div key={short.id} className="short-item">
            <VideoPlayer
              short={short}
              isActive={index === currentIndex}
              onProfileClick={onProfileClick}
            />
          </div>
        ))}
      </div>

      {/* Navigation indicators */}
      <div className="shorts-navigation">
        <button
          className={`nav-btn nav-up ${currentIndex === 0 ? "disabled" : ""}`}
          onClick={scrollToPrevious}
          disabled={currentIndex === 0}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <path d="M7.41 15.41L12 10.83l4.59 4.58L18 14l-6-6-6 6z" />
          </svg>
        </button>

        <div className="progress-indicator">
          {shorts.map((_, index) => (
            <div
              key={index}
              className={`progress-dot ${
                index === currentIndex ? "active" : ""
              }`}
              onClick={() => {
                setCurrentIndex(index);
                scrollToIndex(index);
              }}
            />
          ))}
        </div>

        <button
          className={`nav-btn nav-down ${
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

      {/* Current video info */}
      <div className="video-counter">
        {currentIndex + 1} / {shorts.length}
      </div>
    </div>
  );
};

export default ShortsFeed;
