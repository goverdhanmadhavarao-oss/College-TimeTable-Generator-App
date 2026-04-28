const API_BASE = window.location.origin;
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
const PRIORITY_OPTIONS = [
    { value: "days_off", label: "Days Off" },
    { value: "faculty", label: "Faculty" },
    { value: "time_slots", label: "Time Slots" },
    { value: "compactness", label: "Compactness" },
];
const FIXED_TIME_SLOTS = [
    "08:00-10:00",
    "10:00-12:00",
    "13:00-15:00",
    "15:00-17:00",
];

const state = {
    authToken: localStorage.getItem("tt_auth_token") || "",
    currentUser: null,
    googleClientId: null,
    facultyPreferences: {},
    avoidSlots: [],
    parsedSections: [],
    currentStep: 1,
    resultPayload: null,
    selectedResultIndex: 0,
    authMode: "login",
};

document.addEventListener("DOMContentLoaded", async () => {
    bindAuthUI();
    bindAppUI();
    renderDayCheckboxes();
    initializePrioritySelectors();
    renderAvoidSlotOptions();
    bindStepNavigation();
    switchAuthMode("login");

    await loadAuthConfig();
    await bootstrapSession();
});

function bindAuthUI() {
    document.getElementById("showLoginBtn").addEventListener("click", () => switchAuthMode("login"));
    document.getElementById("showSignupBtn").addEventListener("click", () => switchAuthMode("signup"));
    document.getElementById("loginForm").addEventListener("submit", handleLogin);
    document.getElementById("signupForm").addEventListener("submit", handleSignup);
    document.getElementById("logoutBtn").addEventListener("click", handleLogout);
}

function bindAppUI() {
    document.getElementById("loadCoursesBtn").addEventListener("click", loadCourses);
    document.getElementById("toPreferencesBtn").addEventListener("click", goToPreferences);
    document.getElementById("generateBtn").addEventListener("click", generateTimetables);
    document.getElementById("courseSearch").addEventListener("input", filterCourses);
    document.getElementById("selectAllCoursesBtn").addEventListener("click", () => setAllVisibleCourses(true));
    document.getElementById("clearCoursesBtn").addEventListener("click", () => setAllVisibleCourses(false));
}

async function loadAuthConfig() {
    try {
        const response = await fetch(`${API_BASE}/auth/config`);
        const data = await response.json();
        state.googleClientId = data.google_client_id || null;
        renderGoogleButton();
    } catch (error) {
        setAuthStatus("Unable to load auth configuration.", "error");
    }
}

async function bootstrapSession() {
    if (!state.authToken) {
        showAuthShell();
        return;
    }

    try {
        const data = await apiFetch("/auth/me");
        state.currentUser = data.user;
        showAppShell();
    } catch (error) {
        clearSession();
        showAuthShell();
    }
}

function switchAuthMode(mode) {
    state.authMode = mode;
    document.getElementById("showLoginBtn").classList.toggle("active", mode === "login");
    document.getElementById("showSignupBtn").classList.toggle("active", mode === "signup");
    document.getElementById("loginForm").classList.toggle("hidden", mode !== "login");
    document.getElementById("signupForm").classList.toggle("hidden", mode !== "signup");
    document.getElementById("googleAuthLabel").textContent =
        mode === "login" ? "Sign in with Google" : "Sign up with Google";
    renderGoogleButton();
    setAuthStatus("");
}

function renderGoogleButton() {
    const container = document.getElementById("googleButtonWrap");
    container.innerHTML = "";

    if (!state.googleClientId || !window.google?.accounts?.id) {
        const note = document.createElement("p");
        note.className = "auth-help";
        note.textContent = "Google sign-in will appear when the server is configured.";
        container.appendChild(note);
        return;
    }

    window.google.accounts.id.initialize({
        client_id: state.googleClientId,
        callback: handleGoogleCredential,
    });

    window.google.accounts.id.renderButton(container, {
        theme: "outline",
        size: "large",
        shape: "pill",
        text: state.authMode === "login" ? "signin_with" : "signup_with",
        width: container.clientWidth || 360,
    });
}

async function handleGoogleCredential(response) {
    try {
        const data = await fetchJson("/auth/google", {
            method: "POST",
            body: JSON.stringify({ credential: response.credential }),
        });
        completeLogin(data);
    } catch (error) {
        setAuthStatus(error.message, "error");
    }
}

async function handleLogin(event) {
    event.preventDefault();
    setAuthStatus("Signing in...");

    const payload = {
        email: document.getElementById("loginEmail").value.trim(),
        password: document.getElementById("loginPassword").value,
    };

    try {
        const data = await fetchJson("/auth/login", {
            method: "POST",
            body: JSON.stringify(payload),
        });
        completeLogin(data);
    } catch (error) {
        setAuthStatus(error.message, "error");
    }
}

async function handleSignup(event) {
    event.preventDefault();
    setAuthStatus("Creating account...");

    const payload = {
        name: document.getElementById("signupName").value.trim(),
        email: document.getElementById("signupEmail").value.trim(),
        password: document.getElementById("signupPassword").value,
    };

    try {
        const data = await fetchJson("/auth/signup", {
            method: "POST",
            body: JSON.stringify(payload),
        });
        completeLogin(data);
    } catch (error) {
        setAuthStatus(error.message, "error");
    }
}

async function handleLogout() {
    try {
        if (state.authToken) {
            await fetchJson("/auth/logout", {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${state.authToken}`,
                },
            });
        }
    } catch (error) {
        // Best-effort logout.
    }

    clearSession();
    showAuthShell();
}

function completeLogin(data) {
    state.authToken = data.token;
    state.currentUser = data.user;
    localStorage.setItem("tt_auth_token", data.token);
    setAuthStatus("");
    document.getElementById("loginForm").reset();
    document.getElementById("signupForm").reset();
    showAppShell();
}

function clearSession() {
    state.authToken = "";
    state.currentUser = null;
    localStorage.removeItem("tt_auth_token");
}

function showAuthShell() {
    document.getElementById("authShell").classList.remove("hidden");
    document.getElementById("appShell").classList.add("hidden");
}

function showAppShell() {
    document.getElementById("authShell").classList.add("hidden");
    document.getElementById("appShell").classList.remove("hidden");
    document.getElementById("currentUserName").textContent = state.currentUser?.name || "Signed in";
}

function setAuthStatus(message, type = "") {
    const element = document.getElementById("authStatus");
    element.textContent = message;
    element.className = `status-text ${type}`.trim();
}

async function fetchJson(path, options = {}) {
    const headers = {
        "Content-Type": "application/json",
        ...(options.headers || {}),
    };

    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers,
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
        throw new Error(data.detail || "Request failed.");
    }

    return data;
}

async function apiFetch(path, options = {}) {
    if (!state.authToken) {
        throw new Error("Authentication required.");
    }

    try {
        return await fetchJson(path, {
            ...options,
            headers: {
                Authorization: `Bearer ${state.authToken}`,
                ...(options.headers || {}),
            },
        });
    } catch (error) {
        if (/Authentication required|Invalid session|Session expired/.test(error.message)) {
            clearSession();
            showAuthShell();
        }
        throw error;
    }
}

function bindStepNavigation() {
    document.querySelectorAll("[data-go-step]").forEach((button) => {
        button.addEventListener("click", () => setActiveStep(Number(button.dataset.goStep)));
    });
}

function setActiveStep(step) {
    state.currentStep = step;

    document.querySelectorAll(".step-panel").forEach((panel) => {
        panel.classList.toggle("active", Number(panel.dataset.stepPanel) === step);
    });

    document.querySelectorAll(".step-indicator").forEach((indicator) => {
        const indicatorStep = Number(indicator.dataset.stepIndicator);
        indicator.classList.toggle("active", indicatorStep === step);
        indicator.classList.toggle("completed", indicatorStep < step);
    });

    window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderDayCheckboxes() {
    const container = document.getElementById("daysOffList");
    container.innerHTML = "";

    DAYS.forEach((day) => {
        const label = document.createElement("label");
        label.className = "day-pill";

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.value = day;
        checkbox.addEventListener("change", () => {
            label.classList.toggle("selected", checkbox.checked);
        });

        const text = document.createElement("span");
        text.textContent = day;

        label.appendChild(checkbox);
        label.appendChild(text);
        container.appendChild(label);
    });
}

function initializePrioritySelectors() {
    const defaults = ["days_off", "faculty", "time_slots", "compactness"];

    defaults.forEach((selectedValue, index) => {
        const select = document.getElementById(`priority${index + 1}`);
        PRIORITY_OPTIONS.forEach((option) => {
            const element = document.createElement("option");
            element.value = option.value;
            element.textContent = option.label;
            select.appendChild(element);
        });
        select.value = selectedValue;
    });
}

function setStatus(elementId, message, type = "") {
    const element = document.getElementById(elementId);
    element.textContent = message;
    element.className = `status-text ${type}`.trim();
}

function getSelectedCourses() {
    const checkboxes = document.querySelectorAll("#courseList input[type='checkbox']:checked");
    return Array.from(checkboxes).map((checkbox) => checkbox.value);
}

function getPriorityOrder() {
    return [1, 2, 3, 4].map((index) => document.getElementById(`priority${index}`).value);
}

function validatePriorityOrder(priorityOrder) {
    return new Set(priorityOrder).size === PRIORITY_OPTIONS.length;
}

function getAvailableTimeSlots() {
    return [...FIXED_TIME_SLOTS];
}

function getAvailableFaculty(course) {
    const faculty = new Set();
    state.parsedSections
        .filter((section) => section.course === course)
        .forEach((section) => {
            if (section.faculty) {
                faculty.add(section.faculty);
            }
        });
    return Array.from(faculty).sort();
}

function createSelectableChip(label, selected, onClick) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = `chip selectable-chip ${selected ? "selected" : ""}`.trim();
    chip.innerHTML = `<span>${label}</span>`;
    chip.addEventListener("click", onClick);
    return chip;
}

function renderAvoidSlotOptions() {
    const container = document.getElementById("avoidSlotChips");
    container.innerHTML = "";

    const slots = getAvailableTimeSlots();
    slots.forEach((slot) => {
        const selected = state.avoidSlots.includes(slot);
        container.appendChild(createSelectableChip(slot, selected, () => {
            if (selected) {
                state.avoidSlots = state.avoidSlots.filter((item) => item !== slot);
            } else {
                state.avoidSlots = [...state.avoidSlots, slot];
            }
            renderAvoidSlotOptions();
        }));
    });
}

function renderCourses(courses) {
    const container = document.getElementById("courseList");
    container.innerHTML = "";
    document.getElementById("courseSearch").value = "";

    if (!courses.length) {
        container.innerHTML = '<p class="empty-state">No courses were detected from the provided timetable text.</p>';
        renderFacultyInputs();
        return;
    }

    courses.forEach((course) => {
        const label = document.createElement("label");
        label.className = "course-item";
        label.dataset.courseName = course.toLowerCase();

        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.value = course;
        checkbox.addEventListener("change", renderFacultyInputs);

        const title = document.createElement("span");
        title.textContent = course;

        label.appendChild(checkbox);
        label.appendChild(title);
        container.appendChild(label);
    });

    renderFacultyInputs();
}

function filterCourses() {
    const query = document.getElementById("courseSearch").value.trim().toLowerCase();
    const courseItems = document.querySelectorAll("#courseList .course-item");

    courseItems.forEach((item) => {
        const courseName = (item.dataset.courseName || "").replace(/\s+/g, " ").trim();
        const matches = !query || courseName.includes(query);
        item.classList.toggle("hidden-course", !matches);
    });
}

function setAllVisibleCourses(checked) {
    const visibleCourseItems = document.querySelectorAll("#courseList .course-item:not(.hidden-course) input[type='checkbox']");
    visibleCourseItems.forEach((checkbox) => {
        checkbox.checked = checked;
    });
    renderFacultyInputs();
}

function facultyChipContainerId(course) {
    return `faculty-chip-${course.replace(/[^a-zA-Z0-9]+/g, "-").toLowerCase()}`;
}

function renderFacultyInputs() {
    const container = document.getElementById("facultyPreferences");
    const selectedCourses = getSelectedCourses();

    container.innerHTML = "";

    if (!selectedCourses.length) {
        container.innerHTML = '<p class="empty-state">Select one or more courses to add faculty preferences.</p>';
        return;
    }

    selectedCourses.forEach((course) => {
        state.facultyPreferences[course] = state.facultyPreferences[course] || [];

        const row = document.createElement("div");
        row.className = "faculty-row";

        const label = document.createElement("label");
        label.textContent = course;

        const chipContainer = document.createElement("div");
        chipContainer.className = "chip-list";
        chipContainer.id = facultyChipContainerId(course);

        row.appendChild(label);
        row.appendChild(chipContainer);
        container.appendChild(row);

        renderFacultyOptions(course);
    });

    Object.keys(state.facultyPreferences).forEach((course) => {
        if (!selectedCourses.includes(course)) {
            delete state.facultyPreferences[course];
        }
    });
}

function renderFacultyOptions(course) {
    const container = document.getElementById(facultyChipContainerId(course));
    if (!container) {
        return;
    }

    container.innerHTML = "";

    const facultyOptions = getAvailableFaculty(course);
    if (!facultyOptions.length) {
        container.innerHTML = '<p class="empty-state compact-empty">No faculty options found for this course.</p>';
        return;
    }

    const selectedValues = state.facultyPreferences[course] || [];

    facultyOptions.forEach((name) => {
        const selected = selectedValues.includes(name);
        container.appendChild(createSelectableChip(name, selected, () => {
            const current = state.facultyPreferences[course] || [];
            state.facultyPreferences[course] = selected
                ? current.filter((item) => item !== name)
                : [...current, name];
            renderFacultyOptions(course);
        }));
    });
}

function collectConstraints() {
    const daysOff = Array.from(document.querySelectorAll("#daysOffList input:checked")).map((checkbox) => checkbox.value);
    const priorityOrder = getPriorityOrder();
    const selectedCourses = getSelectedCourses();
    const facultyPref = {};

    selectedCourses.forEach((course) => {
        const values = state.facultyPreferences[course] || [];
        if (values.length) {
            facultyPref[course] = values;
        }
    });

    return {
        days_off: daysOff,
        avoid_slots: [...state.avoidSlots],
        faculty_pref: facultyPref,
        priority_order: priorityOrder,
    };
}

function summarizeConstraints(option) {
    const violations = option.violations || [];
    if (!violations.length) {
        return {
            status: "All selected constraints were achieved.",
            unmet: [],
        };
    }

    const unmet = [];

    if (violations.some((item) => item.includes("class block(s) scheduled"))) {
        unmet.push("Requested days off could not be fully achieved.");
    }

    if (violations.some((item) => item.includes("not preferred"))) {
        unmet.push("Preferred faculty could not be fully achieved.");
    }

    if (violations.some((item) => item.includes("avoided slot"))) {
        unmet.push("Avoided time slots could not be fully achieved.");
    }

    if (violations.some((item) => item.includes("spread-out schedule"))) {
        unmet.push("A compact timetable could not be fully achieved.");
    }

    return {
        status: unmet.length ? "Some constraints could not be fully achieved." : "All selected constraints were achieved.",
        unmet,
    };
}

function renderResults(payload) {
    const options = payload.options || [];
    const missingCourses = payload.missing_courses || [];
    const summary = document.getElementById("resultSummary");
    const tabs = document.getElementById("resultTabs");
    const container = document.getElementById("results");

    state.resultPayload = payload;
    state.selectedResultIndex = 0;

    summary.innerHTML = "";
    tabs.innerHTML = "";
    container.innerHTML = "";

    if (!options.length) {
        summary.innerHTML = '<p class="empty-state">No timetable options could be generated for the current selection.</p>';
        const empty = document.createElement("div");
        empty.className = "result-card";
        empty.innerHTML = `
            <h3>No timetables found</h3>
            <p class="muted">Try selecting fewer courses or relaxing one of the constraints.</p>
        `;

        if (missingCourses.length) {
            const missing = document.createElement("p");
            missing.className = "warning-text";
            missing.textContent = `Missing courses: ${missingCourses.join(", ")}`;
            empty.appendChild(missing);
        }

        container.appendChild(empty);
    } else {
        renderResultHeader(payload);
        renderResultTabs(options);
        renderSelectedResult();
    }
}

function renderResultHeader(payload) {
    const summary = document.getElementById("resultSummary");
    const options = payload.options || [];

    summary.innerHTML = `
        <h3>${options.length} Timetable${options.length === 1 ? "" : "s"} Generated</h3>
        <p class="muted">Ranked by your preferences. Tap a tab to compare.</p>
    `;
}

function renderResultTabs(options) {
    const tabs = document.getElementById("resultTabs");
    tabs.innerHTML = "";

    options.forEach((option, index) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = `result-tab ${index === state.selectedResultIndex ? "active" : ""}`.trim();
        button.innerHTML = `
            <span>${index === 0 ? "Best Match" : `Alternative ${index}`}</span>
            <strong>${option.score}</strong>
        `;
        button.addEventListener("click", () => {
            state.selectedResultIndex = index;
            renderResultTabs(options);
            renderSelectedResult();
        });
        tabs.appendChild(button);
    });
}

function renderSelectedResult() {
    const payload = state.resultPayload || {};
    const options = payload.options || [];
    const container = document.getElementById("results");
    container.innerHTML = "";

    if (!options.length) {
        return;
    }

    const option = options[state.selectedResultIndex] || options[0];
    const summary = summarizeConstraints(option);
    const board = document.createElement("article");
    board.className = "result-board";
    board.innerHTML = `
        <div class="board-top">
            <div>
                <p class="eyebrow">Option ${state.selectedResultIndex + 1}</p>
                <h3>${indexLabel(state.selectedResultIndex)}</h3>
                <div class="result-meta">
                    ${summary.unmet.length
                        ? `<p class="summary-status warning-text">${summary.status}</p><ul class="info-list">${summary.unmet.map((item) => `<li>${item}</li>`).join("")}</ul>`
                        : `<p class="summary-status success-note">${summary.status}</p>`}
                </div>
            </div>
            <div class="score-pill">
                <span>Total Credits</span>
                <strong>${getTotalCredits(option)}</strong>
            </div>
        </div>
        ${buildTimetableGrid(option)}
        <div class="course-card-grid">
            ${buildCourseCards(option)}
        </div>
    `;

    container.appendChild(board);
}

function getTotalCredits(option) {
    return (option.timetable || []).reduce((total, section) => {
        return total + (Number(section.credits) || 0);
    }, 0);
}

function buildTimetableGrid(option) {
    const days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
    const labels = {
        Monday: "Mon",
        Tuesday: "Tue",
        Wednesday: "Wed",
        Thursday: "Thu",
        Friday: "Fri",
        Saturday: "Sat",
    };
    const timeWindows = [
        { label: "8:00-10:00", start: "08:00", end: "10:00" },
        { label: "10:00-12:00", start: "10:00", end: "12:00" },
        { label: "13:00-15:00", start: "13:00", end: "15:00" },
        { label: "15:00-17:00", start: "15:00", end: "17:00" },
    ];
    const cellMap = {};

    option.timetable.forEach((section, index) => {
        const tone = `tone-${(index % 4) + 1}`;
        section.schedule.forEach((block) => {
            const [blockStart, blockEnd] = block.time.split("-");

            timeWindows.forEach((window) => {
                if (rangesOverlap(blockStart, blockEnd, window.start, window.end)) {
                    const key = `${block.day}|${window.label}`;
                    cellMap[key] = cellMap[key] || [];
                    cellMap[key].push({
                        code: section.slot,
                        title: section.course,
                        tone,
                    });
                }
            });
        });
    });

    const header = `
        <div class="table-head table-time">Time</div>
        ${days.map((day) => `<div class="table-head">${labels[day]}</div>`).join("")}
    `;

    const rows = timeWindows.map((window) => {
        const cells = days.map((day) => {
            const key = `${day}|${window.label}`;
            const entries = (cellMap[key] || []).map((entry) => `
                <div class="class-block ${entry.tone}">
                    <strong>${entry.code}</strong>
                    <span>${entry.title}</span>
                </div>
            `).join("");
            return `<div class="table-cell">${entries}</div>`;
        }).join("");

        return `
            <div class="table-time-label">${window.label}</div>
            ${cells}
        `;
    }).join("");

    return `
        <div class="timetable-board">
            ${header}
            ${rows}
        </div>
    `;
}

function buildCourseCards(option) {
    return option.timetable.map((section, index) => {
        const tone = `tone-${(index % 4) + 1}`;
        const tags = section.schedule
            .map((block) => `<span class="schedule-tag ${tone}">${shortDay(block.day)} ${block.time}</span>`)
            .join("");

        return `
            <article class="course-detail-card">
                <div class="course-detail-top">
                    <div>
                        <p class="course-slot ${tone}">${section.slot}</p>
                        <h4>${section.course}</h4>
                    </div>
                    <span class="credit-badge">${Number(section.credits) || 0} Credits</span>
                </div>
                <p class="course-faculty">${section.faculty || "Faculty not available"}</p>
                <div class="schedule-tag-list">
                    ${tags}
                </div>
            </article>
        `;
    }).join("");
}

function shortDay(day) {
    return day.slice(0, 3);
}

function rangesOverlap(startA, endA, startB, endB) {
    return startA < endB && startB < endA;
}

function indexLabel(index) {
    return index === 0 ? "Best Match" : `Alternative ${index}`;
}

function goToPreferences() {
    if (!getSelectedCourses().length) {
        setStatus("loadStatus", "");
        setStatus("generateStatus", "Select at least one course before continuing.", "error");
        return;
    }

    renderFacultyInputs();
    setStatus("generateStatus", "");
    setActiveStep(3);
}

async function loadCourses() {
    const text = document.getElementById("timetableInput").value.trim();

    if (!text) {
        setStatus("loadStatus", "Paste the timetable text first.", "error");
        return;
    }

    setStatus("loadStatus", "Loading courses...");

    try {
        const data = await apiFetch("/parse", {
            method: "POST",
            body: JSON.stringify({
                text,
                include_warnings: false,
            }),
        });

        state.parsedSections = data.sections || [];
        state.avoidSlots = state.avoidSlots.filter((slot) => getAvailableTimeSlots().includes(slot));

        Object.keys(state.facultyPreferences).forEach((course) => {
            const availableFaculty = getAvailableFaculty(course);
            state.facultyPreferences[course] = (state.facultyPreferences[course] || []).filter((name) => availableFaculty.includes(name));
        });

        renderCourses(data.courses || []);
        renderAvoidSlotOptions();
        setStatus("loadStatus", `Loaded ${data.courses.length} course(s).`, "success");
        setActiveStep(2);
    } catch (error) {
        setStatus("loadStatus", error.message, "error");
    }
}

async function generateTimetables() {
    const text = document.getElementById("timetableInput").value.trim();
    const selectedCourses = getSelectedCourses();
    const priorityOrder = getPriorityOrder();

    if (!text) {
        setStatus("generateStatus", "Paste the timetable text before generating.", "error");
        setActiveStep(1);
        return;
    }

    if (!selectedCourses.length) {
        setStatus("generateStatus", "Select at least one course.", "error");
        setActiveStep(2);
        return;
    }

    if (!validatePriorityOrder(priorityOrder)) {
        setStatus("generateStatus", "Each priority must be unique.", "error");
        return;
    }

    setStatus("generateStatus", "Generating timetable options...");

    const constraints = collectConstraints();

    try {
        const data = await apiFetch("/generate", {
            method: "POST",
            body: JSON.stringify({
                text,
                selected_courses: selectedCourses,
                constraints,
                top_n: 3,
                return_debug: true,
            }),
        });

        renderResults(data);
        setStatus("generateStatus", "Timetable options generated successfully.", "success");
        setActiveStep(4);
    } catch (error) {
        setStatus("generateStatus", error.message, "error");
    }
}
