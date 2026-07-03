import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '@/shared/utils/api';
import { useAuthStore } from './authStore';
import { COUNTRIES } from '@/shared/utils/countries';

type Mode = 'login' | 'register';

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

  const inputClass = "w-full px-3 py-2 text-sm border rounded-lg outline-none focus:ring-2 focus:ring-blue-500";

  return (
    <div className="min-h-screen flex bg-white">
      {/* Left side: logo + slogan */}
      <div className="hidden lg:flex w-1/2 flex-col items-center justify-center p-12">
        <div className="flex flex-col items-center max-w-sm">
          <img src="/logo-map2drone.png" alt="Map2Drone" className="w-64 h-auto mb-6" />
          <p className="text-xl text-gray-500 text-center leading-relaxed">
            Planifica, optimiza y ejecuta<br />vuelos de dron con<br />precisión profesional
          </p>
        </div>
      </div>

      {/* Right side: auth */}
      <div className="w-full lg:w-1/2 flex items-center justify-center p-8">
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <div className="lg:hidden flex flex-col items-center mb-8">
            <img src="/logo-map2drone.png" alt="Map2Drone" className="w-48 h-auto mb-4" />
          </div>

          {/* Tabs */}
          <div className="flex mb-6 border-b" style={{ borderColor: '#e5e7eb' }}>
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
                    className="w-20 px-3 py-2 text-sm border rounded-lg bg-gray-50 text-gray-500 outline-none" />
                  <input type="tel" required value={form.phone}
                    onChange={(e) => update('phone', e.target.value)}
                    className="flex-1 px-3 py-2 text-sm border rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
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
        </div>
      </div>
    </div>
  );
}
