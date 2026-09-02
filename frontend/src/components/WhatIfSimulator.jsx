import { useState } from "react";

function WhatIfSimulator({
  missingSkills,
  currentScore,
  prioritizedSkills,
}) {
  const [selectedSkills, setSelectedSkills] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  function toggleSkill(skill) {
    setSelectedSkills((previous) => {
      if (previous.includes(skill)) {
        return previous.filter((item) => item !== skill);
      }

      return [...previous, skill];
    });

    setResult(null);
  }

  async function simulate() {
    if (selectedSkills.length === 0) {
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      let totalImprovement = 0;
      const individualResults = [];

      for (const skill of selectedSkills) {
        const priorityData = prioritizedSkills.find(
          (item) => item.skill === skill
        );

        const jobImportance =
          priorityData?.priority_score ?? 0.5;

        const response = await fetch(
          "http://127.0.0.1:8000/api/v1/career/what-if",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify({
              application_id: "app_123",
              skill: skill,
              current_match_score: currentScore,
              job_importance: jobImportance,
              current_level: 0,
              target_level: 1,
            }),
          }
        );

        if (!response.ok) {
          throw new Error(
            `Simulation failed for ${skill}`
          );
        }

        const data = await response.json();

        totalImprovement += data.estimated_improvement;

        individualResults.push(data);
      }

      const projectedScore = Math.min(
        currentScore + totalImprovement,
        100
      );

      setResult({
        currentScore: currentScore,
        projectedScore: Number(projectedScore.toFixed(2)),
        improvement: Number(totalImprovement.toFixed(2)),
        individualResults: individualResults,
      });

    } catch (error) {
      console.error(error);

      setResult({
        error:
          "Unable to calculate the projected match score.",
      });
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="dashboard-section what-if-section">

      <div className="section-heading">
        <div>
          <p className="eyebrow">
            ISSUE 42 + ISSUE 43
          </p>

          <h2>What-If Simulator</h2>
        </div>

        <p>
          Select skills you plan to learn and see how they
          could improve your job match.
        </p>
      </div>

      <div className="what-if-content">

        {/* SKILL SELECTION */}

        <div className="skill-selection">

          <h3>What if you learn...</h3>

          <div className="simulation-skills">

            {missingSkills.map((skill) => (

              <button
                key={skill}
                className={`simulation-skill ${
                  selectedSkills.includes(skill)
                    ? "selected"
                    : ""
                }`}
                onClick={() => toggleSkill(skill)}
              >

                <span className="checkbox">
                  {selectedSkills.includes(skill)
                    ? "✓"
                    : ""}
                </span>

                {skill}

              </button>

            ))}

          </div>

          <button
            className="simulate-button"
            onClick={simulate}
            disabled={
              selectedSkills.length === 0 ||
              loading
            }
          >
            {loading
              ? "Calculating..."
              : "Simulate Improvement"}
          </button>

        </div>

        {/* RESULT */}

        <div className="simulation-result">

          {!result && (
            <div className="result-placeholder">

              <div className="result-icon">
                ↗
              </div>

              <h3>See your potential</h3>

              <p>
                Select one or more skills to calculate
                your projected match score.
              </p>

            </div>
          )}

          {result?.error && (
            <div className="result-error">

              <h3>Simulation Error</h3>

              <p>{result.error}</p>

            </div>
          )}

          {result && !result.error && (
            <>

              <span className="card-label">
                PROJECTED MATCH
              </span>

              <div className="projected-score">
                {result.projectedScore}
                <span>%</span>
              </div>

              <div className="score-comparison">

                <div>
                  <span>Current</span>

                  <strong>
                    {result.currentScore}%
                  </strong>
                </div>

                <div className="arrow">
                  →
                </div>

                <div>
                  <span>Projected</span>

                  <strong>
                    {result.projectedScore}%
                  </strong>
                </div>

              </div>

              <div className="improvement">
                +{result.improvement}%
              </div>

              <p className="improvement-text">
                Estimated improvement from learning:
                {" "}
                {selectedSkills.join(", ")}
              </p>

            </>
          )}

        </div>

      </div>

    </section>
  );
}

export default WhatIfSimulator;