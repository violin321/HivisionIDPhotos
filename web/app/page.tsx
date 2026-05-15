'use client';

import { LoginGate } from '../components/LoginGate';
import StudioShell from '../components/StudioShell';

export default function Page() {
  return <LoginGate>{(session, onLogout) => <StudioShell username={session.username} onLogout={onLogout} />}</LoginGate>;
}
