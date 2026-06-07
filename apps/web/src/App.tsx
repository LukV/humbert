import { useEffect, useState } from "react";

type Bootstrap = { skin: string; locale: string; app_name: string };

// Skeleton screen. The skin and language are applied server-side onto <html>
// (no flash); here we read /api/bootstrap for the app name and to show the
// resolved skin/locale. The notebook, the cell, and the loop come in block 2.
export default function App() {
  const [boot, setBoot] = useState<Bootstrap | null>(null);

  useEffect(() => {
    fetch("/api/bootstrap")
      .then((r) => (r.ok ? (r.json() as Promise<Bootstrap>) : null))
      .then(setBoot)
      .catch(() => setBoot(null));
  }, []);

  const appName = boot?.app_name ?? "Humbert";

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-paper p-8 font-ui text-ink">
      <h1 className="font-narrative text-4xl text-brand">{appName}</h1>
      <p className="max-w-prose text-center font-narrative text-lg">
        The skeleton stands. The notebook, the cell, and the loop come next.
      </p>
      {boot && (
        <p className="text-sm text-ink/70">
          skin: {boot.skin} · locale: {boot.locale}
        </p>
      )}
    </main>
  );
}
