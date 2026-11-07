import React, { useState, useEffect } from "react";
import { fetchHealth, fetchSamples, fetchRuns, triggerAgentRun } from "./api.js";

const AGENTS = [
  { num: "01", name: "Code Understanding", desc: "AST & Vector Index" },
  { num: "02", name: "Debugging Agent", desc: "Root Cause Analysis" },
  { num: "03", name: "Code Generation", desc: "Proposes Patch" },
  { num: "04", name: "Testing Agent", desc: "Pytest Self-Heal Loop" },
  { num: "05", name: "Code Review", desc: "Audit & Pull Request" },
];

export default function App() {
  const [health, setHealth] = useState(null);
  const [samples, setSamples] = useState([]);
  const [runs, setRuns] = useState([]);
  const [currentRun, setCurrentRun] = useState(null);
  const [activeTab, setActiveTab] = useState("timeline");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [repoSource, setRepoSource] = useState("sample:ecommerce_checkout_bug");
  const [issueDescription, setIssueDescription] = useState("");
  const [errorLogs, setErrorLogs] = useState("");
  const [demonstrateSelfHealing, setDemonstrateSelfHealing] = useState(true);

  useEffect(() => {
    async function init() {
      try {
        const [h, s, r] = await Promise.all([
          fetchHealth(),
          fetchSamples(),
          fetchRuns(),
        ]);
        setHealth(h);
        const list = s.samples || [];
        setSamples(list);
        if (list.length > 0) {
          setRepoSource(list[0].repo_source);
          setIssueDescription(list[0].issue_description);
          setErrorLogs(list[0].error_logs);
        }
        if (r && r.length > 0) {
          setRuns(r);
          setCurrentRun(r[0]);
        }
      } catch (err) {
        setError(err.message || "Could not connect to backend.");
      }
    }
    init();
  }, []);

  const handleSelectSample = (s) => {
    setRepoSource(s.repo_source);
    setIssueDescription(s.issue_description);
    setErrorLogs(s.error_logs);
  };

  const handleRun = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await triggerAgentRun({
        repo_source: repoSource,
        issue_description: issueDescription,
        error_logs: errorLogs,
        llm_provider: "auto",
        max_iterations: 3,
        demonstrate_self_healing: demonstrateSelfHealing,
      });
      setCurrentRun(result);
      const updated = await fetchRuns();
      setRuns(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <header className="header">
        <div>
          <div className="header-title">AI SOFTWARE ENGINEERING AGENT</div>
          <div className="header-sub">5-Agent LangGraph Pipeline • Self-Healing Test Loop</div>
        </div>
        <div style={{ display: "flex", gap: "0.4rem" }}>
          <span className="badge inverted">{health ? "ONLINE" : "CONNECTING"}</span>
          <span className="badge">{health?.database_backend || "local"}</span>
        </div>
      </header>

      <main className="container">
        <aside>
          <div className="box">
            <div className="box-title">
              <span>Input Repository</span>
            </div>

            <div className="field">
              <span className="label">Sample Buggy Repos:</span>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                {samples.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    className={`btn ${repoSource === s.repo_source ? "active" : ""}`}
                    onClick={() => handleSelectSample(s)}
                  >
                    {s.repo_source.replace("sample:", "")}
                  </button>
                ))}
              </div>
            </div>

            <form onSubmit={handleRun}>
              <div className="field">
                <label className="label">Repo URL / Path / Sample ID</label>
                <input
                  className="input"
                  value={repoSource}
                  onChange={(e) => setRepoSource(e.target.value)}
                  required
                />
              </div>

              <div className="field">
                <label className="label">Issue Description</label>
                <textarea
                  className="textarea"
                  value={issueDescription}
                  onChange={(e) => setIssueDescription(e.target.value)}
                />
              </div>

              <div className="field">
                <label className="label">Error Logs</label>
                <textarea
                  className="textarea"
                  value={errorLogs}
                  onChange={(e) => setErrorLogs(e.target.value)}
                />
              </div>

              <div className="field">
                <label
                  style={{
                    fontSize: "0.78rem",
                    display: "flex",
                    gap: "0.4rem",
                    alignItems: "center",
                    cursor: "pointer",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={demonstrateSelfHealing}
                    onChange={(e) => setDemonstrateSelfHealing(e.target.checked)}
                  />
                  <span>Demonstrate Self-Healing Retry Loop</span>
                </label>
              </div>

              <button type="submit" className="btn-run" disabled={loading}>
                {loading ? "RUNNING AGENTS..." : "RUN AGENT PIPELINE"}
              </button>
            </form>

            {error && (
              <div
                style={{
                  border: "1px solid #000000",
                  padding: "0.5rem",
                  marginTop: "0.75rem",
                  fontSize: "0.78rem",
                }}
              >
                ERROR: {error}
              </div>
            )}
          </div>

          <div className="box">
            <div className="box-title">
              <span>Recent Runs</span>
            </div>
            {runs.length === 0 ? (
              <div style={{ fontSize: "0.78rem" }}>No runs yet.</div>
            ) : (
              runs.slice(0, 5).map((r) => (
                <button
                  key={r.id}
                  type="button"
                  className={`btn ${currentRun?.id === r.id ? "active" : ""}`}
                  onClick={() => setCurrentRun(r)}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    width: "100%",
                    marginBottom: "0.35rem",
                  }}
                >
                  <span>
                    {r.repo_name} ({r.iterations_used} iter)
                  </span>
                  <span>{r.tests_passed ? "PASS" : r.status}</span>
                </button>
              ))
            )}
          </div>
        </aside>

        <section>
          <div className="box">
            <div className="box-title">
              <span>5-Agent Pipeline</span>
              {currentRun && (
                <span className="badge inverted">
                  Iterations: {currentRun.iterations_used} | Tests Passed:{" "}
                  {currentRun.tests_passed ? "YES" : "NO"}
                </span>
              )}
            </div>

            <div className="pipeline-grid">
              {AGENTS.map((a) => (
                <div
                  key={a.num}
                  className={`agent-step ${currentRun ? "active-step" : ""}`}
                >
                  <div style={{ fontSize: "0.7rem", fontWeight: 700 }}>AGENT {a.num}</div>
                  <div style={{ fontSize: "0.82rem", fontWeight: 700 }}>{a.name}</div>
                  <div style={{ fontSize: "0.72rem", opacity: 0.8 }}>{a.desc}</div>
                </div>
              ))}
            </div>

            <div className="tabs">
              <button
                className={`tab ${activeTab === "timeline" ? "active" : ""}`}
                onClick={() => setActiveTab("timeline")}
              >
                1. Self-Healing Test Loop
              </button>
              <button
                className={`tab ${activeTab === "bugs" ? "active" : ""}`}
                onClick={() => setActiveTab("bugs")}
              >
                2. Root Cause Analysis
              </button>
              <button
                className={`tab ${activeTab === "diff" ? "active" : ""}`}
                onClick={() => setActiveTab("diff")}
              >
                3. Code Fix & Unit Tests
              </button>
              <button
                className={`tab ${activeTab === "pr" ? "active" : ""}`}
                onClick={() => setActiveTab("pr")}
              >
                4. Code Review & PR
              </button>
            </div>

            {!currentRun ? (
              <div style={{ padding: "2rem", textAlign: "center" }}>
                Select a sample repository on the left and click{" "}
                <strong>RUN AGENT PIPELINE</strong>.
              </div>
            ) : (
              <>
                {activeTab === "timeline" && (
                  <div>
                    <div className="grid-2">
                      {(currentRun.test_history || []).map((it) => (
                        <div key={it.iteration} className="item-row">
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              marginBottom: "0.4rem",
                            }}
                          >
                            <strong>Iteration #{it.iteration}</strong>
                            <span className={`badge ${it.passed ? "inverted" : ""}`}>
                              {it.passed
                                ? `PASSED (${it.passed_count})`
                                : `FAILED (${it.failed_count}) -> RETRY`}
                            </span>
                          </div>
                          <div style={{ fontSize: "0.8rem", marginBottom: "0.5rem" }}>
                            {it.note}
                          </div>
                          <pre className="code-block">{it.output}</pre>
                        </div>
                      ))}
                    </div>
                    <div style={{ marginTop: "1rem" }}>
                      <div className="label" style={{ marginBottom: "0.5rem" }}>
                        AGENT EXECUTION STEPS
                      </div>
                      {(currentRun.agent_timeline || []).map((st) => (
                        <div key={st.step} className="item-row">
                          <div style={{ display: "flex", justifyContent: "space-between" }}>
                            <strong>
                              {st.step}. {st.agent}
                            </strong>
                            <span className="badge">
                              {st.status} ({st.duration_ms} ms)
                            </span>
                          </div>
                          <div style={{ fontSize: "0.82rem", marginTop: "0.25rem" }}>
                            {st.summary}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {activeTab === "bugs" && (
                  <div>
                    <div className="item-row">
                      <strong>Summary:</strong>{" "}
                      {currentRun.root_cause_analysis?.summary}
                      <pre
                        style={{
                          marginTop: "0.5rem",
                          whiteSpace: "pre-wrap",
                          fontSize: "0.8rem",
                        }}
                      >
                        {currentRun.root_cause_analysis?.detailed_explanation}
                      </pre>
                    </div>
                    {(currentRun.root_cause_analysis?.identified_bugs || []).map(
                      (b, i) => (
                        <div key={i} className="item-row">
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              marginBottom: "0.25rem",
                            }}
                          >
                            <strong>
                              <code>
                                {b.file}:{b.line}
                              </code>{" "}
                              ({b.symbol})
                            </strong>
                            <span className="badge inverted">{b.category}</span>
                          </div>
                          <div style={{ fontSize: "0.82rem" }}>{b.explanation}</div>
                        </div>
                      )
                    )}
                  </div>
                )}

                {activeTab === "diff" && (
                  <div className="grid-2">
                    <div>
                      <div className="label">PROPOSED CODE DIFF</div>
                      <pre className="code-block">
                        {currentRun.proposed_changes?.unified_diff}
                      </pre>
                    </div>
                    <div>
                      <div className="label">
                        GENERATED UNIT TESTS ({currentRun.generated_tests?.test_file_path})
                      </div>
                      <pre className="code-block">
                        {currentRun.generated_tests?.test_code}
                      </pre>
                    </div>
                  </div>
                )}

                {activeTab === "pr" && (
                  <div>
                    <div className="item-row">
                      <div style={{ display: "flex", justifyContent: "space-between" }}>
                        <strong>
                          Code Review Verdict: {currentRun.code_review?.verdict} (Score:{" "}
                          {currentRun.code_review?.score}/100)
                        </strong>
                        <span className="badge inverted">
                          {currentRun.pull_request?.branch} -&gt;{" "}
                          {currentRun.pull_request?.base_branch}
                        </span>
                      </div>
                      <div style={{ fontSize: "0.82rem", marginTop: "0.35rem" }}>
                        {currentRun.code_review?.summary}
                      </div>
                    </div>
                    <div className="label">{currentRun.pull_request?.title}</div>
                    <pre className="code-block">
                      {currentRun.pull_request?.body_markdown}
                    </pre>
                  </div>
                )}
              </>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
