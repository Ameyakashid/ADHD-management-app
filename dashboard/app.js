var REFRESH_INTERVAL_MS = 30000;

var STATE_COLORS = {
  baseline: "#4CAF50",
  focus: "#42A5F5",
  hyperfocus: "#AB47BC",
  avoidance: "#FFA726",
  overwhelm: "#EF5350",
  rsd: "#E91E63",
  unknown: "#9E9E9E"
};

function fetchJSON(endpoint) {
  return fetch(endpoint).then(function (r) { return r.json(); });
}

function escapeHTML(str) {
  var div = document.createElement("div");
  div.appendChild(document.createTextNode(str));
  return div.innerHTML;
}

function renderState(data) {
  var banner = document.getElementById("state-banner");
  var label = document.getElementById("state-name");
  var state = "unknown";
  if (data.current && data.current.state) {
    state = data.current.state;
  } else if (data.state && data.state !== "unknown") {
    state = data.state;
  }
  banner.style.backgroundColor = STATE_COLORS[state] || STATE_COLORS.unknown;
  label.textContent = state;
}

function bufferColor(level, capacity) {
  if (capacity === 0) return STATE_COLORS.unknown;
  var pct = level / capacity;
  if (pct > 0.5) return "#4CAF50";
  if (pct > 0.25) return "#FFA726";
  return "#EF5350";
}

function renderBuffers(data) {
  var container = document.getElementById("buffers-list");
  var buffers = data.buffers || [];
  if (buffers.length === 0) {
    container.innerHTML = '<p class="empty-msg">No buffers</p>';
    return;
  }
  var html = "";
  for (var i = 0; i < buffers.length; i++) {
    var b = buffers[i];
    var pct = b.buffer_capacity > 0
      ? Math.round((b.buffer_level / b.buffer_capacity) * 100)
      : 0;
    var color = bufferColor(b.buffer_level, b.buffer_capacity);
    html += '<div class="buffer-item">'
      + '<div class="buffer-label"><span>' + escapeHTML(b.name) + "</span>"
      + "<span>" + b.buffer_level + "/" + b.buffer_capacity + "</span></div>"
      + '<div class="buffer-track"><div class="buffer-fill" style="width:'
      + pct + "%;background:" + color + '"></div></div></div>';
  }
  container.innerHTML = html;
}

function renderTasks(data) {
  var list = document.getElementById("tasks-list");
  var tasks = data.tasks || [];
  if (tasks.length === 0) {
    list.innerHTML = '<li class="empty-msg">No active tasks</li>';
    return;
  }
  var html = "";
  for (var i = 0; i < tasks.length; i++) {
    var t = tasks[i];
    var due = t.due_date ? " &middot; " + escapeHTML(t.due_date) : "";
    html += "<li>" + escapeHTML(t.title) + due + "</li>";
  }
  list.innerHTML = html;
}

function formatTime(timeStr) {
  if (!timeStr) return "";
  var parts = timeStr.split(":");
  var h = parseInt(parts[0], 10);
  var m = parts[1];
  var ampm = h >= 12 ? "PM" : "AM";
  if (h > 12) h -= 12;
  if (h === 0) h = 12;
  return h + ":" + m + " " + ampm;
}

function renderSchedule(data) {
  var list = document.getElementById("schedule-list");
  var checkins = data.checkins || [];
  if (checkins.length === 0) {
    list.innerHTML = '<li class="empty-msg">No check-ins</li>';
    return;
  }
  var html = "";
  for (var i = 0; i < checkins.length; i++) {
    var c = checkins[i];
    var cls = c.is_enabled ? "checkin-enabled" : "checkin-disabled";
    html += '<li class="' + cls + '">'
      + escapeHTML(c.display_name) + " &middot; " + formatTime(c.target_time)
      + "</li>";
  }
  list.innerHTML = html;
}

function renderActivity(data) {
  var list = document.getElementById("activity-list");
  var events = data.activity || [];
  if (events.length === 0) {
    list.innerHTML = '<li class="empty-msg">No recent activity</li>';
    return;
  }
  var html = "";
  var limit = Math.min(events.length, 8);
  for (var i = 0; i < limit; i++) {
    var e = events[i];
    var label = "";
    if (e.type === "task_completed") label = escapeHTML(e.title);
    else if (e.type === "buffer_update") label = escapeHTML(e.name) + " " + e.level + "/" + e.capacity;
    else if (e.type === "checkin_fired") label = escapeHTML(e.name);
    var typeLabel = e.type.replace(/_/g, " ");
    html += '<li><span class="activity-type">' + typeLabel + "</span> " + label + "</li>";
  }
  list.innerHTML = html;
}

function refreshAll() {
  Promise.all([
    fetchJSON("/state"),
    fetchJSON("/buffers"),
    fetchJSON("/tasks"),
    fetchJSON("/schedule"),
    fetchJSON("/activity")
  ]).then(function (results) {
    renderState(results[0]);
    renderBuffers(results[1]);
    renderTasks(results[2]);
    renderSchedule(results[3]);
    renderActivity(results[4]);
  }).catch(function () {
    var banner = document.getElementById("state-banner");
    var label = document.getElementById("state-name");
    label.textContent = "CONNECTION ERROR";
    banner.style.backgroundColor = STATE_COLORS.unknown;
  });
}

refreshAll();
setInterval(refreshAll, REFRESH_INTERVAL_MS);
