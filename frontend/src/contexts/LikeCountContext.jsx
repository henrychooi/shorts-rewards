import { createContext, useContext, useState } from 'react';

const LikeCountContext = createContext();

export function LikeCountProvider({ children }) {
  const [likeCounts, setLikeCounts] = useState({});

  const updateLikeCount = (shortId, likeCount, isLiked) => {
    setLikeCounts(prev => ({
      ...prev,
      [shortId]: { likeCount, isLiked }
    }));
  };

  return (
    <LikeCountContext.Provider value={{ likeCounts, updateLikeCount }}>
      {children}
    </LikeCountContext.Provider>
  );
}

export function useLikeCount() {
  return useContext(LikeCountContext);
}
