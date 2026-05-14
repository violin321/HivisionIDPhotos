'use client';

import { useEffect, useState } from 'react';
import { getAuthState, login, logout, type AuthState } from '../lib/api-client';

function LoginPanel({ onAuthenticated }: { onAuthenticated: (state: AuthState) => void }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setErrorMessage(null);
    try {
      const state = await login(username, password);
      onAuthenticated(state);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Login failed.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-5 py-8 text-ink">
      <section className="w-full max-w-md rounded-[30px] border border-ink/10 bg-porcelain/85 p-8 shadow-panel">
        <p className="font-mono text-[11px] uppercase tracking-[0.34em] text-slate">HivisionIDPhotos</p>
        <h1 className="mt-3 font-serif text-4xl leading-none tracking-[-0.04em]">Studio Login</h1>
        <p className="mt-4 text-sm leading-6 text-graphite">
          Sign in to access uploads, task processing, and signed downloads.
        </p>

        <form className="mt-8 grid gap-4" onSubmit={handleSubmit}>
          <label className="grid gap-2 text-sm font-semibold text-ink">
            Username
            <input
              className="rounded-2xl border border-ink/15 bg-white/80 px-4 py-3 font-mono text-sm outline-none focus:border-measurement"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              disabled={busy}
              required
            />
          </label>
          <label className="grid gap-2 text-sm font-semibold text-ink">
            Password
            <input
              className="rounded-2xl border border-ink/15 bg-white/80 px-4 py-3 font-mono text-sm outline-none focus:border-measurement"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              disabled={busy}
              required
            />
          </label>
          {errorMessage ? <p className="rounded-2xl border border-red-900/15 bg-red-50 px-4 py-3 text-sm text-red-900">{errorMessage}</p> : null}
          <button
            type="submit"
            disabled={busy}
            className="rounded-full bg-ink px-5 py-3 text-sm font-bold uppercase tracking-[0.18em] text-porcelain transition hover:bg-graphite disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </section>
    </main>
  );
}

export function LoginGate({ children }: { children: (session: AuthState, onLogout: () => Promise<void>) => React.ReactNode }) {
  const [session, setSession] = useState<AuthState | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let mounted = true;
    getAuthState()
      .then((state) => {
        if (mounted) setSession(state);
      })
      .catch(() => {
        if (mounted) setSession({ authenticated: false });
      })
      .finally(() => {
        if (mounted) setChecking(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  async function handleLogout() {
    await logout();
    setSession({ authenticated: false });
  }

  if (checking) {
    return (
      <main className="flex min-h-screen items-center justify-center px-5 text-ink">
        <div className="rounded-full border border-ink/10 bg-porcelain/80 px-5 py-3 font-mono text-xs uppercase tracking-[0.22em] text-slate shadow-panel">
          Checking session…
        </div>
      </main>
    );
  }

  if (!session?.authenticated) {
    return <LoginPanel onAuthenticated={setSession} />;
  }

  return <>{children(session, handleLogout)}</>;
}
