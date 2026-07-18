/** Shared blog/recipe submission form. Used both for a fresh pitch
 * (`/blog/submit`, `/recipes/submit`) and for revising one after an editor
 * requested changes (`/account/submissions/:id/edit`) — same fields, the
 * edit case just arrives pre-filled and calls `updateSubmission` instead of
 * `createSubmission`. */

import { useState, type FormEvent } from "react";

import { AuthError } from "../lib/customer-auth";
import {
  createSubmission,
  updateSubmission,
  type SubmissionContentType,
  type SubmissionDetail,
  type SubmissionIngredientInput,
} from "../lib/submissions";

const FIELD =
  "min-h-11 w-full rounded-sm border border-line bg-canvas px-3 text-sm text-ink" +
  " placeholder:text-ink-muted focus:border-brand focus:outline-none";

function Label({ children }: { children: React.ReactNode }) {
  return <span className="text-xs font-medium text-ink-muted">{children}</span>;
}

export function SubmissionForm({
  contentType,
  submissionId,
  initial,
  defaultContactName,
  defaultContactEmail,
  defaultContactPhone,
  onSuccess,
}: {
  contentType: SubmissionContentType;
  submissionId?: string;
  initial?: SubmissionDetail;
  defaultContactName?: string;
  defaultContactEmail?: string;
  defaultContactPhone?: string;
  onSuccess: (result: { id: string; status: string }) => void;
}) {
  const [ingredients, setIngredients] = useState<SubmissionIngredientInput[]>(
    initial?.ingredients?.length ? initial.ingredients : [{ label: "", quantityText: "" }],
  );
  const [steps, setSteps] = useState<string[]>(initial?.steps?.length ? initial.steps : [""]);
  const [dietaryTags, setDietaryTags] = useState(initial?.dietaryTags?.join(", ") ?? "");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    const form = new FormData(event.currentTarget);
    const input = {
      contentType,
      contactName: String(form.get("contactName") ?? ""),
      contactEmail: String(form.get("contactEmail") ?? ""),
      contactPhone: String(form.get("contactPhone") ?? "") || undefined,
      title: String(form.get("title") ?? ""),
      excerpt: String(form.get("excerpt") ?? "") || undefined,
      body: String(form.get("body") ?? ""),
      ...(contentType === "recipe"
        ? {
            prepMinutes: form.get("prepMinutes") ? Number(form.get("prepMinutes")) : undefined,
            cookMinutes: form.get("cookMinutes") ? Number(form.get("cookMinutes")) : undefined,
            servings: form.get("servings") ? Number(form.get("servings")) : undefined,
            dietaryTags: dietaryTags
              .split(",")
              .map((tag) => tag.trim())
              .filter(Boolean),
            ingredients: ingredients.filter((entry) => entry.label.trim()),
            steps: steps.map((step) => step.trim()).filter(Boolean),
          }
        : {}),
    };

    setSubmitting(true);
    try {
      const result = submissionId
        ? await updateSubmission(submissionId, input)
        : await createSubmission(input);
      onSuccess(result);
    } catch (caught) {
      setError(caught instanceof AuthError ? caught.message : "Could not save your submission.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="max-w-2xl space-y-4" onSubmit={handleSubmit}>
      {error ? <p className="text-sm text-danger">{error}</p> : null}

      <label className="block space-y-1">
        <Label>Your name</Label>
        <input
          name="contactName"
          required
          minLength={1}
          maxLength={160}
          defaultValue={initial?.contactName ?? defaultContactName}
          className={FIELD}
        />
      </label>
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="block space-y-1">
          <Label>Email</Label>
          <input
            name="contactEmail"
            type="email"
            required
            defaultValue={initial?.contactEmail ?? defaultContactEmail}
            className={FIELD}
          />
        </label>
        <label className="block space-y-1">
          <Label>Phone (optional)</Label>
          <input
            name="contactPhone"
            type="tel"
            defaultValue={initial?.contactPhone ?? defaultContactPhone ?? ""}
            className={FIELD}
          />
        </label>
      </div>

      <label className="block space-y-1">
        <Label>{contentType === "article" ? "Post title" : "Recipe name"}</Label>
        <input
          name="title"
          required
          minLength={5}
          maxLength={200}
          defaultValue={initial?.title}
          className={FIELD}
        />
      </label>
      <label className="block space-y-1">
        <Label>Short excerpt (optional)</Label>
        <input name="excerpt" maxLength={400} defaultValue={initial?.excerpt ?? ""} className={FIELD} />
      </label>

      {contentType === "recipe" ? (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <label className="block space-y-1">
              <Label>Prep time (min)</Label>
              <input
                name="prepMinutes"
                type="number"
                min={0}
                defaultValue={initial?.prepMinutes ?? ""}
                className={FIELD}
              />
            </label>
            <label className="block space-y-1">
              <Label>Cook time (min)</Label>
              <input
                name="cookMinutes"
                type="number"
                min={0}
                defaultValue={initial?.cookMinutes ?? ""}
                className={FIELD}
              />
            </label>
            <label className="block space-y-1">
              <Label>Servings</Label>
              <input
                name="servings"
                type="number"
                min={0}
                defaultValue={initial?.servings ?? ""}
                className={FIELD}
              />
            </label>
          </div>
          <label className="block space-y-1">
            <Label>Dietary tags (comma separated, optional)</Label>
            <input
              value={dietaryTags}
              onChange={(event) => setDietaryTags(event.target.value)}
              placeholder="vegan, gluten-free"
              className={FIELD}
            />
          </label>

          <div className="space-y-2">
            <Label>Ingredients</Label>
            {ingredients.map((entry, index) => (
              <div key={index} className="flex gap-2">
                <input
                  value={entry.label}
                  onChange={(event) => {
                    const value = event.target.value;
                    setIngredients(
                      ingredients.map((item, i) => (i === index ? { ...item, label: value } : item)),
                    );
                  }}
                  placeholder="Ingredient"
                  className={FIELD}
                />
                <input
                  value={entry.quantityText}
                  onChange={(event) => {
                    const value = event.target.value;
                    setIngredients(
                      ingredients.map((item, i) =>
                        i === index ? { ...item, quantityText: value } : item,
                      ),
                    );
                  }}
                  placeholder="Quantity"
                  className={`${FIELD} max-w-[9rem]`}
                />
                <button
                  type="button"
                  onClick={() => setIngredients(ingredients.filter((_, i) => i !== index))}
                  className="text-xs text-ink-muted hover:text-danger"
                  aria-label={`Remove ingredient ${index + 1}`}
                >
                  Remove
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => setIngredients([...ingredients, { label: "", quantityText: "" }])}
              className="text-xs font-medium text-brand hover:underline"
            >
              + Add ingredient
            </button>
          </div>

          <div className="space-y-2">
            <Label>Steps</Label>
            {steps.map((step, index) => (
              <div key={index} className="flex gap-2">
                <span className="mt-2 text-xs text-ink-muted">{index + 1}.</span>
                <textarea
                  value={step}
                  onChange={(event) => {
                    const next = [...steps];
                    next[index] = event.target.value;
                    setSteps(next);
                  }}
                  rows={2}
                  className={`${FIELD} py-2`}
                />
                <button
                  type="button"
                  onClick={() => setSteps(steps.filter((_, i) => i !== index))}
                  className="text-xs text-ink-muted hover:text-danger"
                  aria-label={`Remove step ${index + 1}`}
                >
                  Remove
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={() => setSteps([...steps, ""])}
              className="text-xs font-medium text-brand hover:underline"
            >
              + Add step
            </button>
          </div>
        </>
      ) : null}

      <label className="block space-y-1">
        <Label>{contentType === "article" ? "Your post" : "Story / intro"}</Label>
        <textarea
          name="body"
          required
          minLength={20}
          rows={10}
          defaultValue={initial?.body}
          placeholder="Write in paragraphs — leave a blank line between paragraphs."
          className={`${FIELD} py-3`}
        />
      </label>

      <button
        type="submit"
        disabled={submitting}
        className="inline-flex min-h-11 items-center rounded-sm bg-brand px-5 text-sm font-medium text-ink-inverse hover:opacity-90 disabled:opacity-50"
      >
        {submitting ? "Saving..." : submissionId ? "Resubmit for review" : "Submit for review"}
      </button>
    </form>
  );
}
