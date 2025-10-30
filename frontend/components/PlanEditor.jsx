import React, { useEffect, useMemo, useState } from "https://esm.sh/react@18";

const h = React.createElement;

function createLocalId(prefix) {
  return `${prefix}-${Math.random().toString(36).slice(2, 10)}`;
}

function ensureArray(value) {
  return Array.isArray(value) ? value : [];
}

function validateDraft(draft) {
  const errors = {
    trimesters: [],
    levels: [],
    topics: [],
    reviewNotes: draft.review_notes && draft.review_notes.length > 1000,
  };

  ensureArray(draft.trimesters).forEach((trimester, index) => {
    const rowErrors = {};
    if (!trimester.name?.trim()) {
      rowErrors.name = "Name is required";
    }
    if (!trimester.start_date) {
      rowErrors.start_date = "Start date is required";
    }
    if (!trimester.end_date) {
      rowErrors.end_date = "End date is required";
    }
    if (trimester.start_date && trimester.end_date) {
      const start = new Date(trimester.start_date);
      const end = new Date(trimester.end_date);
      if (Number.isFinite(start.valueOf()) && Number.isFinite(end.valueOf()) && start > end) {
        rowErrors.end_date = "End date must be after start date";
      }
    }
    errors.trimesters[index] = rowErrors;
  });

  ensureArray(draft.levels).forEach((level, index) => {
    const rowErrors = {};
    if (!level.name?.trim()) {
      rowErrors.name = "Name is required";
    }
    errors.levels[index] = rowErrors;
  });

  const trimesterIds = new Set(ensureArray(draft.trimesters).map((item) => item.id));
  const levelIds = new Set(ensureArray(draft.levels).map((item) => item.id));

  ensureArray(draft.topics).forEach((topic, index) => {
    const rowErrors = {};
    if (!topic.name?.trim()) {
      rowErrors.name = "Name is required";
    }
    if (!topic.trimester_id) {
      rowErrors.trimester_id = "Trimester is required";
    } else if (!trimesterIds.has(topic.trimester_id)) {
      rowErrors.trimester_id = "Trimester must match an existing row";
    }
    if (!topic.level_id) {
      rowErrors.level_id = "Level is required";
    } else if (!levelIds.has(topic.level_id)) {
      rowErrors.level_id = "Level must match an existing row";
    }
    errors.topics[index] = rowErrors;
  });

  const hasErrors =
    errors.reviewNotes ||
    errors.trimesters.some((row) => Object.keys(row || {}).length > 0) ||
    errors.levels.some((row) => Object.keys(row || {}).length > 0) ||
    errors.topics.some((row) => Object.keys(row || {}).length > 0);

  return { errors, hasErrors };
}

function renderErrorMessage(message) {
  if (!message) {
    return null;
  }
  return h("p", { className: "form-error", role: "alert" }, message);
}

function PlanEditor({ draft, onChange, onSave, saving }) {
  const [localDraft, setLocalDraft] = useState(() => ({ ...draft }));
  const [validation, setValidation] = useState(() => ({ errors: {}, hasErrors: false }));
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setLocalDraft({ ...draft });
    setValidation({ errors: {}, hasErrors: false });
    setDirty(false);
  }, [draft.id, draft.updated_at]);

  const derivedValidation = useMemo(() => validateDraft(localDraft), [localDraft]);

  useEffect(() => {
    setValidation(derivedValidation);
  }, [derivedValidation]);

  const notifyChange = (updatedDraft) => {
    setDirty(true);
    if (typeof onChange === "function") {
      onChange(updatedDraft);
    }
  };

  const updateDraft = (updater) => {
    setLocalDraft((current) => {
      const next = updater(current);
      notifyChange(next);
      return next;
    });
  };

  const handleFieldChange = (field, value) => {
    updateDraft((current) => ({
      ...current,
      [field]: value,
    }));
  };

  const handleTrimesterChange = (index, field, value) => {
    updateDraft((current) => {
      const nextTrimesters = ensureArray(current.trimesters).map((item, idx) =>
        idx === index ? { ...item, [field]: value } : item
      );
      return { ...current, trimesters: nextTrimesters };
    });
  };

  const addTrimester = () => {
    updateDraft((current) => ({
      ...current,
      trimesters: [
        ...ensureArray(current.trimesters),
        {
          id: createLocalId("trimester"),
          name: "",
          start_date: "",
          end_date: "",
        },
      ],
    }));
  };

  const removeTrimester = (index) => {
    updateDraft((current) => {
      const trimesters = ensureArray(current.trimesters).filter((_, idx) => idx !== index);
      const validTrimesterIds = new Set(trimesters.map((item) => item.id));
      const topics = ensureArray(current.topics).map((topic) =>
        validTrimesterIds.has(topic.trimester_id)
          ? topic
          : { ...topic, trimester_id: "" }
      );
      return { ...current, trimesters, topics };
    });
  };

  const handleLevelChange = (index, field, value) => {
    updateDraft((current) => {
      const nextLevels = ensureArray(current.levels).map((item, idx) =>
        idx === index ? { ...item, [field]: value } : item
      );
      return { ...current, levels: nextLevels };
    });
  };

  const addLevel = () => {
    updateDraft((current) => ({
      ...current,
      levels: [
        ...ensureArray(current.levels),
        {
          id: createLocalId("level"),
          name: "",
          description: "",
        },
      ],
    }));
  };

  const removeLevel = (index) => {
    updateDraft((current) => {
      const levels = ensureArray(current.levels).filter((_, idx) => idx !== index);
      const validLevelIds = new Set(levels.map((item) => item.id));
      const topics = ensureArray(current.topics).map((topic) =>
        validLevelIds.has(topic.level_id) ? topic : { ...topic, level_id: "" }
      );
      return { ...current, levels, topics };
    });
  };

  const handleTopicChange = (index, field, value) => {
    updateDraft((current) => {
      const nextTopics = ensureArray(current.topics).map((item, idx) =>
        idx === index ? { ...item, [field]: value } : item
      );
      return { ...current, topics: nextTopics };
    });
  };

  const addTopic = () => {
    updateDraft((current) => ({
      ...current,
      topics: [
        ...ensureArray(current.topics),
        {
          id: createLocalId("topic"),
          name: "",
          trimester_id: ensureArray(current.trimesters)[0]?.id || "",
          level_id: ensureArray(current.levels)[0]?.id || "",
          summary: "",
        },
      ],
    }));
  };

  const removeTopic = (index) => {
    updateDraft((current) => ({
      ...current,
      topics: ensureArray(current.topics).filter((_, idx) => idx !== index),
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    const { errors: currentErrors, hasErrors } = validateDraft(localDraft);
    setValidation({ errors: currentErrors, hasErrors });
    if (hasErrors) {
      return;
    }
    if (typeof onSave === "function") {
      const success = await onSave(localDraft);
      if (success) {
        setDirty(false);
      }
    }
  };

  const sectionHeader = (title, actionLabel, actionHandler, actionDisabled) =>
    h(
      "div",
      { className: "section-header" },
      h("h3", null, title),
      h(
        "button",
        {
          type: "button",
          className: "secondary-button",
          onClick: actionHandler,
          disabled: saving || actionDisabled,
        },
        actionLabel
      )
    );

  const renderTrimesterRows = () =>
    ensureArray(localDraft.trimesters).map((trimester, index) => {
      const rowErrors = validation.errors.trimesters?.[index] || {};
      const nameId = `trimester-name-${index}`;
      const startId = `trimester-start-${index}`;
      const endId = `trimester-end-${index}`;

      return h(
        "tr",
        { key: trimester.id || index },
        h(
          "td",
          null,
          h(
            "label",
            { htmlFor: nameId, className: "sr-only" },
            `Trimester ${index + 1} name`
          ),
          h("input", {
            id: nameId,
            name: nameId,
            type: "text",
            value: trimester.name || "",
            onChange: (event) => handleTrimesterChange(index, "name", event.target.value),
          }),
          renderErrorMessage(rowErrors.name)
        ),
        h(
          "td",
          null,
          h(
            "label",
            { htmlFor: startId, className: "sr-only" },
            `Trimester ${index + 1} start date`
          ),
          h("input", {
            id: startId,
            name: startId,
            type: "date",
            value: trimester.start_date || "",
            onChange: (event) => handleTrimesterChange(index, "start_date", event.target.value),
          }),
          renderErrorMessage(rowErrors.start_date)
        ),
        h(
          "td",
          null,
          h(
            "label",
            { htmlFor: endId, className: "sr-only" },
            `Trimester ${index + 1} end date`
          ),
          h("input", {
            id: endId,
            name: endId,
            type: "date",
            value: trimester.end_date || "",
            onChange: (event) => handleTrimesterChange(index, "end_date", event.target.value),
          }),
          renderErrorMessage(rowErrors.end_date)
        ),
        h(
          "td",
          { className: "row-actions" },
          h(
            "button",
            {
              type: "button",
              className: "icon-button",
              onClick: () => removeTrimester(index),
              disabled: saving,
              title: "Remove trimester",
            },
            "✕"
          )
        )
      );
    });

  const renderLevelRows = () =>
    ensureArray(localDraft.levels).map((level, index) => {
      const rowErrors = validation.errors.levels?.[index] || {};
      const nameId = `level-name-${index}`;
      const descriptionId = `level-description-${index}`;

      return h(
        "tr",
        { key: level.id || index },
        h(
          "td",
          null,
          h(
            "label",
            { htmlFor: nameId, className: "sr-only" },
            `Level ${index + 1} name`
          ),
          h("input", {
            id: nameId,
            name: nameId,
            type: "text",
            value: level.name || "",
            onChange: (event) => handleLevelChange(index, "name", event.target.value),
          }),
          renderErrorMessage(rowErrors.name)
        ),
        h(
          "td",
          null,
          h(
            "label",
            { htmlFor: descriptionId, className: "sr-only" },
            `Level ${index + 1} description`
          ),
          h("textarea", {
            id: descriptionId,
            name: descriptionId,
            rows: 2,
            value: level.description || "",
            onChange: (event) => handleLevelChange(index, "description", event.target.value),
          })
        ),
        h(
          "td",
          { className: "row-actions" },
          h(
            "button",
            {
              type: "button",
              className: "icon-button",
              onClick: () => removeLevel(index),
              disabled: saving,
              title: "Remove level",
            },
            "✕"
          )
        )
      );
    });

  const renderTopicRows = () => {
    const trimesterOptions = ensureArray(localDraft.trimesters);
    const levelOptions = ensureArray(localDraft.levels);

    return ensureArray(localDraft.topics).map((topic, index) => {
      const rowErrors = validation.errors.topics?.[index] || {};
      const nameId = `topic-name-${index}`;
      const trimesterId = `topic-trimester-${index}`;
      const levelId = `topic-level-${index}`;
      const summaryId = `topic-summary-${index}`;

      return h(
        "tr",
        { key: topic.id || index },
        h(
          "td",
          null,
          h(
            "label",
            { htmlFor: nameId, className: "sr-only" },
            `Topic ${index + 1} name`
          ),
          h("input", {
            id: nameId,
            name: nameId,
            type: "text",
            value: topic.name || "",
            onChange: (event) => handleTopicChange(index, "name", event.target.value),
          }),
          renderErrorMessage(rowErrors.name)
        ),
        h(
          "td",
          null,
          h(
            "label",
            { htmlFor: trimesterId, className: "sr-only" },
            `Topic ${index + 1} trimester`
          ),
          h(
            "select",
            {
              id: trimesterId,
              name: trimesterId,
              value: topic.trimester_id || "",
              onChange: (event) => handleTopicChange(index, "trimester_id", event.target.value),
            },
            [
              h("option", { key: "blank", value: "" }, "Select trimester"),
              ...trimesterOptions.map((option) =>
                h(
                  "option",
                  { key: option.id, value: option.id },
                  option.name || option.id
                )
              ),
            ]
          ),
          renderErrorMessage(rowErrors.trimester_id)
        ),
        h(
          "td",
          null,
          h(
            "label",
            { htmlFor: levelId, className: "sr-only" },
            `Topic ${index + 1} level`
          ),
          h(
            "select",
            {
              id: levelId,
              name: levelId,
              value: topic.level_id || "",
              onChange: (event) => handleTopicChange(index, "level_id", event.target.value),
            },
            [
              h("option", { key: "blank", value: "" }, "Select level"),
              ...levelOptions.map((option) =>
                h(
                  "option",
                  { key: option.id, value: option.id },
                  option.name || option.id
                )
              ),
            ]
          ),
          renderErrorMessage(rowErrors.level_id)
        ),
        h(
          "td",
          null,
          h(
            "label",
            { htmlFor: summaryId, className: "sr-only" },
            `Topic ${index + 1} summary`
          ),
          h("textarea", {
            id: summaryId,
            name: summaryId,
            rows: 2,
            value: topic.summary || "",
            onChange: (event) => handleTopicChange(index, "summary", event.target.value),
          })
        ),
        h(
          "td",
          { className: "row-actions" },
          h(
            "button",
            {
              type: "button",
              className: "icon-button",
              onClick: () => removeTopic(index),
              disabled: saving,
              title: "Remove topic",
            },
            "✕"
          )
        )
      );
    });
  };

  return h(
    "form",
    { className: "plan-editor", onSubmit: handleSubmit },
    h(
      "div",
      { className: "plan-metadata" },
      h(
        "label",
        { htmlFor: "plan-title" },
        "Plan title"
      ),
      h("input", {
        id: "plan-title",
        name: "plan-title",
        type: "text",
        value: localDraft.title || "",
        onChange: (event) => handleFieldChange("title", event.target.value),
      }),
      h(
        "label",
        { htmlFor: "plan-summary" },
        "Summary"
      ),
      h("textarea", {
        id: "plan-summary",
        name: "plan-summary",
        rows: 3,
        value: localDraft.summary || "",
        onChange: (event) => handleFieldChange("summary", event.target.value),
      })
    ),
    h(
      "section",
      { className: "plan-section" },
      sectionHeader("Trimesters", "Add trimester", addTrimester),
      h(
        "table",
        { className: "plan-table" },
        h(
          "thead",
          null,
          h(
            "tr",
            null,
            h("th", null, "Name"),
            h("th", null, "Start date"),
            h("th", null, "End date"),
            h("th", { className: "row-actions" }, "")
          )
        ),
        h("tbody", null, renderTrimesterRows())
      )
    ),
    h(
      "section",
      { className: "plan-section" },
      sectionHeader("Levels", "Add level", addLevel),
      h(
        "table",
        { className: "plan-table" },
        h(
          "thead",
          null,
          h(
            "tr",
            null,
            h("th", null, "Name"),
            h("th", null, "Description"),
            h("th", { className: "row-actions" }, "")
          )
        ),
        h("tbody", null, renderLevelRows())
      )
    ),
    h(
      "section",
      { className: "plan-section" },
      sectionHeader("Topics", "Add topic", addTopic, !localDraft.trimesters?.length || !localDraft.levels?.length),
      h(
        "table",
        { className: "plan-table" },
        h(
          "thead",
          null,
          h(
            "tr",
            null,
            h("th", null, "Name"),
            h("th", null, "Trimester"),
            h("th", null, "Level"),
            h("th", null, "Summary"),
            h("th", { className: "row-actions" }, "")
          )
        ),
        h("tbody", null, renderTopicRows())
      )
    ),
    h(
      "section",
      { className: "plan-section" },
      h(
        "label",
        { htmlFor: "plan-notes" },
        "Reviewer notes"
      ),
      h("textarea", {
        id: "plan-notes",
        name: "plan-notes",
        rows: 4,
        value: localDraft.review_notes || "",
        maxLength: 1000,
        onChange: (event) => handleFieldChange("review_notes", event.target.value),
      }),
      validation.errors.reviewNotes
        ? renderErrorMessage("Reviewer notes cannot exceed 1000 characters")
        : null
    ),
    h(
      "div",
      { className: "editor-actions" },
      h(
        "button",
        { type: "submit", className: "primary-button", disabled: saving || (!dirty && !validation.hasErrors) },
        saving ? "Saving..." : dirty ? "Save changes" : "Saved"
      ),
      validation.hasErrors
        ? h(
            "p",
            { className: "form-error", role: "alert" },
            "Resolve validation issues before saving."
          )
        : null
    )
  );
}

export default PlanEditor;
