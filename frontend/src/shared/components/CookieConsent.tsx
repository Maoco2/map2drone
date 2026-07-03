import { useAdsense } from '@/shared/adsense/AdsenseContext';
import { useNavigate } from 'react-router-dom';

export default function CookieConsent() {
  const { consented, acceptConsent } = useAdsense();
  const navigate = useNavigate();

  if (consented) return null;

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-between gap-4 px-4 py-3 text-xs shadow-lg"
      style={{
        backgroundColor: 'var(--color-panel)',
        borderTop: '1px solid var(--color-border)',
        color: 'var(--color-text)',
      }}
    >
      <span>
        This site uses cookies and Google AdSense to show relevant ads. By continuing you accept our{' '}
        <button
          onClick={() => navigate('/privacy')}
          className="underline hover:opacity-70"
          style={{ color: '#4f8cff' }}
        >
          Privacy Policy
        </button>.
      </span>
      <div className="flex gap-2 shrink-0">
        <button
          onClick={acceptConsent}
          className="px-3 py-1.5 rounded font-medium text-white transition-opacity hover:opacity-90"
          style={{ backgroundColor: '#4f8cff' }}
        >
          Accept
        </button>
      </div>
    </div>
  );
}
