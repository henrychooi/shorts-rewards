import { useState, useRef } from "react";
import { shortsApi } from "../services/shortsApi";
import "./VideoUpload.css";

const VideoUpload = ({ onUploadSuccess, onClose }) => {
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [videoFile, setVideoFile] = useState(null);
  const [videoPreview, setVideoPreview] = useState(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);
  const videoRef = useRef(null);

  const handleFileSelect = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Validate file type
    const allowedTypes = ["video/mp4", "video/mov", "video/avi", "video/webm"];
    if (!allowedTypes.includes(file.type)) {
      setError("Please select a valid video file (MP4, MOV, AVI, or WebM)");
      return;
    }

    // Validate file size (50MB)
    if (file.size > 50 * 1024 * 1024) {
      setError("Video file size cannot exceed 50MB");
      return;
    }

    setError("");
    setVideoFile(file);

    // Create preview URL
    const previewUrl = URL.createObjectURL(file);
    setVideoPreview(previewUrl);
  };

  const handleVideoLoad = () => {
    if (videoRef.current) {
      const videoDuration = videoRef.current.duration;
      setDuration(videoDuration);

      if (videoDuration > 10) {
        setError("Video duration cannot exceed 10 seconds");
        setVideoFile(null);
        setVideoPreview(null);
        URL.revokeObjectURL(videoPreview);
      }
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();

    if (!videoFile) {
      setError("Please select a video file");
      return;
    }

    if (duration > 10) {
      setError("Video duration cannot exceed 10 seconds");
      return;
    }

    setUploading(true);
    setUploadProgress(0);

    try {
      const formData = new FormData();
      formData.append("video", videoFile);
      formData.append("title", title);
      formData.append("description", description);
      formData.append("duration", duration);

      // Simulate progress for better UX
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return prev;
          }
          return prev + Math.random() * 10;
        });
      }, 200);

      const response = await shortsApi.createShort(formData);

      clearInterval(progressInterval);
      setUploadProgress(100);

      setTimeout(() => {
        onUploadSuccess?.(response.data);
        resetForm();
      }, 500);
    } catch (err) {
      console.error("Upload error:", err);
      setError(
        err.response?.data?.detail ||
          "Failed to upload video. Please try again."
      );
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const resetForm = () => {
    setVideoFile(null);
    setVideoPreview(null);
    setTitle("");
    setDescription("");
    setDuration(0);
    setError("");
    setUploadProgress(0);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    if (videoPreview) {
      URL.revokeObjectURL(videoPreview);
    }
  };

  const handleClose = () => {
    resetForm();
    onClose?.();
  };

  return (
    <div className="upload-overlay">
      <div className="upload-modal">
        <div className="upload-header">
          <h2>Create New Short</h2>
          <button className="close-btn" onClick={handleClose}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
            </svg>
          </button>
        </div>

        <form onSubmit={handleUpload} className="upload-form">
          {!videoPreview ? (
            <div className="file-upload-area">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileSelect}
                accept="video/mp4,video/mov,video/avi,video/webm"
                className="file-input"
                id="video-upload"
              />
              <label htmlFor="video-upload" className="upload-label">
                <div className="upload-icon">
                  <svg
                    width="64"
                    height="64"
                    viewBox="0 0 24 24"
                    fill="currentColor"
                  >
                    <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z" />
                  </svg>
                </div>
                <h3>Upload Your Short Video</h3>
                <p>Drag and drop or click to select</p>
                <div className="upload-requirements">
                  <span>• Max 10 seconds</span>
                  <span>• Max 50MB</span>
                  <span>• MP4, MOV, AVI, WebM</span>
                </div>
              </label>
            </div>
          ) : (
            <div className="video-preview">
              <video
                ref={videoRef}
                src={videoPreview}
                controls
                onLoadedMetadata={handleVideoLoad}
                className="preview-video"
              />
              <button
                type="button"
                className="change-video-btn"
                onClick={() => {
                  resetForm();
                  fileInputRef.current?.click();
                }}
              >
                Change Video
              </button>
            </div>
          )}

          {error && (
            <div className="error-message">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M12,2C17.53,2 22,6.47 22,12C22,17.53 17.53,22 12,22C6.47,22 2,17.53 2,12C2,6.47 6.47,2 12,2M15.59,7L12,10.59L8.41,7L7,8.41L10.59,12L7,15.59L8.41,17L12,13.41L15.59,17L17,15.59L13.41,12L17,8.41L15.59,7Z" />
              </svg>
              {error}
            </div>
          )}

          {videoPreview && (
            <div className="form-fields">
              <div className="field-group">
                <label htmlFor="title">Title (optional)</label>
                <input
                  type="text"
                  id="title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Add a catchy title..."
                  maxLength={150}
                />
                <span className="char-count">{title.length}/150</span>
              </div>

              <div className="field-group">
                <label htmlFor="description">Description (optional)</label>
                <textarea
                  id="description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Tell us about your video..."
                  rows={3}
                  maxLength={500}
                />
                <span className="char-count">{description.length}/500</span>
              </div>

              {duration > 0 && (
                <div className="video-info">
                  <span className="duration-info">
                    Duration: {duration.toFixed(1)}s
                    {duration > 10 && (
                      <span className="warning"> (Too long!)</span>
                    )}
                  </span>
                </div>
              )}
            </div>
          )}

          {uploading && (
            <div className="upload-progress">
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <span className="progress-text">
                Uploading... {Math.round(uploadProgress)}%
              </span>
            </div>
          )}

          <div className="form-actions">
            <button
              type="button"
              className="cancel-btn"
              onClick={handleClose}
              disabled={uploading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="upload-btn"
              disabled={!videoFile || uploading || duration > 10}
            >
              {uploading ? "Uploading..." : "Share Short"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default VideoUpload;
