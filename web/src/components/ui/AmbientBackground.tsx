/** Decorative light behind the glass panels (styles in styles/base.css). Hidden from assistive tech. */
export function AmbientBackground() {
  return (
    <div className="ambient" aria-hidden="true">
      <span className="ambient-teal" />
      <span className="ambient-blue" />
      <span className="ambient-shaft" />
      <span className="ambient-grain" />
    </div>
  );
}
