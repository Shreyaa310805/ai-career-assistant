function RecommendationSection({ recommendations }) {
  if (!recommendations || recommendations.length === 0) {
    return (
      <section className="dashboard-section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">ISSUE 44</p>
            <h2>Learning Recommendations</h2>
          </div>
        </div>

        <p className="empty-message">
          No learning recommendations available yet.
        </p>
      </section>
    );
  }

  return (
    <section className="dashboard-section recommendations-section">

      <div className="section-heading">
        <div>
          <p className="eyebrow">ISSUE 44</p>
          <h2>Learning Recommendations</h2>
        </div>

        <p>
          Curated resources to help you close your most important skill gaps.
        </p>
      </div>

      <div className="recommendation-list">

        {recommendations.map((recommendation) => (
          <div
            className="recommendation-group"
            key={recommendation.skill}
          >

            <div className="recommendation-header">

              <div>
                <h3>{recommendation.skill}</h3>
                <span className="resource-count">
                  {recommendation.resources.length} resources
                </span>
              </div>

              <span
                className={`priority-badge ${
                  recommendation.priority.toLowerCase()
                }`}
              >
                {recommendation.priority}
              </span>

            </div>

            <div className="resource-list">

              {recommendation.resources.map((resource, index) => (

                <div
                  className="resource-card"
                  key={`${resource.title}-${index}`}
                >

                  <div className="resource-icon">
                    {resource.type === "video" ? "▶" : "📘"}
                  </div>

                  <div className="resource-info">

                    <h4>{resource.title}</h4>

                    <div className="resource-meta">
                      <span>{resource.provider}</span>
                      <span>•</span>
                      <span>{resource.difficulty}</span>
                    </div>

                    <span
                      className={`source-label ${
                        resource.source === "external_api"
                          ? "external"
                          : "official"
                      }`}
                    >
                      {resource.source === "external_api"
                        ? "External"
                        : "Official"}
                    </span>

                  </div>

                  <a
                    href={resource.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="resource-button"
                  >
                    {resource.type === "video"
                      ? "Watch"
                      : "Learn"}
                    <span>→</span>
                  </a>

                </div>

              ))}

            </div>

          </div>
        ))}

      </div>

    </section>
  );
}

export default RecommendationSection;