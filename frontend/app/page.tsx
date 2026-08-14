export const dynamic = "force-dynamic";

export default function Home() {
  const apiBaseUrl =
    process.env.NEXT_PUBLIC_API_BASE_URL ?? "API base URL not configured";

  return (
    <main className="dashboard-shell">
      <section className="dashboard-card" aria-labelledby="page-title">
        <p className="eyebrow">Oneremit / PayOut</p>
        <h1 id="page-title">Payout dashboard foundation</h1>
        <p className="intro">
          The application shell is ready for the transfer workflow in the next
          task.
        </p>
        <div className="status-row">
          <span className="status-dot" aria-hidden="true" />
          <span>Frontend is running</span>
        </div>
        <p className="api-note">
          API base: <code>{apiBaseUrl}</code>
        </p>
      </section>
    </main>
  );
}
