import { useState, useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '@/shared/utils/api';
import { useAuthStore } from './authStore';
import { COUNTRIES } from '@/shared/utils/countries';

export default function RegisterPage() {
  const [form, setForm] = useState({
    full_name: '', email: '', password: '', country: '', city: '', phone: '', gender: '', profession: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const setAuth = useAuthStore((s) => s.setAuth);
  const navigate = useNavigate();

  const dialCode = useMemo(() => {
    if (!form.country) return '';
    const c = COUNTRIES.find((c) => c.code === form.country);
    return c ? c.dial : '';
  }, [form.country]);

  const update = (field: string, value: string) => setForm((f) => ({ ...f, [field]: value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    const fullPhone = dialCode ? `${dialCode} ${form.phone}` : form.phone;
    try {
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
    <div className="min-h-screen flex items-center justify-center p-8"
      style={{ background: 'linear-gradient(135deg, #0d47a1 0%, #1a73e8 50%, #42a5f5 100%)' }}>
      <div className="w-full max-w-md">
        <div className="flex flex-col items-center mb-8">
          <img src="/logo-map2drone.png" alt="Map2Drone" className="w-32 h-auto mb-4" />
          <h1 className="text-2xl font-bold text-white">Crear cuenta</h1>
        </div>
        <form onSubmit={handleSubmit} className="bg-white rounded-xl p-6 shadow-xl space-y-3">
          {error && (
            <div className="text-xs p-2 rounded bg-red-50 text-red-600">{error}</div>
          )}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Nombre completo</label>
            <input required value={form.full_name} onChange={(e) => update('full_name', e.target.value)}
              className={inputClass} placeholder="Juan Pérez" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Email</label>
            <input type="email" required value={form.email} onChange={(e) => update('email', e.target.value)}
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
              <select required value={form.country} onChange={(e) => update('country', e.target.value)}
                className={inputClass}>
                <option value="">Seleccionar</option>
                {COUNTRIES.map((c) => (
                  <option key={c.code} value={c.code}>{c.name} ({c.dial})</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Ciudad</label>
              <input required value={form.city} onChange={(e) => update('city', e.target.value)}
                className={inputClass} placeholder="Ciudad" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Teléfono celular</label>
            <div className="flex gap-2">
              <input readOnly value={dialCode}
                className="w-20 px-3 py-2 text-sm border rounded-lg bg-gray-50 text-black outline-none" />
              <input type="tel" required value={form.phone} onChange={(e) => update('phone', e.target.value)}
                className="flex-1 px-3 py-2 text-sm border rounded-lg outline-none focus:ring-2 focus:ring-blue-500 text-black"
                placeholder="555 123 4567" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Sexo</label>
              <select required value={form.gender} onChange={(e) => update('gender', e.target.value)}
                className={inputClass}>
                <option value="">Seleccionar</option>
                <option value="male">Masculino</option>
                <option value="female">Femenino</option>
                <option value="other">Prefiero no decirlo</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Profesión</label>
              <input required value={form.profession} onChange={(e) => update('profession', e.target.value)}
                className={inputClass} placeholder="Topógrafo, piloto..." />
            </div>
          </div>
          <button type="submit" disabled={loading}
            className="w-full py-2.5 text-sm font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
            {loading ? 'Creando cuenta...' : 'Crear cuenta'}
          </button>
          <p className="text-xs text-center text-gray-500">
            ¿Ya tienes cuenta?{' '}
            <Link to="/login" className="text-blue-600 hover:underline">Inicia sesión</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
