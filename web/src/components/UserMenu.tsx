import { useAuth } from '../context/AuthContext';

export default function UserMenu() {
  const { user, logout } = useAuth();
  if (!user) return null;
  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-zinc-300">{user.name}</span>
      <button
        onClick={logout}
        className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
      >
        Sign out
      </button>
    </div>
  );
}
