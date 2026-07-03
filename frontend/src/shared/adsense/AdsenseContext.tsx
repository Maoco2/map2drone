import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';

const CONSENT_KEY = 'map2drone_adsense_consent';
const ADSENSE_CLIENT = 'ca-pub-0000000000000000';

interface AdsenseContextValue {
  consented: boolean;
  adsLoaded: boolean;
  acceptConsent: () => void;
  hasConsent: () => boolean;
}

const AdsenseContext = createContext<AdsenseContextValue>({
  consented: false,
  adsLoaded: false,
  acceptConsent: () => {},
  hasConsent: () => false,
});

function loadAdsenseScript(): Promise<void> {
  return new Promise((resolve) => {
    if (document.getElementById('adsense-script')) {
      resolve();
      return;
    }
    const script = document.createElement('script');
    script.id = 'adsense-script';
    script.src = `https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${ADSENSE_CLIENT}`;
    script.async = true;
    script.crossOrigin = 'anonymous';
    script.onload = () => resolve();
    script.onerror = () => resolve();
    document.head.appendChild(script);
  });
}

export function AdsenseProvider({ children }: { children: ReactNode }) {
  const [consented, setConsented] = useState(() => localStorage.getItem(CONSENT_KEY) === 'true');
  const [adsLoaded, setAdsLoaded] = useState(false);

  const hasConsent = useCallback(() => {
    return localStorage.getItem(CONSENT_KEY) === 'true';
  }, []);

  const acceptConsent = useCallback(() => {
    localStorage.setItem(CONSENT_KEY, 'true');
    setConsented(true);
  }, []);

  useEffect(() => {
    if (consented && !adsLoaded) {
      loadAdsenseScript().then(() => setAdsLoaded(true));
    }
  }, [consented, adsLoaded]);

  return (
    <AdsenseContext.Provider value={{ consented, adsLoaded, acceptConsent, hasConsent }}>
      {children}
    </AdsenseContext.Provider>
  );
}

export function useAdsense() {
  return useContext(AdsenseContext);
}
