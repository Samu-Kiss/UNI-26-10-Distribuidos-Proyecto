const svg = document.getElementById("city");
    const mapWrap = document.getElementById("mapWrap");
    const endScreen = document.getElementById("endScreen");
    const inspector = document.getElementById("inspector");
    const statusDot = document.getElementById("statusDot");
    const statusText = document.getElementById("statusText");
    const tickEl = document.getElementById("tick");
    const realClockEl = document.getElementById("realClock");
    const simClockEl = document.getElementById("simClock");
    const updatedEl = document.getElementById("updated");
    const simInfoButton = document.getElementById("simInfoButton");
    const simInfoPanel = document.getElementById("simInfoPanel");
    const manualControlButton = document.getElementById("manualControlButton");
    const manualControlPanel = document.getElementById("manualControlPanel");
    const ambulanceButton = document.getElementById("ambulanceButton");
    const ambulancePanel = document.getElementById("ambulancePanel");
    const defaultScoreConfig = {
      pesos: { camara: 0.5, espira_inductiva: 0.35, gps: 0.15 },
      umbrales: { bajo: 0.4, alto: 0.7 },
    };

    let lastState = null;
    let scoreConfig = defaultScoreConfig;
    let simulationConfig = null;
    let refreshIntervalId = null;
    let refreshIntervalMs = null;
    let refreshInFlight = false;
    let simPanelOpen = false;
    let manualPanelOpen = false;
    let ambulancePanelOpen = false;
    let controlRequestInFlight = false;
    let ambulanceRequestInFlight = false;
    let manualTargetSuffix = "";
    let manualMessage = "";
    let manualDesiredMode = null;
    let ambulanceSideValue = "";
    let ambulanceRefValue = "";
    let ambulanceMessage = "";
    const INTERSECTION_RADIUS = 32;
    const BORDER_NODE_HALF = 11;
    const VEHICLE_RADIUS = 5.5;
    const WAITING_ANGLE_STEP = 0.18;

    function rowIndex(label) {
      let value = 0;
      for (const ch of label) value = value * 26 + (ch.charCodeAt(0) - 64);
      return value - 1;
    }

    function rowLabel(index) {
      let n = index + 1;
      let out = "";
      while (n > 0) {
        const rem = (n - 1) % 26;
        out = String.fromCharCode(65 + rem) + out;
        n = Math.floor((n - 1) / 26);
      }
      return out;
    }

    function parseNode(id, rows, cols, intersections) {
      const inter = id.match(/^INT-([A-Z]+)(\d+)$/);
      if (inter) {
        const fila = rowIndex(inter[1]);
        const columna = Number(inter[2]) - 1;
        return {
          id,
          tipo: "INTERSECCION",
          x: columna,
          y: fila,
          coordenada: `${inter[1]}${inter[2]}`,
          fila: inter[1],
          columna: Number(inter[2]),
          estado: intersections.get(id) || null,
        };
      }
      const border = id.match(/^BORDE-([NSEO])-([A-Z]+|\d+)$/);
      if (border) {
        const lado = border[1];
        const valor = border[2];
        if (lado === "N") return { id, tipo: "BORDE", lado: "NORTE", x: Number(valor) - 1, y: -1, coordenada: `N${valor}` };
        if (lado === "S") return { id, tipo: "BORDE", lado: "SUR", x: Number(valor) - 1, y: rows, coordenada: `S${valor}` };
        if (lado === "O") return { id, tipo: "BORDE", lado: "OESTE", x: -1, y: rowIndex(valor), coordenada: `O${valor}` };
        return { id, tipo: "BORDE", lado: "ESTE", x: cols, y: rowIndex(valor), coordenada: `E${valor}` };
      }
      return { id, tipo: "NODO", x: 0, y: 0, coordenada: id };
    }

    function clamp01(value) {
      return Math.max(0, Math.min(1, Number(value || 0)));
    }

    function normalizarCamara(vehiculosEnEspera) {
      return clamp01(Number(vehiculosEnEspera || 0) / 10);
    }

    function normalizarEspira(vehiculosEnCirculacion) {
      return clamp01(Number(vehiculosEnCirculacion || 0) / 10);
    }

    function normalizarGps(velocidadPromedio) {
      let velocidad = Math.max(Number(velocidadPromedio || 0), 0);
      if (velocidad === 0) return 0;
      if (velocidad < 10) return 1;
      if (velocidad > 50) velocidad = 50;
      return Number((1 - 0.9 * ((velocidad - 10) / 40)).toFixed(4));
    }

    function round4(value) {
      return Number(Number(value || 0).toFixed(4));
    }

    function viaHasAmbulance(via, state = lastState) {
      if (!state) return false;
      return state.vehiculos.some((veh) => veh.via_actual === via.via_id && veh.tipo === "AMBULANCIA");
    }

    function scoreBreakdown(via, state = lastState) {
      const pesos = { ...defaultScoreConfig.pesos, ...(scoreConfig.pesos || {}) };
      if (viaHasAmbulance(via, state)) {
        return {
          pesos,
          notas: { camara: 1, espira_inductiva: 1, gps: 1 },
          contribuciones: {
            camara: round4(Number(pesos.camara || 0)),
            espira_inductiva: round4(Number(pesos.espira_inductiva || 0)),
            gps: round4(Number(pesos.gps || 0)),
          },
          total: 1,
          prioridadAmbulancia: true,
        };
      }
      const notas = {
        camara: normalizarCamara(via.vehiculos_en_espera),
        espira_inductiva: normalizarEspira(via.vehiculos_en_circulacion),
        gps: normalizarGps(via.velocidad_promedio),
      };
      const contribuciones = {
        camara: round4(notas.camara * Number(pesos.camara || 0)),
        espira_inductiva: round4(notas.espira_inductiva * Number(pesos.espira_inductiva || 0)),
        gps: round4(notas.gps * Number(pesos.gps || 0)),
      };
      const total = round4(contribuciones.camara + contribuciones.espira_inductiva + contribuciones.gps);
      return { pesos, notas, contribuciones, total, prioridadAmbulancia: false };
    }

    function colorByScore(score) {
      const value = Number(score || 0);
      const umbrales = { ...defaultScoreConfig.umbrales, ...(scoreConfig.umbrales || {}) };
      if (value < Number(umbrales.bajo)) return getCss("--green");
      if (value <= Number(umbrales.alto)) return getCss("--yellow");
      return getCss("--red");
    }

    function estadoPorScore(score) {
      const value = Number(score || 0);
      const umbrales = { ...defaultScoreConfig.umbrales, ...(scoreConfig.umbrales || {}) };
      if (value < Number(umbrales.bajo)) return "BAJA";
      if (value <= Number(umbrales.alto)) return "NORMAL";
      return "ALTA";
    }

    function getCss(name) {
      return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    }

    function buildGraph(state) {
      const intersections = new Map(state.intersecciones.map((item) => [item.interseccion_id, item]));
      const nodeIds = new Set();
      for (const via of state.vias) {
        nodeIds.add(via.origen);
        nodeIds.add(via.destino);
      }
      for (const item of state.intersecciones) nodeIds.add(item.interseccion_id);

      let maxRow = 0;
      let maxCol = 0;
      for (const item of state.intersecciones) {
        const parsed = item.interseccion_id.match(/^INT-([A-Z]+)(\d+)$/);
        if (!parsed) continue;
        maxRow = Math.max(maxRow, rowIndex(parsed[1]));
        maxCol = Math.max(maxCol, Number(parsed[2]) - 1);
      }
      const rows = maxRow + 1;
      const cols = maxCol + 1;
      const nodes = new Map([...nodeIds].map((id) => [id, parseNode(id, rows, cols, intersections)]));
      return { nodes, rows, cols };
    }

    function project(node, graph) {
      const rect = svg.getBoundingClientRect();
      const width = Math.max(rect.width, 640);
      const height = Math.max(rect.height, 480);
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      const minX = -1;
      const maxX = graph.cols;
      const minY = -1;
      const maxY = graph.rows;
      const pad = 72;
      const usableW = Math.max(1, width - pad * 2);
      const usableH = Math.max(1, height - pad * 2);
      const scale = Math.min(usableW / Math.max(1, maxX - minX), usableH / Math.max(1, maxY - minY));
      const offsetX = (width - (maxX - minX) * scale) / 2;
      const offsetY = (height - (maxY - minY) * scale) / 2;
      return {
        x: offsetX + (node.x - minX) * scale,
        y: offsetY + (node.y - minY) * scale,
      };
    }

    function el(name, attrs = {}) {
      const node = document.createElementNS("http://www.w3.org/2000/svg", name);
      for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
      return node;
    }

    function nodeEdgePadding(node) {
      if (node?.tipo === "INTERSECCION") return INTERSECTION_RADIUS;
      return BORDER_NODE_HALF;
    }

    function edgeSegment(a, b, sourceNode, targetNode) {
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const len = Math.hypot(dx, dy) || 1;
      const ux = dx / len;
      const uy = dy / len;
      const startPadding = Math.min(nodeEdgePadding(sourceNode), len * 0.35);
      const endPadding = Math.min(nodeEdgePadding(targetNode), len * 0.35);
      return {
        start: { x: a.x + ux * startPadding, y: a.y + uy * startPadding },
        end: { x: b.x - ux * endPadding, y: b.y - uy * endPadding },
        ux,
        uy,
      };
    }

    function arrowPoints(a, b, size, tipInset = 0) {
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const len = Math.hypot(dx, dy) || 1;
      const ux = dx / len;
      const uy = dy / len;
      const px = -uy;
      const py = ux;
      const tip = { x: b.x - ux * tipInset, y: b.y - uy * tipInset };
      const base = { x: tip.x - ux * size, y: tip.y - uy * size };
      return [
        [tip.x, tip.y],
        [base.x + px * size * 0.68, base.y + py * size * 0.68],
        [base.x - px * size * 0.68, base.y - py * size * 0.68],
      ].map((p) => p.join(",")).join(" ");
    }

    function waitingPointOnNodeBorder(a, b, targetNode, queueIndex) {
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const len = Math.hypot(dx, dy) || 1;
      const ux = dx / len;
      const uy = dy / len;
      const radius = targetNode?.tipo === "INTERSECCION" ? INTERSECTION_RADIUS : BORDER_NODE_HALF;
      const stopRadius = targetNode?.tipo === "INTERSECCION" ? radius + VEHICLE_RADIUS + 1 : radius;
      const baseAngle = Math.atan2(-uy, -ux);
      const offsetStep = Math.ceil(queueIndex / 2);
      const offsetSign = queueIndex % 2 === 0 ? -1 : 1;
      const angle = baseAngle + offsetSign * offsetStep * WAITING_ANGLE_STEP;
      return {
        x: b.x + Math.cos(angle) * stopRadius,
        y: b.y + Math.sin(angle) * stopRadius,
      };
    }

    function semaforoDesfavorable(via, graph) {
      const destino = graph.nodes.get(via.destino);
      if (!destino || destino.tipo !== "INTERSECCION" || !destino.estado) return false;
      return destino.estado.fase_activa !== via.eje;
    }

    function draw(state) {
      svg.replaceChildren();
      const graph = buildGraph(state);
      const edgeLayer = el("g");
      const arrowLayer = el("g");
      const hitLayer = el("g");
      const nodeLayer = el("g");
      const vehicleLayer = el("g");
      svg.append(edgeLayer, hitLayer, nodeLayer, arrowLayer, vehicleLayer);

      const positions = new Map();
      for (const [id, node] of graph.nodes) positions.set(id, project(node, graph));

      for (const via of state.vias) {
        const a = positions.get(via.origen);
        const b = positions.get(via.destino);
        if (!a || !b) continue;
        const origen = graph.nodes.get(via.origen);
        const destino = graph.nodes.get(via.destino);
        const segment = edgeSegment(a, b, origen, destino);
        const scoreData = scoreBreakdown(via, state);
        const color = colorByScore(scoreData.total);
        const width = scoreData.total < 0.4 ? 20 : 14 + Math.min(10, scoreData.total * 10);
        const arrowSize = Math.max(38, width * 2.35);
        const line = el("line", {
          x1: segment.start.x, y1: segment.start.y, x2: segment.end.x, y2: segment.end.y,
          stroke: color,
          "stroke-width": width,
          class: "road",
        });
        const arrow = el("polygon", {
          points: arrowPoints(segment.start, segment.end, arrowSize, 0),
          fill: color,
          class: "arrow",
        });
        const hit = el("line", {
          x1: segment.start.x, y1: segment.start.y, x2: segment.end.x, y2: segment.end.y,
          class: "road-hit",
        });
        hit.addEventListener("mouseenter", () => focusItem(viaInfo(via, state)));
        edgeLayer.append(line);
        arrowLayer.append(arrow);
        hitLayer.append(hit);
      }

      for (const [id, node] of graph.nodes) {
        const p = positions.get(id);
        if (!p) continue;
        const isIntersection = node.tipo === "INTERSECCION";
        const isSpawn = !isIntersection && state.vias.some((via) => via.origen === id);
        const fill = isIntersection ? phaseColor(node.estado?.fase_activa) : (isSpawn ? "#111827" : "#6b7280");
        const shape = isIntersection
          ? el("circle", { cx: p.x, cy: p.y, r: INTERSECTION_RADIUS, fill, class: "node" })
          : el("rect", { x: p.x - 11, y: p.y - 11, width: 22, height: 22, rx: 4, fill, class: "node" });
        shape.addEventListener("mouseenter", () => focusItem(nodeInfo(node, state)));
        nodeLayer.append(shape);
      }

      const viaById = new Map(state.vias.map((via) => [via.via_id, via]));
      const waitingByVia = new Map();
      for (const veh of state.vehiculos) {
        const via = viaById.get(veh.via_actual);
        if (!via) continue;
        const a = positions.get(via.origen);
        const b = positions.get(via.destino);
        if (!a || !b) continue;
        const origen = graph.nodes.get(via.origen);
        const destino = graph.nodes.get(via.destino);
        const segment = edgeSegment(a, b, origen, destino);
        const ratio = Math.max(0, Math.min(1, Number(veh.posicion_en_via || 0) / Math.max(1, Number(via.longitud || 1))));
        let x = segment.start.x + (segment.end.x - segment.start.x) * ratio;
        let y = segment.start.y + (segment.end.y - segment.start.y) * ratio;
        const segmentLength = Math.hypot(segment.end.x - segment.start.x, segment.end.y - segment.start.y) || 1;
        const redStopRatio = Math.max(0, 1 - ((VEHICLE_RADIUS + 1) / segmentLength));
        const isAmb = veh.tipo === "AMBULANCIA";
        const mustStopForRed = veh.estado === "EN_COLA" || (
          veh.estado === "CIRCULANDO"
          && semaforoDesfavorable(via, graph)
          && ratio >= redStopRatio
        );
        if (mustStopForRed) {
          const queueIndex = waitingByVia.get(via.via_id) || 0;
          waitingByVia.set(via.via_id, queueIndex + 1);
          const stop = waitingPointOnNodeBorder(a, b, destino, queueIndex);
          x = stop.x;
          y = stop.y;
        }
        const vehicle = isAmb
          ? el("rect", { x: x - 5, y: y - 5, width: 10, height: 10, rx: 2, fill: "#ef4444", class: "vehicle" })
          : el("circle", { cx: x, cy: y, r: VEHICLE_RADIUS, fill: mustStopForRed ? "#dc2626" : "#0f172a", class: "vehicle" });
        vehicle.addEventListener("mouseenter", () => focusItem(vehicleInfo(veh)));
        vehicleLayer.append(vehicle);
      }
    }

    function phaseColor(phase) {
      if (phase === "HORIZONTAL") return getCss("--blue");
      if (phase === "VERTICAL") return getCss("--violet");
      return getCss("--node");
    }

    function fmt(value) {
      if (value === null || value === undefined || value === "") return "--";
      if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(3).replace(/0+$/, "").replace(/\.$/, "");
      return String(value);
    }

    function minutesFromHour(value) {
      const parts = String(value || "00:00").split(":").map((part) => Number(part));
      if (parts.length < 2 || parts.some((part) => Number.isNaN(part))) return 0;
      return parts[0] * 60 + parts[1];
    }

    function hourFromMinutes(totalMinutes) {
      const normalized = ((Math.floor(totalMinutes) % 1440) + 1440) % 1440;
      const hours = Math.floor(normalized / 60);
      const minutes = normalized % 60;
      return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
    }

    function simulatedClock(state) {
      if (!simulationConfig || !state) return "--";
      const tick = Number(state.resumen?.tick_actual || 0);
      const minutesPerTick = Number(simulationConfig.minutos_simulados_por_tick || 1);
      const start = simulationConfig.modo_bucle_infinito
        ? 0
        : minutesFromHour(simulationConfig.hora_inicio_simulada || "12:00");
      return hourFromMinutes(start + tick * minutesPerTick);
    }

    function tickRatePerSecond() {
      const tickSeconds = Number(simulationConfig?.tick_segundos_reales || 0);
      if (!Number.isFinite(tickSeconds) || tickSeconds <= 0) return "--";
      return `${(1 / tickSeconds).toFixed(2)} ticks/s`;
    }

    function updateRealClock() {
      realClockEl.textContent = new Date().toLocaleTimeString();
    }

    function desiredRefreshIntervalMs() {
      const seconds = Number(simulationConfig?.tick_segundos_reales || 1);
      if (!Number.isFinite(seconds) || seconds <= 0) return 1000;
      return Math.max(1, Math.round(seconds * 1000));
    }

    function ensureRefreshInterval() {
      const nextInterval = desiredRefreshIntervalMs();
      if (refreshIntervalId !== null && refreshIntervalMs === nextInterval) return;
      if (refreshIntervalId !== null) clearInterval(refreshIntervalId);
      refreshIntervalMs = nextInterval;
      refreshIntervalId = setInterval(refresh, refreshIntervalMs);
    }

    function simulatedDurationMinutes(config) {
      if (config?.modo_bucle_infinito) return 24 * 60;
      const start = minutesFromHour(config?.hora_inicio_simulada || "12:00");
      const end = minutesFromHour(config?.hora_fin_simulada || "18:00");
      let duration = end - start;
      if (duration <= 0) duration += 24 * 60;
      return duration;
    }

    function isSimulationFinished(state) {
      if (!simulationConfig || simulationConfig.modo_bucle_infinito) return false;
      const tick = Number(state.resumen?.tick_actual || 0);
      const minutesPerTick = Number(simulationConfig.minutos_simulados_por_tick || 1);
      return tick > 0 && tick * minutesPerTick >= simulatedDurationMinutes(simulationConfig);
    }

    function formatDateTime(value) {
      if (!value) return "--";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return fmt(value);
      return date.toLocaleString();
    }

    function theoreticalDurationSeconds() {
      if (!simulationConfig || simulationConfig.modo_bucle_infinito) return null;
      const minutesPerTick = Number(simulationConfig.minutos_simulados_por_tick || 1);
      const tickSeconds = Number(simulationConfig.tick_segundos_reales || 1);
      if (minutesPerTick <= 0 || tickSeconds <= 0) return null;
      const totalTicks = Math.ceil(simulatedDurationMinutes(simulationConfig) / minutesPerTick);
      return totalTicks * tickSeconds;
    }

    function realDurationSeconds(resumen) {
      const start = new Date(resumen.inicio_real || "");
      const end = new Date(resumen.actualizado_en || "");
      if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return null;
      return Math.max(0, (end.getTime() - start.getTime()) / 1000);
    }

    function formatDuration(seconds) {
      if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return "--";
      if (seconds < 60) return `${seconds.toFixed(2)} s`;
      const minutes = Math.floor(seconds / 60);
      const rest = seconds - minutes * 60;
      return `${minutes} min ${rest.toFixed(1)} s`;
    }

    function formatOverhead(realSeconds, theoreticalSeconds) {
      if (realSeconds === null || theoreticalSeconds === null || theoreticalSeconds <= 0) return "--";
      const delta = realSeconds - theoreticalSeconds;
      const pct = (delta / theoreticalSeconds) * 100;
      return `${delta >= 0 ? "+" : ""}${delta.toFixed(2)} s (${pct >= 0 ? "+" : ""}${pct.toFixed(1)}%)`;
    }

    function renderEndScreen(state) {
      const resumen = state.resumen || {};
      const teorico = theoreticalDurationSeconds();
      const real = realDurationSeconds(resumen);
      svg.replaceChildren();
      simInfoButton.classList.remove("active");
      manualControlButton.classList.remove("active");
      ambulanceButton.classList.remove("active");
      simPanelOpen = false;
      manualPanelOpen = false;
      ambulancePanelOpen = false;
      simInfoPanel.classList.remove("visible");
      manualControlPanel.classList.remove("visible");
      ambulancePanel.classList.remove("visible");
      endScreen.innerHTML = `
        <div class="end-panel">
          <h1>Simulacion terminada</h1>
          <p>El dia simulado alcanzo la hora final configurada.</p>
          <div class="end-stats">
            <div class="end-stat"><span>Hora de inicio</span><strong>${fmt(simulationConfig?.hora_inicio_simulada)}</strong></div>
            <div class="end-stat"><span>Hora de fin</span><strong>${fmt(simulationConfig?.hora_fin_simulada)}</strong></div>
            <div class="end-stat"><span>Tick final</span><strong>${fmt(resumen.tick_actual)}</strong></div>
            <div class="end-stat"><span>Cierre registrado</span><strong>${formatDateTime(resumen.actualizado_en)}</strong></div>
            <div class="end-stat"><span>Tiempo real observado</span><strong>${formatDuration(real)}</strong></div>
            <div class="end-stat"><span>Tiempo teorico</span><strong>${formatDuration(teorico)}</strong></div>
            <div class="end-stat"><span>Overhead / latencia</span><strong>${formatOverhead(real, teorico)}</strong></div>
          </div>
        </div>
      `;
      endScreen.classList.add("visible");
      inspector.innerHTML = `<div class="empty">Simulacion terminada. El mapa queda oculto y se conserva la ultima estadistica publicada.</div>`;
    }

    function hideEndScreen() {
      endScreen.classList.remove("visible");
      endScreen.innerHTML = "";
    }

    function kvHtml(rows) {
      return `<div class="kv">${rows.map(([k, v]) => `<div>${k}</div><div>${fmt(v)}</div>`).join("")}</div>`;
    }

    function scoreCardHtml(via, scoreData) {
      const guardado = Number(via.score || 0);
      const diferencia = Math.abs(guardado - scoreData.total);
      if (scoreData.prioridadAmbulancia) {
        return `
          <section class="score-card">
            <div class="score-head">
              <h3>Score</h3>
              <div class="score-total">1</div>
            </div>
            <div class="score-formula">Prioridad de ambulancia activa<br>congestion: ALTA</div>
            <div class="info-box">La via tiene una ambulancia en transito o en espera. Por regla operativa, su score se fuerza a 1.00 y el eje recibe prioridad total.</div>
          </section>
        `;
      }
      const sensorRows = [
        [
          "Camara",
          "camara",
          "Evalua la cola al final de la via antes del semaforo.",
          `vehiculos en cola=${fmt(via.vehiculos_en_espera)}`,
        ],
        [
          "Espira",
          "espira_inductiva",
          "Evalua la ocupacion de vehiculos que aun circulan por la via.",
          `vehiculos en circulacion=${fmt(via.vehiculos_en_circulacion)}`,
        ],
        [
          "GPS",
          "gps",
          "Evalua la lentitud del flujo a partir de la velocidad promedio.",
          `velocidad promedio=${fmt(via.velocidad_promedio)}`,
        ],
      ];
      const formula = `score = camara*${fmt(scoreData.pesos.camara)} + espira*${fmt(scoreData.pesos.espira_inductiva)} + gps*${fmt(scoreData.pesos.gps)}`;
      const warning = diferencia > 0.005
        ? `<div class="score-warning">Score guardado en BD: ${fmt(guardado)}. La vista usa el score recalculado con las metricas actuales.</div>`
        : "";
      return `
        <section class="score-card">
          <div class="score-head">
            <h3>Score</h3>
            <div class="score-total">${fmt(scoreData.total)}</div>
          </div>
          <div class="score-formula">${formula}<br>congestion: ${estadoPorScore(scoreData.total)}</div>
          ${sensorRows.map(([label, key, descripcion, fuente]) => {
            const nota = scoreData.notas[key];
            const peso = scoreData.pesos[key];
            const contribucion = scoreData.contribuciones[key];
            return `
              <div class="score-row">
                <div class="score-label">${label}</div>
                <div>
                  <div class="score-bar"><div class="score-fill" style="width: ${nota * 100}%; background: ${colorByScore(nota)}"></div></div>
                  <div class="score-detail">${descripcion}<br>nota ${fmt(nota)} * peso ${fmt(peso)} = ${fmt(contribucion)}<br>${fuente}</div>
                </div>
              </div>
            `;
          }).join("")}
          ${warning}
        </section>
      `;
    }

    function scoreText(via, scoreData) {
      return [
        `SCORE: ${fmt(scoreData.total)} (${estadoPorScore(scoreData.total)})`,
        `formula: camara*${fmt(scoreData.pesos.camara)} + espira*${fmt(scoreData.pesos.espira_inductiva)} + gps*${fmt(scoreData.pesos.gps)}`,
        `camara: evalua vehiculos en cola antes del semaforo; nota ${fmt(scoreData.notas.camara)} * peso ${fmt(scoreData.pesos.camara)} = ${fmt(scoreData.contribuciones.camara)}; vehiculos en cola=${fmt(via.vehiculos_en_espera)}`,
        `espira: evalua vehiculos que aun circulan por la via; nota ${fmt(scoreData.notas.espira_inductiva)} * peso ${fmt(scoreData.pesos.espira_inductiva)} = ${fmt(scoreData.contribuciones.espira_inductiva)}; vehiculos en circulacion=${fmt(via.vehiculos_en_circulacion)}`,
        `gps: evalua lentitud por velocidad promedio; nota ${fmt(scoreData.notas.gps)} * peso ${fmt(scoreData.pesos.gps)} = ${fmt(scoreData.contribuciones.gps)}; velocidad promedio=${fmt(via.velocidad_promedio)}`,
      ].join("\n");
    }

    function viaInfo(via, state = lastState) {
      const scoreData = scoreBreakdown(via, state);
      const rows = [
        ["tipo", "via"],
        ["id", via.via_id],
        ["origen", via.origen],
        ["destino", via.destino],
        ["direccion", via.direccion],
        ["eje", via.eje],
        ["longitud", via.longitud],
        ["circulacion", via.vehiculos_en_circulacion],
        ["vehiculos en cola", via.vehiculos_en_espera],
        ["velocidad", via.velocidad_promedio],
        ["flujo", via.flujo_vehicular],
        ["tick", via.tick_actual],
        ["actualizado", via.actualizado_en],
      ];
      if (scoreData.prioridadAmbulancia) rows.splice(7, 0, ["prioridad ambulancia", "SI"]);
      return {
        rows,
        html: scoreCardHtml(via, scoreData) + kvHtml(rows),
      };
    }

    function nodeInfo(node, state) {
      const inRoads = state.vias.filter((via) => via.destino === node.id).map((via) => via.via_id).join(", ");
      const outRoads = state.vias.filter((via) => via.origen === node.id).map((via) => via.via_id).join(", ");
      const borderRole = node.tipo === "BORDE" ? (outRoads ? "SPAWN" : "SALIDA") : "--";
      const base = [
        ["tipo", node.tipo],
        ["rol", borderRole],
        ["id", node.id],
        ["coordenada", node.coordenada],
        ["fila", node.fila || node.lado || "--"],
        ["columna", node.columna || "--"],
      ];
      if (node.estado) {
        const cicloTick = node.estado.ciclo_semaforo_tick ?? "--";
        const cicloTotal = node.estado.ciclo_semaforo_total ?? "--";
        const ticksHastaCambio = Number(node.estado.ticks_restantes_fase) < 0 ? "manual" : node.estado.ticks_restantes_fase;
        base.push(
          ["fase activa", node.estado.fase_activa],
          ["fase alterna", node.estado.fase_alterna],
          ["modo control", node.estado.modo_control || "AUTO"],
          ["contador ciclo", `${cicloTick}/${cicloTotal}`],
          ["fase prioritaria", node.estado.fase_prioritaria || node.estado.fase_activa],
          ["ventana prioritaria", node.estado.duracion_fase_prioritaria ?? node.estado.duracion_fase_activa],
          ["ventana secundaria", node.estado.duracion_fase_secundaria ?? node.estado.duracion_fase_alterna],
          ["ventana activa", node.estado.duracion_fase_activa],
          ["ventana alterna", node.estado.duracion_fase_alterna],
          ["ticks hasta cambio", ticksHastaCambio],
          ["tick", node.estado.tick_actual],
          ["actualizado", node.estado.actualizado_en],
        );
      }
      base.push(["vias entrada", inRoads || "--"], ["vias salida", outRoads || "--"]);
      return { rows: base, html: kvHtml(base) };
    }

    function vehicleInfo(veh) {
      const rows = [
        ["tipo", "vehiculo"],
        ["id", veh.vehiculo_id],
        ["clase", veh.tipo],
        ["via", veh.via_actual],
        ["posicion", veh.posicion_en_via],
        ["velocidad", veh.velocidad],
        ["direccion", veh.direccion_actual],
        ["estado", veh.estado],
        ["tick", veh.tick_actual],
        ["actualizado", veh.actualizado_en],
      ];
      return { rows, html: kvHtml(rows) };
    }

    function simulationInfo(state) {
      const resumen = state.resumen || {};
      const faseHorizontal = state.intersecciones.filter((item) => item.fase_activa === "HORIZONTAL").length;
      const faseVertical = state.intersecciones.filter((item) => item.fase_activa === "VERTICAL").length;
      const parados = state.vehiculos.filter((veh) => veh.estado === "EN_COLA").length;
      const circulando = state.vehiculos.filter((veh) => veh.estado === "CIRCULANDO").length;
      const rows = [
        ["hora simulacion", simulatedClock(state)],
        ["modo", simulationConfig?.modo_bucle_infinito ? "bucle infinito" : "rango horario"],
        ["tick actual", resumen.tick_actual],
        ["tick rate", tickRatePerSecond()],
        ["intersecciones", resumen.total_intersecciones || state.intersecciones.length],
        ["vias", resumen.total_vias || state.vias.length],
        ["vehiculos", resumen.total_vehiculos || state.vehiculos.length],
        ["ambulancias", resumen.total_ambulancias || state.vehiculos.filter((veh) => veh.tipo === "AMBULANCIA").length],
        ["semaforos horizontal", faseHorizontal],
        ["semaforos vertical", faseVertical],
        ["vehiculos parados", parados],
        ["vehiculos circulando", circulando],
        ["vehiculos generados ultimo tick", resumen.ultimo_tick_creados],
        ["vehiculos despawneados ultimo tick", resumen.ultimo_tick_eliminados],
      ];
      return {
        rows,
        html: `<section class="score-card"><div class="score-head"><h3>Simulacion</h3><div class="score-total">${fmt(resumen.tick_actual)}</div></div>${kvHtml(rows)}</section>`,
      };
    }

    function currentManualIntersectionId(state = lastState) {
      if (!state) return null;
      const item = state.intersecciones.find((inter) => inter.modo_control === "MANUAL");
      return item ? item.interseccion_id : null;
    }

    function normalizeIntersectionSuffix(value) {
      return String(value || "").trim().toUpperCase().replace(/^INT-/, "");
    }

    function normalizeBorderRef(side, value) {
      const upper = String(value || "").trim().toUpperCase();
      if (side === "N" || side === "S") return upper.replace(/[^0-9]/g, "");
      return upper.replace(/[^A-Z]/g, "");
    }

    function existingIntersectionFromSuffix(suffix, state = lastState) {
      if (!state) return null;
      const full = `INT-${normalizeIntersectionSuffix(suffix)}`;
      return state.intersecciones.find((item) => item.interseccion_id === full) || null;
    }

    function existingBorderNode(side, ref, state = lastState) {
      if (!state) return null;
      const normalizedSide = String(side || "").trim().toUpperCase();
      const normalizedRef = normalizeBorderRef(normalizedSide, ref);
      const full = `BORDE-${normalizedSide}-${normalizedRef}`;
      const nodes = new Set();
      for (const via of state.vias) {
        nodes.add(via.origen);
        nodes.add(via.destino);
      }
      if (!nodes.has(full)) return null;
      const hasSpawn = state.vias.some((via) => via.origen === full);
      return hasSpawn ? full : null;
    }

    function renderSimulationInfo() {
      if (!lastState) return;
      simInfoPanel.innerHTML = simulationInfo(lastState).html;
    }

    function boxMessageHtml(kind, message) {
      if (!message) return "";
      return `<div class="${kind}-box">${message}</div>`;
    }

    async function postJson(url, payload) {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json();
      return { ok: response.ok && Boolean(data.ok), data };
    }

    function renderAmbulancePanel() {
      const warning = ambulanceMessage ? boxMessageHtml("warning", ambulanceMessage) : "";
      ambulancePanel.innerHTML = `
        <div class="panel-head"><h3>Ambulancia</h3></div>
        <p class="panel-hint">Escribe el sufijo de un nodo de borde. La solicitud se envia a PC0 para que el motor cree la ambulancia.</p>
        <div class="panel-form">
          <div class="inline-fields">
            <div class="field">
              <label>Lado</label>
              <input id="ambulanceSideInput" maxlength="1" value="${ambulanceSideValue}">
            </div>
            <div class="field">
              <label>Referencia</label>
              <input id="ambulanceRefInput" value="${ambulanceRefValue}">
            </div>
          </div>
          ${warning}
          <div class="panel-actions">
            <button id="ambulanceSubmitButton" class="action-button primary" type="button" ${ambulanceRequestInFlight ? "disabled" : ""}>Solicitar ambulancia</button>
          </div>
        </div>
      `;
      const sideInput = document.getElementById("ambulanceSideInput");
      const refInput = document.getElementById("ambulanceRefInput");
      const submitButton = document.getElementById("ambulanceSubmitButton");
      sideInput?.addEventListener("input", (event) => {
        ambulanceSideValue = String(event.target.value || "").toUpperCase().slice(0, 1).replace(/[^NSEO]/g, "");
      });
      refInput?.addEventListener("input", (event) => {
        ambulanceRefValue = String(event.target.value || "");
      });
      const validarAmbulancia = () => {
        const nodo = existingBorderNode(ambulanceSideValue, ambulanceRefValue);
        ambulanceMessage =
          ambulanceSideValue || ambulanceRefValue
            ? (nodo ? "" : "Nodo no existe o no sirve como punto de spawn.")
            : "";
        renderAmbulancePanel();
      };
      sideInput?.addEventListener("blur", validarAmbulancia);
      refInput?.addEventListener("blur", validarAmbulancia);
      sideInput?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") validarAmbulancia();
      });
      refInput?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") validarAmbulancia();
      });
      submitButton?.addEventListener("click", submitAmbulanceRequest);
    }

    async function submitAmbulanceRequest() {
      const nodo = existingBorderNode(ambulanceSideValue, ambulanceRefValue);
      if (!nodo) {
        ambulanceMessage = "Nodo no existe o no sirve como punto de spawn.";
        renderAmbulancePanel();
        return;
      }
      ambulanceRequestInFlight = true;
      ambulanceMessage = "";
      renderAmbulancePanel();
      try {
        const { ok, data } = await postJson("/api/ambulancia", { nodo_origen: nodo });
        if (!ok) {
          const error = data.error === "nodo_no_encontrado" || data.error === "nodo_sin_spawn"
            ? "Nodo no existe o no sirve como punto de spawn."
            : "No fue posible enviar la solicitud.";
          ambulanceMessage = error;
        } else {
          await refresh();
        }
      } catch (error) {
        ambulanceMessage = "No fue posible contactar el backend.";
      } finally {
        ambulanceRequestInFlight = false;
        renderAmbulancePanel();
      }
    }

    function renderManualControlPanel() {
      const suffix = normalizeIntersectionSuffix(manualTargetSuffix);
      const interseccion = existingIntersectionFromSuffix(suffix);
      const manualActiva = currentManualIntersectionId();
      const bloqueadaPorOtra = manualActiva && interseccion && manualActiva !== interseccion.interseccion_id;
      const warning = manualMessage
        ? boxMessageHtml("warning", manualMessage)
        : suffix && !interseccion
          ? boxMessageHtml("warning", "Nodo no existe.")
          : bloqueadaPorOtra
            ? boxMessageHtml("warning", `La interseccion ${manualActiva} sigue en manual. Debes devolverla a automatico antes de cambiar de nodo.`)
            : manualActiva && !interseccion && manualTargetSuffix
              ? boxMessageHtml("warning", `La interseccion ${manualActiva} sigue en manual. Debes devolverla a automatico antes de cambiar de nodo.`)
              : "";
      const showChoices = Boolean(interseccion) && (!manualActiva || manualActiva === interseccion.interseccion_id);
      const activeMode = manualActiva === interseccion?.interseccion_id ? interseccion?.modo_control : "AUTO";
      const activePhase = manualActiva === interseccion?.interseccion_id ? interseccion?.fase_activa : "AUTO";
      const selectedMode = manualDesiredMode || (activeMode === "MANUAL" ? activePhase : "AUTO");
      manualControlPanel.innerHTML = `
        <div class="panel-head"><h3>Control manual</h3></div>
        <p class="panel-hint">Escribe el sufijo de una interseccion. Solo puede existir una interseccion en manual a la vez.</p>
        <div class="panel-form">
          <div class="field">
            <label>Interseccion</label>
            <input id="manualTargetInput" value="${manualTargetSuffix}">
          </div>
          ${warning}
          ${showChoices ? `
            <div class="choice-grid">
              <button id="manualHorizontalButton" class="choice-button ${selectedMode === "HORIZONTAL" ? "active" : ""}" type="button" ${controlRequestInFlight ? "disabled" : ""}>
                <span class="choice-box">${selectedMode === "HORIZONTAL" ? "✓" : ""}</span><span>Verde horizontal</span>
              </button>
              <button id="manualVerticalButton" class="choice-button ${selectedMode === "VERTICAL" ? "active" : ""}" type="button" ${controlRequestInFlight ? "disabled" : ""}>
                <span class="choice-box">${selectedMode === "VERTICAL" ? "✓" : ""}</span><span>Verde vertical</span>
              </button>
              <button id="manualAutoButton" class="choice-button ${selectedMode === "AUTO" ? "active" : ""}" type="button" ${controlRequestInFlight ? "disabled" : ""}>
                <span class="choice-box">${selectedMode === "AUTO" ? "✓" : ""}</span><span>Automatico</span>
              </button>
            </div>
          ` : ""}
        </div>
      `;
      document.getElementById("manualTargetInput")?.addEventListener("input", (event) => {
        manualTargetSuffix = normalizeIntersectionSuffix(event.target.value || "");
      });
      const validarInterseccion = () => {
        const existe = existingIntersectionFromSuffix(manualTargetSuffix);
        manualMessage =
          manualTargetSuffix && !existe
            ? "Nodo no existe."
            : "";
        renderManualControlPanel();
      };
      document.getElementById("manualTargetInput")?.addEventListener("blur", validarInterseccion);
      document.getElementById("manualTargetInput")?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") validarInterseccion();
      });
      document.getElementById("manualHorizontalButton")?.addEventListener("click", () => submitManualControl("HORIZONTAL"));
      document.getElementById("manualVerticalButton")?.addEventListener("click", () => submitManualControl("VERTICAL"));
      document.getElementById("manualAutoButton")?.addEventListener("click", () => submitManualControl("AUTO"));
    }

    async function submitManualControl(fase) {
      const interseccion = existingIntersectionFromSuffix(manualTargetSuffix);
      if (!interseccion) {
        manualMessage = "Nodo no existe.";
        renderManualControlPanel();
        return;
      }
      const manualActiva = currentManualIntersectionId();
      if (fase !== "AUTO" && manualActiva && manualActiva !== interseccion.interseccion_id) {
        manualMessage = `La interseccion ${manualActiva} sigue en manual.`;
        renderManualControlPanel();
        return;
      }
      controlRequestInFlight = true;
      manualMessage = "";
      manualDesiredMode = fase;
      renderManualControlPanel();
      try {
        const { ok, data } = await postJson("/api/control-manual", {
          interseccion: interseccion.interseccion_id,
          fase_ganadora: fase,
          duracion_ticks: fase === "AUTO" ? 0 : -1,
        });
        if (!ok) {
          if (data.error === "interseccion_no_encontrada") {
            manualMessage = "Nodo no existe.";
          } else if (data.error === "control_manual_activo_en_otra_interseccion") {
            manualMessage = `${data.interseccion_activa} sigue en manual.`;
          } else {
            manualMessage = "No fue posible aplicar el control manual.";
          }
          manualDesiredMode = null;
        } else {
          await refresh();
        }
      } catch (error) {
        manualMessage = "No fue posible contactar el backend.";
        manualDesiredMode = null;
      } finally {
        controlRequestInFlight = false;
        renderManualControlPanel();
      }
    }

    function setSimulationPanelOpen(open) {
      simPanelOpen = open;
      simInfoButton.classList.toggle("active", open);
      simInfoPanel.classList.toggle("visible", open);
      if (open) renderSimulationInfo();
    }

    function setManualPanelOpen(open) {
      manualPanelOpen = open;
      manualControlButton.classList.toggle("active", open);
      manualControlPanel.classList.toggle("visible", open);
      if (open) {
        if (!manualTargetSuffix && currentManualIntersectionId()) {
          manualTargetSuffix = currentManualIntersectionId().replace(/^INT-/, "");
        }
        renderManualControlPanel();
      }
    }

    function setAmbulancePanelOpen(open) {
      ambulancePanelOpen = open;
      ambulanceButton.classList.toggle("active", open);
      ambulancePanel.classList.toggle("visible", open);
      if (open) renderAmbulancePanel();
    }

    function toggleSimulationPanel() {
      setSimulationPanelOpen(!simPanelOpen);
    }

    function toggleManualPanel() {
      setManualPanelOpen(!manualPanelOpen);
    }

    function toggleAmbulancePanel() {
      setAmbulancePanelOpen(!ambulancePanelOpen);
    }

    function focusItem(info) {
      inspector.innerHTML = info.html;
    }

    function setStatus(ok, text) {
      statusDot.classList.toggle("ok", ok);
      statusDot.classList.toggle("err", !ok);
      statusText.textContent = text;
    }

    function updateMetrics(state) {
      const resumen = state.resumen || {};
      tickEl.textContent = fmt(resumen.tick_actual);
      simClockEl.textContent = simulatedClock(state);
      updatedEl.textContent = resumen.actualizado_en ? new Date(resumen.actualizado_en).toLocaleTimeString() : "--";
      if (simPanelOpen) renderSimulationInfo();
      if (!manualTargetSuffix && currentManualIntersectionId(state)) {
        manualTargetSuffix = currentManualIntersectionId(state).replace(/^INT-/, "");
      }
    }

    async function refresh() {
      if (refreshInFlight) return;
      refreshInFlight = true;
      try {
        const response = await fetch("/api/estado", { cache: "no-store" });
        const payload = await response.json();
        if (!payload.ok) throw new Error(payload.error || "sin datos");
        scoreConfig = payload.score_config || defaultScoreConfig;
        simulationConfig = payload.simulacion || null;
        lastState = payload.estado;
        updateMetrics(lastState);
        if (isSimulationFinished(lastState)) {
          renderEndScreen(lastState);
        } else {
          hideEndScreen();
          draw(lastState);
        }
        setStatus(true, "activo");
      } catch (error) {
        setStatus(false, "sin conexion");
      } finally {
        refreshInFlight = false;
        ensureRefreshInterval();
      }
    }

    window.addEventListener("resize", () => {
      if (!lastState) return;
      if (isSimulationFinished(lastState)) renderEndScreen(lastState);
      else draw(lastState);
    });
    simInfoButton.addEventListener("click", toggleSimulationPanel);
    manualControlButton.addEventListener("click", toggleManualPanel);
    ambulanceButton.addEventListener("click", toggleAmbulancePanel);
    updateRealClock();
    refresh();
    setInterval(updateRealClock, 1000);
    ensureRefreshInterval();
