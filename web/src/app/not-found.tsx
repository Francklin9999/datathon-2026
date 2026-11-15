import Link from 'next/link';

export default function NotFound() {
  return (
    <div className="state state-unavailable" role="status">
      <p className="state-title">Page not found · Page introuvable</p>
      <Link href="/">Home · Accueil</Link>
    </div>
  );
}
