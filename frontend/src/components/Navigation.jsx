import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './Navigation.css';

const Navigation = ({ 
  onCreateShort, 
  onProfileClick, 
  currentUser, 
  currentView, 
  onViewChange 
}) => {
  const [activeTab, setActiveTab] = useState(currentView || 'home');
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.clear();
    navigate('/login');
  };

  const handleTabClick = (tabId, action) => {
    setActiveTab(tabId);
    if (onViewChange) {
      onViewChange(tabId);
    }
    if (action) {
      action();
    }
  };

  const navItems = [
    {
      id: 'home',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
          <path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/>
        </svg>
      ),
      label: 'Home',
      action: () => handleTabClick('home')
    },
    {
      id: 'search',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
          <path d="M15.5 14h-.79l-.28-.27C15.41 12.59 16 11.11 16 9.5 16 5.91 13.09 3 9.5 3S3 5.91 3 9.5 5.91 16 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z"/>
        </svg>
      ),
      label: 'Search',
      action: () => handleTabClick('search')
    },
    {
      id: 'create',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
          <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
        </svg>
      ),
      label: 'Create',
      action: onCreateShort,
      special: true
    },
    {
      id: 'profile',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
        </svg>
      ),
      label: 'Profile',
      action: () => {
        handleTabClick('profile');
        if (onProfileClick) onProfileClick();
      }
    }
  ];

  return (
    <>
      {/* Top header for desktop */}
      <header className="top-header">
        <div className="header-content">
          <div className="logo">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="currentColor">
              <path d="M17 10.5V7c0-.55-.45-1-1-1H4c-.55 0-1 .45-1 1v10c0 .55.45 1 1 1h12c.55 0 1-.45 1-1v-3.5l4 4v-11l-4 4z"/>
            </svg>
            <span>Shorts</span>
          </div>
          
          <div className="header-actions">
            <button className="create-btn-desktop" onClick={onCreateShort}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6v2z"/>
              </svg>
              Create
            </button>
            
            <div className="user-menu">
              <div className="user-avatar">
                {currentUser?.username?.charAt(0).toUpperCase() || 'U'}
              </div>
              <div className="dropdown-menu">
                <div className="user-info">
                  <span className="username">@{currentUser?.username || 'user'}</span>
                </div>
                <button className="dropdown-item" onClick={() => {
                  handleTabClick('profile');
                  if (onProfileClick) onProfileClick();
                }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                  </svg>
                  My Profile
                </button>
                <button className="dropdown-item logout" onClick={handleLogout}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M17 7l-1.41 1.41L18.17 11H8v2h10.17l-2.58 2.59L17 17l5-5zM4 5h8V3H4c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h8v-2H4V5z"/>
                  </svg>
                  Logout
                </button>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Bottom navigation for mobile */}
      <nav className="bottom-nav">
        {navItems.map((item) => (
          <button
            key={item.id}
            className={`nav-item ${activeTab === item.id ? 'active' : ''} ${item.special ? 'special' : ''}`}
            onClick={item.action}
          >
            {item.icon}
            <span className="nav-label">{item.label}</span>
          </button>
        ))}
      </nav>
    </>
  );
};

export default Navigation;
