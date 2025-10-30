import React, { useCallback, useEffect, useMemo, useState } from "https://esm.sh/react@18";
import { createRoot } from "https://esm.sh/react-dom@18/client";
import PlanEditor from "/frontend/components/PlanEditor.jsx";

const h = React.createElement;

function useQueryParam(name, fallback) {
  return useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get(name) || fallback;
  }, [name, fallback]);
}

function StatusMessage({ status, error }) {
  if (error) {
    return h(
      "p",
      { className: "status-message status-message--error", role: "alert" },
      error
    );
  }

  if (status) {
    return h("p", { className: "status-message", role: "status" }, status);
  }

  return null;
}

function PlanReviewPage() {
  const draftId = useQueryParam("draft_id", "demo-draft");
  const [draft, setDraft] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");

  const fetchDraft = useCallback(async () => {
    setLoading(true);
    setError("");
    setStatus("");
    try {
      const response = await fetch(`/plans/${draftId}`);
      if (!response.ok) {
        throw new Error(`Failed to load draft: ${response.statusText}`);
      }
      const data = await response.json();
      setDraft(data);
    } catch (err) {
      console.error(err);
      setError(err.message || "Unable to load draft");
    } finally {
      setLoading(false);
    }
  }, [draftId]);

  useEffect(() => {
    fetchDraft();
  }, [fetchDraft]);

  const handleSave = useCallback(
    async (updatedDraft) => {
      setSaving(true);
      setError("");
      setStatus("");
      try {
        const payload = {
          title: updatedDraft.title,
          summary: updatedDraft.summary,
          review_notes: updatedDraft.review_notes,
          trimesters: updatedDraft.trimesters,
          levels: updatedDraft.levels,
          topics: updatedDraft.topics,
        };
        const response = await fetch(`/plans/${draftId}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!response.ok) {
          const detail = await response.json().catch(() => ({}));
          throw new Error(detail.detail || "Unable to save changes");
        }
        const data = await response.json();
        setDraft(data);
        setStatus("Draft saved successfully");
        return true;
      } catch (err) {
        console.error(err);
        setError(err.message || "Failed to save changes");
        return false;
      } finally {
        setSaving(false);
      }
    },
    [draftId]
  );

  const handleApprove = useCallback(async () => {
    if (!draft) {
      return;
    }
    setSaving(true);
    setError("");
    setStatus("");
    try {
      const response = await fetch(`/plans/${draftId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ review_notes: draft.review_notes || "" }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || "Unable to approve draft");
      }
      const data = await response.json();
      setDraft(data);
      setStatus("Draft approved successfully");
    } catch (err) {
      console.error(err);
      setError(err.message || "Approval failed");
    } finally {
      setSaving(false);
    }
  }, [draft, draftId]);

  const handleReparse = useCallback(async () => {
    if (!draft) {
      return;
    }
    setSaving(true);
    setError("");
    setStatus("");
    try {
      const response = await fetch(`/plans/${draftId}/reparse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ review_notes: draft.review_notes || "" }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || "Unable to request re-parse");
      }
      const data = await response.json();
      setDraft(data);
      setStatus("Re-parse requested");
    } catch (err) {
      console.error(err);
      setError(err.message || "Re-parse request failed");
    } finally {
      setSaving(false);
    }
  }, [draft, draftId]);

  if (loading) {
    return h("p", { className: "status-message", role: "status" }, "Loading draft...");
  }

  if (!draft) {
    return h(
      "div",
      { className: "status-wrapper" },
      h(StatusMessage, { status, error }),
      h(
        "button",
        {
          type: "button",
          className: "primary-button",
          onClick: fetchDraft,
        },
        "Retry"
      )
    );
  }

  return h(
    "section",
    { className: "plan-review__panel" },
    h(
      "header",
      { className: "plan-review__meta" },
      h("div", { className: "plan-review__meta-details" }, [
        h("p", { key: "id" }, [h("strong", { key: "label" }, "Draft ID:"), ` ${draft.id}`]),
        h("p", { key: "status" }, [
          h("strong", { key: "label" }, "Status:"),
          ` ${draft.status}`,
        ]),
        h("p", { key: "updated" }, [
          h("strong", { key: "label" }, "Last updated:"),
          ` ${new Date(draft.updated_at).toLocaleString()}`,
        ]),
      ]),
      h(
        "div",
        { className: "plan-review__actions" },
        h(
          "button",
          {
            type: "button",
            className: "secondary-button",
            onClick: handleReparse,
            disabled: saving,
          },
          "Request Re-parse"
        ),
        h(
          "button",
          {
            type: "button",
            className: "primary-button",
            onClick: handleApprove,
            disabled: saving,
          },
          "Approve"
        )
      )
    ),
    h(StatusMessage, { status, error }),
    h(PlanEditor, {
      draft,
      onSave: handleSave,
      saving,
      onChange: (updated) => setDraft(updated),
    }),
    h(
      "section",
      { className: "plan-history" },
      h("h3", null, "Audit trail"),
      h(
        "ol",
        { className: "plan-history__list" },
        draft.history?.length
          ? draft.history.map((entry, index) =>
              h(
                "li",
                { key: `${entry.timestamp}-${index}` },
                h(
                  "p",
                  null,
                  `${new Date(entry.timestamp).toLocaleString()} — ${entry.action}`
                ),
                entry.payload && Object.keys(entry.payload).length
                  ? h(
                      "pre",
                      { className: "plan-history__payload" },
                      JSON.stringify(entry.payload, null, 2)
                    )
                  : null
              )
            )
          : h("li", { key: "empty" }, "No history yet.")
      )
    )
  );
}

const container = document.getElementById("plan-review-root");
if (container) {
  const root = createRoot(container);
  root.render(h(PlanReviewPage));
}
