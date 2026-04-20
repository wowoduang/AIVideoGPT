const API_BASE_URL = "/api/v1";

export async function analyzeVideo(file: File) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/video/analyze`, {
    method: "POST",
    body: formData,
  });
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to analyze video");
  }
  const data = await response.json();
  return data.analysis;
}

export async function generateScript(analysis: string, config: any) {
  const response = await fetch(`${API_BASE_URL}/script/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ analysis, config }),
  });
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to generate script");
  }
  const data = await response.json();
  return data.script;
}

export async function generateVoiceover(script: string) {
  const response = await fetch(`${API_BASE_URL}/audio/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ script }),
  });
  
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.detail || "Failed to generate audio");
  }
  
  const data = await response.json();
  return data.audioUrl;
}
