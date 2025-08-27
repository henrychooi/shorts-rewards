import api from "../api";

export const shortsApi = {
  // Get all shorts
  getShorts: () => api.get("/api/shorts/"),
  
  // Get specific short
  getShort: (id) => api.get(`/api/shorts/${id}/`),
  
  // Create new short
  createShort: (formData) => api.post("/api/shorts/create/", formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  }),
  
  // Update short
  updateShort: (id, data) => api.patch(`/api/shorts/${id}/`, data),
  
  // Delete short
  deleteShort: (id) => api.delete(`/api/shorts/${id}/`),
  
  // Toggle like
  toggleLike: (shortId) => api.post(`/api/shorts/${shortId}/like/`),
  
  // Add comment
  addComment: (shortId, content, parentId = null) => 
    api.post(`/api/shorts/${shortId}/comment/`, { 
      content, 
      parent: parentId 
    }),
  
  // Get comments
  getComments: (shortId) => api.get(`/api/shorts/${shortId}/comments/`),
  
  // Track view
  trackView: (shortId, watchDuration = 0) => 
    api.post(`/api/shorts/${shortId}/view/`, { watch_duration: watchDuration }),
  
  // Get user's shorts
  getUserShorts: () => api.get("/api/my-shorts/"),
  
  // Get user profile
  getUserProfile: (username) => api.get(`/api/profile/${username}/`),
};
