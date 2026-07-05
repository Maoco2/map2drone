import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { api } from '@/shared/utils/api';
import { useAuthStore } from './authStore';
import { COUNTRIES } from '@/shared/utils/countries';

type Mode = 'login' | 'register';

function FeatureCard({ icon, title, desc }: { icon: string; title: string; desc: string }) {
  return (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
      <div className="text-3xl mb-3">{icon}</div>
      <h3 className="font-semibold text-gray-900 mb-1">{title}</h3>
      <p className="text-sm text-gray-500 leading-relaxed">{desc}</p>
    </div>
  );
}

function StepCard({ num, title, desc }: { num: number; title: string; desc: string }) {
  return (
    <div className="flex flex-col items-center text-center">
      <div className="w-10 h-10 rounded-full bg-blue-600 text-white flex items-center justify-center font-bold text-sm mb-3">{num}</div>
      <h3 className="font-semibold text-gray-900 mb-1">{title}</h3>
      <p className="text-sm text-gray-500 leading-relaxed max-w-xs">{desc}</p>
    </div>
  );
}

export default function LandingPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [mode, setMode] = useState<Mode>('login');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [form, setForm] = useState({
    full_name: '', email: '', password: '', country: '', city: '', phone: '', gender: '', profession: '',
  });

  const dialCode = form.country
    ? COUNTRIES.find((c) => c.code === form.country)?.dial ?? ''
    : '';

  const update = (field: string, value: string) => setForm((f) => ({ ...f, [field]: value }));

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await api.auth.login({ email, password });
      setAuth(res.user, res.access_token);
      navigate('/projects', { replace: true });
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const fullPhone = dialCode ? `${dialCode} ${form.phone}` : form.phone;
      const res = await api.auth.register({ ...form, phone: fullPhone });
      setAuth(res.user, res.access_token);
      navigate('/projects', { replace: true });
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const inputClass = "w-full px-3 py-2 text-sm border rounded-lg outline-none focus:ring-2 focus:ring-blue-500 text-black";

  return (
    <div className="min-h-screen bg-white">
      {/* Nav */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <img src="/icon-map2drone.png" alt="Map2Drone" className="w-6 h-6" />
          <span className="font-semibold text-gray-900">Map2Drone</span>
        </div>
        <nav className="flex items-center gap-4 text-sm">
          <Link to="/about" className="text-gray-500 hover:text-gray-900 transition-colors">Acerca de</Link>
          <Link to="/privacy" className="text-gray-500 hover:text-gray-900 transition-colors">Privacidad</Link>
        </nav>
      </header>

      {/* Hero */}
      <section className="max-w-4xl mx-auto px-6 pt-20 pb-16 text-center">
        <h1 className="text-4xl md:text-5xl font-bold text-gray-900 leading-tight mb-4">
          Planifica vuelos de dron<br />con precisión profesional
        </h1>
        <p className="text-lg text-gray-500 max-w-2xl mx-auto mb-8 leading-relaxed">
          Map2Drone genera cuadrículas de vuelo optimizadas con conciencia del terreno.
          Dibuja un polígono, configura los parámetros y exporta a Litchi CSV al instante.
          Gratis, sin instalación.
        </p>
        <a
          href="#auth"
          className="inline-block px-8 py-3 text-sm font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
        >
          Comenzar gratis
        </a>
      </section>

      {/* Features */}
      <section className="max-w-5xl mx-auto px-6 pb-16">
        <h2 className="text-2xl font-bold text-gray-900 text-center mb-8">Funcionalidades</h2>
        <div className="grid md:grid-cols-3 gap-6">
          <FeatureCard
            icon="🗺️"
            title="Conciencia del terreno"
            desc="Altitud AGL basada en datos de elevación reales. El primer waypoint se sitúa a la altitud MSL ingresada y el resto se ajustan automáticamente al terreno."
          />
          <FeatureCard
            icon="✚"
            title="Patrón en cruz"
            desc="Cuadrícula doble con orientaciones 0° y 90° para cobertura completa del área. Ideal para fotogrametría y mapeo agrícola."
          />
          <FeatureCard
            icon="📥"
            title="Exportación Litchi CSV"
            desc="Exporta tus misiones directamente a CSV compatible con Litchi. Límites de seguridad: +500m MSL máximo, -200m MSL mínimo."
          />
          <FeatureCard
            icon="🎯"
            title="Precisión submétrica"
            desc="Coordenadas con 6 decimales. Control total sobre distancia entre líneas, ángulo de la cuadrícula y velocidad de vuelo."
          />
          <FeatureCard
            icon="🔒"
            title="Gratuito y seguro"
            desc="Sin costos ocultos. Tus datos se almacenan de forma segura con autenticación por email y contraseña cifrada."
          />
          <FeatureCard
            icon="🌐"
            title="Sin instalación"
            desc="Funciona directo en el navegador. Cargadores de terreno desde Open-Elevation API, mapas base de OpenTopoMap y Esri."
          />
        </div>
      </section>

      {/* How it works */}
      <section className="bg-gray-50 py-16">
        <div className="max-w-4xl mx-auto px-6">
          <h2 className="text-2xl font-bold text-gray-900 text-center mb-10">Cómo funciona</h2>
          <div className="grid md:grid-cols-3 gap-8">
            <StepCard num={1} title="Dibuja un polígono" desc="Marca los límites del área a volar directamente sobre el mapa. Ajusta los vértices con precisión." />
            <StepCard num={2} title="Configura la misión" desc="Define distancia entre líneas, altitud, velocidad, ángulo de cuadrícula y activa el modo terreno." />
            <StepCard num={3} title="Exporta y vuela" desc="Descarga el archivo CSV e impórtalo en Litchi. Tu dron seguirá la ruta optimizada al instante." />
          </div>
        </div>
      </section>

      {/* Use cases */}
      <section className="max-w-5xl mx-auto px-6 py-16">
        <h2 className="text-2xl font-bold text-gray-900 text-center mb-8">Casos de uso</h2>
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl p-6 border border-gray-100">
            <h3 className="font-semibold text-gray-900 mb-1">Agricultura de precisión</h3>
            <p className="text-sm text-gray-500 leading-relaxed">Monitoreo de cultivos, detección de estrés hídrico, análisis NDVI. Vuelos sistemáticos con cobertura completa del campo.</p>
          </div>
          <div className="bg-white rounded-xl p-6 border border-gray-100">
            <h3 className="font-semibold text-gray-900 mb-1">Topografía y fotogrametría</h3>
            <p className="text-sm text-gray-500 leading-relaxed">Generación de ortofotos, modelos digitales de elevación y curvas de nivel con superposición frontal y lateral controlada.</p>
          </div>
          <div className="bg-white rounded-xl p-6 border border-gray-100">
            <h3 className="font-semibold text-gray-900 mb-1">Inspección de infraestructura</h3>
            <p className="text-sm text-gray-500 leading-relaxed">Relevamiento de líneas eléctricas, oleoductos, paneles solares y obras civiles con rutas de vuelo repetibles.</p>
          </div>
          <div className="bg-white rounded-xl p-6 border border-gray-100">
            <h3 className="font-semibold text-gray-900 mb-1">Mapeo ambiental</h3>
            <p className="text-sm text-gray-500 leading-relaxed">Inventarios forestales, monitoreo de humedales, control de erosión y estudios de impacto ambiental con datos geoespaciales.</p>
          </div>
        </div>
      </section>

      {/* Auth section */}
      <section id="auth" className="bg-gray-50 py-16">
        <div className="max-w-sm mx-auto px-6">
          <div className="text-center mb-8">
            <img src="/logo-map2drone.png" alt="Map2Drone" className="w-48 h-auto mx-auto mb-4" />
            <h2 className="text-xl font-bold text-gray-900">Crea tu cuenta gratuita</h2>
            <p className="text-sm text-gray-500 mt-1">Sin compromisos, sin tarjeta de crédito</p>
          </div>

          {/* Tabs */}
          <div className="flex mb-6 border-b border-gray-200">
            <button
              onClick={() => { setMode('login'); setError(''); }}
              className={`flex-1 pb-3 text-sm font-semibold transition-colors ${
                mode === 'login'
                  ? 'text-blue-600 border-b-2 border-blue-600'
                  : 'text-gray-400 hover:text-gray-600'
              }`}
            >
              Iniciar sesión
            </button>
            <button
              onClick={() => { setMode('register'); setError(''); }}
              className={`flex-1 pb-3 text-sm font-semibold transition-colors ${
                mode === 'register'
                  ? 'text-blue-600 border-b-2 border-blue-600'
                  : 'text-gray-400 hover:text-gray-600'
              }`}
            >
              Crear cuenta
            </button>
          </div>

          {error && (
            <div className="text-xs p-2 rounded mb-4 bg-red-50 text-red-600">{error}</div>
          )}

          {mode === 'login' ? (
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Email</label>
                <input type="email" required value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={inputClass} placeholder="tu@email.com" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Contraseña</label>
                <input type="password" required value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={inputClass} placeholder="••••••••" />
              </div>
              <button type="submit" disabled={loading}
                className="w-full py-2.5 text-sm font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
                {loading ? 'Entrando...' : 'Entrar'}
              </button>
            </form>
          ) : (
            <form onSubmit={handleRegister} className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Nombre completo</label>
                <input required value={form.full_name}
                  onChange={(e) => update('full_name', e.target.value)}
                  className={inputClass} placeholder="Juan Pérez" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Email</label>
                <input type="email" required value={form.email}
                  onChange={(e) => update('email', e.target.value)}
                  className={inputClass} placeholder="tu@email.com" />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Contraseña</label>
                <input type="password" required minLength={6} value={form.password}
                  onChange={(e) => update('password', e.target.value)}
                  className={inputClass} placeholder="Mínimo 6 caracteres" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">País</label>
                  <select required value={form.country}
                    onChange={(e) => update('country', e.target.value)} className={inputClass}>
                    <option value="">Seleccionar</option>
                    {COUNTRIES.map((c) => (
                      <option key={c.code} value={c.code}>{c.name} ({c.dial})</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Ciudad</label>
                  <input required value={form.city}
                    onChange={(e) => update('city', e.target.value)}
                    className={inputClass} placeholder="Ciudad" />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Teléfono celular</label>
                <div className="flex gap-2">
                  <input readOnly value={dialCode}
                    className="w-20 px-3 py-2 text-sm border rounded-lg bg-gray-50 text-black outline-none" />
                  <input type="tel" required value={form.phone}
                    onChange={(e) => update('phone', e.target.value)}
                    className="flex-1 px-3 py-2 text-sm border rounded-lg outline-none focus:ring-2 focus:ring-blue-500 text-black"
                    placeholder="555 123 4567" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Sexo</label>
                  <select required value={form.gender}
                    onChange={(e) => update('gender', e.target.value)} className={inputClass}>
                    <option value="">Seleccionar</option>
                    <option value="male">Masculino</option>
                    <option value="female">Femenino</option>
                    <option value="other">Prefiero no decirlo</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Profesión</label>
                  <input required value={form.profession}
                    onChange={(e) => update('profession', e.target.value)}
                    className={inputClass} placeholder="Topógrafo, piloto..." />
                </div>
              </div>
              <button type="submit" disabled={loading}
                className="w-full py-2.5 text-sm font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
                {loading ? 'Creando cuenta...' : 'Crear cuenta'}
              </button>
            </form>
          )}

          <p className="text-xs text-gray-400 text-center mt-6">
            Al crear una cuenta aceptas nuestra{' '}
            <Link to="/privacy" className="text-blue-500 hover:underline">Política de Privacidad</Link>
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="text-center py-6 text-xs text-gray-400 border-t border-gray-100">
        <div className="flex justify-center gap-4 mb-2">
          <Link to="/about" className="hover:text-gray-600 transition-colors">Acerca de</Link>
          <Link to="/privacy" className="hover:text-gray-600 transition-colors">Privacidad</Link>
        </div>
        &copy; {new Date().getFullYear()} Map2Drone. Todos los derechos reservados.
      </footer>
    </div>
  );
}
