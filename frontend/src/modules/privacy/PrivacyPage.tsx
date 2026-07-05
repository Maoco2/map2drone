import { Link } from 'react-router-dom';

export default function PrivacyPage() {
  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ backgroundColor: 'var(--color-panel)', color: 'var(--color-text)' }}
    >
      <header
        className="flex items-center justify-between px-6 py-4 border-b"
        style={{ borderColor: 'var(--color-border)' }}
      >
        <div className="flex items-center gap-2">
          <img src="/icon-map2drone.png" alt="Map2Drone" className="w-6 h-6" />
          <span className="font-semibold">Map2Drone</span>
        </div>
        <Link
          to="/"
          className="text-xs px-3 py-1.5 rounded font-medium transition-opacity hover:opacity-80"
          style={{ backgroundColor: '#4f8cff', color: '#fff' }}
        >
          Back to App
        </Link>
      </header>

      <main className="flex-1 max-w-3xl mx-auto px-6 py-8 text-sm space-y-6">
        <h1 className="text-2xl font-bold">Privacy Policy</h1>
        <p style={{ color: 'var(--color-text-secondary)' }}>Last updated: July 2026</p>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">1. Information We Collect</h2>
          <p>
            Map2Drone collects minimal information necessary to provide the drone mission planning service:
          </p>
          <ul className="list-disc pl-5 space-y-1">
            <li>Account information: name, email, password (hashed), country, city, phone, profession.</li>
            <li>Mission data: polygon coordinates, waypoints, flight parameters.</li>
            <li>Usage data: page views, feature usage (anonymized).</li>
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">2. How We Use Your Data</h2>
          <ul className="list-disc pl-5 space-y-1">
            <li>To provide and improve the mission planning service.</li>
            <li>To authenticate users and manage projects.</li>
            <li>To serve relevant advertisements via Google AdSense.</li>
            <li>We do not sell your personal data to third parties.</li>
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">3. Cookies and Advertising</h2>
          <p>
            We use cookies to improve your experience and to serve personalized ads through Google AdSense.
            Google uses cookies to serve ads based on your previous visits to this site and other websites.
            You can opt out of personalized advertising by visiting{' '}
            <a
              href="https://adssettings.google.com"
              target="_blank"
              rel="noopener noreferrer"
              className="underline"
              style={{ color: '#4f8cff' }}
            >
              Google Ad Settings
            </a>.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">4. Third-Party Services</h2>
          <p>We use the following third-party services:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>Google AdSense — for advertising</li>
            <li>Open-Elevation API — for elevation data</li>
            <li>OpenTopoMap / Esri — for map tiles</li>
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">5. Data Security</h2>
          <p>
            We implement reasonable security measures including password hashing, HTTPS,
            and database encryption. However, no method of transmission is 100% secure.
          </p>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">6. Your Rights (GDPR)</h2>
          <p>If you are in the EU, you have the right to:</p>
          <ul className="list-disc pl-5 space-y-1">
            <li>Access your personal data</li>
            <li>Rectify inaccurate data</li>
            <li>Delete your data (right to be forgotten)</li>
            <li>Withdraw consent at any time</li>
            <li>Data portability</li>
          </ul>
        </section>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">7. Contact</h2>
          <p>
            For any privacy-related inquiries, please contact us at{' '}
            <span className="font-mono" style={{ color: '#4f8cff' }}>contacto@map2drone.app</span>.
          </p>
        </section>
      </main>

      <footer
        className="text-center py-4 text-xs border-t"
        style={{ borderColor: 'var(--color-border)', color: 'var(--color-text-secondary)' }}
      >
        &copy; {new Date().getFullYear()} Map2Drone. All rights reserved.
      </footer>
    </div>
  );
}
