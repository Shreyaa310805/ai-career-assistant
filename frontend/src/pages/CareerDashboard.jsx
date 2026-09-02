import { useEffect, useState } from "react";
import { getCareerRoadmap } from "../services/api";
import RecommendationSection from "../components/RecommendationSection";
import WhatIfSimulator from "../components/WhatIfSimulator";
import CareerRoadmap from "../components/CareerRoadmap";
import "./CareerDashboard.css";

function CareerDashboard() {
  const [roadmap, setRoadmap] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();

    async function loadRoadmap() {
      try {
        const data = await getCareerRoadmap("app_123", controller.signal);

        if (!controller.signal.aborted) {
          setRoadmap(data);
        }
      } catch (loadError) {
        if (!controller.signal.aborted) {
          console.error("Roadmap error:", loadError);
          setError(
            "We couldn't load your career roadmap. Make sure the API server is running and try again.",
          );
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadRoadmap();

    return () => controller.abort();
  }, []);

  if (loading) {
    return (
      <div className="status-container">
        <div className="loader"></div>
        <h2>Loading your career intelligence...</h2>
      </div>
    );
  }

  if (error) {
    return (
      <div className="status-container">
        <h2>Something went wrong</h2>
        <p>{error}</p>
      </div>
    );
  }

  const {
    company,
    role,
    current_match_score,
    skill_gap,
    prioritized_skills,
  } = roadmap;

  return (
    <div className="dashboard">

      {/* HEADER */}
      <header className="dashboard-header">
        <div>
          <p className="eyebrow">CAREER INTELLIGENCE</p>
          <h1>Your Career Growth Dashboard</h1>
          <p className="subtitle">
            Understand your skill gaps and build your path toward your target role.
          </p>
        </div>

        <div className="role-badge">
          <span>Target Role</span>
          <strong>{role}</strong>
          <small>{company}</small>
        </div>
      </header>

      {/* SUMMARY CARDS */}
      <section className="summary-grid">

        <div className="summary-card score-card">
          <span className="card-label">CURRENT MATCH</span>

          <div className="score-value">
            {current_match_score}
            <span>%</span>
          </div>

          <div className="progress-bar">
            <div
              className="progress-fill"
              style={{ width: `${current_match_score}%` }}
            ></div>
          </div>

          <p>Match between your current skills and target role.</p>
        </div>

        <div className="summary-card">
          <span className="card-label">MISSING SKILLS</span>
          <div className="big-number">
            {skill_gap.skill_gap_count}
          </div>
          <p>Skills to focus on next.</p>
        </div>

        <div className="summary-card">
          <span className="card-label">MATCHED SKILLS</span>
          <div className="big-number">
            {skill_gap.matched_skills.length}
          </div>
          <p>Skills already aligned with the role.</p>
        </div>

      </section>

      {/* SKILL GAP */}
      <section className="dashboard-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">ISSUE 40</p>
            <h2>Skill Gap Analysis</h2>
          </div>
          <p>
            Compare your current skills with the requirements
            for {role}.
          </p>
        </div>

        <div className="skill-gap-grid">

          <div className="skill-group matched-group">
            <h3>✓ Matched Skills</h3>

            <div className="skill-tags">
              {skill_gap.matched_skills.map((skill) => (
                <span className="skill-tag matched" key={skill}>
                  {skill}
                </span>
              ))}
            </div>
          </div>

          <div className="skill-group missing-group">
            <h3>! Skills to Develop</h3>

            <div className="skill-tags">
              {skill_gap.missing_skills.map((skill) => (
                <span className="skill-tag missing" key={skill}>
                  {skill}
                </span>
              ))}
            </div>
          </div>

          <div className="skill-group extra-group">
            <h3>+ Additional Skills</h3>

            <div className="skill-tags">
              {skill_gap.extra_skills.map((skill) => (
                <span className="skill-tag extra" key={skill}>
                  {skill}
                </span>
              ))}
            </div>
          </div>

        </div>
      </section>

      {/* PRIORITY SKILLS */}
      <section className="dashboard-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">ISSUE 41</p>
            <h2>Skill Priority</h2>
          </div>

          <p>
            Start with the skills that have the greatest impact
            on your target role.
          </p>
        </div>

        <div className="priority-grid">
          {prioritized_skills.map((item) => (
            <div className="priority-card" key={item.skill}>

              <div className="priority-top">
                <h3>{item.skill}</h3>

                <span
                  className={`priority-badge ${item.priority.toLowerCase()}`}
                >
                  {item.priority}
                </span>
              </div>

              <div className="priority-score">
                <div className="priority-progress">
                  <div
                    className="priority-fill"
                    style={{
                      width: `${item.priority_score * 100}%`,
                    }}
                  ></div>
                </div>

                <span>
                  {Math.round(item.priority_score * 100)}% Priority
                </span>
              </div>

              <p>{item.reason}</p>
            </div>
          ))}
        </div>
      </section>
      <RecommendationSection
        recommendations={roadmap.recommendations}
      />

      <WhatIfSimulator
        missingSkills={skill_gap.missing_skills}
        currentScore={current_match_score}
        prioritizedSkills={prioritized_skills}
      />

      <CareerRoadmap roadmap={roadmap} />

    </div>
  );
}

export default CareerDashboard;
