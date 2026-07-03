import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '@/shared/utils/api';
import { useAuthStore } from './authStore';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const setAuth = useAuthStore((s) => s.setAuth);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
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

  return (
    <div className="min-h-screen flex items-center justify-center p-8"
      style={{ background: 'linear-gradient(135deg, #0d47a1 0%, #1a73e8 50%, #42a5f5 100%)' }}>
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <img src="/logo-map2drone.png" alt="Map2Drone" className="w-32 h-auto mb-4" />
          <h1 className="text-2xl font-bold text-white">Iniciar sesión</h1>
        </div>
        <form onSubmit={handleSubmit} className="bg-white rounded-xl p-6 shadow-xl space-y-4">
          {error && (
            <div className="text-xs p-2 rounded bg-red-50 text-red-600">{error}</div>
          )}
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Email</label>
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
              className="w-full px-3 py-2 text-sm border rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="tu@email.com" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Contraseña</label>
            <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
              className="w-full px-3 py-2 text-sm border rounded-lg outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="••••••••" />
          </div>
          <button type="submit" disabled={loading}
            className="w-full py-2.5 text-sm font-semibold text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
            {loading ? 'Entrando...' : 'Entrar'}
          </button>
          <p className="text-xs text-center text-gray-500">
            ¿No tienes cuenta?{' '}
            <Link to="/register" className="text-blue-600 hover:underline">Regístrate</Link>
          </p>
        </form>
      </div>
    </div>
  );
}
