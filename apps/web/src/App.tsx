import { useState } from "react";

type Skin = "humbert" | "proef";

// A skeleton screen whose only job is to prove the stack stands: Tailwind v4
// tokens resolve, and the runtime skin swap works. The notebook, the cell, and
// the loop come in block 2.
export default function App() {
  const [skin, setSkin] = useState<Skin>("humbert");

  function toggleSkin() {
    const next: Skin = skin === "humbert" ? "proef" : "humbert";
    document.documentElement.setAttribute("data-skin", next);
    setSkin(next);
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-paper p-8 font-ui text-ink">
      <h1 className="font-narrative text-4xl text-brand">Humbert</h1>
      <p className="max-w-prose text-center font-narrative text-lg">
        The skeleton stands. The notebook, the cell, and the loop come next.
      </p>
      <button
        type="button"
        onClick={toggleSkin}
        className="rounded border border-brand px-3 py-1 text-sm text-brand"
      >
        Skin: {skin} — tap to swap
      </button>
    </main>
  );
}
