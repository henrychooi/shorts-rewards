import { createContext, useContext, useState } from 'react';

const ViewCountContext = createContext();

export function ViewCountProvider({ children }) {
  const [viewCounts, setViewCounts] = useState({});

  const updateViewCount = (shortId, count) => {
    setViewCounts(prev => ({
      ...prev,
      [shortId]: count
    }));
  };

  return (
    <ViewCountContext.Provider value={{ viewCounts, updateViewCount }}>
      {children}
    </ViewCountContext.Provider>
  );
}

export function useViewCount() {
  return useContext(ViewCountContext);
}
