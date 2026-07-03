import { createContext, useContext, type ReactNode } from 'react';

interface AdsenseContextValue {
  consented: boolean;
  adsLoaded: boolean;
}

const AdsenseContext = createContext<AdsenseContextValue>({
  consented: true,
  adsLoaded: true,
});

export function AdsenseProvider({ children }: { children: ReactNode }) {
  return (
    <AdsenseContext.Provider value={{ consented: true, adsLoaded: true }}>
      {children}
    </AdsenseContext.Provider>
  );
}

export function useAdsense() {
  return useContext(AdsenseContext);
}
