import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import FullCalendar from "@fullcalendar/react";
import dayGridPlugin from "@fullcalendar/daygrid";
import timeGridPlugin from "@fullcalendar/timegrid";
import interactionPlugin from "@fullcalendar/interaction";
import "@fullcalendar/daygrid/main.css";
import "@fullcalendar/timegrid/main.css";
import "../styles.css";

const API_BASE =
  typeof process !== "undefined"
    ? process.env.NEXT_PUBLIC_API_BASE || process.env.REACT_APP_API_BASE || ""
    : "";

const TRIMESTER_STYLES = {
  1: { label: "Trimester 1", color: "#38bdf8" },
  2: { label: "Trimester 2", color: "#f97316" },
  3: { label: "Trimester 3", color: "#10b981" }
};

const DEFAULT_SESSION_COLOR = "#64748b";

function toList(value) {
  if (Array.isArray(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    return value
      .split(/[,\n]/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
  return [];
}

function buildTooltip(extendedProps) {
  const tooltipLines = [];
  if (extendedProps.topic) {
    tooltipLines.push(`Topic: ${extendedProps.topic}`);
  }
  if (extendedProps.trimester) {
    tooltipLines.push(`Trimester: ${extendedProps.trimester}`);
  }
  if (extendedProps.activities?.length) {
    tooltipLines.push(`Activities: ${extendedProps.activities.join(", ")}`);
  }
  if (extendedProps.materials?.length) {
    tooltipLines.push(`Materials: ${extendedProps.materials.join(", ")}`);
  }
  if (extendedProps.summary) {
    tooltipLines.push(extendedProps.summary);
  }
  if (extendedProps.type === "holiday" && extendedProps.description) {
    tooltipLines.push(extendedProps.description);
  }
  return tooltipLines.join("\n");
}

function transformSession(session) {
  const activities = toList(session.activities ?? session.activitySummary);
  const materials = toList(session.materials ?? session.materialSummary);
  const trimester = session.trimester ?? session.term ?? null;
  return {
    ...session,
    title: session.title || session.topic || "Class Session",
    start: session.start,
    end: session.end || session.start,
    trimester,
    activities,
    materials,
    topic: session.topic || session.title,
    summary: session.summary,
    type: "session"
  };
}

function transformHoliday(holiday) {
  return {
    id: holiday.id || `holiday-${holiday.date}`,
    title: holiday.title || holiday.name || "Holiday",
    start: holiday.date,
    end: holiday.date,
    allDay: true,
    description: holiday.description || holiday.reason,
    type: "holiday"
  };
}

const Modal = ({ isOpen, title, onClose, children }) => {
  if (!isOpen) {
    return null;
  }
  return (
    <div className="modal-backdrop" role="presentation">
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <header className="modal-header">
          <h2>{title}</h2>
          <button type="button" className="modal-close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
};

const TrimesterLegend = () => (
  <div className="trimester-legend" aria-label="Trimester color legend">
    {Object.entries(TRIMESTER_STYLES).map(([key, value]) => (
      <div key={key} className="trimester-legend-item">
        <span className="trimester-color" style={{ backgroundColor: value.color }} />
        <span>{value.label}</span>
      </div>
    ))}
  </div>
);

const renderEventContent = (eventInfo) => {
  const { extendedProps } = eventInfo.event;
  const activities = extendedProps.activities?.length
    ? `Activities: ${extendedProps.activities.join(", ")}`
    : null;
  const materials = extendedProps.materials?.length
    ? `Materials: ${extendedProps.materials.join(", ")}`
    : null;
  const summary = extendedProps.summary || extendedProps.topicSummary || null;
  return (
    <div
      className={`agenda-event ${extendedProps.type === "holiday" ? "agenda-event-holiday" : ""}`}
      data-testid={`agenda-event-${extendedProps.id || eventInfo.event.id}`}
    >
      <div className="agenda-event-title">{eventInfo.event.title}</div>
      {summary ? <div className="agenda-event-summary">{summary}</div> : null}
      {activities ? <div className="agenda-event-meta">{activities}</div> : null}
      {materials ? <div className="agenda-event-meta">{materials}</div> : null}
    </div>
  );
};

const AgendaPage = () => {
  const [sessions, setSessions] = useState([]);
  const [holidays, setHolidays] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedSession, setSelectedSession] = useState(null);
  const [selectedEventId, setSelectedEventId] = useState(null);
  const [activeModal, setActiveModal] = useState(null);
  const [editState, setEditState] = useState({ topic: "", activities: "", materials: "" });
  const [holidayState, setHolidayState] = useState({ date: "", reason: "" });
  const [resourceState, setResourceState] = useState({ description: "", files: [] });
  const [feedback, setFeedback] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadAgenda = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/api/agenda`);
      if (!response.ok) {
        throw new Error("Failed to load agenda data");
      }
      const payload = await response.json();
      const incomingSessions = (payload.sessions || payload.classes || []).map(transformSession);
      const incomingHolidays = (payload.holidays || []).map(transformHoliday);
      setSessions(incomingSessions);
      setHolidays(incomingHolidays);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAgenda();
  }, [loadAgenda]);

  const events = useMemo(() => {
    const sessionEvents = sessions.map((session) => ({
      id: session.id,
      title: session.title,
      start: session.start,
      end: session.end,
      extendedProps: {
        ...session,
        trimester: session.trimester,
        topic: session.topic,
        activities: session.activities,
        materials: session.materials,
        summary: session.summary,
        type: "session"
      }
    }));
    const holidayEvents = holidays.map((holiday) => ({
      id: holiday.id,
      title: holiday.title,
      start: holiday.start,
      end: holiday.end,
      allDay: true,
      display: "background",
      extendedProps: {
        ...holiday,
        type: "holiday"
      }
    }));
    return [...sessionEvents, ...holidayEvents];
  }, [sessions, holidays]);

  useEffect(() => {
    if (sessions.length && !selectedSession && !selectedEventId) {
      const firstSession = sessions[0];
      setSelectedSession(firstSession);
      setSelectedEventId(firstSession.id);
    }
  }, [sessions, selectedSession, selectedEventId]);

  const closeModal = () => {
    setActiveModal(null);
    setFeedback("");
  };

  const openModal = (key) => {
    setActiveModal(key);
    setFeedback("");
  };

  const handleEventClick = useCallback(
    (info) => {
      info.jsEvent?.preventDefault();
      info.jsEvent?.stopPropagation?.();
      const session = sessions.find((item) => item.id === info.event.id);
      if (!session) {
        return;
      }
      setSelectedSession(session);
      setSelectedEventId(session.id);
      setActiveModal(null);
    },
    [sessions]
  );

  const eventDidMount = (info) => {
    const { extendedProps } = info.event;
    const trimesterColor = TRIMESTER_STYLES[extendedProps.trimester]?.color;
    if (extendedProps.type === "holiday") {
      info.el.classList.add("agenda-holiday-cell");
    }
    if (trimesterColor) {
      info.el.style.setProperty("--agenda-event-color", trimesterColor);
      info.el.style.borderColor = trimesterColor;
      info.el.style.backgroundColor = `${trimesterColor}22`;
      info.el.style.color = "#0f172a";
    } else if (extendedProps.type !== "holiday") {
      info.el.style.setProperty("--agenda-event-color", DEFAULT_SESSION_COLOR);
      info.el.style.borderColor = DEFAULT_SESSION_COLOR;
      info.el.style.backgroundColor = "#e2e8f0";
      info.el.style.color = "#0f172a";
    }
    info.el.setAttribute("title", buildTooltip(extendedProps));
  };

  useEffect(() => {
    if (!selectedSession) {
      return;
    }
    setEditState({
      topic: selectedSession.topic || "",
      activities: selectedSession.activities?.join(", ") || "",
      materials: selectedSession.materials?.join(", ") || ""
    });
    setHolidayState({
      date: selectedSession.start ? selectedSession.start.slice(0, 10) : "",
      reason: ""
    });
    setResourceState({ description: "", files: [] });
  }, [selectedSession]);

  const eventClassNames = useCallback(
    (arg) => {
      const classes = [];
      if (arg.event.id === selectedEventId) {
        classes.push("agenda-event-active");
      }
      return classes;
    },
    [selectedEventId]
  );

  const handleClearSelection = () => {
    setSelectedSession(null);
    setSelectedEventId(null);
    setActiveModal(null);
  };

  const formattedSessionDate = useMemo(() => {
    if (!selectedSession?.start) {
      return "Date to be announced";
    }
    try {
      return new Date(selectedSession.start).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short"
      });
    } catch (err) {
      return selectedSession.start;
    }
  }, [selectedSession]);

  const handleEditChange = (event) => {
    const { name, value } = event.target;
    setEditState((prev) => ({ ...prev, [name]: value }));
  };

  const handleHolidayChange = (event) => {
    const { name, value } = event.target;
    setHolidayState((prev) => ({ ...prev, [name]: value }));
  };

  const handleResourceChange = (event) => {
    const { name, files, value } = event.target;
    if (name === "files") {
      setResourceState((prev) => ({ ...prev, files: Array.from(files || []) }));
    } else {
      setResourceState((prev) => ({ ...prev, [name]: value }));
    }
  };

  const updateSessionState = (sessionId, updatedFields) => {
    setSessions((prev) =>
      prev.map((session) =>
        session.id === sessionId
          ? {
              ...session,
              ...updatedFields,
              activities: toList(updatedFields.activities ?? session.activities),
              materials: toList(updatedFields.materials ?? session.materials)
            }
          : session
      )
    );
  };

  const handleSessionSubmit = async (event) => {
    event.preventDefault();
    if (!selectedSession) {
      return;
    }
    setIsSubmitting(true);
    setFeedback("");
    try {
      const payload = {
        topic: editState.topic,
        activities: toList(editState.activities),
        materials: toList(editState.materials)
      };
      const response = await fetch(
        `${API_BASE}/api/agenda/sessions/${encodeURIComponent(selectedSession.id)}`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify(payload)
        }
      );
      if (!response.ok) {
        throw new Error("Failed to update session");
      }
      let updatedSession = null;
      try {
        updatedSession = await response.json();
      } catch (err) {
        updatedSession = null;
      }
      updateSessionState(selectedSession.id, {
        ...payload,
        ...(updatedSession || {})
      });
      setFeedback("Session updated successfully.");
    } catch (err) {
      setFeedback(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleHolidaySubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    setFeedback("");
    try {
      const payload = {
        date: holidayState.date,
        description: holidayState.reason,
        sessionId: selectedSession?.id
      };
      const response = await fetch(`${API_BASE}/api/agenda/holidays`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        throw new Error("Failed to mark holiday");
      }
      let createdHoliday = null;
      try {
        createdHoliday = await response.json();
      } catch (err) {
        createdHoliday = null;
      }
      const holidayData = transformHoliday({
        ...(createdHoliday || {}),
        date: holidayState.date,
        description: holidayState.reason
      });
      setHolidays((prev) => {
        const existing = prev.find((item) => item.id === holidayData.id);
        if (existing) {
          return prev.map((item) => (item.id === holidayData.id ? holidayData : item));
        }
        return [...prev, holidayData];
      });
      setFeedback("Holiday saved.");
    } catch (err) {
      setFeedback(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResourceSubmit = async (event) => {
    event.preventDefault();
    if (!selectedSession) {
      return;
    }
    setIsSubmitting(true);
    setFeedback("");
    try {
      const formData = new FormData();
      formData.append("description", resourceState.description);
      resourceState.files.forEach((file) => formData.append("files", file));
      formData.append("sessionId", selectedSession.id);
      const response = await fetch(
        `${API_BASE}/api/agenda/sessions/${encodeURIComponent(selectedSession.id)}/resources`,
        {
          method: "POST",
          body: formData
        }
      );
      if (!response.ok) {
        throw new Error("Failed to upload resources");
      }
      setFeedback("Resources uploaded successfully.");
      setResourceState({ description: "", files: [] });
    } catch (err) {
      setFeedback(err.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="agenda-page">
      <header className="agenda-header">
        <h1>Class Agenda</h1>
        <p>Review and manage class sessions with trimester visibility and quick editing tools.</p>
      </header>
      <section className="agenda-content">
        <TrimesterLegend />
        {loading ? <p role="status">Loading agenda…</p> : null}
        {error ? (
          <div role="alert" className="agenda-error">
            {error}
            <button type="button" onClick={loadAgenda} className="link-button">
              Retry
            </button>
          </div>
        ) : null}
        {!loading && !error ? (
          <div className="agenda-layout">
            <div className="agenda-calendar" aria-label="Class calendar view">
              {events.length ? (
                <FullCalendar
                  plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
                  initialView="timeGridWeek"
                  headerToolbar={{
                    left: "prev,next today",
                    center: "title",
                    right: "dayGridMonth,timeGridWeek,timeGridDay"
                  }}
                  events={events}
                  eventClick={handleEventClick}
                  eventContent={renderEventContent}
                  eventDidMount={eventDidMount}
                  eventClassNames={eventClassNames}
                  height="auto"
                  slotMinTime="07:00:00"
                  slotMaxTime="18:00:00"
                  firstDay={1}
                  nowIndicator
                  weekends
                />
              ) : (
                <div className="agenda-empty-state" role="status">
                  <h2>No sessions yet</h2>
                  <p>
                    Once sessions are published they will appear on the calendar. Use the quick tips
                    to learn how to add content and share materials with your class.
                  </p>
                </div>
              )}
            </div>
            <aside className="agenda-sidebar" aria-label="Agenda guidance and details">
              <section className="agenda-guide">
                <h2>Quick tips</h2>
                <ol>
                  <li>Select any session on the calendar to review its details.</li>
                  <li>Use the action buttons below to update topics, mark holidays, or add resources.</li>
                  <li>Students will see trimester colors on events to understand pacing.</li>
                </ol>
              </section>
              <section className="agenda-session-card" aria-live="polite">
                <header>
                  <h2>Session details</h2>
                  {selectedSession ? (
                    <button type="button" className="link-button" onClick={handleClearSelection}>
                      Clear selection
                    </button>
                  ) : null}
                </header>
                {selectedSession ? (
                  <div className="agenda-session-body">
                    <p className="agenda-session-title">{selectedSession.title}</p>
                    <dl>
                      <div>
                        <dt>Date</dt>
                        <dd>{formattedSessionDate}</dd>
                      </div>
                      {selectedSession.trimester ? (
                        <div>
                          <dt>Trimester</dt>
                          <dd>{TRIMESTER_STYLES[selectedSession.trimester]?.label}</dd>
                        </div>
                      ) : null}
                      {selectedSession.summary ? (
                        <div>
                          <dt>Summary</dt>
                          <dd>{selectedSession.summary}</dd>
                        </div>
                      ) : null}
                      {selectedSession.activities?.length ? (
                        <div>
                          <dt>Activities</dt>
                          <dd>{selectedSession.activities.join(", ")}</dd>
                        </div>
                      ) : null}
                      {selectedSession.materials?.length ? (
                        <div>
                          <dt>Materials</dt>
                          <dd>{selectedSession.materials.join(", ")}</dd>
                        </div>
                      ) : null}
                    </dl>
                    <div className="agenda-session-actions">
                      <button type="button" onClick={() => openModal("edit")}>
                        Edit session
                      </button>
                      <button type="button" className="secondary" onClick={() => openModal("holiday")}>
                        Mark holiday
                      </button>
                      <button type="button" className="secondary" onClick={() => openModal("resource")}>
                        Upload resources
                      </button>
                    </div>
                  </div>
                ) : (
                  <p className="agenda-session-placeholder">
                    Choose a session to see the agenda details, recommended materials, and next steps.
                  </p>
                )}
              </section>
            </aside>
          </div>
        ) : null}
      </section>

      <Modal
        isOpen={activeModal === "edit"}
        title={selectedSession ? `Edit ${selectedSession.title}` : "Edit session"}
        onClose={closeModal}
      >
        {selectedSession ? (
          <Fragment>
            <form onSubmit={handleSessionSubmit} className="modal-form">
              <label>
                Topic
                <input
                  type="text"
                  name="topic"
                  value={editState.topic}
                  onChange={handleEditChange}
                  required
                />
              </label>
              <label>
                Activities
                <textarea
                  name="activities"
                  value={editState.activities}
                  onChange={handleEditChange}
                  placeholder="Separate activities with commas"
                />
              </label>
              <label>
                Materials
                <textarea
                  name="materials"
                  value={editState.materials}
                  onChange={handleEditChange}
                  placeholder="List materials for students"
                />
              </label>
              <div className="modal-actions">
                <button type="submit" disabled={isSubmitting}>
                  {isSubmitting ? "Saving…" : "Save changes"}
                </button>
                <button type="button" className="secondary" onClick={closeModal}>
                  Cancel
                </button>
              </div>
            </form>
            <div className="modal-divider" />
            <div className="modal-secondary-actions">
              <button type="button" onClick={() => openModal("holiday")}>
                Mark Holiday
              </button>
              <button type="button" onClick={() => openModal("resource")}>
                Upload Resources
              </button>
            </div>
            {feedback ? <p className="modal-feedback">{feedback}</p> : null}
          </Fragment>
        ) : (
          <p>Select a session to begin editing.</p>
        )}
      </Modal>

      <Modal
        isOpen={activeModal === "holiday"}
        title="Mark Holiday"
        onClose={closeModal}
      >
        <form onSubmit={handleHolidaySubmit} className="modal-form">
          <label>
            Date
            <input type="date" name="date" value={holidayState.date} onChange={handleHolidayChange} required />
          </label>
          <label>
            Reason
            <textarea
              name="reason"
              value={holidayState.reason}
              onChange={handleHolidayChange}
              placeholder="Reason for the holiday"
              required
            />
          </label>
          <div className="modal-actions">
            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Saving…" : "Save holiday"}
            </button>
            <button type="button" className="secondary" onClick={closeModal}>
              Cancel
            </button>
          </div>
        </form>
        {feedback ? <p className="modal-feedback">{feedback}</p> : null}
      </Modal>

      <Modal
        isOpen={activeModal === "resource"}
        title="Upload Resources"
        onClose={closeModal}
      >
        <form onSubmit={handleResourceSubmit} className="modal-form">
          <label>
            Description
            <textarea
              name="description"
              value={resourceState.description}
              onChange={handleResourceChange}
              placeholder="Share context for the resources"
              required
            />
          </label>
          <label>
            Files
            <input type="file" name="files" multiple onChange={handleResourceChange} />
          </label>
          <div className="modal-actions">
            <button type="submit" disabled={isSubmitting}>
              {isSubmitting ? "Uploading…" : "Upload"}
            </button>
            <button type="button" className="secondary" onClick={closeModal}>
              Cancel
            </button>
          </div>
        </form>
        {feedback ? <p className="modal-feedback">{feedback}</p> : null}
      </Modal>
    </div>
  );
};

export default AgendaPage;
