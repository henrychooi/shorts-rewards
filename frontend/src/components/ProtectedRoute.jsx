import { Navigate } from "react-router-dom";
import { jwtDecode } from "jwt-decode";
import api from "../api";
import { REFRESH_TOKEN, ACCESS_TOKEN } from "../constants";
import { useState, useEffect } from "react";

function ProtectedRoute({ children }) {
  const [isAuthorised, setIsAuthorised] = useState(null);

  useEffect(() => {
    auth().catch(() => setIsAuthorised(false));
  }, []);

  const refreshToken = async () => {
    const refreshToken = localStorage.getItem(REFRESH_TOKEN);
    try {
      const res = await api.post("/api/token/refresh/", {
        refresh: refreshToken,
      });
      if (res.status === 200) {
        localStorage.setItem(ACCESS_TOKEN, res.data.access);
        setIsAuthorised(true);
      } else {
        setIsAuthorised(false);
      }
    } catch (error) {
      console.log(error);
      setIsAuthorised(false);
    }
  };

  const auth = async () => {
    const token = localStorage.getItem(ACCESS_TOKEN);
    if (!token) {
      setIsAuthorised(false);
      return;
    }

    try {
      const decoded = jwtDecode(token);
      const tokenExpiration = decoded?.exp;
      const now = Date.now() / 1000;
      const skew = 30; // seconds

      if (tokenExpiration && tokenExpiration <= now + skew) {
        // Token expired or about to expire: try refresh
        await refreshToken();
      } else {
        // Token is still valid
        setIsAuthorised(true);
      }
    } catch (e) {
      // Invalid token
      setIsAuthorised(false);
    }
  };

  if (isAuthorised === null) {
    return <div>Loading...</div>;
  }

  return isAuthorised ? children : <Navigate to="/login" />;
}

export default ProtectedRoute;
