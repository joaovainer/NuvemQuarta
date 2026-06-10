const form = document.querySelector("#idea-form");
const demoButton = document.querySelector("#demo-button");
const refreshButton = document.querySelector("#refresh-button");
const message = document.querySelector("#form-message");
const ideasList = document.querySelector("#ideas-list");

const databaseStatus = document.querySelector("#database-status");
const redisStatus = document.querySelector("#redis-status");
const queueSize = document.querySelector("#queue-size");
const workerStatus = document.querySelector("#worker-status");

const statusLabel = {
  queued: "Na fila",
  processing: "Processando",
  done: "Concluida",
  failed: "Falhou",
};

function setMessage(text, isError = false) {
  message.textContent = text;
  message.style.color = isError ? "var(--red)" : "var(--muted)";
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `Erro HTTP ${response.status}`);
  }

  return response.json();
}

function renderStats(stats = {}) {
  databaseStatus.textContent = "ok";
  redisStatus.textContent = "ok";
  queueSize.textContent = stats.queue_size ?? 0;
  workerStatus.textContent = stats.worker_last_heartbeat ? "ativo" : "aguardando";
}

function renderIdeas(ideas) {
  if (!ideas.length) {
    ideasList.innerHTML = '<p class="hint">Nenhuma ideia ainda. Envie uma ou crie dados demo.</p>';
    return;
  }

  ideasList.innerHTML = ideas
    .map((idea) => {
      const tags = idea.tags?.length ? idea.tags : ["Aguardando analise"];
      const score = idea.analysis?.pontuacao ? `<span class="pill">Pontuacao ${idea.analysis.pontuacao}</span>` : "";
      const summary = idea.analysis?.resumo || "O worker ainda vai processar esta ideia.";
      return `
        <article class="idea">
          <div class="idea-header">
            <div>
              <h3>${escapeHtml(idea.title)}</h3>
              <p>Enviada por ${escapeHtml(idea.author)}</p>
            </div>
            <span class="status ${idea.status}">${statusLabel[idea.status] || idea.status}</span>
          </div>
          <p>${escapeHtml(idea.description)}</p>
          <p><strong>Analise:</strong> ${escapeHtml(summary)}</p>
          <div class="pill-row">
            ${tags.map((tag) => `<span class="pill">${escapeHtml(tag)}</span>`).join("")}
            ${score}
          </div>
        </article>
      `;
    })
    .join("");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function loadDashboard() {
  const payload = await request("/api/ideas");
  renderStats(payload.stats);
  renderIdeas(payload.ideas);
}

async function loadHealth() {
  try {
    const health = await request("/api/health");
    databaseStatus.textContent = health.database === "ok" ? "ok" : "erro";
    redisStatus.textContent = health.redis === "ok" ? "ok" : "erro";
    queueSize.textContent = health.queue_size ?? 0;
    workerStatus.textContent = health.worker_last_heartbeat ? "ativo" : "aguardando";
  } catch {
    databaseStatus.textContent = "erro";
    redisStatus.textContent = "erro";
    workerStatus.textContent = "offline";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submitButton = form.querySelector('button[type="submit"]');
  submitButton.disabled = true;
  setMessage("Enviando para a API...");

  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());

  try {
    await request("/api/ideas", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    form.reset();
    setMessage("Ideia salva. O worker deve processar em instantes.");
    await loadDashboard();
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    submitButton.disabled = false;
  }
});

demoButton.addEventListener("click", async () => {
  demoButton.disabled = true;
  setMessage("Criando dados demo...");
  try {
    await request("/api/demo", { method: "POST" });
    setMessage("Dados demo criados e enviados para a fila.");
    await loadDashboard();
  } catch (error) {
    setMessage(error.message, true);
  } finally {
    demoButton.disabled = false;
  }
});

refreshButton.addEventListener("click", loadDashboard);

loadHealth();
loadDashboard();
setInterval(loadDashboard, 3500);
setInterval(loadHealth, 5000);
