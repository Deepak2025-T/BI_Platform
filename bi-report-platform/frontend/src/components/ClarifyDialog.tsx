import { useMemo, useState } from "react";
import type { ClarifyResult, DashboardParameters, PlannedChart } from "../api/types";
import Icon from "./Icon";
import Modal from "./Modal";

interface Props {
  /** The request as typed. The answers are added to it, never put in place of it. */
  prompt: string;
  /** What is set in More options already. Answers are merged on top. */
  parameters: DashboardParameters;
  result: ClarifyResult;
  /** Build with the request as it now reads. */
  onBuild: (prompt: string, parameters: DashboardParameters) => void;
  onClose: () => void;
}

/** What the answers so far make of the request: the words, the shapes and the look. */
function compose(prompt: string, parameters: DashboardParameters, result: ClarifyResult,
                        picked: Record<string, string>) {
  const chosen = result.questions
    .map((q) => q.options.find((o) => o.id === picked[q.id]))
    .filter((o): o is NonNullable<typeof o> => !!o);
  const adds = chosen.map((o) => o.adds.trim()).filter(Boolean);
  // The shapes every answer named, with the ones already set in More options kept.
  const charts = [...(parameters.charts ?? [])];
  for (const o of chosen) for (const c of o.charts) if (!charts.includes(c as PlannedChart)) charts.push(c as PlannedChart);
  const style = chosen.reduce((all, o) => ({ ...all, ...o.style }), { ...(parameters.style ?? {}) });
  return {
    prompt: [prompt.trim(), ...adds].join(" "),
    parameters: { ...parameters, charts, style },
    answered: chosen.length,
  };
}

/**
 * The few questions a request leaves open, asked before the build rather than guessed during it.
 *
 * "Build a Risk Status Chart" is a real request, but it does not say what shape the chart should
 * be, whether it should carry counts or shares, or whether each status keeps its own colour. A
 * model asked that question guesses all three, and the person finds out what it guessed only
 * after a minute of waiting. Each answer here costs one click.
 *
 * Nothing is applied out of sight: the box at the bottom shows the request exactly as it will be
 * sent, with the words each answer added, and the request can be built unanswered at any point.
 */
export default function ClarifyDialog({ prompt, parameters, result, onBuild, onClose }: Props) {
  const [picked, setPicked] = useState<Record<string, string>>({});
  const made = useMemo(() => compose(prompt, parameters, result, picked),
                       [prompt, parameters, result, picked]);
  const left = result.questions.length - made.answered;

  const build = () => onBuild(made.prompt, made.parameters);

  return (
    <Modal title="A few things before I build this" size="lg" onClose={onClose} onSubmit={build}
      footer={
        <>
          <button type="button" className="btn btn-ghost" onClick={() => onBuild(prompt, parameters)}>
            Build it as I wrote it
          </button>
          <button type="submit" className="btn btn-primary">
            Build my report
            <Icon name="arrow" size={16} className="go-arrow" />
          </button>
        </>
      }>
      <div className="stack">
        <p className="muted small">
          {result.subject?.column
            ? <>This looks like a report about <b>{result.subject.label}</b>. </>
            : null}
          {left === 0
            ? "Everything is answered."
            : `${left} question${left === 1 ? "" : "s"} your request doesn't answer yet. Skip any of them and the model decides.`}
        </p>

        {result.questions.map((q) => (
          <fieldset key={q.id} className="clarify-q">
            <legend>{q.question}</legend>
            {q.hint && <p className="muted small clarify-hint">{q.hint}</p>}
            <div className="clarify-options">
              {q.options.map((o) => {
                const on = picked[q.id] === o.id;
                return (
                  <button key={o.id} type="button" className={"clarify-opt" + (on ? " on" : "")}
                    aria-pressed={on}
                    // Clicking the chosen answer again unsets it, so a question can be left open.
                    onClick={() => setPicked((p) => ({ ...p, [q.id]: on ? "" : o.id }))}>
                    <span className="clarify-opt-label">
                      <span className="clarify-tick" aria-hidden="true">{on ? <Icon name="check" size={13} /> : null}</span>
                      {o.label}
                    </span>
                    {o.hint && <span className="muted small">{o.hint}</span>}
                  </button>
                );
              })}
            </div>
          </fieldset>
        ))}

        <div className="field">
          <span>What will be built</span>
          <div className="clarify-preview">{made.prompt}</div>
          <span className="muted small">
            Your words, with each answer added to the end. Nothing else is sent.
          </span>
        </div>
      </div>
    </Modal>
  );
}
