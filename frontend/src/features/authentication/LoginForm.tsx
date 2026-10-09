import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from './AuthContext';

export const LoginForm: React.FC = () => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email.trim() || !password) {
      setError('Please enter both email and password.');
      return;
    }

    try {
      setIsSubmitting(true);
      await login(email, password);
      navigate('/admin/menu');
    } catch (err: any) {
      setError(err.message || 'Login failed. Please check credentials.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDemoLogin = (demoEmail: string, demoPass: string) => {
    setEmail(demoEmail);
    setPassword(demoPass);
  };

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col justify-center py-12 sm:px-6 lg:px-8 text-slate-100 font-sans">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-amber-500/20 text-amber-400 mb-4 border border-amber-500/30">
          <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
          </svg>
        </div>
        <h2 className="text-3xl font-extrabold text-white tracking-tight">ROMS Staff Portal</h2>
        <p className="mt-2 text-sm text-slate-400">
          Sign in to manage restaurant outlets, menus, and daily availability
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
        <div className="bg-slate-800/90 backdrop-blur-md py-8 px-6 shadow-2xl rounded-2xl border border-slate-700 sm:px-10">
          {error && (
            <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm flex items-start space-x-3">
              <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>{error}</span>
            </div>
          )}

          <form className="space-y-6" onSubmit={handleSubmit}>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                Staff Email Address
              </label>
              <div className="mt-2">
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="admin@himachalhospitality.com"
                  className="w-full px-4 py-3 rounded-xl bg-slate-900/80 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 transition-all text-sm"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300">
                Password
              </label>
              <div className="mt-2">
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full px-4 py-3 rounded-xl bg-slate-900/80 border border-slate-700 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-amber-500/50 focus:border-amber-500 transition-all text-sm"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isSubmitting}
              className="w-full py-3.5 px-4 rounded-xl bg-amber-500 hover:bg-amber-600 focus:ring-4 focus:ring-amber-500/30 text-slate-950 font-bold text-sm tracking-wide shadow-lg shadow-amber-500/20 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex justify-center items-center"
            >
              {isSubmitting ? (
                <span className="flex items-center space-x-2">
                  <svg className="animate-spin h-5 w-5 text-slate-950" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>Signing In...</span>
                </span>
              ) : (
                'Sign In to Dashboard'
              )}
            </button>
          </form>

          {/* Quick Demo Logins Helper */}
          <div className="mt-8 pt-6 border-t border-slate-700/80">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-3 text-center">
              Quick Demo Accounts
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => handleDemoLogin('admin@himachalhospitality.com', 'admin123')}
                className="w-full text-left px-3 py-2 rounded-lg bg-slate-900/50 hover:bg-slate-700/50 border border-slate-700/50 text-xs text-slate-300 flex flex-col justify-between transition-colors"
              >
                <span className="font-semibold text-white">Himachali Admin</span>
                <span className="text-amber-400 font-mono text-[10px]">Owner (All Outlets)</span>
              </button>
              <button
                type="button"
                onClick={() => handleDemoLogin('manager@riverside.com', 'manager123')}
                className="w-full text-left px-3 py-2 rounded-lg bg-slate-900/50 hover:bg-slate-700/50 border border-slate-700/50 text-xs text-slate-300 flex flex-col justify-between transition-colors"
              >
                <span className="font-semibold text-white">Riverside Manager</span>
                <span className="text-amber-400 font-mono text-[10px]">Manager (Riverside)</span>
              </button>
              <button
                type="button"
                onClick={() => handleDemoLogin('waiter@riverside.com', 'waiter123')}
                className="w-full text-left px-3 py-2 rounded-lg bg-slate-900/50 hover:bg-slate-700/50 border border-slate-700/50 text-xs text-slate-300 flex flex-col justify-between transition-colors"
              >
                <span className="font-semibold text-white">Riverside Waiter</span>
                <span className="text-emerald-400 font-mono text-[10px]">Waiter Staff</span>
              </button>
              <button
                type="button"
                onClick={() => handleDemoLogin('manager@town.com', 'manager123')}
                className="w-full text-left px-3 py-2 rounded-lg bg-slate-900/50 hover:bg-slate-700/50 border border-slate-700/50 text-xs text-slate-300 flex flex-col justify-between transition-colors"
              >
                <span className="font-semibold text-white">Town Manager</span>
                <span className="text-blue-400 font-mono text-[10px]">Manager (Town Rest.)</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
