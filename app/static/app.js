document.addEventListener("DOMContentLoaded", () => {
  const experimentForm = document.getElementById("experiment-form");
  const experimentsList = document.getElementById("experiments-list");
  const statusSummary = document.getElementById("status-summary");
  const conversationLog = document.getElementById("conversation-log");
  const statusSection = document.getElementById("experiment-status");

  let currentExperimentId = null;

  const fetchExperiments = () => {
    fetch("/api/experiments")
      .then((res) => res.json())
      .then((data) => {
        experimentsList.innerHTML = "";
        data.forEach((exp) => {
          const li = document.createElement("li");
          li.classList.add("list-group-item");
          li.textContent = `#${exp.id}: ${exp.status}`;
          li.style.cursor = "pointer";
          li.onclick = () => selectExperiment(exp.id);
          experimentsList.appendChild(li);
        });
      });
  };

  const selectExperiment = (id) => {
    currentExperimentId = id;
    statusSection.style.display = "block";
    updateExperimentStatus();
  };

  const updateExperimentStatus = () => {
    if (!currentExperimentId) return;

    fetch(`/api/experiments/${currentExperimentId}`)
      .then((res) => res.json())
      .then((data) => {
        statusSummary.innerHTML = `<strong>Status:</strong> ${data.status}`;
        conversationLog.textContent = data.conversation
          .map((m) => `${m.sender}: ${m.content}`)
          .join("\n\n");
      });
  };

  experimentForm.addEventListener("submit", (e) => {
    e.preventDefault();

    const formData = new FormData(experimentForm);
    const payload = {
      prompt: formData.get("prompt"),
      ai_client: formData.get("ai_client"),
      model: formData.get("model"),
    };

    fetch("/api/experiments", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    })
      .then((res) => res.json())
      .then((data) => {
        fetchExperiments();
        selectExperiment(data.id);
      });
  });

  setInterval(() => {
    if (currentExperimentId) {
      updateExperimentStatus();
    }
  }, 3000);

  fetchExperiments();
});
