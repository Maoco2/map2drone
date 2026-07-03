import { useEffect, useRef } from 'react';
import { useAdsense } from '@/shared/adsense/AdsenseContext';

interface AdSlotProps {
  slotId: string;
  format?: 'auto' | 'rectangle' | 'horizontal' | 'vertical';
  className?: string;
  style?: React.CSSProperties;
}

export default function AdSlot({ slotId, format = 'auto', className = '', style }: AdSlotProps) {
  const { consented, adsLoaded } = useAdsense();
  const insRef = useRef<HTMLModElement>(null);
  const pushed = useRef(false);

  useEffect(() => {
    if (!consented || !adsLoaded) return;
    if (pushed.current) return;

    const timer = setTimeout(() => {
      try {
        (window as any).adsbygoogle = (window as any).adsbygoogle || [];
        (window as any).adsbygoogle.push({});
        pushed.current = true;
      } catch {}
    }, 100);

    return () => clearTimeout(timer);
  }, [consented, adsLoaded]);

  if (!consented) {
    return (
      <div
        className={`flex items-center justify-center text-xs ${className}`}
        style={{
          minHeight: format === 'rectangle' ? 250 : 90,
          backgroundColor: 'var(--color-surface)',
          color: 'var(--color-text-secondary)',
          borderRadius: 4,
          ...style,
        }}
      >
        Ad
      </div>
    );
  }

  return (
    <div className={className} style={style}>
      <ins
        ref={insRef}
        className="adsbygoogle"
        style={{ display: 'block', minHeight: format === 'rectangle' ? 250 : 90 }}
        data-ad-client="ca-pub-0000000000000000"
        data-ad-slot={slotId}
        data-ad-format={format}
        data-full-width-responsive="true"
      />
    </div>
  );
}
