// The student's own errors (api/app/progress.py): which kinds of mistake
// their teacher has marked in their returned work, most frequent first,
// with examples from their own writing.
//
// A horizontal bar list: one series (how often), so one colour, no legend;
// the count is written at each bar's end, so nothing depends on colour or
// hover. Each row is a button that opens its examples. Plain counts only,
// never scores or percentages.
import { useEffect, useState } from "react";
import { api } from "../api";
import type { ErrorExample, MyErrors, ProfileRow } from "../types";

type View = "all" | "recent";

export default function MyProgress({ initialOpen = null }: { initialOpen?: string | null }) {
  const [data, setData] = useState<MyErrors | null>(null);
  const [error, setError] = useState("");
  const [view, setView] = useState<View>("all");
  const [open, setOpen] = useState<string | null>(initialOpen);

  useEffect(() => {
    api<MyErrors>("/me/errors").then(setData, () => setError("Could not load your progress. Check your connection and try again."));
  }, []);

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="loading">Loading…</p>;
  if (data.pieces === 0 || data.all.length === 0) {
    return (
      <div className="empty">
        <h2>{data.pieces === 0 ? "Nothing here yet" : "No mistakes marked yet"}</h2>
        <p className="muted">
          {data.pieces === 0
            ? "When your teacher returns your writing, the kinds of mistakes they marked show here."
            : "Your teacher hasn't marked any mistakes in your returned work. Well done!"}
        </p>
      </div>
    );
  }

  const rows = view === "all" ? data.all : data.recent;
  const most = Math.max(1, ...rows.map((r) => r.errors));
  const showToggle = data.recent_pieces < data.pieces;
  const pieces = (n: number) => `${n} piece${n === 1 ? "" : "s"} of writing`;

  return (
    <section aria-labelledby="progress-title">
      <h2 id="progress-title" className="visually-hidden">My mistakes</h2>
      <p className="muted">
        The kinds of mistakes your teacher marked in your writing, most common first. Tap one to see examples.
      </p>
      {showToggle && (
        <div className="segmented" role="tablist" aria-label="Which writing to count">
          <button role="tab" aria-selected={view === "all"} className={view === "all" ? "active" : ""} onClick={() => setView("all")}>
            All my writing
          </button>
          <button role="tab" aria-selected={view === "recent"} className={view === "recent" ? "active" : ""} onClick={() => setView("recent")}>
            My last {data.recent_pieces}
          </button>
        </div>
      )}
      <p className="chart-caption">From {pieces(view === "all" ? data.pieces : data.recent_pieces)}</p>

      {rows.length === 0 ? (
        <p className="notice">No mistakes marked in your most recent writing.</p>
      ) : (
        <ul className="bar-list">
          {rows.map((row) => (
            <li key={row.code}>
              <button
                className={`bar-row${open === row.code ? " open" : ""}`}
                aria-expanded={open === row.code}
                onClick={() => setOpen(open === row.code ? null : row.code)}
              >
                <span className="bar-label">
                  <span className="code">{row.code}</span> {row.meaning}
                </span>
                <span className="bar-track" aria-hidden="true">
                  <span className="bar" style={{ width: `${(row.errors / most) * 100}%` }} />
                </span>
                <span className="bar-value">{row.errors === 1 ? "once" : `${row.errors} times`}</span>
              </button>
              {open === row.code && <Details row={row} examples={data.examples[row.code] ?? []} />}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function Details({ row, examples }: { row: ProfileRow; examples: ErrorExample[] }) {
  const corrections = [
    row.fixed && `fixed ${row.fixed === 1 ? "once" : `${row.fixed} times`}`,
    row.changed_wrongly && `changed but not right ${row.changed_wrongly === 1 ? "once" : `${row.changed_wrongly} times`}`,
    row.unfixed && `not fixed ${row.unfixed === 1 ? "once" : `${row.unfixed} times`}`,
  ].filter(Boolean);
  return (
    <div className="bar-details">
      {corrections.length > 0 && <p>In your corrections: {corrections.join(", ")}.</p>}
      {examples.length > 0 && (
        <>
          <h3>From your writing</h3>
          <ul className="examples">
            {examples.map((ex, i) => (
              <li key={i}>
                <p className="spanned">
                  {ex.cut_start && "… "}
                  {ex.text.slice(0, ex.start)}
                  <mark className="span">
                    {ex.text.slice(ex.start, ex.end)}
                    <span className="code">{row.code}</span>
                  </mark>
                  {ex.text.slice(ex.end)}
                  {ex.cut_end && " …"}
                </p>
                {ex.title && <p className="muted example-source">{ex.title}</p>}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
