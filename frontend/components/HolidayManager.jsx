const { useEffect, useMemo, useState } = React;

const API_BASE = window.location.origin;

function HolidayManager() {
  const [years, setYears] = useState([]);
  const [selectedYearId, setSelectedYearId] = useState(null);
  const [classes, setClasses] = useState([]);
  const [holidays, setHolidays] = useState([]);
  const [formState, setFormState] = useState({
    name: "",
    start_date: "",
    end_date: "",
    academic_year_id: null,
  });
  const [editingId, setEditingId] = useState(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [selectedClass, setSelectedClass] = useState(null);

  useEffect(() => {
    async function bootstrap() {
      const response = await fetch(`${API_BASE}/academic-years`);
      const data = await response.json();
      setYears(data);
      if (!selectedYearId && data.length) {
        setSelectedYearId(data[0].id);
      }
    }
    bootstrap().catch((error) => {
      console.error("Failed to load academic years", error);
      setStatusMessage("Unable to load academic years.");
    });
  }, []);

  useEffect(() => {
    if (!selectedYearId) {
      return;
    }
    setFormState((previous) => ({
      ...previous,
      academic_year_id: selectedYearId,
    }));
    refreshClasses(selectedYearId);
    refreshHolidays(selectedYearId);
  }, [selectedYearId]);

  async function refreshClasses(yearId) {
    try {
      const response = await fetch(`${API_BASE}/classes?academic_year_id=${yearId}`);
      const data = await response.json();
      setClasses(data);
    } catch (error) {
      console.error("Failed to load classes", error);
      setStatusMessage("Unable to load classes.");
    }
  }

  async function refreshHolidays(yearId) {
    try {
      const response = await fetch(`${API_BASE}/holidays?academic_year_id=${yearId}`);
      const data = await response.json();
      setHolidays(data);
    } catch (error) {
      console.error("Failed to load holidays", error);
      setStatusMessage("Unable to load holidays.");
    }
  }

  function resetForm() {
    setFormState({
      name: "",
      start_date: "",
      end_date: "",
      academic_year_id: selectedYearId,
    });
    setEditingId(null);
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (!formState.name || !formState.start_date || !formState.end_date) {
      setStatusMessage("Complete all form fields.");
      return;
    }

    const payload = {
      ...formState,
      academic_year_id: Number(formState.academic_year_id),
    };

    try {
      setIsSaving(true);
      const method = editingId ? "PUT" : "POST";
      const url = editingId
        ? `${API_BASE}/holidays/${editingId}`
        : `${API_BASE}/holidays`;
      const response = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || "Unable to save holiday.");
      }
      const data = await response.json();
      setStatusMessage(
        editingId ? "Holiday updated successfully." : "Holiday created successfully."
      );
      resetForm();
      await refreshHolidays(selectedYearId);
      await refreshClasses(selectedYearId);
      if (data.suggestions?.length) {
        alert(
          [
            "Rescheduling suggestions:",
            ...data.suggestions.map((item) => `• ${item.suggestion}`),
          ].join("\n")
        );
      }
    } catch (error) {
      console.error(error);
      setStatusMessage(error.message);
    } finally {
      setIsSaving(false);
    }
  }

  function handleEdit(holiday) {
    setEditingId(holiday.id);
    setFormState({
      name: holiday.name,
      start_date: holiday.start_date,
      end_date: holiday.end_date,
      academic_year_id: holiday.academic_year_id,
    });
  }

  async function handleDelete(holidayId) {
    if (!window.confirm("Delete this holiday?")) {
      return;
    }
    try {
      const response = await fetch(`${API_BASE}/holidays/${holidayId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || "Unable to delete holiday.");
      }
      setStatusMessage("Holiday removed.");
      if (holidayId === editingId) {
        resetForm();
      }
      await refreshHolidays(selectedYearId);
      await refreshClasses(selectedYearId);
    } catch (error) {
      console.error(error);
      setStatusMessage(error.message);
    }
  }

  function openClassModal(classItem) {
    setSelectedClass(classItem);
  }

  function closeClassModal() {
    setSelectedClass(null);
  }

  const calendarItems = useMemo(() => {
    if (!classes.length) {
      return [];
    }
    return classes.map((classItem) => {
      const overlapsHoliday = classItem.suggestions?.length;
      return {
        ...classItem,
        overlapsHoliday,
      };
    });
  }, [classes]);

  return (
    <section className="holiday-manager">
      <header className="holiday-manager__header">
        <h2>Holiday Planning</h2>
        <div className="holiday-manager__year-picker">
          <label htmlFor="holiday-year">Academic year</label>
          <select
            id="holiday-year"
            value={selectedYearId || ""}
            onChange={(event) => setSelectedYearId(Number(event.target.value) || null)}
          >
            <option value="" disabled>
              Select a year
            </option>
            {years.map((year) => (
              <option key={year.id} value={year.id}>
                {year.name}
              </option>
            ))}
          </select>
        </div>
      </header>

      <div className="holiday-manager__content">
        <form className="holiday-form" onSubmit={handleSubmit}>
          <h3>{editingId ? "Edit holiday" : "Create holiday"}</h3>
          <label>
            Name
            <input
              type="text"
              value={formState.name}
              onChange={(event) =>
                setFormState((prev) => ({ ...prev, name: event.target.value }))
              }
              required
            />
          </label>
          <label>
            Start date
            <input
              type="date"
              value={formState.start_date}
              onChange={(event) =>
                setFormState((prev) => ({ ...prev, start_date: event.target.value }))
              }
              required
            />
          </label>
          <label>
            End date
            <input
              type="date"
              value={formState.end_date}
              onChange={(event) =>
                setFormState((prev) => ({ ...prev, end_date: event.target.value }))
              }
              required
            />
          </label>
          <div className="holiday-form__actions">
            <button type="submit" disabled={isSaving}>
              {editingId ? "Update" : "Create"}
            </button>
            <button type="button" onClick={resetForm} disabled={isSaving}>
              Reset
            </button>
          </div>
          {statusMessage && <p className="holiday-form__status">{statusMessage}</p>}
        </form>

        <div className="holiday-list">
          <h3>Holidays</h3>
          {!holidays.length && <p>No holidays scheduled yet.</p>}
          <ul>
            {holidays.map((holiday) => (
              <li key={holiday.id} className="holiday-list__item">
                <div>
                  <h4>{holiday.name}</h4>
                  <p>
                    {holiday.start_date} → {holiday.end_date}
                  </p>
                  {holiday.suggestions?.length ? (
                    <ul className="holiday-list__suggestions">
                      {holiday.suggestions.map((item) => (
                        <li key={item.id}>{item.suggestion}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="holiday-list__no-conflict">No conflicts detected.</p>
                  )}
                </div>
                <div className="holiday-list__actions">
                  <button type="button" onClick={() => handleEdit(holiday)}>
                    Edit
                  </button>
                  <button type="button" onClick={() => handleDelete(holiday.id)}>
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="holiday-calendar">
        <h3>Calendar view</h3>
        {!calendarItems.length && <p>No classes scheduled.</p>}
        <div className="calendar-grid">
          {calendarItems.map((item) => (
            <button
              type="button"
              key={item.id}
              className={`calendar-grid__item ${
                item.overlapsHoliday ? "calendar-grid__item--holiday" : ""
              }`}
              onClick={() => openClassModal(item)}
            >
              <span className="calendar-grid__date">{item.scheduled_date}</span>
              <span className="calendar-grid__name">{item.name}</span>
              {item.overlapsHoliday && <span className="calendar-grid__badge">Holiday</span>}
            </button>
          ))}
        </div>
      </div>

      {selectedClass && (
        <div className="class-modal" role="dialog" aria-modal="true">
          <div className="class-modal__content">
            <header className="class-modal__header">
              <h3>{selectedClass.name}</h3>
              <button type="button" onClick={closeClassModal} aria-label="Close">
                ×
              </button>
            </header>
            <p>
              Scheduled for <strong>{selectedClass.scheduled_date}</strong>
            </p>
            {selectedClass.suggestions?.length ? (
              <ul className="class-modal__suggestions">
                {selectedClass.suggestions.map((item) => (
                  <li key={item.id}>{item.suggestion}</li>
                ))}
              </ul>
            ) : (
              <p>No holiday conflicts detected.</p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}

ReactDOM.createRoot(document.getElementById("holiday-manager"))?.render(<HolidayManager />);
