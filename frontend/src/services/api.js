const API_BASE_URL = "http://127.0.0.1:8000/api/v1/career";
const REQUEST_TIMEOUT_MS = 15_000;

export async function getCareerRoadmap(applicationId, signal) {
  const timeoutController = new AbortController();
  const timeoutId = window.setTimeout(
    () => timeoutController.abort(),
    REQUEST_TIMEOUT_MS,
  );

  try {
    const response = await fetch(
      `${API_BASE_URL}/roadmap/${applicationId}`,
      { signal: AbortSignal.any([signal, timeoutController.signal].filter(Boolean)) },
    );

    if (!response.ok) {
      throw new Error("Failed to fetch career roadmap");
    }

    return response.json();
  } catch (error) {
    if (error.name === "AbortError" && !signal?.aborted) {
      throw new Error("The career roadmap request timed out. Please try again.");
    }

    throw error;
  } finally {
    window.clearTimeout(timeoutId);
  }
}

export async function getRoadmap(applicationId) {
  const response = await fetch(`${API_BASE_URL}/roadmap/${applicationId}`);

  if (!response.ok) {
    throw new Error("Failed to fetch roadmap");
  }

  return response.json();
}
