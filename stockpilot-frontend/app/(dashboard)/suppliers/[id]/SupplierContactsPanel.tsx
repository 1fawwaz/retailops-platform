"use client";

import { useState } from "react";
import { useSupplierContacts } from "../../../../hooks/useSupplierContacts";
import { useCreateContact } from "../../../../hooks/useCreateContact";
import { useDeleteContact } from "../../../../hooks/useDeleteContact";
import { Form } from "../../../../components/forms/Form";
import { FormField } from "../../../../components/forms/FormField";
import { AppError } from "../../../../lib/api/errors";
import {
  supplierContactFormSchema,
  type SupplierContactFormValues,
} from "../../../../lib/validation/suppliers";

const CONTACT_DEFAULTS: SupplierContactFormValues = { name: "", email: "", phone: "", role: "" };

export function SupplierContactsPanel({ supplierId, canManage }: { supplierId: number; canManage: boolean }) {
  const contacts = useSupplierContacts(supplierId);
  const createContact = useCreateContact(supplierId);
  const deleteContact = useDeleteContact(supplierId);
  const [addingContact, setAddingContact] = useState(false);
  const [contactError, setContactError] = useState<string | null>(null);

  async function handleAddContact(values: SupplierContactFormValues) {
    setContactError(null);
    try {
      await createContact.mutateAsync(values);
      setAddingContact(false);
    } catch (err) {
      setContactError(
        err instanceof AppError ? err.message : "Something went wrong. Please try again.",
      );
    }
  }

  return (
    <div className="rounded-[6px] border border-[var(--color-hairline)] bg-[var(--color-surface)] p-4">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-[16px] font-medium text-[var(--color-text-hi)]">Contacts</h2>
        {canManage && !addingContact && (
          <button
            type="button"
            onClick={() => setAddingContact(true)}
            className="rounded-[6px] border border-[var(--color-hairline)] px-3 py-1 text-[13px] text-[var(--color-text-hi)] hover:border-[var(--color-hairline-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
          >
            Add contact
          </button>
        )}
      </div>

      {addingContact && (
        <div className="mb-4 border-b border-[var(--color-hairline)] pb-4">
          <Form
            schema={supplierContactFormSchema}
            defaultValues={CONTACT_DEFAULTS}
            onSubmit={handleAddContact}
            className="max-w-sm"
          >
            <FormField<SupplierContactFormValues> name="name" label="Name" />
            <FormField<SupplierContactFormValues> name="email" label="Email" type="email" />
            <FormField<SupplierContactFormValues> name="phone" label="Phone" />
            <FormField<SupplierContactFormValues> name="role" label="Role" />
            {contactError && (
              <p role="alert" className="mb-4 text-[13px] text-[var(--color-danger)]">
                {contactError}
              </p>
            )}
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={createContact.isPending}
                className="rounded-[6px] bg-[var(--color-accent)] px-3 py-1.5 text-[13px] text-[var(--color-canvas)] disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
              >
                {createContact.isPending ? "Saving…" : "Save contact"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setAddingContact(false);
                  setContactError(null);
                }}
                className="rounded-[6px] border border-[var(--color-hairline)] px-3 py-1.5 text-[13px] text-[var(--color-text-hi)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--color-accent)]"
              >
                Cancel
              </button>
            </div>
          </Form>
        </div>
      )}

      {contacts.isPending ? (
        <div className="h-10 w-full animate-pulse rounded-[6px] bg-[var(--color-raised)]" />
      ) : contacts.isError ? (
        <p className="text-[13px] text-[var(--color-danger)]">Could not load contacts.</p>
      ) : contacts.data && contacts.data.length > 0 ? (
        <ul className="flex flex-col gap-2">
          {contacts.data.map((contact) => (
            <li
              key={contact.id}
              className="flex items-center justify-between border-b border-[var(--color-hairline)] pb-2 text-[13px] last:border-b-0"
            >
              <div>
                <span className="text-[var(--color-text-hi)]">{contact.name}</span>
                {contact.role && <span className="text-[var(--color-text-mid)]"> — {contact.role}</span>}
                {(contact.email || contact.phone) && (
                  <div className="text-[var(--color-text-mid)]">
                    {[contact.email, contact.phone].filter(Boolean).join(" · ")}
                  </div>
                )}
              </div>
              {canManage && (
                <button
                  type="button"
                  onClick={() => deleteContact.mutate(contact.id)}
                  disabled={deleteContact.isPending}
                  className="text-[13px] text-[var(--color-danger)] hover:underline disabled:opacity-60"
                >
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-[13px] text-[var(--color-text-mid)]">No contacts recorded yet.</p>
      )}
    </div>
  );
}
