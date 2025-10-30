import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AgendaPage from "../agenda.jsx";

describe("AgendaPage", () => {
  const sampleAgenda = {
    sessions: [
      {
        id: "session-1",
        title: "Algebra I",
        start: "2024-01-09T09:00:00",
        end: "2024-01-09T10:00:00",
        trimester: 1,
        topic: "Linear Equations",
        activities: ["Group work", "Review"],
        materials: ["Textbook", "Calculator"],
        summary: "Linear equations overview"
      }
    ],
    holidays: [
      {
        id: "holiday-2024-01-01",
        date: "2024-01-01",
        title: "New Year",
        description: "School closed"
      }
    ]
  };

  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  it("renders agenda events from API", async () => {
    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => sampleAgenda
    });

    render(<AgendaPage />);

    expect(await screen.findByText("Algebra I")).toBeInTheDocument();
    expect(screen.getByText(/Linear equations overview/)).toBeInTheDocument();
    expect(screen.getByText(/Group work/)).toBeInTheDocument();
    expect(fetch).toHaveBeenCalledWith(expect.stringContaining("/api/agenda"));
  });

  it("allows editing a session and sends updates", async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => sampleAgenda
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "session-1",
          topic: "Quadratic Functions",
          activities: ["Pair work"],
          materials: ["Graph paper"]
        })
      });

    render(<AgendaPage />);

    const eventNode = await screen.findByTestId("agenda-event-session-1");
    fireEvent.click(eventNode);

    const editButton = await screen.findByRole("button", { name: /edit session/i });
    fireEvent.click(editButton);

    const topicInput = await screen.findByLabelText("Topic");
    fireEvent.change(topicInput, { target: { value: "Quadratic Functions" } });

    const activitiesInput = screen.getByLabelText("Activities");
    fireEvent.change(activitiesInput, { target: { value: "Pair work" } });

    const materialsInput = screen.getByLabelText("Materials");
    fireEvent.change(materialsInput, { target: { value: "Graph paper" } });

    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    await waitFor(() => {
      expect(fetch).toHaveBeenLastCalledWith(
        expect.stringContaining("/api/agenda/sessions/session-1"),
        expect.objectContaining({
          method: "PUT",
          body: JSON.stringify({
            topic: "Quadratic Functions",
            activities: ["Pair work"],
            materials: ["Graph paper"]
          })
        })
      );
    });

    expect(await screen.findByText(/Session updated successfully/)).toBeInTheDocument();
  });

  it("allows marking a holiday from the modal", async () => {
    fetch
      .mockResolvedValueOnce({
        ok: true,
        json: async () => sampleAgenda
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "holiday-2024-01-10",
          date: "2024-01-10",
          title: "Snow Day",
          description: "Inclement weather"
        })
      });

    render(<AgendaPage />);

    const eventNode = await screen.findByTestId("agenda-event-session-1");
    fireEvent.click(eventNode);

    const holidayButton = await screen.findByRole("button", { name: /mark holiday/i });
    fireEvent.click(holidayButton);

    const dateInput = await screen.findByLabelText("Date");
    fireEvent.change(dateInput, { target: { value: "2024-01-10" } });

    const reasonInput = screen.getByLabelText("Reason");
    fireEvent.change(reasonInput, { target: { value: "Inclement weather" } });

    fireEvent.click(screen.getByRole("button", { name: /save holiday/i }));

    await waitFor(() => {
      expect(fetch).toHaveBeenLastCalledWith(
        expect.stringContaining("/api/agenda/holidays"),
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            date: "2024-01-10",
            description: "Inclement weather",
            sessionId: "session-1"
          })
        })
      );
    });

    expect(await screen.findByText(/Holiday saved/)).toBeInTheDocument();
  });
});
