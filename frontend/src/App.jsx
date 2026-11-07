import React, { useState, useEffect } from "react";
import {
  fetchHealth,
  fetchSamples,
  fetchRuns,
  triggerAgentRun,
  searchCodeVectors,
} from "./api.js";

const AGENT_PIPELINE = [
  {
    key: "Code Understanding Agent",
    index: "Agent 01",
    name: "Code Understanding",
    desc: "AST parser, symbol map & pgvector indexing",
  },
  {
    key: "Debugging Agent",
    index: "Agent 02",
    name: "Debugging Agent",
    desc: "Error log trace & root cause localization",
  },
  {
    key: "Code Generation Agent",
    index: "Agent 03",
    name: "Code Generation",
    desc: "Synthesizes & refines patch from test feedback",
  },
  {
    key: "Testing Agent",
    index: "Agent 04",
    name: "Testing Agent",
    desc: "Generates pytest suite & runs self-healing loop",
  },
  {
    key: "Code Review Agent",
    index: "Agent 05",
    name: "Code Review & PR",
    desc: "Security/quality audit & Pull Request creation",
  },
];

function DiffViewer({ diffText }) {
  if (!diffText) {
    return <div className="code-box">No diff generated.</div>;
  }
  const lines = diffText.split("\n");
  return (
    <pre className="code-box">
      {lines.map((line, idx) => {
        if (line.startsWith("+") && !line.startsWith("+++")) {
          return (
            <span key={idx} className="diff-line-add">
              {line}
            </span>
          );
        }
        if (line.startsWith("-") && !line.startsWith("---")) {
          return (
            <span key={idx} className="diff-line-del">
              {line}
            </span>
          );
        }
        if (line.startsWith("@@") || line.startsWith("---") || line.startsWith("+++")) {
          return (
            <span key={idx} className="diff-line-hunk">
              {line}
            </span>
          );
        }
        return (
          <span key={idx} style={{ display: "block", padding: "0 0.35rem" }}>
            {line}
          </span>
        );
      })}
    </pre>
  );
}

export default function App() {
  const [health, setHealth] = useState(null);
  const [samples, setSamples] = useState([]);
  const [runs, setRuns] = useState([]);
  const [currentRun, setCurrentRun] = useState(null);
  const [activeTab, setActiveTab] = useState("self_healing");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Form inputs
  const [repoSource, setRepoSource] = useState("sample:ecommerce_checkout_bug");
  const [issueDescription, setIssueDescription] = useState("");
  const [errorLogs, setErrorLogs] = useState("");
  const [llmProvider, setLlmProvider] = useState("auto");
  const [apiKey, setApiKey] = useState("");
  const [githubToken, setGithubToken] = useState("");
  const [createGithubPr, setCreateGithubPr] = useState(false);
  const [maxIterations, setMaxIterations] = useState(3);
  const [demonstrateSelfHealing, setDemonstrateSelfHealing] = useState(true);

  // Vector search playground
  const [vectorQuery, setVectorQuery] = useState("discount percentage subtotal coupon");
  const [vectorResults, setVectorResults] = useState([]);
  const [searchingVectors, setSearchingVectors] = useState(false);
  const [copiedPr, setCopiedPr] = useState(false);

  const handleDownloadPatch = () => {
    const diff = currentRun?.proposed_changes?.unified_diff;
    if (!diff) return;
    const blob = new Blob([diff], { type: "text/x-diff;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${currentRun.repo_name}-${currentRun.id}.patch`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleCopyPrMarkdown = () => {
    const md = currentRun?.pull_request?.body_markdown;
    if (!md) return;
    navigator.clipboard.writeText(md);
    setCopiedPr(true);
    setTimeout(() => setCopiedPr(false), 2000);
  };

  useEffect(() => {
    async function init() {
      try {
        const [h, s, r] = await Promise.all([
          fetchHealth(),
          fetchSamples(),
          fetchRuns(),
        ]);
        setHealth(h);
        const sampleList = s.samples || [];
        setSamples(sampleList);
        if (sampleList.length > 0) {
          setRepoSource(sampleList[0].repo_source);
          setIssueDescription(sampleList[0].issue_description);
          setErrorLogs(sampleList[0].error_logs);
        }
        if (r && r.length > 0) {
          setRuns(r);
          setCurrentRun(r[0]);
        }
      } catch (err) {
        setError(err.message || "Could not reach backend API.");
      }
    }
    init();
  }, []);

  const handleSelectSample = (sample) => {
    setRepoSource(sample.repo_source);
    setIssueDescription(sample.issue_description);
    setErrorLogs(sample.error_logs);
  };

  const handleRunPipeline = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await triggerAgentRun({
        repo_source: repoSource,
        issue_description: issueDescription,
        error_logs: errorLogs,
        llm_provider: llmProvider,
        api_key: apiKey || null,
        github_token: githubToken || null,
        create_github_pr: createGithubPr,
        max_iterations: Number(maxIterations),
        demonstrate_self_healing: demonstrateSelfHealing,
      });
      setCurrentRun(result);
      const updatedRuns = await fetchRuns();
      setRuns(updatedRuns);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleVectorSearch = async (e) => {
    e.preventDefault();
    if (!vectorQuery.trim()) return;
    setSearchingVectors(true);
    try {
      const res = await searchCodeVectors({
        run_id: currentRun ? currentRun.id : null,
        query: vectorQuery,
        top_k: 5,
      });
      setVectorResults(res.results || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setSearchingVectors(false);
    }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <div className="brand-icon">AI</div>
          <div>
            <div className="brand-title">AI Software Engineering Agent</div>
            <div className="brand-subtitle">
              5-Agent LangGraph Orchestrator • Self-Healing Pytest Loop • FastAPI + pgvector
            </div>
          </div>
        </div>
        <div className="status-pills">
          <span className="pill green">
            ● Backend: {health ? "Connected" : "Connecting..."}
          </span>
          <span className="pill blue">
            Vector DB: {health?.database_backend || "pgvector"}
          </span>
          <span className="pill amber">
            Orchestrator: LangGraph 5-Agent StateGraph
          </span>
        </div>
      </header>

      <main className="main-layout">
        {/* Left Sidebar: Repository & Agent Controls */}
        <aside style={{ display: "flex", flexDirection: "column", gap: "1.1rem" }}>
          <section className="panel">
            <div className="panel-title">
              <span>1. Target Repository & Bug Context</span>
              <span className="pill blue">Input</span>
            </div>

            {samples.length > 0 && (
              <div>
                <span className="form-label">Quick-Load Built-In Buggy Repositories:</span>
                <div className="preset-buttons">
                  {samples.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      className={`btn-preset ${repoSource === s.repo_source ? "active" : ""}`}
                      onClick={() => handleSelectSample(s)}
                    >
                      <div style={{ fontWeight: 700, marginBottom: "2px" }}>
                        {s.repo_source.replace("sample:", "")}
                      </div>
                      <div style={{ fontSize: "0.68rem", color: "var(--text-secondary)" }}>
                        3 Intentional Bugs
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            <form onSubmit={handleRunPipeline}>
              <div className="form-group">
                <label className="form-label">
                  GitHub Repository URL, Local Path, or Sample ID
                </label>
                <input
                  className="input"
                  value={repoSource}
                  onChange={(e) => setRepoSource(e.target.value)}
                  placeholder="https://github.com/owner/repo or sample:ecommerce_checkout_bug"
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Issue Description</label>
                <textarea
                  className="textarea"
                  value={issueDescription}
                  onChange={(e) => setIssueDescription(e.target.value)}
                  placeholder="Describe the bug or unexpected behavior..."
                />
              </div>

              <div className="form-group">
                <label className="form-label">Error Logs / Stack Trace</label>
                <textarea
                  className="textarea"
                  value={errorLogs}
                  onChange={(e) => setErrorLogs(e.target.value)}
                  placeholder="Paste traceback or pytest failure logs..."
                />
              </div>

              <div className="grid-2" style={{ marginBottom: "0.75rem" }}>
                <div>
                  <label className="form-label">LLM Engine</label>
                  <select
                    className="select"
                    value={llmProvider}
                    onChange={(e) => setLlmProvider(e.target.value)}
                  >
                    <option value="auto">Auto (Gemini / OpenAI / AST Engine)</option>
                    <option value="gemini">Gemini API (google-genai)</option>
                    <option value="openai">OpenAI API</option>
                    <option value="mock">Offline AST & Heuristic Engine</option>
                  </select>
                </div>
                <div>
                  <label className="form-label">Max Test Iterations</label>
                  <select
                    className="select"
                    value={maxIterations}
                    onChange={(e) => setMaxIterations(Number(e.target.value))}
                  >
                    <option value={1}>1 Iteration</option>
                    <option value={2}>2 Iterations</option>
                    <option value={3}>3 Iterations (Recommended)</option>
                    <option value={5}>5 Iterations</option>
                  </select>
                </div>
              </div>

              {llmProvider !== "mock" && (
                <div className="form-group">
                  <label className="form-label">
                    Optional Gemini / OpenAI API Key (leave blank for offline engine)
                  </label>
                  <input
                    type="password"
                    className="input"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="AIza... or sk-..."
                  />
                </div>
              )}

              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={demonstrateSelfHealing}
                  onChange={(e) => setDemonstrateSelfHealing(e.target.checked)}
                />
                <span>
                  <strong>Demonstrate Self-Healing Loop</strong> (Iteration 1 catches edge-case test failure → Iteration 2 modifies fix & passes)
                </span>
              </label>

              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={createGithubPr}
                  onChange={(e) => setCreateGithubPr(e.target.checked)}
                />
                <span>Push & Create Live GitHub PR (requires GitHub Token)</span>
              </label>

              {createGithubPr && (
                <div className="form-group">
                  <label className="form-label">GitHub Personal Access Token</label>
                  <input
                    type="password"
                    className="input"
                    value={githubToken}
                    onChange={(e) => setGithubToken(e.target.value)}
                    placeholder="ghp_..."
                  />
                </div>
              )}

              <button className="btn-primary" type="submit" disabled={loading}>
                {loading
                  ? "Running 5-Agent Pipeline & Pytest Self-Healing Loop..."
                  : "▶ Launch AI Software Engineering Agent"}
              </button>
            </form>

            {error && (
              <div
                style={{
                  marginTop: "0.85rem",
                  padding: "0.65rem",
                  borderRadius: "8px",
                  background: "rgba(239, 68, 68, 0.15)",
                  border: "1px solid rgba(239, 68, 68, 0.4)",
                  color: "#fca5a5",
                  fontSize: "0.8rem",
                }}
              >
                {error}
              </div>
            )}
          </section>

          {/* Past Runs History */}
          <section className="panel">
            <div className="panel-title">
              <span>Recent Agent Runs ({runs.length})</span>
            </div>
            {runs.length === 0 ? (
              <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
                No runs executed yet. Click Launch above to start!
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                {runs.slice(0, 6).map((r) => (
                  <button
                    key={r.id}
                    type="button"
                    className={`btn-preset ${currentRun?.id === r.id ? "active" : ""}`}
                    onClick={() => setCurrentRun(r)}
                    style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
                  >
                    <div>
                      <div style={{ fontWeight: 700 }}>{r.repo_name}</div>
                      <div style={{ fontSize: "0.7rem", color: "var(--text-secondary)" }}>
                        {r.id} • {r.iterations_used} iter(s)
                      </div>
                    </div>
                    <span className={`pill ${r.tests_passed ? "green" : "red"}`}>
                      {r.tests_passed ? "TESTS PASSED" : r.status}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </section>
        </aside>

        {/* Right Workspace: 5-Agent Graph & Detailed Outputs */}
        <section style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {/* 5-Agent Pipeline Cards */}
          <div className="panel">
            <div className="panel-title">
              <span>LangGraph 5-Agent Orchestration Pipeline</span>
              {currentRun && (
                <div style={{ display: "flex", gap: "0.5rem" }}>
                  <span className="pill blue">Run ID: {currentRun.id}</span>
                  <span className={`pill ${currentRun.tests_passed ? "green" : "amber"}`}>
                    Self-Healing Iterations: {currentRun.iterations_used} / {currentRun.max_iterations}
                  </span>
                </div>
              )}
            </div>

            <div className="agent-flow-bar">
              {AGENT_PIPELINE.map((ag) => {
                const isSelfHealed =
                  currentRun &&
                  currentRun.iterations_used > 1 &&
                  (ag.key === "Code Generation Agent" || ag.key === "Testing Agent");
                return (
                  <div
                    key={ag.key}
                    className={`agent-node-card ${currentRun ? "done" : ""} ${
                      isSelfHealed ? "healed" : ""
                    }`}
                  >
                    <div className="agent-node-index">{ag.index}</div>
                    <div className="agent-node-name">{ag.name}</div>
                    <div className="agent-node-desc">{ag.desc}</div>
                    {isSelfHealed && (
                      <div style={{ marginTop: "0.4rem" }}>
                        <span className="pill amber" style={{ fontSize: "0.66rem" }}>
                          ↻ Self-Healed ({currentRun.iterations_used}x)
                        </span>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>

            {!currentRun ? (
              <div
                style={{
                  textAlign: "center",
                  padding: "2.5rem 1rem",
                  color: "var(--text-secondary)",
                }}
              >
                <h3 style={{ color: "var(--text-primary)", marginBottom: "0.4rem" }}>
                  Ready to Diagnose, Fix, Test & Open a Pull Request
                </h3>
                <p style={{ fontSize: "0.86rem", maxWidth: "620px", margin: "0 auto" }}>
                  Select one of the built-in buggy repositories on the left (or enter a GitHub repository URL) and click{" "}
                  <strong>Launch AI Software Engineering Agent</strong> to watch the 5 agents collaborate.
                </p>
              </div>
            ) : (
              <>
                <nav className="tabs-nav">
                  <button
                    className={`tab-btn ${activeTab === "self_healing" ? "active" : ""}`}
                    onClick={() => setActiveTab("self_healing")}
                  >
                    1. Self-Healing Test Loop ({currentRun.iterations_used} Iterations)
                  </button>
                  <button
                    className={`tab-btn ${activeTab === "root_cause" ? "active" : ""}`}
                    onClick={() => setActiveTab("root_cause")}
                  >
                    2. Debugging & Root Cause ({currentRun.root_cause_analysis?.identified_bugs?.length || 0} Bugs)
                  </button>
                  <button
                    className={`tab-btn ${activeTab === "diff_tests" ? "active" : ""}`}
                    onClick={() => setActiveTab("diff_tests")}
                  >
                    3. Code Fix Diff & Unit Tests
                  </button>
                  <button
                    className={`tab-btn ${activeTab === "code_structure" ? "active" : ""}`}
                    onClick={() => setActiveTab("code_structure")}
                  >
                    4. Code Structure & pgvector Search
                  </button>
                  <button
                    className={`tab-btn ${activeTab === "pr_review" ? "active" : ""}`}
                    onClick={() => setActiveTab("pr_review")}
                  >
                    5. Code Review & Pull Request
                  </button>
                </nav>

                {/* TAB 1: SELF-HEALING TEST LOOP & AGENT TIMELINE */}
                {activeTab === "self_healing" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <div
                      style={{
                        background: "rgba(99, 102, 241, 0.1)",
                        border: "1px solid rgba(99, 102, 241, 0.35)",
                        borderRadius: "10px",
                        padding: "0.9rem 1.1rem",
                      }}
                    >
                      <div style={{ fontWeight: 700, fontSize: "0.9rem", marginBottom: "0.25rem" }}>
                        ★ Agentic Highlight: Iterative Test → Inspect Failure → Modify Fix → Re-Test Loop
                      </div>
                      <div style={{ fontSize: "0.82rem", color: "var(--text-secondary)" }}>
                        The Testing Agent executes <code>pytest</code> inside an isolated sandbox workspace. When a test fails, LangGraph routes the exact <code>pytest</code> failure traceback back to the Code Generation Agent, which modifies its proposed fix and re-runs the test suite until all tests pass.
                      </div>
                    </div>

                    <div className="grid-2">
                      {(currentRun.test_history || []).map((iter) => (
                        <div
                          key={iter.iteration}
                          className={`timeline-card ${iter.passed ? "passed" : "retry"}`}
                        >
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              alignItems: "center",
                              marginBottom: "0.5rem",
                            }}
                          >
                            <span style={{ fontWeight: 700, fontSize: "0.92rem" }}>
                              Test Loop — Iteration #{iter.iteration}
                            </span>
                            <span className={`pill ${iter.passed ? "green" : "amber"}`}>
                              {iter.passed
                                ? `PASSED (${iter.passed_count} passed)`
                                : `FAILED (${iter.failed_count} failed → Self-Heal Triggered)`}
                            </span>
                          </div>
                          <p
                            style={{
                              fontSize: "0.8rem",
                              color: "var(--text-secondary)",
                              marginBottom: "0.6rem",
                            }}
                          >
                            {iter.note}
                          </p>
                          <pre className="code-box" style={{ maxHeight: "230px" }}>
                            {iter.output}
                          </pre>
                        </div>
                      ))}
                    </div>

                    <div>
                      <h4 style={{ fontSize: "0.9rem", marginBottom: "0.65rem" }}>
                        Step-by-Step Multi-Agent Execution Trace
                      </h4>
                      <div className="timeline-list">
                        {(currentRun.agent_timeline || []).map((step) => (
                          <div
                            key={step.step}
                            className={`timeline-card ${
                              step.status === "SELF_HEAL_RETRY" ? "retry" : "passed"
                            }`}
                          >
                            <div
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                                marginBottom: "0.25rem",
                              }}
                            >
                              <div>
                                <span
                                  style={{
                                    fontWeight: 700,
                                    color: "var(--accent-blue)",
                                    marginRight: "0.5rem",
                                  }}
                                >
                                  Step {step.step}: {step.agent}
                                </span>
                                <span style={{ fontSize: "0.76rem", color: "var(--text-secondary)" }}>
                                  ({step.role})
                                </span>
                              </div>
                              <div style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
                                <span className="pill">{step.duration_ms} ms</span>
                                <span
                                  className={`pill ${
                                    step.status === "SELF_HEAL_RETRY" ? "amber" : "green"
                                  }`}
                                >
                                  {step.status}
                                </span>
                              </div>
                            </div>
                            <div style={{ fontSize: "0.83rem" }}>{step.summary}</div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* TAB 2: DEBUGGING & ROOT CAUSE ANALYSIS */}
                {activeTab === "root_cause" && currentRun.root_cause_analysis && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <div className="timeline-card passed">
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          marginBottom: "0.4rem",
                        }}
                      >
                        <span style={{ fontWeight: 700, fontSize: "0.95rem" }}>
                          Root Cause Summary ({currentRun.root_cause_analysis.primary_file})
                        </span>
                        <span className="pill green">
                          Confidence: {Math.round((currentRun.root_cause_analysis.confidence || 0.95) * 100)}%
                        </span>
                      </div>
                      <p style={{ fontSize: "0.86rem", marginBottom: "0.6rem", fontWeight: 600 }}>
                        {currentRun.root_cause_analysis.summary}
                      </p>
                      <pre
                        style={{
                          whiteSpace: "pre-wrap",
                          fontSize: "0.81rem",
                          color: "var(--text-secondary)",
                          fontFamily: "inherit",
                        }}
                      >
                        {currentRun.root_cause_analysis.detailed_explanation}
                      </pre>
                    </div>

                    <h4 style={{ fontSize: "0.9rem" }}>Pinpointed Code Defects</h4>
                    <div className="timeline-list">
                      {(currentRun.root_cause_analysis.identified_bugs || []).map((bug, i) => (
                        <div key={i} className="timeline-card retry">
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "space-between",
                              marginBottom: "0.3rem",
                            }}
                          >
                            <span style={{ fontWeight: 700 }}>
                              <code>
                                {bug.file}:{bug.line}
                              </code>{" "}
                              — <code>{bug.symbol}</code>
                            </span>
                            <div style={{ display: "flex", gap: "0.4rem" }}>
                              <span className="pill blue">{bug.category}</span>
                              <span className={`pill ${bug.severity === "HIGH" ? "red" : "amber"}`}>
                                {bug.severity}
                              </span>
                            </div>
                          </div>
                          <div style={{ fontSize: "0.83rem" }}>{bug.explanation}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* TAB 3: CODE DIFF & GENERATED UNIT TESTS */}
                {activeTab === "diff_tests" && (
                  <div className="grid-2">
                    <div>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          marginBottom: "0.5rem",
                        }}
                      >
                        <h4 style={{ fontSize: "0.9rem" }}>Proposed Unified Code Diff</h4>
                        <div style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
                          <span className="pill green">Iteration {currentRun.proposed_changes?.iteration}</span>
                          <button
                            type="button"
                            className="btn-preset"
                            style={{ padding: "0.22rem 0.55rem", fontSize: "0.72rem" }}
                            onClick={handleDownloadPatch}
                          >
                            ⬇ Download .patch
                          </button>
                        </div>
                      </div>
                      <DiffViewer diffText={currentRun.proposed_changes?.unified_diff} />
                    </div>
                    <div>
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          marginBottom: "0.5rem",
                        }}
                      >
                        <h4 style={{ fontSize: "0.9rem" }}>
                          Generated Pytest Suite ({currentRun.generated_tests?.test_file_path})
                        </h4>
                        <span className="pill blue">
                          {currentRun.generated_tests?.test_cases_summary?.length || 0} Tests
                        </span>
                      </div>
                      <pre className="code-box">{currentRun.generated_tests?.test_code}</pre>
                    </div>
                  </div>
                )}

                {/* TAB 4: CODE STRUCTURE & PGVECTOR SEARCH */}
                {activeTab === "code_structure" && currentRun.code_structure && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                    <div className="grid-2">
                      <div className="timeline-card">
                        <h4 style={{ fontSize: "0.88rem", marginBottom: "0.5rem" }}>
                          AST Structure Map ({currentRun.code_structure.total_files} files,{" "}
                          {currentRun.code_structure.total_lines} lines)
                        </h4>
                        {(currentRun.code_structure.files || []).map((f) => (
                          <div
                            key={f.file}
                            style={{
                              padding: "0.55rem",
                              background: "var(--bg-primary)",
                              borderRadius: "6px",
                              marginBottom: "0.45rem",
                              fontSize: "0.8rem",
                            }}
                          >
                            <div style={{ fontWeight: 700, color: "var(--accent-blue)" }}>
                              {f.file} ({f.line_count} lines)
                            </div>
                            <div style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>
                              Classes: {f.classes.map((c) => c.name).join(", ") || "None"} | Functions:{" "}
                              {f.functions.map((fn) => fn.name).join(", ") || "None"}
                            </div>
                          </div>
                        ))}
                      </div>

                      <div className="timeline-card">
                        <h4 style={{ fontSize: "0.88rem", marginBottom: "0.5rem" }}>
                          Interactive pgvector Semantic Code Search ({currentRun.code_structure.chunks_indexed} chunks indexed)
                        </h4>
                        <form
                          onSubmit={handleVectorSearch}
                          style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem" }}
                        >
                          <input
                            className="input"
                            value={vectorQuery}
                            onChange={(e) => setVectorQuery(e.target.value)}
                            placeholder="Search symbols, e.g. 'loyalty coupon negative subtotal'..."
                          />
                          <button
                            type="submit"
                            className="btn-primary"
                            style={{ width: "auto", whiteSpace: "nowrap" }}
                            disabled={searchingVectors}
                          >
                            {searchingVectors ? "Searching..." : "Search Vectors"}
                          </button>
                        </form>

                        <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                          {(vectorResults.length > 0
                            ? vectorResults
                            : currentRun.code_structure.top_relevant_chunks || []
                          ).map((chunk, idx) => (
                            <div
                              key={idx}
                              style={{
                                padding: "0.55rem",
                                background: "var(--bg-primary)",
                                borderRadius: "6px",
                                fontSize: "0.78rem",
                                display: "flex",
                                justifyContent: "space-between",
                                alignItems: "center",
                              }}
                            >
                              <div>
                                <code>{chunk.symbol_name}</code>{" "}
                                <span style={{ color: "var(--text-secondary)" }}>
                                  ({chunk.file_path})
                                </span>
                              </div>
                              <span className="pill green">
                                Score: {chunk.similarity}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* TAB 5: CODE REVIEW & PULL REQUEST */}
                {activeTab === "pr_review" && currentRun.pull_request && (
                  <div className="grid-2">
                    <div className="timeline-card passed">
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          marginBottom: "0.6rem",
                        }}
                      >
                        <h4 style={{ fontSize: "0.92rem" }}>Code Review Agent Verdict</h4>
                        <span className="pill green">
                          {currentRun.code_review?.verdict} • Score: {currentRun.code_review?.score}/100
                        </span>
                      </div>
                      <p style={{ fontSize: "0.83rem", marginBottom: "0.85rem" }}>
                        {currentRun.code_review?.summary}
                      </p>
                      <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                        {(currentRun.code_review?.checklist || []).map((item, idx) => (
                          <div
                            key={idx}
                            style={{
                              padding: "0.55rem",
                              background: "var(--bg-primary)",
                              borderRadius: "6px",
                              fontSize: "0.8rem",
                            }}
                          >
                            <div style={{ fontWeight: 700, color: item.passed ? "#34d399" : "#f87171" }}>
                              {item.passed ? "✓" : "✗"} {item.item}
                            </div>
                            <div style={{ color: "var(--text-secondary)", fontSize: "0.76rem" }}>
                              {item.comment}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="timeline-card">
                      <div
                        style={{
                          display: "flex",
                          justifyContent: "space-between",
                          alignItems: "center",
                          marginBottom: "0.5rem",
                        }}
                      >
                        <h4 style={{ fontSize: "0.92rem" }}>
                          Pull Request #{currentRun.pull_request.pr_number}
                        </h4>
                        <div style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
                          <span className="pill blue">
                            Branch: {currentRun.pull_request.branch} → {currentRun.pull_request.base_branch}
                          </span>
                          <button
                            type="button"
                            className="btn-preset"
                            style={{ padding: "0.22rem 0.55rem", fontSize: "0.72rem" }}
                            onClick={handleCopyPrMarkdown}
                          >
                            {copiedPr ? "✓ Copied!" : "📋 Copy PR Markdown"}
                          </button>
                        </div>
                      </div>
                      <div style={{ fontWeight: 700, fontSize: "0.88rem", marginBottom: "0.5rem" }}>
                        {currentRun.pull_request.title}
                      </div>
                      <pre className="code-box" style={{ whiteSpace: "pre-wrap" }}>
                        {currentRun.pull_request.body_markdown}
                      </pre>
                    </div>
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

