import { useState } from "react";
import api from "../api";
import { useNavigate, Link } from "react-router-dom";
import { ACCESS_TOKEN, REFRESH_TOKEN } from "../constants";
import "../styles/Form.css";

function Form({ route, method }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const name = method === "login" ? "Login" : "Register";

  const handleSubmit = async (e) => {
    setLoading(true);
    e.preventDefault();
    setErrors(null);

    try {
      const res = await api.post(route, { username, password });
      if (method === "login") {
        localStorage.setItem(ACCESS_TOKEN, res.data.access);
        localStorage.setItem(REFRESH_TOKEN, res.data.refresh);
        localStorage.setItem("username", username);
        navigate("/");
      } else {
        navigate("/login");
      }
    } catch (error) {
      console.error("Authentication error:", error);

      if (error.response) {
        // Server responded with error status
        const status = error.response.status;
        const data = error.response.data;

        if (status === 401) {
          setErrors({
            detail: "Invalid username or password. Please try again.",
          });
        } else if (status === 400) {
          setErrors(data);
        } else if (status >= 500) {
          setErrors({ detail: "Server error. Please try again later." });
        } else {
          setErrors(data || { detail: "Login failed. Please try again." });
        }
      } else if (error.request) {
        // Network error
        setErrors({
          detail: "Network error. Please check your connection and try again.",
        });
      } else {
        // Other error
        setErrors({
          detail: "An unexpected error occurred. Please try again.",
        });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleUsernameChange = (e) => {
    setUsername(e.target.value);
    if (errors) {
      setErrors(null);
    }
  };

  const handlePasswordChange = (e) => {
    setPassword(e.target.value);
    if (errors) {
      setErrors(null);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="form-container">
      <h1>{name}</h1>
      {errors && (
        <div className="error-message">
          {errors.detail ? (
            <p>{errors.detail}</p>
          ) : (
            Object.keys(errors).map((key) => (
              <p key={key}>
                {Array.isArray(errors[key])
                  ? `${key}: ${errors[key].join(", ")}`
                  : `${key}: ${errors[key]}`}
              </p>
            ))
          )}
        </div>
      )}
      <input
        className="form-input"
        type="text"
        value={username}
        onChange={handleUsernameChange}
        placeholder="Username"
      />
      <input
        className="form-input"
        type="password"
        value={password}
        onChange={handlePasswordChange}
        placeholder="Password"
      />
      <button type="submit" className="form-button" disabled={loading}>
        {loading ? "Loading..." : name}
      </button>
      {method === "login" && (
        <p>
          Don't have an account? <Link to="/register">Register here</Link>
        </p>
      )}
      {method !== "login" && (
        <p>
          Already have an account? <Link to="/login">Login here</Link>
        </p>
      )}
    </form>
  );
}

export default Form;
