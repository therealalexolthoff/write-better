// The table for editing an evaluation's flagged errors: code, exact words,
// which occurrence, correction and explanation. The API re-checks every
// span against the text (api/app/review.py); this only collects input.
import type { Annotation, Code } from "../types";

// The API stores computed offsets on each annotation but doesn't accept
// them back; strip them before sending.
export const withoutOffsets = (annotations: Annotation[]) => annotations.map(({ start: _s, end: _e, ...a }) => a);

export function AnnotationsEditor({
  annotations,
  codes,
  disabled,
  onChange,
}: {
  annotations: Annotation[];
  codes: Code[];
  disabled: boolean;
  onChange: (a: Annotation[]) => void;
}) {
  const edit = (i: number, patch: Partial<Annotation>) =>
    onChange(annotations.map((a, j) => (j === i ? { ...a, ...patch } : a)));
  const blank: Annotation = { code: codes[0]?.code ?? "SP", span_text: "", occurrence: 1, correction: "", explanation: "" };

  return (
    <>
      <table className="annotations">
        <thead>
          <tr>
            <th>Code</th>
            <th>Exact words</th>
            <th title="If the same words appear more than once: which one (1 = first)">Which</th>
            <th>Correction</th>
            <th>Explanation</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {annotations.map((a, i) => (
            <tr key={i}>
              <td>
                <select value={a.code} disabled={disabled} onChange={(e) => edit(i, { code: e.target.value })}>
                  {codes.map((c) => <option key={c.code} value={c.code} title={c.description}>{c.code}</option>)}
                </select>
              </td>
              <td><input value={a.span_text} disabled={disabled} onChange={(e) => edit(i, { span_text: e.target.value })} /></td>
              <td>
                <input
                  type="number"
                  min={1}
                  className="narrow-input"
                  value={a.occurrence}
                  disabled={disabled}
                  onChange={(e) => edit(i, { occurrence: Number(e.target.value) || 1 })}
                />
              </td>
              <td><input value={a.correction} disabled={disabled} onChange={(e) => edit(i, { correction: e.target.value })} /></td>
              <td><input value={a.explanation} disabled={disabled} onChange={(e) => edit(i, { explanation: e.target.value })} /></td>
              <td>
                {!disabled && (
                  <button onClick={() => onChange(annotations.filter((_, j) => j !== i))} aria-label="Remove annotation">
                    Remove
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {annotations.length === 0 && <p className="muted">No errors flagged.</p>}
      {!disabled && <button onClick={() => onChange([...annotations, blank])}>Add annotation</button>}
    </>
  );
}
