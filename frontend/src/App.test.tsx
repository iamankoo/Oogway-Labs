import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import App from "@/App";

describe("App", () => {
  it("renders the product shell with the welcome state and a disabled composer", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: /ask lenny about growth/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /new conversation/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/message lenny growth assistant/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send message/i })).toBeDisabled();
  });

  it("fills the composer when a suggested prompt is selected", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const user = userEvent.setup();
    render(<App />);

    const prompt = screen.getByRole("button", {
      name: /what signals indicate we've found product-market fit/i,
    });
    await user.click(prompt);

    expect(screen.getByLabelText(/message lenny growth assistant/i)).toHaveValue(
      "What signals indicate we've found product-market fit?",
    );
  });
});
