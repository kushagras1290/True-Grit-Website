/**
 * Per-locale field overrides for database-sourced content (migration 0068)
 * -- navigation labels, category/product names and descriptions, article/
 * recipe titles and excerpts.
 *
 * One generic panel rather than five near-copies of `PageTranslationsPanel`
 * (site-control.tsx, migration 0067): unlike a CMS page's block tree, every
 * entity type here is just a handful of flat text fields, so one field-list
 * prop is enough to describe any of them. `TRANSLATION_LOCALES` is imported
 * from site-control.tsx rather than duplicated -- both live in this same
 * admin package, so there is no cross-package reason to keep separate copies
 * the way that module's own comment justifies for the storefront's list.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { Button, Input, Select } from "../components/ui";
import { useToast } from "../components/toast";
import { ApiError, api, type EntityTranslationType } from "../lib/api";
import { formatDateTime } from "../lib/format";
import { TRANSLATION_LOCALES } from "./site-control";

export interface TranslatableField {
  /** Matches a key in `services.entity_translation.TRANSLATABLE_FIELDS` on
   *  the API, camelCase (e.g. `shortDescription`, `heroTitle`). */
  key: string;
  label: string;
  multiline?: boolean;
}

export function EntityTranslationsPanel({
  entityType,
  entityId,
  fields,
}: {
  entityType: EntityTranslationType;
  entityId: string;
  fields: TranslatableField[];
}) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [locale, setLocale] = useState(TRANSLATION_LOCALES[0]!.code);
  const [values, setValues] = useState<Record<string, string>>({});

  const translation = useQuery({
    queryKey: ["entity-translation", entityType, entityId, locale],
    queryFn: () => api.entityTranslation(entityType, entityId, locale),
  });
  const translatedLocales = useQuery({
    queryKey: ["entity-translations", entityType, entityId],
    queryFn: () => api.entityTranslations(entityType, entityId),
  });

  useEffect(() => {
    if (translation.data) setValues(translation.data.fields);
  }, [translation.data]);

  function invalidate() {
    return Promise.all([
      queryClient.invalidateQueries({
        queryKey: ["entity-translation", entityType, entityId, locale],
      }),
      queryClient.invalidateQueries({
        queryKey: ["entity-translations", entityType, entityId],
      }),
    ]);
  }

  const saveMutation = useMutation({
    mutationFn: () => api.saveEntityTranslation(entityType, entityId, locale, values),
    onSuccess: async () => {
      await invalidate();
      toast.success("Translation saved.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not save the translation."),
  });

  const autoTranslateMutation = useMutation({
    mutationFn: () => api.autoTranslateEntity(entityType, entityId, locale),
    onSuccess: async () => {
      await invalidate();
      toast.success("Auto-translated — review the result before it goes live.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not auto-translate."),
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteEntityTranslation(entityType, entityId, locale),
    onSuccess: async () => {
      await invalidate();
      toast.success("Translation removed — this locale now falls back to English.");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? error.message : "Could not remove the translation."),
  });

  const translatedLocaleCodes = new Set(
    (translatedLocales.data ?? []).map((entry) => entry.locale),
  );
  const busy =
    saveMutation.isPending || autoTranslateMutation.isPending || deleteMutation.isPending;

  return (
    <div className="border-t border-line pt-5">
      <h3 className="font-display text-lg text-ink">Translations</h3>
      <p className="mt-1 text-sm text-ink-muted">
        A locale with no saved translation falls back to English on the storefront — nothing
        breaks by leaving one blank. "Auto-translate" runs a real machine-translation model on the
        Worker's own AI binding (free, but not perfect) and fills the fields below for review, it
        does not save on its own.
      </p>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Select
          value={locale}
          onChange={(event) => setLocale(event.target.value)}
          aria-label="Locale to translate"
          className="max-w-xs"
        >
          {TRANSLATION_LOCALES.map((entry) => (
            <option key={entry.code} value={entry.code}>
              {translatedLocaleCodes.has(entry.code) ? "✓ " : ""}
              {entry.label}
            </option>
          ))}
        </Select>
        <Button
          type="button"
          variant="secondary"
          disabled={busy}
          onClick={() => autoTranslateMutation.mutate()}
        >
          {autoTranslateMutation.isPending ? "Translating..." : "Auto-translate"}
        </Button>
      </div>

      {translation.data?.autoTranslated ? (
        <p className="mt-3 rounded-md border border-warning/40 bg-warning/5 px-4 py-2 text-sm text-warning">
          Machine-translated, not yet reviewed by a person.
        </p>
      ) : null}

      <div className="mt-3 space-y-3">
        {fields.map((field) => (
          <label key={field.key} className="block text-sm">
            <span className="mb-1 block font-medium text-ink">{field.label}</span>
            {field.multiline ? (
              <textarea
                className="w-full rounded-sm border border-line bg-canvas px-3 py-2 text-sm text-ink focus:border-brand focus:outline-none"
                rows={3}
                value={values[field.key] ?? ""}
                onChange={(event) =>
                  setValues((current) => ({ ...current, [field.key]: event.target.value }))
                }
              />
            ) : (
              <Input
                value={values[field.key] ?? ""}
                onChange={(event) =>
                  setValues((current) => ({ ...current, [field.key]: event.target.value }))
                }
              />
            )}
          </label>
        ))}
      </div>

      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-ink-muted">
          {translation.data?.updatedAt
            ? `Last saved ${formatDateTime(translation.data.updatedAt)}`
            : "No saved translation for this locale yet — showing English as a starting point."}
        </p>
        <div className="flex gap-2">
          {translation.data?.updatedAt ? (
            <Button
              type="button"
              variant="destructive"
              disabled={busy}
              onClick={() => deleteMutation.mutate()}
            >
              Remove translation
            </Button>
          ) : null}
          <Button type="button" variant="primary" disabled={busy} onClick={() => saveMutation.mutate()}>
            {saveMutation.isPending ? "Saving..." : "Save translation"}
          </Button>
        </div>
      </div>
    </div>
  );
}
