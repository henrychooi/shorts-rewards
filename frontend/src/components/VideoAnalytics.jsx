import { useState, useEffect } from "react";
import { shortsApi } from "../services/shortsApi";
import "./VideoAnalytics.css";

const VideoAnalytics = ({ shortId, onClose }) => {
  const [analytics, setAnalytics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        setLoading(true);
        const response = await shortsApi.getVideoAnalytics(shortId);
        if (response.data.status === "success") {
          setAnalytics(response.data.analytics);
        } else {
          setError("Failed to load analytics");
        }
      } catch (err) {
        setError("Error loading analytics");
        console.error("Analytics error:", err);
      } finally {
        setLoading(false);
      }
    };

    if (shortId) {
      fetchAnalytics();
    }
  }, [shortId]);

  const formatPercentage = (value) => `${value}%`;
  const formatNumber = (value) => value.toLocaleString();

  if (loading) {
    return (
      <div className="analytics-overlay">
        <div className="analytics-modal">
          <div className="analytics-header">
            <h2>Video Analytics</h2>
            <button className="close-btn" onClick={onClose}>
              ×
            </button>
          </div>
          <div className="analytics-loading">Loading...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="analytics-overlay">
        <div className="analytics-modal">
          <div className="analytics-header">
            <h2>Video Analytics</h2>
            <button className="close-btn" onClick={onClose}>
              ×
            </button>
          </div>
          <div className="analytics-error">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="analytics-overlay" onClick={onClose}>
      <div className="analytics-modal" onClick={(e) => e.stopPropagation()}>
        <div className="analytics-header">
          <h2>Video Analytics</h2>
          <button className="close-btn" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="analytics-content">
          {/* Overview Stats */}
          <div className="analytics-section">
            <h3>Overview</h3>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-value">
                  {formatNumber(analytics.total_views)}
                </div>
                <div className="stat-label">Total Views</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  {formatNumber(analytics.unique_viewers)}
                </div>
                <div className="stat-label">Unique Viewers</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  {formatNumber(analytics.like_count)}
                </div>
                <div className="stat-label">Likes</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  {formatNumber(analytics.comment_count)}
                </div>
                <div className="stat-label">Comments</div>
              </div>
            </div>
          </div>

          {/* Engagement Metrics */}
          <div className="analytics-section">
            <h3>Engagement</h3>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-value">
                  {formatPercentage(analytics.average_watch_percentage)}
                </div>
                <div className="stat-label">Avg Watch %</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  {formatPercentage(analytics.completion_rate)}
                </div>
                <div className="stat-label">Completion Rate</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  {formatNumber(analytics.total_rewatches)}
                </div>
                <div className="stat-label">Total Rewatches</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  {formatPercentage(analytics.average_engagement_score)}
                </div>
                <div className="stat-label">Engagement Score</div>
              </div>
            </div>
          </div>

          {/* Video Info */}
          <div className="analytics-section">
            <h3>Video Details</h3>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-value">
                  {analytics.duration
                    ? `${Math.round(analytics.duration)}s`
                    : "N/A"}
                </div>
                <div className="stat-label">Duration</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  {analytics.total_rewatches > 0
                    ? `${(
                        analytics.total_rewatches / analytics.unique_viewers
                      ).toFixed(1)}`
                    : "0"}
                </div>
                <div className="stat-label">Avg Rewatches/Viewer</div>
              </div>
            </div>
          </div>

          {/* Performance Indicators */}
          <div className="analytics-section">
            <h3>Performance Indicators</h3>
            <div className="indicators">
              <div
                className={`indicator ${
                  analytics.completion_rate >= 80
                    ? "good"
                    : analytics.completion_rate >= 50
                    ? "okay"
                    : "poor"
                }`}
              >
                <span className="indicator-label">Completion Rate:</span>
                <span className="indicator-status">
                  {analytics.completion_rate >= 80
                    ? "Excellent"
                    : analytics.completion_rate >= 50
                    ? "Good"
                    : "Needs Improvement"}
                </span>
              </div>

              <div
                className={`indicator ${
                  analytics.average_engagement_score >= 70
                    ? "good"
                    : analytics.average_engagement_score >= 40
                    ? "okay"
                    : "poor"
                }`}
              >
                <span className="indicator-label">Engagement:</span>
                <span className="indicator-status">
                  {analytics.average_engagement_score >= 70
                    ? "High"
                    : analytics.average_engagement_score >= 40
                    ? "Medium"
                    : "Low"}
                </span>
              </div>

              <div
                className={`indicator ${
                  analytics.total_rewatches >= analytics.unique_viewers * 0.3
                    ? "good"
                    : analytics.total_rewatches >=
                      analytics.unique_viewers * 0.1
                    ? "okay"
                    : "poor"
                }`}
              >
                <span className="indicator-label">Rewatch Rate:</span>
                <span className="indicator-status">
                  {analytics.total_rewatches >= analytics.unique_viewers * 0.3
                    ? "High"
                    : analytics.total_rewatches >=
                      analytics.unique_viewers * 0.1
                    ? "Medium"
                    : "Low"}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VideoAnalytics;
