import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { z } from "zod";
import { Form } from "./Form";
import { FormField } from "./FormField";

// Same dummy resource as DataTable.test.tsx -- BUILD.md Stage 0's "built
// against one dummy resource first."
const widgetSchema = z.object({
  name: z.string().min(1, "Name is required."),
  quantity: z.number().min(0, "Quantity cannot be negative."),
});
type WidgetFormValues = z.infer<typeof widgetSchema>;

function DummyWidgetForm({ onSubmit }: { onSubmit: (values: WidgetFormValues) => void }) {
  return (
    <Form schema={widgetSchema} defaultValues={{ name: "", quantity: 0 }} onSubmit={onSubmit}>
      <FormField<WidgetFormValues> name="name" label="Name" />
      <FormField<WidgetFormValues> name="quantity" label="Quantity" type="number" />
      <button type="submit">Save</button>
    </Form>
  );
}

describe("Form + FormField", () => {
  it("calls onSubmit with parsed values when the form is valid", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<DummyWidgetForm onSubmit={onSubmit} />);

    await user.type(screen.getByLabelText("Name"), "Widget A");
    await user.clear(screen.getByLabelText("Quantity"));
    await user.type(screen.getByLabelText("Quantity"), "5");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(onSubmit).toHaveBeenCalledWith({ name: "Widget A", quantity: 5 });
  });

  it("shows a field-associated error and does not submit when validation fails", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<DummyWidgetForm onSubmit={onSubmit} />);

    await user.click(screen.getByRole("button", { name: "Save" }));

    const error = await screen.findByText("Name is required.");
    expect(error).toBeInTheDocument();
    const nameInput = screen.getByLabelText("Name");
    expect(nameInput).toHaveAttribute("aria-invalid", "true");
    expect(nameInput).toHaveAttribute("aria-describedby", error.id);
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
