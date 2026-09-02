function CareerRoadmap({ roadmap }) {
  if (!roadmap) {
    return (
      <section className="dashboard-section roadmap-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">ISSUE 45</p>
            <h2>Career & Skill Roadmap</h2>
          </div>

          <p>
            A structured path based on your skill gaps,
            priorities and learning resources.
          </p>
        </div>

        <div className="roadmap-loading">
          Loading your career roadmap...
        </div>
      </section>
    );
  }

  const prioritySkills = roadmap.prioritized_skills || [];
  const recommendations = roadmap.recommendations || [];

  return (
    <section className="dashboard-section roadmap-section">

      {/* HEADER */}

      <div className="section-heading">
        <div>
          <p className="eyebrow">ISSUE 45</p>

          <h2>Career & Skill Roadmap</h2>
        </div>

        <p>
          Your recommended learning journey for becoming
          a stronger {roadmap.role} candidate.
        </p>
      </div>

      {/* CURRENT STATUS */}

      <div className="roadmap-summary">

        <div className="summary-card">
          <span>ROLE</span>
          <strong>{roadmap.role}</strong>
        </div>

        <div className="summary-card">
          <span>COMPANY</span>
          <strong>{roadmap.company}</strong>
        </div>

        <div className="summary-card">
          <span>CURRENT MATCH</span>
          <strong>{roadmap.current_match_score}%</strong>
        </div>

        <div className="summary-card">
          <span>SKILL GAPS</span>
          <strong>
            {roadmap.skill_gap?.skill_gap_count || 0}
          </strong>
        </div>

      </div>

      {/* ROADMAP */}

      <div className="roadmap-timeline">

        {/* STEP 1 */}

        <div className="roadmap-step">

          <div className="timeline-marker">
            1
          </div>

          <div className="timeline-content">

            <span className="phase-label">
              STEP 1
            </span>

            <h3>Identify Your Skill Gaps</h3>

            <p>
              These are the skills currently missing from
              your profile for this role.
            </p>

            <div className="roadmap-skills">

              {roadmap.skill_gap?.missing_skills?.map(
                (skill) => (
                  <span
                    className="roadmap-skill"
                    key={skill}
                  >
                    {skill}
                  </span>
                )
              )}

            </div>

          </div>

        </div>

        {/* STEP 2 */}

        <div className="roadmap-step">

          <div className="timeline-marker">
            2
          </div>

          <div className="timeline-content">

            <span className="phase-label">
              STEP 2
            </span>

            <h3>Learn High-Priority Skills</h3>

            <p>
              Focus first on the skills that can have the
              greatest impact on your job match.
            </p>

            <div className="priority-list">

              {prioritySkills.map((item) => (

                <div
                  className="priority-roadmap-card"
                  key={item.skill}
                >

                  <div>
                    <strong>{item.skill}</strong>

                    <p>
                      {item.reason}
                    </p>
                  </div>

                  <div className="priority-score">

                    <span>
                      {item.priority}
                    </span>

                    <strong>
                      {item.priority_score}
                    </strong>

                  </div>

                </div>

              ))}

            </div>

          </div>

        </div>

        {/* STEP 3 */}

        <div className="roadmap-step">

          <div className="timeline-marker">
            3
          </div>

          <div className="timeline-content">

            <span className="phase-label">
              STEP 3
            </span>

            <h3>Follow Learning Resources</h3>

            <p>
              Use the recommended resources to build each
              missing skill.
            </p>

            <div className="resource-list">

              {recommendations.map(
                (recommendation) => (

                  <div
                    className="resource-roadmap-card"
                    key={recommendation.skill}
                  >

                    <div className="resource-header">

                      <strong>
                        {recommendation.skill}
                      </strong>

                      <span>
                        {recommendation.priority}
                      </span>

                    </div>

                    <div className="resource-items">

                      {recommendation.resources
                        ?.slice(0, 2)
                        .map((resource) => (

                          <a
                            key={resource.url}
                            href={resource.url}
                            target="_blank"
                            rel="noreferrer"
                            className="resource-link"
                          >

                            <span>
                              {resource.title}
                            </span>

                            <span>
                              →
                            </span>

                          </a>

                        ))}

                    </div>

                  </div>

                )
              )}

            </div>

          </div>

        </div>

        {/* STEP 4 */}

        <div className="roadmap-step final-step">

          <div className="timeline-marker">
            4
          </div>

          <div className="timeline-content">

            <span className="phase-label">
              STEP 4
            </span>

            <h3>Simulate Your Improvement</h3>

            <p>
              Use the What-If Simulator to estimate how
              learning these skills could improve your match.
            </p>

            <div className="roadmap-final-card">

              <strong>
                Ready to test your potential?
              </strong>

              <p>
                Select skills in the What-If Simulator and
                compare your current and estimated match score.
              </p>

            </div>

          </div>

        </div>

      </div>

    </section>
  );
}

export default CareerRoadmap;